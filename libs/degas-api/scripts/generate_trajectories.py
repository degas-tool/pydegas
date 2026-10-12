"""Generate ground-truth trajectory CSVs for the case-study examples."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def thermostat(
    rng: np.random.Generator, t_on: float = 17.0, t_off: float = 20.0
) -> np.ndarray:
    T = np.zeros(31)
    curr_t = 16.0
    is_on = -1
    for i in range(31):
        T[i] = curr_t
        if is_on > 0:
            new_t = 0.99 * curr_t + 0.5 + rng.normal(0.0, 0.1)
        else:
            new_t = 0.99 * curr_t + rng.normal(0.0, 0.1)
        curr_t = new_t
        if is_on > 0 and new_t > t_off:
            is_on = -1
        elif is_on <= 0 and new_t < t_on:
            is_on = 1
    T[30] = curr_t
    # Per-program post-loop measurement noise (matches examples.ts).
    T[:30] = T[:30] + rng.normal(0.0, 1.0, size=30)
    return T


def gearbox(rng: np.random.Generator, s1: float = 10.0, s2: float = 20.0) -> np.ndarray:
    v = np.zeros(21)
    w = 0.0
    gear = 1
    curr_v = 5.0
    nxt = gear
    for i in range(21):
        v[i] = curr_v
        if gear > 0.8:
            new_v = 1.078 * curr_v + 0.1 * rng.normal(5.0, 1.0)
        else:
            new_v = curr_v - 0.00005 * curr_v * curr_v + rng.normal(0.0, 1.0)
        curr_v = new_v
        if gear > 0:
            if gear < 1.5 and new_v > s1:
                nxt = gear + 1
                gear = 0
                w = 0.3
            elif gear < 2.5 and new_v > s2:
                nxt = gear + 1
                gear = 0
                w = 0.3
        else:
            if w < 0.1:
                gear = nxt
        w = w - 0.1
        v[i] = v[i] + rng.normal(0.0, 0.5)
    return v


def bouncing_ball(
    rng: np.random.Generator, r: float = 5.0, c: float = 0.0025
) -> np.ndarray:
    H = np.zeros(36)
    curr_h = rng.normal(9.0, 1.0)
    mode = -1.0
    curr_v = 0.0
    dt = 0.08
    for i in range(35):
        H[i] = curr_h
        if mode < 0:
            new_v = curr_v - 9.8 * dt + rng.normal(0.0, 0.1)
        else:
            spring = 0.14 * (r * curr_v + c * curr_h) * dt
            new_v = curr_v - 9.8 * dt - spring + rng.normal(0.0, 0.1)
        curr_v = new_v
        new_h = curr_h + curr_v * dt + rng.normal(0.0, 0.1)
        curr_h = new_h
        if mode < 0 and curr_h <= 0:
            mode = 1
        elif mode >= 0 and curr_h > 0:
            mode = -1
    H[35] = curr_h
    return H


SIMULATORS = {
    "thermostat": thermostat,
    "gearbox": gearbox,
    "bouncing_ball": bouncing_ball,
}


def generate(name: str, n: int, seed: int, out_dir: Path) -> Path:
    sim = SIMULATORS[name]
    rng = np.random.default_rng(seed)
    rows = np.array([sim(rng) for _ in range(n)])
    path = out_dir / f"{name}_trajectories.csv"
    np.savetxt(path, rows, delimiter=",", fmt="%.4f")
    print(f"  wrote {path}  shape={rows.shape}")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("name", choices=[*SIMULATORS, "all"], default="all", nargs="?")
    p.add_argument("--n", type=int, default=100, help="number of trajectories")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--out", type=Path, default=Path(__file__).resolve().parent.parent / "data"
    )
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    targets = list(SIMULATORS) if args.name == "all" else [args.name]
    print(
        f"generating {args.n} trajectories per program (seed={args.seed}) into {args.out}"
    )
    for name in targets:
        generate(name, args.n, args.seed, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
