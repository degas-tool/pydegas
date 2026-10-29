import torch
import numpy as np
from torch.distributions import MultivariateNormal

def compute_likelihood(output_dist, data_var_list, data):
    """ computes the likelihood of output_dist with respect to variables data_var_list sampled in data """

    data = torch.tensor(data)
    likelihood = 0
    # extract indexes of the variables in the data
    try:
        data_var_index = [output_dist.var_list.index(element) for element in data_var_list ]
    except ValueError:  # if the program doesn't have all the variables we are using for the likelihood
            return torch.tensor(-np.inf)
    except:
            raise
    for k in range(output_dist.gm.n_comp()):
        # extract the covariance matrix only for the variables in the data
        sigma = output_dist.gm.sigma[k][data_var_index][:, data_var_index]
        # first I consider the mu only for variables in the data
        mu = output_dist.gm.mu[k][data_var_index]
        # selects indices of delta (discrete) variables and non-delta (continuous) variables
        #deltas = np.where(np.diag(sigma) == 0)[0]
        #not_deltas = np.where(np.diag(sigma) != 0)[0]
        diag = torch.diag(sigma)

        # Indices where diagonal elements are zero or non-zero
        deltas = torch.where(diag == 0)[0]
        not_deltas = torch.where(diag != 0)[0]
        # saves means of delta and non-delta variables and covariance matrix of non-delta
        mu_delta = mu[deltas]
        mu_not_delta = mu[not_deltas]
        sigma_not_delta = sigma[not_deltas][:, not_deltas]
        # computes pdf of non-delta variables 
        if len(mu_not_delta) >= 1:  # if there is at least one continuous variable
            continuous_pdf = output_dist.gm.pi[k]*MultivariateNormal(mu_not_delta, sigma_not_delta).log_prob(data[:,not_deltas]).exp()
        else:
            continuous_pdf = output_dist.gm.pi[k]*torch.ones(len(data))
        # computes pmf of delta variables
        if len(mu_delta) >= 1:   # if there is at least one discrete variable
            discrete_pmf = torch.all((mu_delta == data[:, deltas]),dim=1)
        else:
            discrete_pmf = torch.ones(len(data))
        #except ValueError:  # if the covariance matrix is singular
        #    return torch.tensor(-np.inf)
        #except:
        #    raise
        likelihood += continuous_pdf*discrete_pmf # sums likelihood of every data over all components
    
    return torch.sum(torch.log(likelihood))/len(data)