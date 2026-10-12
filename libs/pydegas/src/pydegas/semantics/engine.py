"""SOGA execution engine."""

from __future__ import annotations

import logging
from typing import Any

import torch

import pydegas.cfg.nodes as nodes
from pydegas.cfg.graph import ControlFlowGraph
from pydegas.cfg.smoother import negate
from pydegas.exceptions import InvalidConstraintError, ModelConstructionError
from pydegas.mixtures.constants import EPS, TOL_PROB
from pydegas.mixtures.distribution import Dist
from pydegas.mixtures.gaussian_mix import GaussianMix
from pydegas.semantics.merge import merge, prune
from pydegas.semantics.truncate import truncate
from pydegas.semantics.update import update_rule


logger = logging.getLogger(__name__)


def update_child(
    child: nodes.CFGNode,
    dist: Dist,
    p: torch.Tensor,
    trunc: str | None,
    exec_queue: list[nodes.CFGNode],
) -> None:
    if isinstance(child, nodes.MergeNode | nodes.ExitNode):
        child.list_dist.append((p, dist))
    else:
        child.dist = dist
        child.p = p
        child.trunc = trunc
    if child not in exec_queue:
        exec_queue.append(child)


def start_soga(
    cfg: ControlFlowGraph,
    params_dict: dict[str, torch.Tensor] | None = None,
    pruning: str = "classic",
    Kmax: int | None = None,
    parallel: int | None = None,
) -> Dist:
    """
    Invokes SOGA on the root of the CFG object cfg, initializing current_distribution to a Dirac delta centered in zero.
    If pruning='classic' implements pruning at the merge nodes with maximum number of component Kmax.
    """
    if params_dict is None:
        params_dict = {}

    # initializes current_dist
    var_list = cfg.ID_list
    data = cfg.data
    n_dim = len(var_list)
    gm = GaussianMix(
        torch.tensor([[1.0]]),
        torch.zeros((1, n_dim)),
        EPS * torch.eye(n_dim).reshape(1, n_dim, n_dim),
    )
    init_dist = Dist(var_list, gm)
    cfg.root.dist = init_dist

    # initializes visit queue
    exec_queue: list[nodes.CFGNode] = [cfg.root]

    # executes SOGA on nodes on exec_queue
    while len(exec_queue) > 0:
        soga(exec_queue.pop(0), data, parallel, pruning, exec_queue, params_dict, Kmax)

    # returns output distribution
    exit_node = cfg.node_list["exit"]
    if not isinstance(exit_node, nodes.ExitNode):
        logger.error("CFG exit node has unexpected type: %s", type(exit_node).__name__)
        raise ModelConstructionError("CFG exit node has unexpected type")
    _p, current_dist = merge(exit_node.list_dist)
    exit_node.list_dist = []
    return current_dist


def soga(
    node: nodes.CFGNode,
    data: dict[str, Any],
    parallel: int | None,
    pruning: str,
    exec_queue: list[nodes.CFGNode],
    params_dict: dict[str, torch.Tensor],
    Kmax: int | None = None,
) -> None:
    current_dist: Dist
    current_p: torch.Tensor
    current_trunc: str | None

    if not isinstance(node, nodes.MergeNode | nodes.ExitNode):
        if node.dist is None:
            logger.error("Node %s has no distribution before execution", node.name)
            raise ModelConstructionError(f"Node {node.name} has no distribution before execution")
        current_dist = node.dist
        current_p = torch.as_tensor(node.p)
        current_trunc = node.trunc

    # starts execution
    if isinstance(node, nodes.EntryNode):
        if node.dist is None:
            logger.error("Entry node has no initial distribution")
            raise ModelConstructionError("Entry node has no initial distribution")
        update_child(node.children[0], node.dist, torch.tensor(1.0), None, exec_queue)

    # if tests saves LBC and calls on children
    if isinstance(node, nodes.TestNode):
        if node.smooth:
            current_trunc = node.smooth
        else:
            current_trunc = node.LBC
        if current_trunc is None:
            logger.error("Test node %s has no truncation condition", node.name)
            raise ModelConstructionError(f"Test node {node.name} has no truncation condition")
        if "==" in current_trunc or "!=" in current_trunc:
            logger.error("Degeneracy in if condition detected at node %s. Please smooth the program.", node.name)
            raise InvalidConstraintError("Degeneracy in if condition detected. Please smooth the program.")

        for child in node.children:
            update_child(child, current_dist, current_p, current_trunc, exec_queue)

    # if loop saves checks the condition and decides which child node must be accessed
    if isinstance(node, nodes.LoopNode):
        if node.idx is None:
            logger.error("Loop node %s has no loop index", node.name)
            raise ModelConstructionError(f"Loop node {node.name} has no loop index")
        # the first time is accessed set the value of the counter to 0 and converts node.const into a number
        if data[node.idx][0] is None:
            data[node.idx][0] = torch.tensor(0.0)
        if type(node.const) is str:
            if "[" in node.const:
                data_name, data_idx_raw = node.const.split("[")
                data_idx_raw = data_idx_raw[:-1]
                # data_idx is a data
                if data_idx_raw in data:
                    data_idx = int(data[data_idx_raw][0])
                # data_idx is a number
                else:
                    data_idx = int(data_idx_raw)
                node.const = torch.tensor(int(data[data_name][data_idx]))
            else:
                node.const = torch.tensor(int(node.const))

        if node.const is None:
            logger.error("Loop node %s has no loop bound", node.name)
            raise ModelConstructionError(f"Loop node {node.name} has no loop bound")
        # successively checks the condition and decides which child node must be accessed
        if data[node.idx][0] < node.const:
            for child in node.children:
                if isinstance(child, nodes.StateNode) and child.cond is True:
                    update_child(child, current_dist, current_p, current_trunc, exec_queue)
        else:
            data[node.idx][0] = None
            for child in node.children:
                if isinstance(child, nodes.StateNode) and child.cond is False:
                    update_child(child, current_dist, current_p, current_trunc, exec_queue)

    # if state checks wheter cond!=None. If yes, truncates to current_trunc, eventually negating it. In any case applies the rule in expr. Appends the distribution in the next merge node or calls recursively on children. If child is loop node increments its idx.
    if isinstance(node, nodes.StateNode):
        if node.cond is not None and current_trunc is not None:
            if node.cond is False:
                current_trunc = negate(current_trunc)
            p, current_dist = truncate(current_dist, current_trunc, data, params_dict)
            current_trunc = None
            current_p = p * current_p

        if node.smooth:
            expr: str | None = node.smooth
        else:
            expr = node.expr
        if expr is None:
            logger.error("State node %s has no assignment expression", node.name)
            raise ModelConstructionError(f"State node {node.name} has no assignment expression")
        if current_p > TOL_PROB:
            current_dist = update_rule(current_dist, expr, data, params_dict)

        # updating child
        child = node.children[0]
        if isinstance(child, nodes.LoopNode):
            if child.idx is None:
                logger.error("Loop child %s has no loop index", child.name)
                raise ModelConstructionError(f"Loop child {child.name} has no loop index")
            if data[child.idx][0] is not None:
                data[child.idx][0] += 1
        update_child(child, current_dist, current_p, current_trunc, exec_queue)

    # if observe truncates to LBC and calls on children
    if isinstance(node, nodes.ObserveNode):
        if node.smooth:
            current_trunc = node.smooth
        else:
            current_trunc = node.LBC
        if current_trunc is None:
            logger.error("Observe node %s has no truncation condition", node.name)
            raise ModelConstructionError(f"Observe node {node.name} has no truncation condition")
        p, current_dist = truncate(current_dist, current_trunc, data, params_dict)
        current_trunc = None
        if p < TOL_PROB:
            logger.error("Conditioning to zero probability event at observe node %s", node.name)
        child = node.children[0]
        update_child(child, current_dist, current_p, current_trunc, exec_queue)

    # if merge checks whether all paths have been explored.
    # Either returns or merge distributions and calls on children
    if isinstance(node, nodes.MergeNode):
        if len(node.list_dist) != len(node.parent):
            return
        current_p, current_dist = merge(node.list_dist)
        node.list_dist = []
        if Kmax is not None:
            current_dist = prune(current_dist, pruning, Kmax)
        child = node.children[0]
        update_child(child, current_dist, current_p, None, exec_queue)

    if isinstance(node, nodes.ExitNode):
        return

    if isinstance(node, nodes.PruneNode):
        if node.dist is None:
            logger.error("Prune node %s has no distribution before execution", node.name)
            raise ModelConstructionError(f"Prune node {node.name} has no distribution before execution")
        current_dist = node.dist
        current_p = torch.as_tensor(node.p)
        current_trunc = node.trunc
        kmax = node.Kmax if node.Kmax is not None else Kmax
        if kmax is None:
            logger.error("Prune node %s has no Kmax value", node.name)
            raise ModelConstructionError(f"Prune node {node.name} has no Kmax value")
        current_dist = prune(current_dist, pruning, kmax)
        child = node.children[0]
        update_child(child, current_dist, current_p, current_trunc, exec_queue)
