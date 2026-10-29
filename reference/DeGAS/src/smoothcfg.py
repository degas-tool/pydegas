# The smoother traverses the cfg in the same fashion as SOGA but without computing any distribution. 
# It only corrects instructions that would cause degeneracy using a smoothing input parameter smooth_eps.
# Loops are checked only once.

from libSOGAtruncate import negate
import re
import numpy as np

# FUNCTIONS FOR STRING PARSING

def extract_var_and_index(expression):
    """     Extracts the variable name and index from a string like 'data[i]'. """
    # Define the regular expression pattern
    pattern = r'(\w+)\[(\w+)\]'
    
    # Use re.match to find the variable name and index
    match = re.match(pattern, expression)
    
    if match:
        var_name = match.group(1)
        index = match.group(2)
        return var_name, index

    
def extract_variables(expression):
    """ Extracts variable names from an expression string. """
    # Pattern for finding variables
    pattern = r'\b[a-zA-Z_]\w*\([^)]*\)|\b[a-zA-Z_]\w*\[[^]]*\]|\b[a-zA-Z_]\w*\b'
    # Finding pattern occurences
    matches = re.findall(pattern, expression)
    # Filter numbers out
    variables = [match for match in matches if not re.match(r'^\d+$', match)]
    return variables


def extract_lists(gm_string):
    """ Extracts the lists of parameters from a gm string. """
    # Pattern for lists
    pattern = r'\[[^\]]*\]'
    # Finding pattern occurrences
    matches = re.findall(pattern, gm_string)
    return matches


def format_float_list(string_list):
    """ Formats a list of floats to avoid scientific notation. """
    formatted_list = '['
    for var_string in string_list:
        formatted_list += var_string + ', '
    formatted_list = formatted_list[:-2] +']'
    return formatted_list


def expr_is_prod(expr, vars):
    """ Returns True if the expression is a product of two variables. """
    expr = expr.replace(' ', '')
    if len(vars) == 2:
        var1, var2 = vars
        if '{}*{}'.format(var1,var2) in expr or '{}*{}'.format(var2,var1) in expr:
            return True 
        else:
            return False
    else:
        return False

# SMOOTHING FUNCTION

def smooth_asgmt_gm(var, expr, eps):
    """ var is a term 'gm([], [], [])'. Adds gaussian noise to components with 0 std. """
    weights, mean, stds = extract_lists(var)
    stds = stds.strip('[]').split(',')  # the problem is that one ore more stds could be a parameter
    for i, std in enumerate(stds):
        if not '_' in std and eval(std) == 0:
            stds[i] = f'{float(eps):.10f}'
    stds = format_float_list(stds)
    expr = expr.replace(var, 'gm({}, {}, {})'.format(weights, mean, stds))
    return expr

    
def update_smoothed_vars(smoothed_vars, var_name, idx, var_list, data):
    """ Updates the list of smoothed variables. """
    if idx is None:   # var_name is a variable
        if var_name not in smoothed_vars:
            smoothed_vars.append(var_name)
    elif idx in data.keys(): # var_name is of type var_name[index_name] all variable var_name are smoothed
        for var in var_list:
            if var.startswith(var_name) and '[' in var[len(var_name):]:   
                if var not in smoothed_vars:
                    smoothed_vars.append(var)
    else: # var_name is of type var_name[index] only var_name[index] is smoothed
        target = var_name + '[' + idx + ']'
        if target not in smoothed_vars:
            smoothed_vars.append(target)
    return smoothed_vars               


def smooth_asgmt(node, var_list, smoothed_vars, data, smooth_eps):
    """ Smooths an assignment statement. There are three cases in which the assignment is smoothed:
    1. The assignment is a constant assignment (no variables).
    2. The assignment contains degenerate gm variables.
    3. The assignment is a deterministic function of the other variables (no gm variables)."""
    
    orig_expr = node.expr

    if orig_expr == 'skip':
        return

    lhs, rhs = orig_expr.replace(' ', '').split('=')
    # which variable is being smoothed?
    target_var = lhs
    if '[' in target_var:
        var_name, idx = extract_var_and_index(target_var)
    else:
        var_name = target_var
        idx = None
    # which variables are in the expression?
    vars = extract_variables(rhs)
    gm_vars = [var for var in vars if 'gm(' in var]

    new_orig_expr = None

    # CASE 1: constant assignment (no variables)
    if len(vars) == 0:
        new_orig_expr = orig_expr + '+ gm([1.], [0.], [{:.10f}])'.format(smooth_eps)
        smoothed_vars = update_smoothed_vars(smoothed_vars, var_name, idx, var_list, data)
    # CASE 2: degenerate gm vars 
    if len(vars) > 0 and len(gm_vars) > 0:
        for gm in gm_vars:                         # only smooths if gm is degenerate
            _, _, stds = extract_lists(gm)
            stds = stds.strip('[]').split(',') 
            for std in stds:
                if not '_' in std and eval(std) == 0:     # stds can be parameters
                    new_orig_expr = smooth_asgmt_gm(gm, orig_expr, smooth_eps)
                    smoothed_vars = update_smoothed_vars(smoothed_vars, var_name, idx, var_list, data)
    # CASE 3: variables deterministically determined by the others (no gm_vars)
    if len(vars) > 0 and len(gm_vars) == 0:
        if not expr_is_prod(orig_expr, vars) and not target_var in vars: # if the expression is not a product of two variables and the target variable is not in the expression
            new_orig_expr = orig_expr + '+ gm([1.], [0.], [{:.10f}])'.format(smooth_eps)
            #smoothed_vars = update_smoothed_vars(smoothed_vars, var_name, idx, var_list, data)
    
    if new_orig_expr:
        node.smooth = new_orig_expr


# FUNCTIONS FOR SMOOTHING TRUNCATIONS

def smooth_trunc(trunc, node, smoothed_vars, smooth_eps):
    """ trunc is a truncation var ('<'|'<='|'=='|'!='|'>='|'>') val.
    WARNING: the lhs must be a single variable (TO DO: deal with linear expressions at the l.h.s.).
    This functions transforms the conditions:
    > var == val -> var > val - delta and var < val + delta
    > var != val -> var < val - delta or var > val + delta
    > var <= val -> var < val + delta
    > var < val -> var < val - delta
    > var >= val -> var > val - delta
    > var > val -> var > val + delta
    where delta is selected by the function select_delta, depending on the current distribution"""
    
    if '==' in trunc:
        ops = '=='
    elif '!=' in trunc:
        ops = '!='
    elif '<=' in trunc:
        ops = '<='
    elif '<' in trunc:
        ops = '<'
    elif '>=' in trunc:
        ops = '>='
    elif '>' in trunc:
        ops = '>'
        
    # check if the target variable has been smoothed
    target_var, target_val = trunc.split(ops)
    if not target_var.replace(' ', '') in smoothed_vars:
        return trunc 
        
    # currently selects delta as a constant function of epsilon. TO DO: make it a function of the distribution.
    delta = 5*np.sqrt(smooth_eps)   # maybe this should not be linear in smooth_eps (see Continualization)

    if ops == '==':
        new_trunc = '{} > {} - {:.10f} and {} < {} + {:.10f}'.format(target_var, target_val, delta, target_var, target_val, delta)
    elif ops == '!=':
        new_trunc = '{} < {} - {:.10f} or {} > {} + {:.10f}'.format(target_var, target_val, delta, target_var, target_val, delta)
    elif ops == '<=':
        new_trunc = '{} {} {} + {:.10f}'.format(target_var, ops, target_val, delta)
    elif ops == '<':
        new_trunc = '{} {} {} - {:.10f}'.format(target_var, ops, target_val, delta)
    elif ops == '>=':
        new_trunc = '{} {} {} - {:.10f}'.format(target_var, ops, target_val, delta)
    elif ops == '>':
        new_trunc = '{} {} {} + {:.10f}'.format(target_var, ops, target_val, delta)
    
    node.smooth = new_trunc
    
    return new_trunc    


# SMOOTHER FUNCTIONS ACTING ON THE CFG

def smooth_cfg(cfg, params_dict={}, pruning=None, Kmax=None, parallel=None, smooth_eps=1e-3):
    """ Invokes Smoother on the cfg using a queue for scheduling next node visit."""

    var_list = cfg.ID_list
    data = cfg.data
    smoothed_vars = cfg.smoothed_vars
    
    # initializes visit queue
    exec_queue = [cfg.root]
    
    # executes SOGA on nodes on exec_queue
    while(len(exec_queue)>0):
        smoother(exec_queue.pop(0), var_list, smoothed_vars, data, parallel, exec_queue, params_dict, smooth_eps)



def smoother(node, var_list, smoothed_vars, data, parallel, exec_queue, params_dict, smooth_eps):

    """ Smoother traverses the cfg in the same fashion as SOGA and corrects tests, observe and state nodes that may cause degeneracy.
    The corrected truncations and assignmets are saved in the node.smooth attribute. """

    #print('Entering', node)
    #print('\n')


    if node.type == 'entry':
        child = node.children[0]
        if child not in exec_queue:
            exec_queue.append(child)
            

    if node.type == 'test':
        current_trunc = node.LBC
        current_trunc = smooth_trunc(current_trunc, node, smoothed_vars, smooth_eps)
        for child in node.children:
            if child not in exec_queue:
                child.set_trunc(current_trunc)
                exec_queue.append(child)
            

    if node.type == 'loop':
        if node.smooth is False: # first time is accessed
            node.smooth = True
            for child in node.children:
                if child not in exec_queue:
                    exec_queue.append(child)
        else: # second time is accessed
            return


    if node.type == 'state':
        if node.cond != None and not node.trunc is None:
            if node.cond == False:
                current_trunc = negate(node.trunc)       ### see libSOGAtruncate
        smooth_asgmt(node, var_list, smoothed_vars, data, smooth_eps)
        child = node.children[0]
        if child not in exec_queue:
            exec_queue.append(child)
        
    
    if node.type == 'observe':
        current_trunc = node.LBC
        current_trunc = smooth_trunc(current_trunc, node, smoothed_vars, smooth_eps)       
        child = node.children[0]
        if child not in exec_queue:
            exec_queue.append(child)


    if node.type == 'merge':
        for child in node.children:
            if child not in exec_queue:
                exec_queue.append(child)
                
                
    if node.type == 'exit':
        return
    

    if node.type == 'prune':
        for child in node.children:
            if child not in exec_queue:
                exec_queue.append(child)