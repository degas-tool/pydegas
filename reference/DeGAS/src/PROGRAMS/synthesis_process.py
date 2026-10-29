import sys, os
sys.path.append(os.path.abspath(os.path.join('..')))
print(sys.path)
import gc

from sogaPreprocessor import *
from producecfg import *
from smoothcfg import *
from libSOGA import *
import matplotlib.pyplot as plt
import numpy as np
import torch
from optimization import *
torch.set_default_dtype(torch.float64)
from PROGRAMS.data_generating_process import *
from PROGRAMS.likelihood import *
from PROGRAMS.programs import *
from PROGRAMS.run_pyro import *
import time

import torch
import torch.distributions.constraints as constraints
import pyro
from pyro.optim import Adam
from pyro.infer import SVI, Trace_ELBO, TraceEnum_ELBO
from pyro.infer import MCMC, NUTS
import pyro.distributions as dist
import pandas as pd
import arviz as az

torch.multiprocessing.set_sharing_strategy("file_system")
import multiprocessing as mp
torch.set_num_threads(1)




def neg_log_likelihood_programs(data, dist, idx):
    log_likelihood = torch.log(dist.gm.marg_pdf(data, idx))
    return - torch.sum(log_likelihood)

def run_optimization(name, data, params_init, true_params, eps, sensitivity_analysis=False, lr =0.05, steps = 100):
    soga_code = get_program(name)
    compiledFile = compile2SOGA_text(soga_code)
    cfg = produce_cfg_text(compiledFile)
    smooth_cfg(cfg, smooth_eps=eps)

    params_dict = initialize_params(params_init)  
    output_dist = start_SOGA(cfg, params_dict)
    print("number of components: ", output_dist.gm.pi.shape[0])
    with open("current_dist_stats.txt", "a") as f:
        #write program name withpout overwriting
        f.write(f"Program: {name}\n")
    data_var_list = get_vars(name)
    data_var_index = [output_dist.var_list.index(var) for var in data_var_list]
    data = torch.tensor(data, dtype=torch.float64)
    loss = lambda dist : neg_log_likelihood_programs(data, dist, data_var_index)

    # repeat t
    loss_list, time, number_of_iterations = optimize(cfg, params_dict, loss, n_steps=steps, lr=lr, print_progress=False)

    if sensitivity_analysis:
        error_list = []
        #use the average error
        avg_error = np.mean([abs(params_dict[key].item() - true_value)/abs(true_value) for key, true_value in true_params.items()])
        return avg_error

    
        
    #for key, value in params_dict.items():
        #print(f"{key}: {value.item()}")

    # get the true value of the parameters from true_params and compute the relative error
    #for key, true_value in true_params.items():
       # estimated_value = params_dict[key].item()
       # error = abs(estimated_value - true_value)/abs(true_value)

    #calculate average error
    avg_error = np.mean([abs(params_dict[key].item() - true_value)/abs(true_value) for key, true_value in true_params.items()])
    # print(f"Average error: {avg_error}")

    return loss_list, params_dict, avg_error, time, number_of_iterations



#main function, taking as input the name of the program

def process(name, all = False):
    #set seed for reproducibility
    np.random.seed(17)
    program = name
    data_size = 1000
    true_params, init_params, lr_param, lr_VI_param, mcmc_steps_param, mcmc_warmup_param = get_params(program)
    data = generate_dataset(program, data_size, true_params)  
    print("DeGAS optimization")
    '''
    if all:
         best_lr = lr_param
    else:
    # run one optimization for lr in [0.01, 0.05, 0.1] and choose the best one
        best_lr = 0.01
        best_error = float('inf')
        for lr in [0.001, 0.005, 0.01, 0.05, 0.1, 0.2]:
            try:
                loss_list, params, error, time_degas, number_of_iterations = run_optimization(program, data, init_params, true_params, eps=0.001, lr=lr, steps=500, sensitivity_analysis=False)
                if error < best_error:
                    best_error = error
                    best_lr = lr
            except Exception as e:
                print(f"Error occurred for lr={lr}: {e}")
                continue
        print(f"Best lr: {best_lr}")
    # now run the optimization with the best lr for 10 times and save in a file in losses_csv the average loss (with std) and in another file in errors_csv the R2 error
    losses = []
    parameters = []
    time_list = []
    iters_list = []
    for i in range(1):
        loss_list, params, error, time_degas, number_of_iterations = run_optimization(program, data, init_params, true_params, eps=0.001, lr=best_lr, steps=500)
        losses.append(loss_list)
        parameters.append(params)
        time_list.append(time_degas)
        iters_list.append(number_of_iterations)

    losses = np.array(losses)
    mean_loss = np.mean(losses, axis=0)
    std_loss = np.std(losses, axis=0)
    np.savetxt(f"losses_csv/losses_{program}.csv", np.vstack((mean_loss, std_loss)).T, delimiter=",", header="mean,std", comments='')

    errors_degas = []
    for params in parameters:
        #calculate mean relative error
        error = np.mean([abs(params[key].item() - true_value)/abs(true_value) for key, true_value in true_params.items()])
        #print(f"Error in run: {error}")
        errors_degas.append(error)
    errors_degas = np.array(errors_degas)

    mean_time_degas = np.mean(time_list)
    print(f"Mean time: {mean_time_degas}")
    np.savetxt(f"time_csv/time_{program}.csv", np.array([mean_time_degas]), delimiter=",", header="time", comments='')

    mean_iters = np.mean(iters_list)
    #convert to int
    mean_iters = int(mean_iters)
    print(f"Mean iterations: {mean_iters}")
    np.savetxt(f"iters_csv/iters_{program}.csv", np.array([mean_iters]), delimiter=",", header="iterations", comments='')

    #save best learning rate
    np.savetxt(f"best_lr_csv/best_lr_{program}.csv", np.array([best_lr]), delimiter=",", header="best_lr", comments='')

    mean_error_degas = np.mean(errors_degas)
    print(f"Mean relative error: {mean_error_degas}")
    np.savetxt(f"errors_csv/errors_{program}.csv", np.array([mean_error_degas]), delimiter=",", header="R2", comments='')

    #save the params value in a csv file
    params_df = pd.DataFrame([{key: params[key].item() for key in params.keys()} for params in parameters])
    params_df.to_csv(f"opt_params/params_{program}.csv", index=False)

    if not all:
    # Sensitivity analysis
        print("Sensitivity analysis")
        error_list = []
        for eps in [0.1, 0.01, 0.001, 0.0001]:
            #print(f"Running optimization for eps={eps}")
            error = run_optimization(program, data, init_params, true_params, eps=eps, sensitivity_analysis=True, lr=best_lr, steps= mean_iters)
            error_list.append(error)

        # plot the error as a function of eps
        eps_values = [0.1, 0.01, 0.001, 0.0001]

        #print the error values
        for eps, error in zip(eps_values, error_list):
            print(f"Epsilon: {eps}, Error: {error}")
        '''
    
    ### PYRO INFERENCE

    print("Pyro inference")
    pyro.clear_param_store()
    model, guide = get_model_guide(program)
    if True: #all:
        best_lr = lr_VI_param
    else:
    #choose the best learning rate between [0.01, 0.05, 0.1]
        best_lr = 0.01
        best_error = float('inf')
        for lr in [0.001, 0.0005, 0.01, 0.05, 0.1, 0.2]:
            try:
                loss_list, iterations, time_VI = run_inference(model, guide, model_params=(data_size,torch.tensor(data, dtype=torch.float64)), n_steps=1000, lr=lr)
                error = np.mean([abs(pyro.param(key + "_map").item() - true_value)/abs(true_value) for key, true_value in true_params.items()])
                if error < best_error:
                    best_error = error
                    best_lr = lr
            except Exception as e:
                print(f"Error occurred for lr={lr}: {e}")
                continue
            #loss_list, iterations, time_VI = run_inference(model, guide, model_params=(data_size,torch.tensor(data, dtype=torch.float64)), n_steps=10000, lr=lr)
            #calculate mean relative error
            
    #with best lr run inference 10 times and save all the results
        print(f"Best lr for VI: {best_lr}")
    params_list = []
    loss_list_VI = []
    time_list_VI = []
    iters_list_VI = []
    for i in range(10):
        loss_list, iterations, time_VI = run_inference(model, guide, model_params=(data_size,torch.tensor(data, dtype=torch.float64)), n_steps=50000, lr=best_lr)
        params_list.append({key: pyro.param(key + "_map").item() for key in true_params.keys()})
        loss_list_VI.append(loss_list)
        time_list_VI.append(time_VI)
        iters_list_VI.append(iterations)
    errors_VI = []
    for params in params_list:
        #calculate mean relative error
        error = np.mean([abs(params[key] - true_value)/abs(true_value) for key, true_value in true_params.items()])
        errors_VI.append(error)
       #print(f"Error in run VI {i}: {error}")
    errors_VI = np.array(errors_VI)
    mean_error_VI = np.mean(errors_VI)
    print(f"Mean iterations VI: {np.mean(iters_list_VI)}")
    print(f"Mean relative error VI: {mean_error_VI}")
    print(f"Mean time VI: {np.mean(time_list_VI)}")
    np.savetxt(f"errors_csv/errors_VI_{program}.csv", np.array([mean_error_VI]), delimiter=",", header="R2_VI", comments='')
    #save loss
    #loss_list_VI = np.array(loss_list_VI)
    mean_loss_VI = np.mean(loss_list_VI, axis=0)
    std_loss_VI = np.std(loss_list_VI, axis=0)
    np.savetxt(f"losses_csv/losses_VI_{program}.csv", np.vstack((mean_loss_VI, std_loss_VI)).T, delimiter=",", header="mean,std", comments='')

    #for key, true_value in true_params.items():
            #estimated_value = pyro.param(key + "_map").item()
            #error = abs(estimated_value - true_value)/abs(true_value)
            #print(f"Error in {key}: {error}")

    #avg_error = np.mean([abs(pyro.param(key + "_map").item() - true_value)/abs(true_value) for key, true_value in true_params.items()])
    #print(f"Average error: {avg_error}")
    
    np.savetxt(f"time_csv/time_VI_{program}.csv", np.array([np.mean(time_list_VI)]), delimiter=",", header="time_VI", comments='')
    np.savetxt(f"iters_csv/iters_VI_{program}.csv", np.array([np.mean(iterations)]), delimiter=",", header="iterations_VI", comments='')
    #save the params value in a csv file
    params_df = pd.DataFrame(params_list)
    params_df.to_csv(f"opt_params/params_VI_{program}.csv", index=False)
    
    
    print("MCMC inference")
    rhat = 2.0
    num_samples = 0
    warmup_steps = 50

    if all:
        num_samples = mcmc_steps_param
        warmup_steps = mcmc_warmup_param
        pyro.clear_param_store()
        # Do the same with MCMC
        nuts_kernel = NUTS(model, adapt_step_size=True)
        mcmc = MCMC(nuts_kernel, num_samples=num_samples, warmup_steps=warmup_steps, num_chains=4)
        start = time.time()
        mcmc.run((data_size, torch.tensor(data, dtype=torch.float64)))
        end = time.time()
        # Get total time
        total_time = end - start
        print(f"Total MCMC runtime: {total_time:.3f} seconds")
        if total_time > 600:
            print("MCMC runtime exceeded 6000 seconds, stopping further runs.")
            return mean_error_VI, np.mean(time_list_VI), np.nan, np.nan, np.nan, np.nan, mean_time_degas, mean_error_degas
        #mcmc.summary()
        samples = mcmc.get_samples(group_by_chain=True)
        #print("Samples obtained")
        gc.collect()
        mp.active_children()  # triggers cleanup
        for p in mp.active_children():
            p.terminate()
        #print("Active children terminated")
        idata = az.convert_to_inference_data(samples)
        #print("Converted to inference data")
        #print(az.summary(idata, round_to=4))
        try:
            rhat_all = az.rhat(idata)
            valid_rhat = rhat_all.where(~np.isnan(rhat_all), drop=True)
            rhat = valid_rhat.to_array().max().item()
            neff = az.ess(idata).to_array().min().item()
        except Exception as e:
            print(f"Error computing R-hat and Neff: {e}")
            rhat = float('inf')
            neff = 0
            mean_error_VI, np.mean(time_list_VI), np.NaN, np.NaN, np.NaN, np.NaN, mean_time_degas, mean_error_degas
    else:
        while rhat > 1.05 and num_samples < 60000:

                num_samples += 500
                if num_samples > 2000:
                        warmup_steps += 50
                elif num_samples > 5000:
                        warmup_steps += 100
                print(f"Running MCMC with num_samples={num_samples}, warmup_steps={warmup_steps}")
                # Run the inference with num_samples=500, warmup_steps=50 and check convergence with R-hat and Neff
                pyro.clear_param_store()
                # Do the same with MCMC
                nuts_kernel = NUTS(model, adapt_step_size=True)
                mcmc = MCMC(nuts_kernel, num_samples=num_samples, warmup_steps=warmup_steps, num_chains=4)
                start = time.time()
                mcmc.run((data_size, torch.tensor(data, dtype=torch.float64)))
                end = time.time()
                # Get total time
                total_time = end - start
                print(f"Total MCMC runtime: {total_time:.3f} seconds")
                if total_time > 600:
                    print("MCMC runtime exceeded 6000 seconds, stopping further runs.")
                    break
                #mcmc.summary()
                samples = mcmc.get_samples(group_by_chain=True)
                print("Samples obtained")
                gc.collect()
                mp.active_children()  # triggers cleanup
                for p in mp.active_children():
                    p.terminate()
                print("Active children terminated")
                idata = az.convert_to_inference_data(samples)
                print("Converted to inference data")
                #print(az.summary(idata, round_to=4))
                try:
                    rhat_all = az.rhat(idata)
                    valid_rhat = rhat_all.where(~np.isnan(rhat_all), drop=True)
                    rhat = valid_rhat.to_array().max().item()
                    neff = az.ess(idata).to_array().min().item()
                except Exception as e:
                    print(f"Error computing R-hat and Neff: {e}")
                    rhat = float('inf')
                    neff = 0
                    continue

                print(f"R-hat maximum: {rhat}")
                print(f"Neff minimum: {neff}")
                print(f"Num samples: {num_samples}")
                print(f"Warmup steps: {warmup_steps}")


    for key, true_value in true_params.items():
            estimated_value = torch.mean(samples[key])
            error = abs(estimated_value - true_value)/abs(true_value)
            print(f"Error in {key}: {error}")

    avg_error = np.mean([abs(torch.mean(samples[key]) - true_value)/abs(true_value) for key, true_value in true_params.items()])
    print(f"Average error: {avg_error}")

    return np.mean(time_list_VI), mean_error_VI, total_time, avg_error, rhat, neff, mean_time_degas, mean_error_degas


if __name__ == "__main__":
    #take argument name from command line
    if len(sys.argv) > 1:
        name = sys.argv[1]
    else:
        name = "all"

    print(f"Running optimization for program: {name}")
    if name == "all":
        #['bernoulli', 'burglary', 'clickgraph', 'clinicaltrial', 'grass', 
        programs = ['murdermistery', 'surveyunbiased', 'trueskills',
                    'twocoins', 'altermu', 'altermu2', 'normalmixtures', 'pid']
        for program in programs:
            print(f"Processing program: {program}")
            #process(program, all = True)
            time_VI, error_VI, time_mcmc, error_mcmc, rhat, neff, time_degas, error_degas = process(program, all=True)
            # open a file results_all.csv (if exists, otherwise create) and append the results
            with open("results_all.csv", "a") as f:
                f.write(f"{program},{time_VI},{error_VI},{time_mcmc},{error_mcmc},{rhat},{neff},{time_degas},{error_degas}\n")
    else:
        process(name)