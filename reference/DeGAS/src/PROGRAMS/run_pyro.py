import torch
import torch.distributions.constraints as constraints
import pyro
from pyro.optim import Adam
from pyro.infer import SVI, Trace_ELBO, TraceEnum_ELBO, TraceGraph_ELBO
from pyro.infer import MCMC, NUTS
import pyro.distributions as dist
from time import time
import numpy as np
import matplotlib.pyplot as plt


def run_inference(model, guide, model_params, n_steps=1000, lr=0.05):
    # Setup the optimizer
    adam_params = {"lr": lr}
    optimizer = Adam(adam_params)
    
    # Setup the inference algorithm
    svi = SVI(model, guide, optimizer, loss=Trace_ELBO())
    
    # Initialize the parameters
    pyro.clear_param_store()
    
    # Perform inference
    loss_list = []
    total_start = time()
    iterations = n_steps
    for step in range(n_steps):
        #check for convergence within a tolerance of 1e-8 and wit a patience of 30 iterations
        loss = svi.step(model_params)
        loss_list.append(loss)
        if step > 30 and abs(loss_list[-1] - loss_list[-2]) < 1e-8 and all(abs(loss_list[-j] - loss_list[-j-1]) < 1e-8 for j in range(2, 31)):
            #print(f"Converged at iteration {step}")
            iterations = step
            break
        #if step % int(n_steps/10) == 0:
            #print(f"Step {step} : loss = {loss}")
    total_end = time()
    #print('Inference performed in ', round(total_end-total_start, 3))
    
    return loss_list, iterations, round(total_end-total_start, 3)

def get_model_guide(program):
    if program == "bernoulli":
        return model_bernoulli, guide_bernoulli
    elif program == "burglary":
        return model_burglary, guide_burglary
    elif program == "clickgraph":
        return model_clickgraph, guide_clickgraph
    elif program == "clinicaltrial":
        return model_clinicaltrial, guide_clinicaltrial
    elif program == "coinbias":
        return model_coinbias, guide_coinbias
    elif program == "grass":
        return model_grass, guide_grass
    elif program == "murdermistery":
        return model_murdermistery, guide_murdermistery
    elif program == "noisior":
        return model_noisior, guide_noisior
    elif program == "surveyunbiased":
        return model_surveyunbiased, guide_surveyunbiased
    elif program == "trueskills":
        return model_trueskills, guide_trueskills
    elif program == "twocoins":
        return model_twocoins, guide_twocoins
    elif program == "altermu":
        return model_altermu, guide_altermu
    elif program == "altermu2":
        return model_altermu2, guide_altermu2
    elif program == "normalmixtures":
        return model_normalmixtures, guide_normalmixtures
    elif program == "test":
        return model_test, guide_test
    elif program == "test2":
        return model_test2, guide_test2
    elif program == "pid":
        return model_pid, guide_pid
    else:
        raise ValueError("Program not recognized")

def model_bernoulli(params):
    N, y = params
    p = pyro.sample("p", dist.Uniform(0,1))

    with pyro.plate("data_plate", N):
        y = pyro.sample("y", dist.Bernoulli(p), obs=y[:, 0])

def guide_bernoulli(params):
    p_map = pyro.param('p_map', torch.tensor(0.5))
    pyro.sample("p", dist.Delta(p_map))


def model_burglary(params):
    """
    params: torch.tensor of shape [N, 6]
            columns = [burglary, earthquake, alarm, maryWakes, phoneWorking, called]
    """
    N, data = params

    # Split columns
    burglary_obs     = data[:, 0]
    earthquake_obs   = data[:, 1]
    alarm_obs        = data[:, 2]
    maryWakes_obs    = data[:, 3]
    phoneWorking_obs = data[:, 4]
    called_obs       = data[:, 5]

    pb = pyro.sample("pb", dist.Beta(1., 1.))
    pe = pyro.sample("pe", dist.Beta(1., 1.))

    with pyro.plate("data", N):

        # --- Burglary ---
        burglary = pyro.sample("burglary",
                               dist.Bernoulli(pb),
                               obs=burglary_obs)

        # --- Earthquake ---
        earthquake = pyro.sample("earthquake",
                                 dist.Bernoulli(pe),
                                 obs=earthquake_obs)

        # --- Alarm ---
        alarm_prob = torch.where(
            (burglary.bool() | earthquake.bool()),
            torch.tensor(1.0),
            torch.tensor(0.0)
        )
        alarm = pyro.sample("alarm", dist.Bernoulli(alarm_prob), obs=alarm_obs)

        # --- Mary wakes ---
        mary_prob = torch.where(
            alarm.bool() & earthquake.bool(), torch.tensor(0.8),
            torch.where(alarm.bool(), torch.tensor(0.6), torch.tensor(0.2))
        )
        pyro.sample("maryWakes", dist.Bernoulli(mary_prob), obs=maryWakes_obs)

        # --- Phone working ---
        phone_prob = torch.where(earthquake.bool(), torch.tensor(0.7), torch.tensor(0.99))
        pyro.sample("phoneWorking", dist.Bernoulli(phone_prob), obs=phoneWorking_obs)

        # --- Called ---
        call_prob = torch.where(
            maryWakes_obs.bool() & phoneWorking_obs.bool(),
            torch.tensor(1.0),
            torch.tensor(0.0)
        )
        pyro.sample("called", dist.Bernoulli(call_prob), obs=called_obs)



def guide_burglary(params):
    # Define variational parameters (learnable)
    pb_map = pyro.param("pb_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    pe_map = pyro.param("pe_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)

    pyro.sample("pb", dist.Beta(pb_map * 10, (1 - pb_map) * 10))
    pyro.sample("pe", dist.Beta(pe_map * 10, (1 - pe_map) * 10))


def model_clickgraph(params):
    #observing only click0 and click1
    N, data = params
    p = pyro.sample("p", dist.Uniform(0,1))

    with pyro.plate("data", N):
        # Prior on similarity variable
        sim = pyro.sample("sim", dist.Bernoulli(p))

        # Priors on latent click probabilities
        beta1 = pyro.sample("beta1", dist.Uniform(0., 1.))
        # Conditional definition for beta2
        beta2_same = beta1
        beta2_diff = pyro.sample("beta2_diff", dist.Uniform(0., 1.))
        beta2 = sim * beta2_same + (1 - sim) * beta2_diff

        # Observed clicks
        click0 = pyro.sample("click0", dist.Bernoulli(beta1), obs=data[:, 0])
        click1 = pyro.sample("click1", dist.Bernoulli(beta2), obs=data[:, 1])


def guide_clickgraph(params):
    N, data = params
    # Variational posterior for global latent variable p
    p_map = pyro.param("p_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    pyro.sample("p", dist.Delta(p_map))

def model_clinicaltrial(params):

    N, data = params
    
    # Priors on probabilities
    pe = pyro.sample("pe", dist.Uniform(0., 1.))   # probability of effect
    pt = pyro.sample("pt", dist.Uniform(0., 1.))   # treatment success prob
    pc = pyro.sample("pc", dist.Uniform(0., 1.))  # baseline control prob
    
    with pyro.plate("data", N):
        # Sample whether effect is active
        effect = pyro.sample("effect", dist.Bernoulli(pe))
        
        # pc = pt if effect == 1 else pc_base
        pc_real = effect * pt + (1 - effect) * pc

        # Observed outcomes
        ycontr = pyro.sample("ycontr", dist.Bernoulli(pc_real), obs=data[:, 0])
        ytreated = pyro.sample("ytreated", dist.Bernoulli(pt), obs=data[:, 1])

def guide_clinicaltrial(params):

    # Variational parameters for global latent variables
    pe_map = pyro.param("pe_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    pt_map = pyro.param("pt_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    pc_map = pyro.param("pc_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)

    pyro.sample("pe", dist.Delta(pe_map))
    pyro.sample("pt", dist.Delta(pt_map))
    pyro.sample("pc", dist.Delta(pc_map))

def model_coinbias(params):
    N, data = params

    # Priors for Beta parameters (shape parameters p1, p2)
    p1 = pyro.sample("p1", dist.Uniform(0., 1.))
    p2 = pyro.sample("p2", dist.Uniform(0., 1.))

    # Latent bias sampled from a Beta distribution
    bias = pyro.sample("bias", dist.Beta(p1, p2))

    # Likelihood: observed binary outcomes
    with pyro.plate("data_plate", N):
        pyro.sample("y", dist.Bernoulli(bias), obs=data)


def guide_coinbias(params):
    # Variational parameters (unconstrained, so we apply softplus)
    p1_map = pyro.param("p1_map", torch.tensor(1.0), constraint=dist.constraints.positive)
    p2_map = pyro.param("p2_map", torch.tensor(1.0), constraint=dist.constraints.positive)
    
    # Approximate posteriors
    pyro.sample("p1", dist.Delta(p1_map))
    pyro.sample("p2", dist.Delta(p2_map))


def model_grass(params):
    """
    Pyro model replicating the generative process of generate_grass_dataset().
    Observes: rain, sprinkler, wetGrass, wetRoof if data is provided.
    """
    N, data = params

    pcloudy = pyro.sample("pcloudy", dist.Uniform(0., 1.))
    p1 = pyro.sample("p1", dist.Uniform(0., 1.))
    p2 = pyro.sample("p2", dist.Uniform(0., 1.))
    p3 = pyro.sample("p3", dist.Uniform(0., 1.))

    with pyro.plate("data", N):
        # Cloudiness prior
        cloudy = pyro.sample("cloudy", dist.Bernoulli(pcloudy))

        # Conditional rain/sprinkler given cloudy
        rain_prob = torch.where(cloudy.bool(), torch.tensor(0.8), torch.tensor(0.2))
        sprinkler_prob = torch.where(cloudy.bool(), torch.tensor(0.1), torch.tensor(0.5))
        rain = pyro.sample("rain", dist.Bernoulli(rain_prob),
                           obs=data[:, 0])
        sprinkler = pyro.sample("sprinkler", dist.Bernoulli(sprinkler_prob),
                                obs=data[:, 1])

        # temp variables
        temp1 = pyro.sample("temp1", dist.Bernoulli(p1))
        temp2 = pyro.sample("temp2", dist.Bernoulli(p2))
        temp3 = pyro.sample("temp3", dist.Bernoulli(p3))

        # wetRoof logic
        wetRoof = torch.where((temp1 == 1) & (rain == 1),
                              torch.tensor(1.0),
                              torch.tensor(0.0))
        pyro.sample("wetRoof", dist.Bernoulli(wetRoof),
                    obs=data[:, 3])

        # OR nodes and wetGrass
        or1 = torch.where((temp2 == 1) & (rain == 1),
                          torch.tensor(1.0),
                          torch.tensor(0.0))
        or2 = torch.where((temp3 == 1) & (sprinkler == 1),
                          torch.tensor(1.0),
                          torch.tensor(0.0))
        wetGrass = torch.where((or1 == 1) | (or2 == 1),
                               torch.tensor(1.0),
                               torch.tensor(0.0))
        pyro.sample("wetGrass", dist.Bernoulli(wetGrass),
                    obs=data[:, 2])

def guide_grass(params):
    N, data = params

    # Variational parameters (unconstrained, so we apply softplus)
    p1_map = pyro.param("p1_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    p2_map = pyro.param("p2_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    p3_map = pyro.param("p3_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    pcloudy_map = pyro.param("pcloudy_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)

    # Approximate posteriors
    pyro.sample("pcloudy", dist.Delta(pcloudy_map))
    pyro.sample("p1", dist.Delta(p1_map))
    pyro.sample("p2", dist.Delta(p2_map))
    pyro.sample("p3", dist.Delta(p3_map))


def model_murdermistery(params):
    N, data = params
    palice = pyro.sample("palice", dist.Uniform(0., 1.))
    alice = pyro.sample("alice", dist.Bernoulli(palice))
    # Likelihood: observed binary outcomes
    with pyro.plate("data_plate", N):
        gun_prob = torch.where(alice.bool(), torch.tensor(0.03), torch.tensor(0.8))
        pyro.sample("withGun", dist.Bernoulli(gun_prob), obs=data[:,0])


def guide_murdermistery(params):
    # Variational parameters (unconstrained, so we apply softplus)
    palice_map = pyro.param("palice_map", torch.tensor(0.9), constraint=dist.constraints.unit_interval)    
    # Approximate posteriors
    pyro.sample("palice", dist.Delta(palice_map))


def model_noisior(params):
    N, data = params
    p0 = pyro.sample("p0", dist.Uniform(0.0, 1.0))
    p1 = pyro.sample("p1", dist.Uniform(0.0, 1.0))
    p2 = pyro.sample("p2", dist.Uniform(0.0, 1.0))
    p4 = pyro.sample("p4", dist.Uniform(0.0, 1.0))

    with pyro.plate("data", N):
        n0 = pyro.sample("n0", dist.Bernoulli(p0))
        n4 = pyro.sample("n4", dist.Bernoulli(p4))

        n1 = torch.where(n0.bool(), p1, p2)    # scalar per batch element
        n21 = torch.where(n0.bool(), p1, p2)
        n22 = torch.where(n4.bool(), p1, p2)
        n33 = torch.where(n4.bool(), p1, p2)

        # P(n2=1) = 1 - (1-n21)*(1-n22)
        n2_prob = 1.0 - (1.0 - n21) * (1.0 - n22)
        # sample or observe n2
        n2 = pyro.sample("n2", dist.Bernoulli(n2_prob), obs=(data[:, 0]))

        # b31 is the Bernoulli(n1) that selects n31 = p1 if b31==1 else p2
        b31 = pyro.sample("b31", dist.Bernoulli(n1))
        n31 = torch.where(b31.bool(), p1, p2)

        n32 = torch.where(n2.bool(), p1, p2)

        n3_prob = 1.0 - (1.0 - n31) * (1.0 - n32) * (1.0 - n33)
        pyro.sample("n3", dist.Bernoulli(n3_prob), obs=(data[:, 1]))

def guide_noisior(params):
    # Variational parameters (unconstrained, so we apply softplus)
    p0_map = pyro.param("p0_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    p1_map = pyro.param("p1_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    p2_map = pyro.param("p2_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    p4_map = pyro.param("p4_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)

    # Approximate posteriors
    pyro.sample("p0", dist.Delta(p0_map))
    pyro.sample("p1", dist.Delta(p1_map))
    pyro.sample("p2", dist.Delta(p2_map))
    pyro.sample("p4", dist.Delta(p4_map))


def model_surveyunbiased(params):
    N, y = params
    # Prior for theta
    bias1 = pyro.sample("bias1", dist.Uniform(0, 1))
    bias2 = pyro.sample("bias2", dist.Uniform(0, 1))

    # Likelihood
    with pyro.plate("data_plate", N):
        ansb1 = pyro.sample("ansb1", dist.Bernoulli(bias1), obs=y[:, 0])
        ansb2 = pyro.sample("ansb2", dist.Bernoulli(bias2), obs=y[:, 1])

def guide_surveyunbiased(params):
    bias1_map = pyro.param("bias1_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    bias2_map = pyro.param("bias2_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)

    pyro.sample("bias1", dist.Delta(bias1_map))
    pyro.sample("bias2", dist.Delta(bias2_map))

def model_trueskills(params):
    N, data = params
    pa = pyro.sample("pa", dist.Uniform(0, 200))
    pb = pyro.sample("pb", dist.Uniform(0, 200))
    pc = pyro.sample("pc", dist.Uniform(0, 200))

    with pyro.plate("data", N):
        skillA = pyro.sample("skillA", dist.Normal(pa, 10))
        skillB = pyro.sample("skillB", dist.Normal(pb, 10))
        skillC = pyro.sample("skillC", dist.Normal(pc, 10))

        perfA = pyro.sample("perfA", dist.Normal(skillA, 15), obs=data[:, 0])
        perfB = pyro.sample("perfB", dist.Normal(skillB, 15), obs=data[:, 1])
        perfC = pyro.sample("perfC", dist.Normal(skillC, 15), obs=data[:, 2])



def guide_trueskills(params):
    pa_map = pyro.param("pa_map", torch.tensor(100.0))
    pb_map = pyro.param("pb_map", torch.tensor(100.0))
    pc_map = pyro.param("pc_map", torch.tensor(100.0))

    pyro.sample("pa", dist.Delta(pa_map))
    pyro.sample("pb", dist.Delta(pb_map))
    pyro.sample("pc", dist.Delta(pc_map))

def model_twocoins(params):
    N, data = params
    first = pyro.sample("first", dist.Uniform(0, 1))
    second = pyro.sample("second", dist.Uniform(0, 1))

    with pyro.plate("data", N):
        coin1 = pyro.sample("coin1", dist.Bernoulli(first))
        coin2 = pyro.sample("coin2", dist.Bernoulli(second))
        both = torch.where((coin1 == 1) & (coin2 == 1),
                           torch.tensor(1.0),
                           torch.tensor(0.0))
        pyro.sample("both", dist.Bernoulli(both), obs=data[:, 0])

def guide_twocoins(params):
    first_map = pyro.param("first_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    second_map = pyro.param("second_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)

    pyro.sample("first", dist.Delta(first_map))
    pyro.sample("second", dist.Delta(second_map))

def model_altermu(params):
    N, data = params
    p1 = pyro.sample("p1", dist.Uniform(-10, 10))
    p2 = pyro.sample("p2", dist.Uniform(-10, 10))
    p3 = pyro.sample("p3", dist.Uniform(-10, 10))

    with pyro.plate("data", N):
        w1 = pyro.sample("w1", dist.Normal(p1, 5))
        w2 = pyro.sample("w2", dist.Normal(p2, 5))
        w3 = pyro.sample("w3", dist.Normal(p3, 5))

        mean = w1 * w2
        mean = 3 * mean - w3

        y = pyro.sample("y", dist.Normal(mean, 1), obs=data[:, 0])

def guide_altermu(params):
    p1_map = pyro.param("p1_map", torch.tensor(0.0))
    p2_map = pyro.param("p2_map", torch.tensor(0.0))
    p3_map = pyro.param("p3_map", torch.tensor(0.0))

    pyro.sample("p1", dist.Delta(p1_map))
    pyro.sample("p2", dist.Delta(p2_map))
    pyro.sample("p3", dist.Delta(p3_map))

def model_altermu2(params):
    N, data = params
    muy = pyro.sample("muy", dist.Uniform(-10, 10))
    vary = pyro.sample("vary", dist.Uniform(0.1, 20))

    with pyro.plate("data", N):
        w1 = pyro.sample("w1", dist.Uniform(-10, 10))
        w2 = pyro.sample("w2", dist.Uniform(-10, 10))
        y_mean = w1 + w2 + muy
        y = pyro.sample("y", dist.Normal(y_mean, vary), obs=data[:, 0])

def guide_altermu2(params):
    muy_map = pyro.param("muy_map", torch.tensor(0.0))
    vary_map = pyro.param("vary_map", torch.tensor(1.0), constraint=dist.constraints.positive)

    pyro.sample("muy", dist.Delta(muy_map))
    pyro.sample("vary", dist.Delta(vary_map))

def model_normalmixtures(params):
    N, data = params
    theta = pyro.sample("theta", dist.Uniform(0, 1))
    p1 = pyro.sample("p1", dist.Uniform(-20, 20))
    p2 = pyro.sample("p2", dist.Uniform(-20, 20))

    with pyro.plate("data", N):
        mu1 = pyro.sample("mu1", dist.Normal(p1, 1))
        mu2 = pyro.sample("mu2", dist.Normal(p2, 1))
        component = pyro.sample("component", dist.Bernoulli(theta))
        y_mean = torch.where(component.bool(), mu1, mu2)
        y = pyro.sample("y", dist.Normal(y_mean, 1), obs=data[:, 0])

def guide_normalmixtures(params):
    theta_map = pyro.param("theta_map", torch.tensor(0.5), constraint=dist.constraints.unit_interval)
    p1_map = pyro.param("p1_map", torch.tensor(0.0))
    p2_map = pyro.param("p2_map", torch.tensor(0.0))

    pyro.sample("theta", dist.Delta(theta_map))
    pyro.sample("p1", dist.Delta(p1_map))
    pyro.sample("p2", dist.Delta(p2_map))

def model_test(params):
    N, data = params
    p1 = pyro.sample("p1", dist.Uniform(-10, 10))
    p2 = pyro.sample("p2", dist.Uniform(-10, 10))
    p3 = pyro.sample("p3", dist.Uniform(-10, 10))

    with pyro.plate("data", N):
        v = pyro.sample("v", dist.Normal(p1, 1))
        y_mean = torch.where(v > 0, p2, -2.)
        y = pyro.sample("y", dist.Normal(y_mean, 1), obs=data[:, 0])

def guide_test(params):
    p1_map = pyro.param("p1_map", torch.tensor(0.))
    p2_map = pyro.param("p2_map", torch.tensor(0.))
    #p3_map = pyro.param("p3_map", torch.tensor(0.))

    pyro.sample("p1", dist.Delta(p1_map))
    pyro.sample("p2", dist.Delta(p2_map))
    #pyro.sample("p3", dist.Delta(p3_map))


def model_test2(params):
    N, data = params
    p1 = pyro.sample("p1", dist.Uniform(-10, 10))
    sigma1 = pyro.sample("sigma1", dist.Uniform(0, 10))

    with pyro.plate("data", N):
        v = pyro.sample("v", dist.Normal(0., sigma1))
        y_mean = torch.where(v < p1, 0., 1.)
        y = pyro.sample("y", dist.Bernoulli(y_mean), obs=data[:, 0])

def guide_test2(params):
    p1_map = pyro.param("p1_map", torch.tensor(0.))
    sigma1_map = pyro.param("sigma1_map", torch.tensor(1.), constraint=dist.constraints.positive)
    #p3_map = pyro.param("p3_map", torch.tensor(0.))

    pyro.sample("p1", dist.Delta(p1_map))
    pyro.sample("sigma1", dist.Delta(sigma1_map))

def model_pid(params):
    N, data = params
    # Sample parameters
    s0 = pyro.sample("s0", dist.Normal( torch.tensor(43.0), 1.0))
    s1 = pyro.sample("s1", dist.Normal(torch.tensor(-26.0), 1.0))
    s2 = pyro.sample("s2", dist.Normal(torch.tensor(0.0), 1.0))

    target = 3.14
    dt = 0.15
    inertia = 10
    decay = 0.9
    T = 50
    init_ang = 0.5

    traj_list = []
    v = torch.zeros(N)
    ang = torch.ones(N) * init_ang
    id = torch.zeros(N)

    noise = dist.Normal(0., 0.25)
    noise_ang = dist.Normal(0., 0.25)

    for i in range(T):
        traj_list.append(ang)
        d = target - ang
        torq = s0 * d + s1 * v + s2 * id
        id = decay * id + d * dt
        oldv = v
        v = v + (dt / inertia) * torq + noise.rsample([N])
        ang = ang + (dt / 2) * (v + oldv) + noise_ang.rsample([N])

    traj = torch.stack(traj_list, dim=1)

    with pyro.plate("data", N):
        pyro.sample("obs", dist.Normal(traj, 0.5).to_event(1), obs=data)

def guide_pid(params):
    s0_loc = pyro.param("s0_map", torch.tensor(43.0))
    s1_loc = pyro.param("s1_map", torch.tensor(-26.0))
    s2_loc = pyro.param("s2_map", torch.tensor(0.0))

    pyro.sample("s0", dist.Normal(s0_loc, torch.tensor(1.0)))
    pyro.sample("s1", dist.Normal(s1_loc, torch.tensor(1.0)))
    pyro.sample("s2", dist.Normal(s2_loc, torch.tensor(1.0)))

