from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field
from typing import Any, ClassVar

import torch

from pydegas.mixtures.distribution import Dist


def _copy_tensor(t: torch.Tensor) -> torch.Tensor:
    """Return a detached clone so copied tensors carry no autograd history."""
    return t.clone().detach()


@dataclass
class CFGNode:
    """Base CFG node carrying the probabilistic state after execution."""

    # Class-level constant; dataclasses skips ClassVar so it is never part of
    # __init__. Each subclass redeclares it to fix the value for that node type.
    node_type: ClassVar[str] = ""

    name: str
    dist: Dist | None = None
    # Path probability; starts as 1.0, updated during SOGA execution.
    p: torch.Tensor | float = 1.0
    # Truncation condition string e.g. "x < 3.0"; set by the builder or smoother.
    trunc: str | None = None
    parent: list[CFGNode] = field(default_factory=list)
    children: list[CFGNode] = field(default_factory=list)

    def connect(self, child: CFGNode) -> None:
        self.children.append(child)
        child.parent.append(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> CFGNode:
        # Prevent re-copying the same node (handles parent-children cycles).
        if id(self) in memo:
            return memo[id(self)]

        cls = self.__class__
        new = object.__new__(cls)
        memo[id(self)] = new

        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if isinstance(value, torch.Tensor):
                copied = _copy_tensor(value)
            else:
                copied = copy.deepcopy(value, memo)
            object.__setattr__(new, f.name, copied)

        return new


@dataclass
class EntryNode(CFGNode):
    node_type: ClassVar[str] = "entry"


@dataclass
class StateNode(CFGNode):
    node_type: ClassVar[str] = "state"
    # Raw assignment expression text, e.g. "x=x+1" or "skip".
    expr: str | None = None
    # True → if-branch, False → else-branch, None → unconditional.
    cond: bool | None = None
    # Smoothed assignment expression injected by smoothcfg, or None.
    smooth: str | None = None


@dataclass
class TestNode(CFGNode):
    node_type: ClassVar[str] = "test"
    # Boolean condition text from the grammar, e.g. "x<0".
    LBC: str | None = None
    # Smoothed condition string injected by smoothcfg, or None.
    smooth: str | None = None


@dataclass
class ObserveNode(CFGNode):
    node_type: ClassVar[str] = "observe"
    # Boolean condition text from the grammar.
    LBC: str | None = None
    # Smoothed condition string injected by smoothcfg, or None.
    smooth: str | None = None
    # True for hard-observe ('hobserve'), False for soft-observe ('observe').
    hard: bool = False


@dataclass
class MergeNode(CFGNode):
    node_type: ClassVar[str] = "merge"
    # Accumulates (path_prob, dist) pairs from each branch during SOGA execution.
    list_dist: list[tuple[torch.Tensor, Dist]] = field(default_factory=list)


@dataclass
class PruneNode(CFGNode):
    node_type: ClassVar[str] = "prune"
    # Maximum number of GM components to retain after pruning.
    Kmax: int | None = None


@dataclass
class LoopNode(CFGNode):
    node_type: ClassVar[str] = "loop"
    # Loop variable name, e.g. "i".
    idx: str | None = None
    # Loop bound: a string from the grammar initially, converted to torch.Tensor at runtime.
    const: str | torch.Tensor | None = None
    # Tracks whether the loop body has been visited by the smoother.
    smooth: bool = False


@dataclass
class ExitNode(CFGNode):
    node_type: ClassVar[str] = "exit"
    # Accumulates (path_prob, dist) pairs from all paths reaching the exit.
    list_dist: list[tuple[torch.Tensor, Dist]] = field(default_factory=list)
