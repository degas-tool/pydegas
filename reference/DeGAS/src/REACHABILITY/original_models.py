import matplotlib.pyplot as plt
import torch
from torch import distributions


### THERMOSTAT
### Model params = { 'T': time steps, 'init_T': initial temp, 'tOn': turn-on temperature, 'tOff': turn-off temperature}

def thermostat_model(T=20, init_T=15., tOn=16, tOff=20, k=0.01, h=0.5, eps=0.1):
    
    T = int(T)
    traj = torch.zeros(T)
    isOn = False
    traj[0] = init_T
    noise = distributions.Normal(torch.tensor(0.), torch.tensor(eps))
    onlist = []
    onlist.append(isOn)   
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
        onlist.append(isOn)
            
    return traj, onlist

### GEARBOX
### Model params = { 'T': time steps, 'init_v': initial velocity, 'gear': initial gear, 's1': shift point 1, 's2': shift point 2, 's3': shift point 3, 's4': shift point 4}

def gearbox(T=20, init_v=5., gear=1, s1=10, s2=20):
    
    traj = torch.zeros(T)
    traj[0] = init_v
    #noise = distributions.Normal(torch.tensor(0.), torch.tensor(eps))

    w = 0.
    p = [5, 15, 25, 40, 60]
    s = [s1, s2]
    alpha = [0.78, 0.78, 0.78, 0.55, 0.25]

    dt = 0.1
    
    for i in range(1,T):
        
        #update velocity
        if gear >= 1:
            traj[i] = traj[i-1] + dt*traj[i-1]*alpha[gear-1] + dt*distributions.Normal(5., 1.).rsample() 
        else:
            traj[i] = traj[i-1] - dt*0.0005*traj[i-1]**2 + distributions.Normal(0., 1.).rsample() 

        # update gear
        if gear >= 1 and gear < 3 and traj[i] > s[gear-1]:
            nxt = gear + 1
            gear = 0
            w = 0.4
        elif gear == 0 and w <= 0:
            gear = nxt

        w = w - 0.1            
            
    return traj , w 

### PID
### Model params = { 'T': time steps, 'init_ang': initial angle, 's0': P gain, 's1': I gain, 's2': D gain}

def pid(T=50, init_ang = 0.5, s0=1, s1=1, s2=1):

    target = 3.14
    dt = 0.1
    inertia = 10
    decay = 0.9
    
    traj = torch.zeros(T)

    noise = distributions.Normal(torch.tensor(0.), torch.tensor(0.25))
    noise_ang = distributions.Normal(torch.tensor(0.), torch.tensor(0.25))

    v = 0 
    ang = init_ang 
    id = 0 

    for i in range(0,T):

        traj[i] = ang 
        
        d = target - ang 
        torq = s0*d + s1*v + s2*id 
        id = decay*id + d*dt
        oldv = v 
        v = v + (dt/inertia)*torq + noise.rsample()
        ang = ang + (dt/2)*(v+oldv) + noise_ang.rsample()

    traj[T-1] = ang 

    #Actually we want to use ideal trajectories
    observed_traj = target*torch.ones(T)

    return observed_traj, ang

def bouncing_ball(T=30, init_H=9., eps=0.1, R = 5.0, C = 400, m = 7.0):

    g = 9.81
    #R = 5.0
    #C = 0.0025 #thus 1/C = 400
    #m = 7.0 #thus 1/m = 0.14
    dt = 0.08
    mode = -1.

    traj = torch.zeros(T)
    traj[0] = distributions.Normal(init_H, 1).rsample()
    v = 0.
    mode_list = []
    mode_list.append(mode)

    noise = distributions.Normal(torch.tensor(0.), torch.tensor(eps))

    for i in range(1,T):
        
        if mode == -1.:
            v = v - g*dt + noise.rsample()
        else:
            v = v - (g + ((R*v+traj[i-1]*C)/m))*dt + noise.rsample()
        
        traj[i] = traj[i-1] + v*dt + noise.rsample()

        if traj[i] <= 0:
            mode = 1.
        else:
            mode = -1.
        mode_list.append(mode)

    return traj, mode_list

### UTILS

def generate_traj(model, n_traj, model_params):
    """
    Generate a set of trajectories using the specified model and parameters.
    """
    traj_set = []
    for _ in range(n_traj):
        traj, mode = model(**model_params)
        traj_set.append(traj)
    return torch.vstack(traj_set), mode


def plot_traj_set(traj_set, single_traj=0, color='blue', ls='-', label=None):
    """
    Plot a set of trajectories.
    """
    T = traj_set.shape[1]
    for i in range(single_traj):
        plt.plot(range(T), traj_set[i], color='grey')
    #plt.plot(range(T), torch.mean(traj_set, 0), lw=3, ls=ls, color=color, label=label)
    plt.legend()


def get_orig_params(name):
    if name == 'thermostat':
        orig_params = {'T': 30,   # time steps
        'init_T': 16.,  # initial temperature
        'tOn': 17,      # turn-on temperature
        'tOff': 20}
        n_traj = 100
        params = {'tOn':  15., 'tOff':22.}
        var_name = 'T'
        model = thermostat_model
        n_steps = 40
        lr = 0.1
    elif name == 'gearbox':
        orig_params = {'T': 20,   # time steps
               'init_v': 5.,  # initial velocity
               'gear': 1,      # initial gear
               's1': 10.,
               's2': 20.}
        n_traj = 1000
        params = {'s1':8., 's2':12.}
        var_name = 'v'
        model = gearbox
        n_steps = 200
        lr = 0.3

    elif name == 'bouncing_ball':
        orig_params = {'T': 35,   # time steps
               'init_H': 9.,  # initial height
               'R': 7.0,
               'C': 400.,
               'm': 7.0}
        n_traj = 100
        params = {'R':  -1., 'C':450.}
        var_name = 'H'
        model = bouncing_ball
        n_steps = 50
        lr = 0.8

    elif   name == 'pid':
        orig_params = {'T': 50,
               'init_ang': 0.5,
               's0': 46.,
               's1': -23.,
               's2': 0.}
        n_traj = 500
        params = {'s0':46., 's1':-23., 's2':0.}
        var_name = 'ang'
        model = pid
        n_steps = 1000
        lr = 0.2
    else:
        raise ValueError(f"Unknown program name: {name}")
    return orig_params, n_traj, params, var_name, model, n_steps, lr
