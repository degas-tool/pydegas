"""
This module implements the CFG smoothing pass.
"""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING

import pydegas.cfg.nodes as _nodes
from pydegas.mixtures.constants import SMOOTH_EPS


if TYPE_CHECKING:
    from pydegas.cfg.graph import ControlFlowGraph


logger = logging.getLogger(__name__)


def negate(trunc: str) -> str:
    """Return the logical negation of a condition string.

    Handles compound conditions joined by ``and`` / ``or`` recursively and
    flips relational operators for atomic predicates.
    """
    if " and " in trunc:
        t1, t2 = trunc.split(" and ", 1)
        return negate(t1) + " or " + negate(t2)
    if " or " in trunc:
        t1, t2 = trunc.split(" or ", 1)
        return negate(t2) + " and " + negate(t1)
    for old, new in [("<=", ">"), (">=", "<"), ("<", ">="), (">", "<="), ("==", "!="), ("!=", "==")]:
        if old in trunc:
            return trunc.replace(old, new, 1)
    return trunc


def _extract_var_and_index(expression: str) -> tuple[str, str] | tuple[str, None]:
    """Parse ``var[idx]`` -> ``(var, idx)``, or ``var`` -> ``(var, None)``."""
    match = re.match(r"(\w+)\[(\w+)\]", expression)
    if match:
        return match.group(1), match.group(2)
    return expression, None


def _extract_variables(expression: str) -> list[str]:
    """Return identifiers found in *expression*, excluding bare numbers."""
    pattern = r"\b[a-zA-Z_]\w*\([^)]*\)|\b[a-zA-Z_]\w*\[[^\]]*\]|\b[a-zA-Z_]\w*\b"
    return [m for m in re.findall(pattern, expression) if not re.match(r"^\d+$", m)]


def _extract_lists(gm_string: str) -> list[str]:
    """Return the three bracket-delimited lists from a ``gm(...)`` string."""
    return re.findall(r"\[[^\]]*\]", gm_string)


def _format_float_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _expr_is_prod(expr: str, variables: list[str]) -> bool:
    """Return True if *expr* is a product of exactly two variables."""
    if len(variables) != 2:
        return False
    v1, v2 = variables
    expr_clean = expr.replace(" ", "")
    return f"{v1}*{v2}" in expr_clean or f"{v2}*{v1}" in expr_clean


def _smooth_gm_term(gm_term: str, full_expr: str, eps: float) -> str:
    """Replace zero-std components in *gm_term* with eps, return updated *full_expr*."""
    weights, mean, stds_bracket = _extract_lists(gm_term)
    stds = stds_bracket.strip("[]").split(",")
    for i, std in enumerate(stds):
        std = std.strip()
        if "_" not in std and eval(std) == 0:  # noqa: S307
            stds[i] = f"{float(eps):.10f}"
    new_gm = f"gm({weights}, {mean}, {_format_float_list(stds)})"
    return full_expr.replace(gm_term, new_gm)


def _update_smoothed_vars(
    smoothed_vars: list[str],
    var_name: str,
    idx: str | None,
    var_list: list[str],
    data: dict,
) -> list[str]:
    """Record which variables have been smoothed."""
    if idx is None:
        if var_name not in smoothed_vars:
            smoothed_vars.append(var_name)
    elif idx in data:
        for var in var_list:
            if var.startswith(var_name) and "[" in var[len(var_name) :]:
                if var not in smoothed_vars:
                    smoothed_vars.append(var)
    else:
        target = f"{var_name}[{idx}]"
        if target not in smoothed_vars:
            smoothed_vars.append(target)
    return smoothed_vars


def _smooth_assignment(
    node: _nodes.StateNode,
    var_list: list[str],
    smoothed_vars: list[str],
    data: dict,
    eps: float,
) -> None:
    """Compute the smoothed expression for *node* and write it to ``node.smooth``."""
    orig_expr = node.expr
    if orig_expr is None or orig_expr == "skip":
        return

    lhs, rhs = orig_expr.replace(" ", "").split("=", 1)
    target_var = lhs
    var_name, idx = _extract_var_and_index(target_var)

    variables = _extract_variables(rhs)
    gm_vars = [v for v in variables if "gm(" in v]

    new_expr: str | None = None

    # Case 1 - constant assignment (no variables at all)
    if not variables:
        new_expr = orig_expr + f"+ gm([1.], [0.], [{eps:.10f}])"
        smoothed_vars = _update_smoothed_vars(smoothed_vars, var_name, idx, var_list, data)

    # Case 2 - contains a degenerate gm term (zero std)
    if variables and gm_vars:
        for gm_term in gm_vars:
            _, _, stds_bracket = _extract_lists(gm_term)
            stds = stds_bracket.strip("[]").split(",")
            for std in stds:
                std = std.strip()
                if "_" not in std and eval(std) == 0:  # noqa: S307
                    new_expr = _smooth_gm_term(gm_term, orig_expr, eps)
                    smoothed_vars = _update_smoothed_vars(smoothed_vars, var_name, idx, var_list, data)

    # Case 3 - deterministic function of other variables (no gm term)
    if variables and not gm_vars:
        if not _expr_is_prod(orig_expr, variables) and target_var not in variables:
            new_expr = orig_expr + f"+ gm([1.], [0.], [{eps:.10f}])"

    if new_expr:
        logger.debug("smooth assignment %s  ->  %s", node.name, new_expr)
        node.smooth = new_expr


def _smooth_truncation(
    trunc: str,
    node: _nodes.TestNode | _nodes.ObserveNode,
    smoothed_vars: list[str],
    eps: float,
) -> str:
    """Relax a strict condition string when the involved variable has been smoothed."""
    for ops in ("==", "!=", "<=", ">=", "<", ">"):
        if ops in trunc:
            break
    else:
        return trunc

    target_var, target_val = trunc.split(ops, 1)
    if target_var.strip() not in smoothed_vars:
        return trunc

    delta = 5 * math.sqrt(eps)
    tv, val = target_var, target_val

    match ops:
        case "==":
            new_trunc = f"{tv} > {val} - {delta:.10f} and {tv} < {val} + {delta:.10f}"
        case "!=":
            new_trunc = f"{tv} < {val} - {delta:.10f} or {tv} > {val} + {delta:.10f}"
        case "<=":
            new_trunc = f"{tv} <= {val} + {delta:.10f}"
        case "<":
            new_trunc = f"{tv} < {val} - {delta:.10f}"
        case ">=":
            new_trunc = f"{tv} >= {val} - {delta:.10f}"
        case ">":
            new_trunc = f"{tv} > {val} + {delta:.10f}"
        case _:
            return trunc

    logger.debug("smooth truncation %s  ->  %s", node.name, new_trunc)
    node.smooth = new_trunc
    return new_trunc


def _visit(
    node: _nodes.CFGNode,
    var_list: list[str],
    smoothed_vars: list[str],
    data: dict,
    exec_queue: list[_nodes.CFGNode],
    eps: float,
) -> None:
    """Process one node and enqueue its successors."""
    if isinstance(node, _nodes.EntryNode):
        for child in node.children:
            if child not in exec_queue:
                exec_queue.append(child)

    elif isinstance(node, _nodes.TestNode):
        current_trunc = _smooth_truncation(node.LBC or "", node, smoothed_vars, eps)
        for child in node.children:
            if child not in exec_queue:
                child.trunc = current_trunc
                exec_queue.append(child)

    elif isinstance(node, _nodes.LoopNode):
        if not node.smooth:  # False on first visit, True thereafter
            node.smooth = True
            for child in node.children:
                if child not in exec_queue:
                    exec_queue.append(child)
        # second visit -> skip (loop body already smoothed)

    elif isinstance(node, _nodes.StateNode):
        if node.cond is False and node.trunc is not None:
            node.trunc = negate(node.trunc)
        _smooth_assignment(node, var_list, smoothed_vars, data, eps)
        for child in node.children:
            if child not in exec_queue:
                exec_queue.append(child)

    elif isinstance(node, _nodes.ObserveNode):
        current_trunc = _smooth_truncation(node.LBC or "", node, smoothed_vars, eps)
        for child in node.children:
            if child not in exec_queue:
                exec_queue.append(child)

    elif isinstance(node, (_nodes.MergeNode, _nodes.PruneNode)):
        for child in node.children:
            if child not in exec_queue:
                exec_queue.append(child)

    # ExitNode - nothing to do


def smooth(cfg: ControlFlowGraph, smooth_eps: float = SMOOTH_EPS) -> None:
    """Annotate cfg in-place with smoothed expressions.

    Traverses the CFG in the same queue-based order as the SOGA execution
    and writes node.smooth on nodes where the original expression or
    condition would cause degeneracy.
    """
    logger.debug("smoothing CFG  eps=%.2e  vars=%s", smooth_eps, cfg.ID_list)
    exec_queue: list = [cfg.root]
    while exec_queue:
        _visit(exec_queue.pop(0), cfg.ID_list, cfg.smoothed_vars, cfg.data, exec_queue, smooth_eps)
    logger.debug("smoothing done  smoothed_vars=%s", cfg.smoothed_vars)
