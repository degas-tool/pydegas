import matplotlib.pyplot as plt

import torch
from torch import distributions, sigmoid

# packages for MCMC
import pyro
import pyro.distributions as dist
from pyro.infer import MCMC, NUTS, HMC

# packages for VI
from pyro.infer import SVI, Trace_ELBO
import torch.nn.functional as F


### THERMOSTAT
### Model params = { 'T': time steps, 'init_T': initial temp, 'tOn': turn-on temperature, 'tOff': turn-off temperature}

def thermostat_model(T=20, init_T=15., tOn=16, tOff=20, k=0.01, h=0.5, eps=0.1):
    
    T = int(T)
    traj = torch.zeros(T)
    isOn = False
    traj[0] = init_T
    noise = distributions.Normal(torch.tensor(0.), torch.tensor(eps))
        
    for i in range(1,T):
        
        #update temperature
        if isOn:
            traj[i] = traj[i-1] -k*traj[i-1] + h + noise.rsample() 
        else:
            traj[i] = traj[i-1] -k*traj[i-1] + noise.rsample() 

        # update thermostat state
        if isOn and traj[i] > tOff:
            isOn = False
        elif not isOn and traj[i] < tOn:
            isOn = True
            
    return traj

def create_thermostat_pyro(initial_params, eps=1.0):
    """
    Creates a Pyro model with specified initial parameters
    """

    T = initial_params['T']
    init_T = initial_params['init_T']
    init_tOn = initial_params['tOn']
    init_tOff = initial_params['tOff']

    def thermostat_pyro(observed_traj, eps=eps, k=0.01, h=0.5):
        
        tOn = pyro.sample("tOn", dist.Normal(init_tOn, 0.1))
        tOff = pyro.sample("tOff", dist.Normal(init_tOff, 0.1))

        batch_size = observed_traj.shape[0]
        traj = torch.zeros(batch_size, T)
        traj[:, 0] = init_T
        isOn = torch.zeros(batch_size, dtype=torch.bool)
        noise = dist.Normal(0.0, 0.1)

        for i in range(1, T):
            traj[:, i] = traj[:, i - 1] - k * traj[:, i - 1] + noise.sample([batch_size])
            traj[:, i] += h * isOn.float()
            isOn = torch.where((isOn & (traj[:, i] > tOff)) | (~isOn & (traj[:, i] < tOn)), ~isOn, isOn)

        with pyro.plate("data", batch_size):
            pyro.sample("obs", dist.Normal(traj, eps).to_event(1), obs=observed_traj)

    return thermostat_pyro


def create_thermostat_smooth_pyro(initial_params, sharpness, eps=1.0):

    T = initial_params['T']
    init_T = initial_params['init_T']
    init_tOn = initial_params['tOn']
    init_tOff = initial_params['tOff']

    def thermostat_smooth_pyro(observed_traj, sharpness=sharpness, eps=eps, k=0.01, h=0.5):
    
        # higher sharpness means sharper transitions 
        tOn = pyro.sample("tOn", dist.Normal(init_tOn, 0.1))
        tOff = pyro.sample("tOff", dist.Normal(init_tOff, 0.1))

        batch_size = observed_traj.shape[0]
        traj = torch.zeros(batch_size, T)
        traj[:, 0] = init_T
        isOn_prob = torch.zeros(batch_size)  # probability that isOn is True
        noise = dist.Normal(0.0, 0.1)

        def sigmoid(x):
            return 1 / (1 + torch.exp(-x))

        for i in range(1, T):
            # Smooth transitions
            turn_on =  sigmoid(sharpness * (tOn - traj[:, i-1]))
            turn_off = sigmoid(sharpness * (traj[:, i-1] - tOff))
            isOn_prob = isOn_prob * (1 - turn_off) + (1 - isOn_prob) * turn_on
            traj[:, i] = traj[:, i-1] - k * traj[:, i-1] + h * isOn_prob + noise.sample([batch_size])

        with pyro.plate("data", batch_size):
            pyro.sample("obs", dist.Normal(traj, eps).to_event(1), obs=observed_traj)

    return thermostat_smooth_pyro


def create_thermostat_guide(initial_params):
    """
    Creates the guide for SVI
    """

    T = initial_params['T']
    init_T = initial_params['init_T']
    init_tOn = initial_params['tOn']
    init_tOff = initial_params['tOff']

    def thermostat_guide(observed_traj, T=T, init_T=init_T, k=0.01, h=0.5, eps=0.5):
    
        # Variational parameters for tOn and tOff
        tOn_loc = pyro.param("tOn_loc", torch.tensor(init_tOn))
        tOff_loc = pyro.param("tOff_loc", torch.tensor(init_tOff))

        # Sample tOn and tOff from variational distributions
        pyro.sample("tOn", dist.Normal(tOn_loc, torch.tensor(0.5)))
        pyro.sample("tOff", dist.Normal(tOff_loc, torch.tensor(0.5)))

    return thermostat_guide

### UTILS

def generate_traj(model, n_traj, model_params):
    """
    Generate a set of trajectories using the specified model and parameters.
    """
    traj_set = []
    for _ in range(n_traj):
        traj = model(**model_params)
        traj_set.append(traj)
    return torch.vstack(traj_set)


def plot_traj_set(traj_set, single_traj=0, color='blue', ls='-', label=None):
    """
    Plot a set of trajectories.
    """
    T = traj_set.shape[1]
    for i in range(single_traj):
        plt.plot(range(T), traj_set[i], color='grey')
    plt.plot(range(T), torch.mean(traj_set, 0), lw=3, ls=ls, color=color, label=label)
    plt.legend()


def run_NUTS(pyro_model, traj_set, num_samples=1000, warmup_steps=500, num_chains=1):
    """
    Run NUTS sampling on the given trajectory set using the specified Pyro model.
    """

    nuts_kernel = NUTS(pyro_model)    # NUTS fails to converge (acc. prob = 0.0 both with nonsmooth and smooth)
    mcmc = MCMC(nuts_kernel, num_samples=num_samples, warmup_steps=warmup_steps, num_chains=num_chains)
    mcmc.run(traj_set)

    # Extract posterior samples
    posterior_samples = mcmc.get_samples()
    return posterior_samples
