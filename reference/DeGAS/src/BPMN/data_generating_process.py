import torch
from torch.distributions import Normal

# -------------------------------------------------
# Basic samplers (match your modeling language)
# -------------------------------------------------
def std_normal():
    """gm([1],[0.],[1.])"""
    return Normal(0.0, 1.0).sample().item()

def normal(mu):
    """gm([1],[mu],[1.])"""
    return Normal(float(mu), 1.0).sample().item()

def u01():
    """uniform([0,1],2)"""
    return torch.rand(()).item()

def sample_positive(draw_fn, max_tries=10_000):
    """Implements observe(x > 0) via rejection sampling."""
    for _ in range(max_tries):
        x = draw_fn()
        if x > 0.0:
            return float(x)
    raise RuntimeError("Failed to sample positive value.")

# -------------------------------------------------
# Resource selection with random tie-break
# -------------------------------------------------
def choose_resource(resload0, resload1, duration):
    """
    Least-loaded resource with RANDOM tie-break.
    Returns: start, end, new_resload0, new_resload1
    """
    if resload0 < resload1:
        start = resload0
        end = start + duration
        return start, end, end, resload1

    if resload1 < resload0:
        start = resload1
        end = start + duration
        return start, end, resload0, end

    # tie
    if torch.rand(()) < 0.5:
        start = resload0
        end = start + duration
        return start, end, end, resload1
    else:
        start = resload1
        end = start + duration
        return start, end, resload0, end

# -------------------------------------------------
# Single-trace simulator
# -------------------------------------------------
def simulate_process_once(
    *,
    _muinfo,
    _mupayE,
    _mupayS,
    _mupack,
    _muprepinv,
    _musendinv,
    _switch,
    _resourcesrate,
):
    """
    Literal implementation of your updated model.
    Returns endacts (observed), plus auxiliaries.
    """

    # Resource capacity
    resourcerate2 = _resourcesrate * _resourcesrate
    R = 1.0 + resourcerate2   # R in {1,2}

    tactivities = torch.zeros(5)
    startacts = torch.zeros(5)
    endacts = torch.zeros(5)

    t = 0.0

    # -------------------------------------------------
    # ACTIVITY 0
    # -------------------------------------------------
    tactivities[0] = sample_positive(
        lambda: _muinfo * _muinfo + std_normal()
    )
    startacts[0] = t
    endacts[0] = startacts[0] + tactivities[0]
    t = endacts[0].item()

    # -------------------------------------------------
    # ACTIVITY 1 (XOR)
    # -------------------------------------------------
    switch2 = _switch * _switch

    if u01() - switch2 < 0.0:
        tactivities[1] = sample_positive(lambda: normal(_mupayE))
        payment_mode = "E"
    else:
        tactivities[1] = sample_positive(lambda: normal(_mupayS))
        payment_mode = "S"

    startacts[1] = t
    endacts[1] = startacts[1] + tactivities[1]
    t = endacts[1].item()

    # -------------------------------------------------
    # PARALLEL BLOCK DURATIONS
    # -------------------------------------------------
    tactivities[2] = sample_positive(
        lambda: _mupack * _mupack + std_normal()
    )
    tactivities[3] = sample_positive(
        lambda: _muprepinv * _muprepinv + std_normal()
    )
    tactivities[4] = sample_positive(
        lambda: _musendinv * _musendinv + std_normal()
    )

    resload0 = t
    resload1 = t

    # -------------------------------------------------
    # Helper to schedule task 2 or 3
    # -------------------------------------------------
    def schedule(task_id):
        nonlocal resload0, resload1
        dur = tactivities[task_id].item()

        if R < 1.5:
            startacts[task_id] = resload0
            endacts[task_id] = startacts[task_id] + dur
            resload0 = endacts[task_id].item()
        else:
            s, e, resload0, resload1 = choose_resource(
                resload0, resload1, dur
            )
            startacts[task_id] = s
            endacts[task_id] = e

    # -------------------------------------------------
    # Random ordering between task 2 and 3
    # -------------------------------------------------
    if u01() < 0.5:
        schedule(2)
        schedule(3)
        order23 = "2_then_3"
    else:
        schedule(3)
        schedule(2)
        order23 = "3_then_2"

    # -------------------------------------------------
    # TASK 4 (depends on task 3)
    # -------------------------------------------------
    ready4 = endacts[3].item()

    if R < 1.5:
        startacts[4] = ready4 if resload0 < ready4 else resload0
        endacts[4] = startacts[4] + tactivities[4]
        resload0 = endacts[4].item()
    else:
        if resload0 < resload1:
            startacts[4] = ready4 if resload0 < ready4 else resload0
            endacts[4] = startacts[4] + tactivities[4]
            resload0 = endacts[4].item()
        elif resload1 < resload0:
            startacts[4] = ready4 if resload1 < ready4 else resload1
            endacts[4] = startacts[4] + tactivities[4]
            resload1 = endacts[4].item()
        else:
            if u01() < 0.5:
                startacts[4] = ready4 if resload0 < ready4 else resload0
                endacts[4] = startacts[4] + tactivities[4]
                resload0 = endacts[4].item()
            else:
                startacts[4] = ready4 if resload1 < ready4 else resload1
                endacts[4] = startacts[4] + tactivities[4]
                resload1 = endacts[4].item()

    # -------------------------------------------------
    # AND join
    # -------------------------------------------------
    if R < 1.5:
        t = resload0
    else:
        t = resload0 if resload0 > resload1 else resload1

    return {
        "endacts": endacts.clone(),   # <- observed
        "startacts": startacts.clone(),
        "tactivities": tactivities.clone(),
        "makespan": t,
        "payment_mode": payment_mode,
        "order23": order23,
        "R": R,
    }

# -------------------------------------------------
# Dataset generator
# -------------------------------------------------
def simulate_n(n, **params):
    endacts_all = torch.zeros((n, 5))
    startacts_all = torch.zeros((n, 5))
    tactivities_all = torch.zeros((n, 5))

    makespans = []
    payment_modes = []
    order23s = []

    for i in range(n):
        out = simulate_process_once(**params)
        endacts_all[i] = out["endacts"]
        startacts_all[i] = out["startacts"]
        tactivities_all[i] = out["tactivities"]
        makespans.append(out["makespan"])
        payment_modes.append(out["payment_mode"])
        order23s.append(out["order23"])

    meta = {
        "makespans": torch.tensor(makespans),
        "payment_modes": payment_modes,
        "order23": order23s,
        "R": out["R"],
    }
    return endacts_all, startacts_all, tactivities_all, meta
