from original_models import *
import sys, os, os
sys.path.append(os.path.abspath(os.path.join('..')))
from optimization import *

import pandas as pd
import matplotlib.pyplot as plt
from sogaPreprocessor import *
from producecfg import *
from smoothcfg import *
from libSOGA import *
import matplotlib.pyplot as plt
import numpy as np
import torch

torch.set_default_dtype(torch.float64)



def process(name, all = False):
    orig_params, n_traj, params, var_name, model, n_steps, lr = get_orig_params(name)
    orig_traj = generate_traj(model, n_traj, orig_params)

    compiledFile=compile2SOGA('../../programs/SOGA/Optimization/CaseStudies/'+name+'.soga')
    cfg = produce_cfg(compiledFile)
    smooth_cfg(cfg)

    # initialize parameters
    T = orig_params['T']
    init_var = orig_params['init_' + var_name]
    # computes loss
    idx=list(range(1, T))

    params_dict = initialize_params(params)  

    # computes SOGA output
    output_dist = start_SOGA(cfg, params_dict)

    # loss
    print('Initial loss value for ',name, ' : ', neg_log_likelihood(orig_traj, output_dist, idx))

    y_init = []
    y_var_init = []
    for i in range(T):
        y_init.append(output_dist.gm.mean()[output_dist.var_list.index(var_name+'['+ str(i) +']')].detach().numpy())
        y_var_init.append(torch.sqrt(output_dist.gm.cov()[output_dist.var_list.index(var_name+'['+ str(i) +']'), output_dist.var_list.index(var_name+'['+ str(i) +']')]).detach().numpy())

    df = pd.DataFrame({'Y_mean': y_init, 'Y_std': y_var_init})
    df.to_csv('csv_files/'+name+'_init.csv', index=False)

    # Optimization in SOGA
    # Define the optimizer with init_mean as the parameter
    params_dict = initialize_params(params)

    # Define loss
    loss = lambda dist : neg_log_likelihood(orig_traj, dist, idx)

    # cfg for SOGA
    cfg = produce_cfg(compiledFile)
    smooth_cfg(cfg)

    # gradient based optimization
    loss_list, time_opt, n_iters = optimize(cfg, params_dict, loss, n_steps=n_steps, lr=lr, print_progress=False)

    # print results:
    for key, value in params_dict.items():
        print(f"{key}: {value.item()}")

    print("Time for optimization: ", time_opt, " seconds")

    # plots the final result
    cfg = produce_cfg(compiledFile)
    smooth_cfg(cfg)
    output_dist = start_SOGA(cfg, params_dict)

    # export loss_list to csv
    loss_list = (np.array(loss_list) - np.min(loss_list)) / (np.max(loss_list) - np.min(loss_list))

    df_loss = pd.DataFrame({'Loss': loss_list})
    df_loss.to_csv('csv_files/'+name+'_loss.csv', index=False)

    y = []
    y_var = []
    for i in range(T):
        y.append(output_dist.gm.mean()[output_dist.var_list.index(var_name+'['+ str(i) +']')].detach().numpy())
        y_var.append(torch.sqrt(output_dist.gm.cov()[output_dist.var_list.index(var_name+'['+ str(i) +']'), output_dist.var_list.index(var_name+'['+ str(i) +']')]).detach().numpy())

    df = pd.DataFrame({'Y_mean': y, 'Y_std': y_var})
    df.to_csv('csv_files/'+name+'_opt.csv', index=False)

    if all:
        return T, y_init, orig_traj, y, y_var_init, y_var
    else:
        plt.plot(range(T), y_init, lw=3, label='SOGA init params')
        plt.fill_between(range(T), np.array(y_init) - np.array(y_var_init), np.array(y_init) + np.array(y_var_init), alpha=0.2)
        plot_traj_set(orig_traj, single_traj=10, color='red', label='orig')
        plt.plot(range(T), y, lw=3, label='SOGA opt params')
        plt.fill_between(range(T), np.array(y) - np.array(y_var), np.array(y) + np.array(y_var), alpha=0.2)
        plt.legend()    

        plt.show()

        plt.plot(df_loss['Loss'])
        plt.xlabel('Iteration')
        plt.ylabel('Loss')
        plt.title('Loss over iterations')
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

        for i, prog in enumerate(['thermostat', 'gearbox', 'bouncing_ball', 'pid']):
            plt.subplot(2, 2, i+1)
            T, y_init, orig_traj, y, y_var_init, y_var = process(prog, all=True)
            plt.plot(range(T), y_init, lw=3, label='SOGA init params')
            plt.fill_between(range(T), np.array(y_init) - np.array(y_var_init), np.array(y_init) + np.array(y_var_init), alpha=0.2)
            plot_traj_set(orig_traj, single_traj=10, color='red', label='orig')
            plt.plot(range(T), y, lw=3, label='SOGA opt params')
            plt.fill_between(range(T), np.array(y) - np.array(y_var), np.array(y) + np.array(y_var), alpha=0.2)
            plt.title(prog)
            plt.xlabel('Time steps')
            plt.ylabel('Value')
            plt.legend()
        plt.show()

        #only one plot for the losses
        plt.figure(figsize=(12, 10))
        for prog in ['thermostat', 'gearbox', 'bouncing_ball', 'pid']:
            df_loss = pd.read_csv('csv_files/'+prog+'_loss.csv')
            plt.plot(range(len(df_loss['Loss'])), df_loss['Loss'], label=prog)

        plt.xlabel('Iteration')
        plt.ylabel('Loss')
        plt.title('Loss over iterations for all programs')
        plt.legend()
        plt.show()

