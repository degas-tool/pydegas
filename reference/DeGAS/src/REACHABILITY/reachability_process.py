import sys, os
sys.path.append(os.path.abspath(os.path.join('..')))
print(sys.path)

from sogaPreprocessor import *
from producecfg import *
from smoothcfg import *
from libSOGA import *
from time import time
import matplotlib.pyplot as plt
import numpy as np
import torch
import pandas as pd

from REACHABILITY.optimization import *
from REACHABILITY.programs import *
torch.set_default_dtype(torch.float64)

def get_loss(name):
    if name == 'bouncing_ball':
        loss = lambda dist : - (1 - dist.gm.marg_cdf(torch.tensor([7.]), idx=torch.argmax(dist.gm.mean()[int(dist.gm.mean()[[i for i, var in enumerate(dist.var_list) if var == 'valid'][0]]):35]) + int(dist.gm.mean()[[i for i, var in enumerate(dist.var_list) if var == 'valid'][0]])))
    elif name == 'gearbox':
        indexes = [i for i in range(21)]
        loss = lambda dist : dist.gm.marg_cdf(torch.tensor([16.]), idx=indexes)
    elif name == 'thermostat':
        dt = 0.1
        loss = lambda dist : -((dist.gm.marg_cdf(torch.tensor([20.1]), idx=[int(np.round(0.6/dt)), int(np.round(1.8/dt)), int(np.round(2.4/dt))]) - dist.gm.marg_cdf(torch.tensor([19.9]), idx=[int(np.round(0.6/dt)), int(np.round(1.8/dt)), int(np.round(2.4/dt))]))*dist.gm.marg_pdf(torch.tensor([-1., -1., -1.]).unsqueeze(0), idx = [int(np.round(0.6/dt))+25, int(np.round(1.8/dt))+25, int(np.round(2.4/dt))+25]).squeeze())

    else:
        raise ValueError(f"Unknown program name: {name}")
    return loss

def get_hyperparams(name):
    if name == 'bouncing_ball':
        hyperparams = {'lr': 0.1, 'n_steps': 50}
    elif name == 'gearbox':
        hyperparams = {'lr': 0.5, 'n_steps': 40}
    elif name == 'thermostat':
        hyperparams = {'lr': 0.0001, 'n_steps': 500}
    else:
        raise ValueError(f"Unknown program name: {name}")
    return hyperparams

def process(name, all = False):

    soga_code, params, t, traj_var = get_program(name)
    compiledFile = compile2SOGA_text(soga_code)
    cfg = produce_cfg_text(compiledFile)
    smooth_cfg(cfg)

    # initialize parameters
   
    params_dict = initialize_params(params)  

    # computes SOGA output
    output_dist = start_SOGA(cfg, params_dict)
    #y_init = output_dist.gm.mean()[:t].detach()

    y_init = []
    y_var_init = []
    for i in range(t):
        y_init.append(output_dist.gm.mean()[output_dist.var_list.index(traj_var+'['+ str(i) +']')].detach().numpy())
        y_var_init.append(torch.sqrt(output_dist.gm.cov()[output_dist.var_list.index(traj_var+'['+ str(i) +']'), output_dist.var_list.index(traj_var+'['+ str(i) +']')]).detach().numpy())

    df = pd.DataFrame({'Y_mean': y_init, 'Y_std': y_var_init})
    df.to_csv('csv_files/' + name + '_init.csv', index=False)

    params_dict = initialize_params(params)
    # gradient based optimization
    hyperparams = get_hyperparams(name)
    loss_list = optimize(cfg, params_dict, get_loss(name), n_steps=hyperparams['n_steps'], lr=hyperparams['lr'], print_progress=False)

    # print results:
    for key, value in params_dict.items():
        print(f"{key}: {value.item()}")

    compiledFile = compile2SOGA_text(soga_code)
    cfg = produce_cfg_text(compiledFile)
    smooth_cfg(cfg)
    output_dist = start_SOGA(cfg, params_dict)
    y_opt = output_dist.gm.mean()[:t].detach()

    y = []
    y_var = []
    for i in range(t):
        y.append(output_dist.gm.mean()[output_dist.var_list.index(traj_var+'['+ str(i) +']')].detach().numpy())
        y_var.append(torch.sqrt(output_dist.gm.cov()[output_dist.var_list.index(traj_var+'['+ str(i) +']'), output_dist.var_list.index(traj_var+'['+ str(i) +']')]).detach().numpy())

    df = pd.DataFrame({'Y_mean': y, 'Y_std': y_var})
    df.to_csv('csv_files/' + name + '_opt.csv', index=False)

    loss_list = (np.array(loss_list) - np.min(loss_list)) / (np.max(loss_list) - np.min(loss_list))
    df_loss = pd.DataFrame({'Loss': loss_list})
    df_loss.to_csv('csv_files/' + name + '_loss.csv', index=False)

    if all:
        return t, y_init, y_var_init, y, y_var
    else:
        plt.plot(range(t), y_opt, lw=3, label='Optimized params')
        plt.plot(range(t), y_init, lw=3, label='Initial params')
        plt.legend()
        plt.show()



if __name__ == "__main__":
    #take argument name from command line
    if len(sys.argv) > 1:
        name = sys.argv[1]
    else:
        name = "all"
    print(f"Running optimization for program: {name}")

    if name == "all":
        #create a plot 2x2 with the single models plot and one with all the losses 
        plt.figure(figsize=(12, 10))
        plt.subplot(2, 2, 1)
        #put one plot in each subplot in the loop

        for i, prog in enumerate(['thermostat', 'gearbox', 'bouncing_ball']):
            plt.subplot(2, 2, i+1)
            T, y_init, y_var_init, y, y_var = process(prog, all=True)
            plt.plot(range(T), y_init, lw=3, label='SOGA init params')
            plt.fill_between(range(T), np.array(y_init) - np.array(y_var_init), np.array(y_init) + np.array(y_var_init), alpha=0.2)
            plt.plot(range(T), y, lw=3, label='SOGA opt params')
            plt.fill_between(range(T), np.array(y) - np.array(y_var), np.array(y) + np.array(y_var), alpha=0.2)
            plt.title(prog)
            plt.xlabel('Time steps')
            plt.ylabel('Value')
            plt.legend()
  

        #only one plot for the losses
        plt.subplot(2, 2, 4)
        for prog in ['thermostat', 'gearbox', 'bouncing_ball']:
            df_loss = pd.read_csv('csv_files/'+prog+'_loss.csv')
            plt.plot(range(len(df_loss['Loss'])), df_loss['Loss'], label=prog)

        plt.xlabel('Iteration')
        plt.ylabel('Loss')
        plt.title('Loss over iterations for all programs')
        plt.legend()
        plt.show()

    else:
        process(name)