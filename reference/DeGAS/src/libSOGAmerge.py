# Contains the functions for computing the resulting distribution when a merge is invoked according to the following dependencies.

# SOGA (defined in SOGA.py)
# |- merge
#     |- prune
#        |- classic_prune
#        |   |- compute_matrix_mean
#        |   |- dist
#        |   |- merge_comp
#        |- ranking_prune


from libSOGAshared import *


def merge(list_dist):
    """
    Given a list of couples (p,dist), where each dist is a Dist object, computes a couple (current_p, current_dist), in which current_pi is the sum of p and current_dist is a single GaussianMix object.
    """
    ## creates tensors for the new gm
    p_list = []
    pi_list = []
    mu_list = []
    sigma_list = []
    for (p, dist) in list_dist:
        if p < TOL_PROB:
            continue
        p_list.append(p)
        pi_list.append(dist.gm.pi)
        mu_list.append(dist.gm.mu)
        sigma_list.append(dist.gm.sigma)
    # if list is empty
    if len(p_list) == 0:
        return torch.tensor(0.), list_dist[0][1]
    # else
    p = torch.stack(p_list).view(-1,1,1)
    pi = torch.vstack([p[i]*pi_list[i] for i in range(len(p_list))])
    mu = torch.vstack(mu_list)
    sigma = torch.vstack(sigma_list)

    # normalizes weights
    current_p = torch.sum(p)
    if current_p > TOL_PROB:
        pi = pi/current_p
    else:
        current_p = torch.tensor(0.)

    # creates the new gm
    new_gm = GaussianMix(pi, mu, sigma)
    new_gm.delete_zeros()
    
    return current_p, Dist(list_dist[0][1].var_list, new_gm)


def prune(current_dist, pruning, Kmax):
    if pruning == 'classic':
        current_dist = classic_prune(current_dist, Kmax)
    elif pruning == 'ranking':
        current_dist = ranking_prune(current_dist, Kmax)
    elif pruning == 'kmeans':
        current_dist = kmeans_prune(current_dist, Kmax)
    return current_dist


def kmeans_prune(output_dist, Kmax):
    """ Partitions the mean vectors of output_dist using the k-means clustering algorithm and then substitutes each cluster with a single Gaussian component. """
    
    if output_dist.gm.n_comp() <= Kmax:
        return output_dist
    else:
        labels, _ = k_means(torch.clone(output_dist.gm.mu), Kmax)

        d = output_dist.gm.n_dim()

        # computes the new weights
        new_pis = torch.zeros(Kmax, 1)
        new_pis.scatter_add_(0, labels.view(-1, 1), output_dist.gm.pi)   # these are the weights of the new mixture
        normalized_pis = output_dist.gm.pi / new_pis[labels] # these are the weights normalized for each cluster

        # computes the new means
        weighted_mus = output_dist.gm.mu * normalized_pis
        new_mus = torch.zeros(Kmax, d)
        new_mus.scatter_add_(0, labels.view(-1, 1).expand(-1, d), weighted_mus)  # these are the means of the new mixture

        # computes the new covariances
        diff = output_dist.gm.mu - new_mus[labels]
        weighted_sigmas = normalized_pis.view(-1, 1, 1) * output_dist.gm.sigma + torch.einsum('bi,bj->bij', diff, diff) * normalized_pis.view(-1, 1, 1)
        new_sigmas = torch.zeros(Kmax, d, d)
        new_sigmas.scatter_add_(0, labels.view(-1, 1, 1).expand(-1, d, d), weighted_sigmas)

        return Dist(output_dist.var_list, GaussianMix(new_pis, new_mus, new_sigmas))


def k_means(points, k, max_iters=100, tol=1e-4):
    # Randomly initialize k cluster centers
    c, d = points.shape
    centers = points[torch.randperm(c)[:k]]

    for _ in range(max_iters):
        # Compute distances from points to centers
        distances = torch.cdist(points, centers)
        # Assign each point to the nearest center
        labels = torch.argmin(distances, dim=1)
        # Compute new centers as the mean of assigned points
        new_centers = torch.stack([points[labels == i].mean(dim=0) for i in range(k)])
        # Check for convergence
        if torch.all(torch.abs(new_centers - centers) < tol):
            break
        centers = new_centers

    return labels, centers


def ranking_prune(current_dist, Kmax):
    """ Keeps only the Kmax component with higher prob"""
    if current_dist.gm.n_comp() > Kmax:
        rank = torch.argsort(current_dist.gm.pi, dim=0, descending=True)
        current_dist.gm.pi = current_dist.gm.pi[rank].squeeze(1)[:Kmax]
        current_dist.gm.mu = current_dist.gm.mu[rank].squeeze(1)[:Kmax]
        current_dist.gm.sigma = current_dist.gm.sigma[rank].squeeze(1)[:Kmax]
        current_dist.gm.pi = current_dist.gm.pi/torch.sum(current_dist.gm.pi)
    return current_dist


def compute_matrix_mean(current_dist):
    pi = current_dist.gm.pi
    s = len(current_dist.gm.pi)
    pmu = pi.view(-1,1)*current_dist.gm.mu
    sums = pmu.unsqueeze(1) + pmu
    pis = (pi + pi.unsqueeze(1)).reshape(s,s,1)
    return sums/pis

def delete_indices(tensor, idx_list):
    """ Deletes elements from a tensor at the specified indices. """
    mask = torch.ones(tensor.size(0), dtype=torch.bool)
    mask[idx_list] = False  # Set the indices in idx_list to False
    return tensor[mask]


def merge_comp(current_dist, i, j, tot_mean):
    pii, pij = current_dist.gm.pi[i], current_dist.gm.pi[j]
    compi, compj = current_dist.gm.comp(i), current_dist.gm.comp(j)
    # deletes component to be merged from the current dist
    idx_list = [i,j]
    current_dist.gm.pi = delete_indices(current_dist.gm.pi, idx_list)
    current_dist.gm.mu = delete_indices(current_dist.gm.mu, idx_list)
    current_dist.gm.sigma = delete_indices(current_dist.gm.sigma, idx_list)
    # computes statistics of the merged component
    tot_p = pii + pij
    v = torch.stack([compi.mu[0], compj.mu[0]]) - tot_mean
    pi_pair = torch.vstack([pii/tot_p, pij/tot_p])
    sigma_pair = torch.stack([compi.sigma[0], compj.sigma[0]])
    tot_cov = (pi_pair.view(-1, 1, 1) * sigma_pair).sum(dim=0) + torch.mm(v.t(), pi_pair*v)
    # updates distribution
    current_dist.gm.pi = torch.cat((current_dist.gm.pi, tot_p.unsqueeze(0)))
    current_dist.gm.mu = torch.cat((current_dist.gm.mu, tot_mean.unsqueeze(0)))
    current_dist.gm.sigma = torch.cat((current_dist.gm.sigma, tot_cov.unsqueeze(0)))
    return current_dist
        
def classic_prune(current_dist, Kmax):
    """ Merges components with optimal cost 
        cost(i, j) = pi_i * || mu_i - weighted_sum_ij ||^2 + pi_j * || mu_j - weighted_sum_ij ||^2
        until the number of components is less than Kmax. """
    
    if current_dist.gm.n_comp() > Kmax:
        n = current_dist.gm.n_comp()

        # Computes the cost matrix
        matrix_mu = compute_matrix_mean(current_dist)     # elem (i,j) is the weighted sum of mu_i and mu_j
        dist_matrix = torch.sum(torch.pow((current_dist.gm.mu - matrix_mu), 2), axis=2).T   # elem (i,j) is the distance between mu_i and the weighted sum of mu_i and mu_j
        weight_dist_matrix = current_dist.gm.pi.view(-1,1)*dist_matrix   # row i is pi_i * || mu_i - weighted_sum_ij ||^2
        cost_matrix = weight_dist_matrix + weight_dist_matrix.T          # elem (i,j) is the cost of merging i and j
       
        while n > Kmax:
            # Computes indices of components with minimal cost
            i_indices, j_indices = torch.triu_indices(cost_matrix.size(0), cost_matrix.size(1), offset=1)
            upper_triangular_values = cost_matrix[i_indices, j_indices]
            min_index = torch.argmin(upper_triangular_values)
            i, j = i_indices[min_index].item(), j_indices[min_index].item()  
            # Merges components
            current_dist = merge_comp(current_dist, i, j, matrix_mu[i,j])
            # Updates n and matrix_mu
            n = current_dist.gm.n_comp()
            matrix_mu = compute_matrix_mean(current_dist)
            # Deletes the row and column of the merged components from the cost matrix
            mask = torch.ones(cost_matrix.size(0), dtype=torch.bool)
            mask[[i,j]] = False  # Set the indices to remove as False
            cost_matrix = cost_matrix[mask][:, mask]
            # If number of components still too high adds a new row and column to the cost matrix, corresponding to the new component
            if n > Kmax:
                # computes the costs for the newly added component
                new_cost = torch.sum(torch.pow((current_dist.gm.mu[-1].unsqueeze(0) - matrix_mu[:, -1]), 2), axis = 1).unsqueeze(0)
                new_column = new_cost[:, :-1].T  
                new_row = new_cost  
                cost_matrix = torch.cat((cost_matrix, new_column), dim=1)
                cost_matrix = torch.cat((cost_matrix, new_row), dim=0)
    return current_dist

