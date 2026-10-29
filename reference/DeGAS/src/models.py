import torch
from torch import distributions

# THERMOSTAT 

# The original model simulates a thermostat system where the temperature is adjusted based on whether the thermostat is on or off.
# The two parameters `tOn` and `tOff` define the thresholds for turning the thermostat on and off.
# We assume we have some trajectories of temperature readings from this system, but we do not know the value of `tOn` and `tOff`.
# We use the function `orig_model` to generate synthetic temperature trajectories for the thermostat system 
# (setting the value of `tOn` and `tOff` to the true values of 18 and 20 respectively).

def thermostat(T=10, init_T=17., tOn=18, tOff=20, k=0.01, h=0.5, eps=0.1):
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


# GEARBOX

def gearbox(T=20, init_v=5., gear=1, s1=10, s2=20):
    
    traj = torch.zeros(T)
    traj[0] = init_v
    #noise = distributions.Normal(torch.tensor(0.), torch.tensor(eps))

    w = 0.
    p = [5, 15, 25, 40, 60]
    s = [s1, s2]
    alpha = [0.78, 0.78, 0.78, 0.55, 0.25]
    
    for i in range(1,T):
        
        #update velocity
        if gear >= 1:
            traj[i] = traj[i-1] + 0.1*traj[i-1]*alpha[gear-1] + 0.1*distributions.Normal(5., 1.).rsample() 
        else:
            traj[i] = traj[i-1] - 0.1*0.0005*traj[i-1]**2 + distributions.Normal(0., 1.).rsample() 

        # update gear
        if gear >= 1 and gear < 3 and traj[i] > s[gear-1]:
            nxt = gear + 1
            gear = 0
            w = 0.3
        elif gear == 0 and w < 0:
            gear = nxt

        w = w - 0.1            
            
    return traj 

# PID CONTROLLER

def pid(T=50, init_ang = 0.5, b1=-1, b2=-2, b3=1, b4=-6, s0=1, s1=1, s2=1):

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
    old_v = 0 
    for i in range(0,T):

        traj[i] = ang 
        
        d = target - ang 
        torq = s0*d + s1*v + s2*id 
        id = decay*id + d*dt
        oldv = v 
        
        v = v + (dt/inertia)*torq + noise.rsample()
        ang = ang + (dt/2)*(v+oldv) + noise_ang.rsample()
        
        #if b1*d+b2>0 and b2*d+b4>0:
        #    brakev = -1
        #else:
        # brakev = 1        
        
        #if ang > 6.28:
        #    ang = ang - 6.28
        #elif ang < 0:
        #    ang = ang + 6.28

    traj[T-1] = ang 

    return traj        