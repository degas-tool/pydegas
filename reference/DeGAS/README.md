# DeGAS

DeGAS (Differentiable Gaussian Approximate Semantics) is a tool that allows optimizing parameters of probabilistic programs using torch's gradient-based optimization without resorting to sampling.

To use DeGAS in Python you need to import the module `optimization` from src.

Then you will need to perform the following steps:

- write a program using the SOGA syntax and compile it to a smooth CFG;

- initialize the parameters;

- specify a loss to be minimized;

- run an optimization loop, as usually done in gradient-based optimization.

An example of the complete pipeline can be found in the notebook `src/Thermostat.ipynb`.

Below we detail every step and what are the available function in the `optimization` module.

## Writing and compiling a program

To use DeGAS your model must be written in the SOGA syntax. You can find examples of programs written in this syntax in `programs/SOGA/Optimization`. Here we give a short recap of the accepted syntax.

#### Data

At the beginning of your file you can declare data. These are arrays that can be accessed but cannot be overwritten by the program. To declare data use the keyword `data` before declaring an array. For example:
`data obs = [0., 1., 0., 0., 1.];`

can be accessed at any point of the program using `obs[i]` where `i` is an integer index (indexing starts from 0).

NOTE: currently the SOGA syntax does not support index arithmetic. Arrays and data can only be accessed using a single variable or a number, not expressions such as `i+1`. 

#### Instructions

The SOGA syntax accepted by DeGAS supports 4 types of instruction: assignments, conditionals, loops and observe.

In the following:

-  `var` is any variable name. You do not need to declare scalar variables in advance, as DeGAS infers them automatically when parsing the program. For array variables declare `array[size] var` before using the array, for example `array[10] y;`. Array values are accessed using the usual notation `var[i]` where `i` is an integer index ;  

-  `const` is either a constant (i.e. a number), a data value or a parameter;

-  `dist` is a distribution. In SOGA all distributions are approximated by Gaussian Mixtures, which are declared as `gm(pi_list, mu_list, sigma_list)` where `pi_list` is a list of scalar weights summing to 1, `mu_list` is a list of scalar means and `sigma_list` is a list of scalar standard deviations. For example a standard normal distribution can be assigned using `gm([1.], [0.], [1.])` or the shortcut `gauss(0,1)`. Supported primitives for assigning distributions are: `gauss(mu, sigma)`, `bernoulli(p)`, `uniform([a,b], C)`, `beta([a,b], C)`, `laplace(mu, sigma, C)`, `exprnd(lambda, C)` where `C` is the number of components of the approximating mixture and `mu`, `sigma`, `a`, `b`, `lambda` are distribution-specific parameters.

-  `block` is any sequence of instructions.

* Assignments assign a program variable with a value. An assignment can be either be linear or non-linear. A linear assignment has the form

`var_name = const + const*var + ... + const*var;`

A non-linear assignment has the form:

` var_name = const*var*var; `

At the R.H.S. of an assignment `var` can also be a distribution `dist`. To assign more complex expressions use subsequent assignments. For example:

`z = x + y + 1;`
`z = x*z;`

* Conditionals are expressed by if-then-else statements. The main structure is:

` if bexpr { block } else { block } end if;`

Here `bexpr` is a Boolean expression of the form:

`var (< | <= | >=| > ) const`.

* Loops are expressed by *bounded* for statement. The main structure is:

`for var in range(const) { block } end for;`

For example:

`for i in range(10) { x = obs[i]; } end for;`

* Observe are expressed as

`observe(bexpr)` where `bexpr` is as in the conditional statement.

#### Parameters

In DeGAS some constants appearing in the programs can be left as unspecified parameters to be optimized. In this case instead of using a contant value the user can use the syntax `_par` where `par` is a parameter name properly initialized (see below).

Examples of parameter usage are:

*  `x = gm([1.], [_mu], [_sigma]);`, which defines a Gaussian with parametric mean and std;

*  `x = _a * y + _b;`, which assigns `x` as a linear function of `y` with parametric slope and intercept.

#### Compiling a program to a smooth CFG

To compile the program to a CFG object the following instructions must be used:
 
```
compiledFile = compile2SOGA('path_to_file.soga')
cfg = produce_cfg(compiledFile)
smooth_cfg(cfg)
```

After these instructions the object cfg will represents a smoothed program. The cfg can be explored using the dictionary `cfg.node_list`.

## Parameters initialization

If the programs containg unspecified parameters (i.e. terms `_par`), they need to be initialized.

The initialization is specified through a dictionary in the following form:

``` params_dict = { "par1" : torch.tensor(v1, requires_grad = True), ...} ```

The module `optimization` contains the function `initialize_params` that takes as input a dictionary `{"par1":v1, ...}` and transforms it into a dictionary in the above form, suitable for DeGAS optimization.

## Loss declaration

For performing optimization you must specify the loss to be minimized.

A loss is function taking as input an object Dist representing a Gaussian Mixture distribution and returning a scalar value. However, it can depend on different arguments.  

For example, the module `optimization` contains the loss `neg_log_likelihhod` defined as

```
def neg_log_likelihood(traj_set, dist, idx):
	log_likelihood = torch.log(dist.gm.marg_pdf(traj_set[:, idx], idx))
	return - torch.sum(log_likelihood)
```

The function depends on a set of trajectories, a distribution and a set of indices. It can be used to define a proper loss function by declaring:

```
loss_func = lambda dist : neg_log_likelihood(traj_set, dist, idx)
```

In the module `optimization` other functions for loss definition are available such as the `L2_distance` function and the `signal_error` function.

  

### Running the optimization loop

The actual optimization is performed by the function `optimize` from the `optimization` module.

The function takes as input a CFG object, a dictionary containing initialized parameters and a loss function. It creates an gradient-descent loop using the torch optimizer Adam.

As an alternative, the user can define its own optimization loop as standard in gradient-descent optimization. For example the following code is equivalent to invoking the function `optimize` with a user-defined stopping criterion.

```
# creates the optimizer, passing the parameters of the program as the parameters to optimize
optimizer = torch.optim.Adam([params_dict[key] for key in params_dict.keys()], lr=lr)

for i in range(n_steps):
	optimizer.zero_grad() # Reset gradients
	
	# loss computation
	current_dist = start_SOGA(cfg, params_dict) # computes the output distribution for the current values of the parameters stored in params_dict
	loss = loss_func(current_dist) # computes loss using a user-defined loss function

	# checks user-defined stopping criterion
	if stopping_criterion(loss):
		break
		
	# backpropagates
	loss.backward()

	# updates parameters
	optimizer.step()
```