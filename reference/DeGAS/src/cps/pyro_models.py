import torch
from torch import distributions, sigmoid
from time import time
import matplotlib.pyplot as plt

# packages for MCMC
import pyro
import pyro.distributions as dist
from pyro.infer import MCMC, NUTS, HMC

# packages for VI
from pyro.infer import SVI, Trace_ELBO
import torch.nn.functional as F

### THERMOSTAT
### Model params = { 'T': time steps, 'init_T': initial temp, 'tOn': turn-on temperature, 'tOff': turn-off temperature}

def create_thermostat_pyro(initial_params, eps=1.0):
    """
    Creates a Pyro model with specified initial parameters
    """

    T = initial_params['T']
    init_T = initial_params['init_T']
    init_tOn = initial_params['tOn']
    init_tOff = initial_params['tOff']

    def thermostat_pyro(observed_traj, eps=eps, k=0.01, h=0.5):
        
        tOn = pyro.sample("tOn", dist.Normal(init_tOn, 1.0))
        tOff = pyro.sample("tOff", dist.Normal(init_tOff, 1.0))

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

    def thermostat_guide(observed_traj):
    
        # Variational parameters for tOn and tOff
        tOn_loc = pyro.param("tOn_loc", torch.tensor(init_tOn))
        tOff_loc = pyro.param("tOff_loc", torch.tensor(init_tOff))

        # Sample tOn and tOff from variational distributions
        pyro.sample("tOn", dist.Normal(tOn_loc, torch.tensor(0.5)))
        pyro.sample("tOff", dist.Normal(tOff_loc, torch.tensor(0.5)))

    return thermostat_guide

### GEARBOX
### Model params = { 'T': time steps, 'init_v': initial velocity, 'gear': initial gear, 's1': shift point 1, 's2': shift point 2, 's3': shift point 3, 's4': shift point 4}

def create_gearbox_pyro(initial_params, eps=1.0):

    T = initial_params['T']
    init_v = initial_params['init_v']
    gear = initial_params['gear']
    init_s1 = initial_params['s1']
    init_s2 = initial_params['s2']

    def gearbox_pyro(observed_traj, eps=eps):

        s1 = pyro.sample("s1", dist.Normal(init_s1, 10.0))
        s2 = pyro.sample("s2", dist.Normal(init_s2, 10.0))

        batch_size = observed_traj.shape[0]
        traj = torch.zeros(batch_size, T)
        traj[:, 0] = init_v

        w = torch.zeros(batch_size)
        gear = torch.ones(batch_size, dtype=torch.long)
        nxt = torch.zeros(batch_size, dtype=torch.long)
        alpha = [0.78, 0.78, 0.78, 0.55, 0.25]
        s = torch.stack([s1, s2])

        dt = 0.1

        for i in range(1, T):
        
            # update gear
            for b in range(batch_size):

                #update velocity
                if gear[b] >= 1:
                    traj[b, i] = traj[b, i-1] + dt*traj[b, i-1]*alpha[gear[b]-1] + dt*distributions.Normal(5., 1.).rsample() 
                else:
                    traj[b, i] = traj[b, i-1] - dt*0.0005*traj[b, i-1]**2 + distributions.Normal(0., 1.).rsample() 

                # update gear
                if gear[b] >= 1 and gear[b] < 3 and traj[b, i] > s[gear[b]-1]:
                    nxt[b] = gear[b] + 1
                    gear[b] = 0
                    w[b] = 0.3
                elif gear[b] == 0 and w[b] < 0:
                    gear[b] = nxt[b]
        
                w[b] = w[b] - dt

        with pyro.plate("data", batch_size):
            pyro.sample("obs", dist.Normal(traj, eps).to_event(1), obs=observed_traj)
    
    return gearbox_pyro


def create_gearbox_guide(initial_params):
    """
    Creates the guide for SVI
    """

    init_s1 = initial_params['s1']
    init_s2 = initial_params['s2']

    def gearbox_guide(observed_traj):
        
        s1_loc = pyro.param("s1_loc", init_s1)
        s2_loc = pyro.param("s2_loc", init_s2)

        pyro.sample("s1", dist.Normal(s1_loc, torch.tensor(1.0)))
        pyro.sample("s2", dist.Normal(s2_loc, torch.tensor(1.0)))

    return gearbox_guide


### PID 
### Model params = { 'T': time steps, 'init_ang': initial angle, 's0': P gain, 's1': I gain, 's2': D gain}

def create_pid_pyro(initial_params, eps=0.5):

    T = initial_params['T']
    init_ang = initial_params['init_ang']
    init_s0 = initial_params['s0']
    init_s1 = initial_params['s1']
    init_s2 = initial_params['s2']

    def pid_pyro(observed_traj):
        # Sample parameters
        s0 = pyro.sample("s0", dist.Normal(init_s0, 1.0))
        s1 = pyro.sample("s1", dist.Normal(init_s1, 1.0))
        s2 = pyro.sample("s2", dist.Normal(init_s2, 1.0))

        target = 3.14
        dt = 0.1
        inertia = 10
        decay = 0.9

        batch_size = observed_traj.shape[0]
        traj_list = []
        v = torch.zeros(batch_size)
        ang = torch.ones(batch_size) * init_ang
        id = torch.zeros(batch_size)

        noise = dist.Normal(0., 0.25)
        noise_ang = dist.Normal(0., 0.25)

        for i in range(T):
            traj_list.append(ang)
            d = target - ang
            torq = s0 * d + s1 * v + s2 * id
            id = decay * id + d * dt
            oldv = v
            v = v + (dt / inertia) * torq + noise.rsample([batch_size])
            ang = ang + (dt / 2) * (v + oldv) + noise_ang.rsample([batch_size])

        traj = torch.stack(traj_list, dim=1)

        with pyro.plate("data", batch_size):
            pyro.sample("obs", dist.Normal(traj, eps).to_event(1), obs=observed_traj)

    return pid_pyro


def create_pid_guide(initial_params):
    """
    Creates the guide for SVI
    """

    init_s0 = initial_params['s0']
    init_s1 = initial_params['s1']
    init_s2 = initial_params['s2']

    def pid_guide(observed_traj):
        
        s0_loc = pyro.param("s0_loc", init_s0)
        s1_loc = pyro.param("s1_loc", init_s1)
        s2_loc = pyro.param("s2_loc", init_s2)

        pyro.sample("s0", dist.Normal(s0_loc, torch.tensor(1.0)))
        pyro.sample("s1", dist.Normal(s1_loc, torch.tensor(1.0)))
        pyro.sample("s2", dist.Normal(s2_loc, torch.tensor(1.0)))

    return pid_guide


### UTILS


def run_NUTS(pyro_model, traj_set, num_samples=1000, warmup_steps=500, num_chains=1, adapt_step_size=True, step_size=1e-3):
    """
    Run NUTS sampling on the given trajectory set using the specified Pyro model.
    """

    nuts_kernel = NUTS(pyro_model, adapt_step_size=adapt_step_size, step_size=step_size)    # NUTS fails to converge (acc. prob = 0.0 both with nonsmooth and smooth)
    mcmc = MCMC(nuts_kernel, num_samples=num_samples, warmup_steps=warmup_steps, num_chains=num_chains)
    mcmc.run(traj_set)

    # Extract posterior samples
    posterior_samples = mcmc.get_samples()
    return posterior_samples


def run_SVI(model, guide, traj_set, num_steps=1000, lr=0.1, num_particles=1, loss_plot=False):

    pyro.clear_param_store()
    optimizer = pyro.optim.Adam({"lr": lr})
    svi = SVI(model, guide, optimizer, loss=Trace_ELBO(num_particles=num_particles))   # with a 100 num_particles and the smooth model the training is more stable

    loss_list = []
    step_list = []

    # Training loop
    start = time()

    for step in range(num_steps):
    
        loss = svi.step(traj_set)

        if step % 100 == 0:
            loss_list.append(loss)
            step_list.append(step)
            print(f"Step {step}: Loss = {loss}")
            #for name, value in pyro.get_param_store().items():
            #    print(name, value.grad)

    end = time()

    print(f"Optimization performed in {end - start:.2f} seconds")

    if loss_plot:
        plt.plot(step_list, loss_list)
        plt.ylabel("Loss")