from __future__ import annotations

import copy
import logging
from typing import Any

import pydegas.cfg.nodes as nodes
from pydegas.parse.soga.SOGAListener import SOGAListener
from pydegas.parse.soga.SOGAParser import SOGAParser


logger = logging.getLogger(__name__)


class ControlFlowGraph(SOGAListener):
    def __init__(self) -> None:
        # counters for nodes of different types
        self.n_state: int = 0
        self.n_test: int = 0
        self.n_merge: int = 0
        self.n_observe: int = 0
        self.n_loop: int = 0
        self.n_prune: int = 0

        # root of the CFG
        self.root: nodes.EntryNode = nodes.EntryNode(name="entry")

        # dictionary for data (used by enterData / enterArray)
        self.data: dict[str, Any] = {}

        # ordered name, node mapping; preserves insertion order = traversal order
        self.node_list: dict[str, nodes.CFGNode] = {"entry": self.root}
        self.ID_list: list[str] = []

        # internal builder state
        self._current_node: nodes.CFGNode = self.root
        self._flag: bool | None = None  # True = if-branch, False = else/loop-exit
        self._subroot: list[nodes.CFGNode] = []  # stack of open conditionals/loops

        self.smoothed_vars: list[str] = []

    def enterData(self, ctx: SOGAParser.DataContext) -> None:
        data_name = ctx.symvars().getText()
        data_value = eval(ctx.list_().getText())  # noqa: S307
        self.data[data_name] = data_value

    def enterArray(self, ctx: SOGAParser.ArrayContext) -> None:
        n = int(ctx.NUM().getText())
        var_name = ctx.IDV().getText()
        for i in range(n):
            self.ID_list.append(f"{var_name}[{i}]")

    def enterAssignment(self, ctx: SOGAParser.AssignmentContext) -> None:
        """New StateNode for each assignment; inherits branch condition from _flag."""
        node = nodes.StateNode(name=f"state{self.n_state}")
        self.n_state += 1
        if self._flag is not None:
            node.cond = self._flag
            self._flag = None
        node.expr = ctx.getText()
        node.parent.append(self._current_node)
        self._current_node.children.append(node)
        self._current_node = node
        self.node_list[node.name] = node
        logger.debug("state  %s  expr=%r  cond=%s", node.name, node.expr, node.cond)

    def enterConditional(self, ctx: SOGAParser.ConditionalContext) -> None:
        """New TestNode pushed onto the subroot stack when entering an if/else."""
        node = nodes.TestNode(name=f"test{self.n_test}")
        self.n_test += 1
        node.parent.append(self._current_node)
        self._current_node.children.append(node)
        self._current_node = node
        self._subroot.append(self._current_node)
        self.node_list[node.name] = node

    def enterIfclause(self, ctx: SOGAParser.IfclauseContext) -> None:
        """Store the boolean condition on the TestNode; set _flag for the if-branch."""
        self._current_node.LBC = ctx.bexpr().getText()  # type: ignore[attr-defined]
        self._flag = True
        logger.debug("test   %s  LBC=%r", self._current_node.name, self._current_node.LBC)  # type: ignore[attr-defined]
        if ctx.block().instr(0).assignment() is None:
            self._create_skip()

    def exitIfclause(self, ctx: SOGAParser.IfclauseContext) -> None:
        """Return to the TestNode after the if-branch so the else-branch can branch from it."""
        self._current_node = self._subroot[-1]

    def enterElseclause(self, ctx: SOGAParser.ElseclauseContext) -> None:
        """Set _flag for the else-branch."""
        self._flag = False
        if ctx.block().instr(0).assignment() is None:
            self._create_skip()

    def exitElseclause(self, ctx: SOGAParser.ElseclauseContext) -> None:
        """Pop the TestNode and add a MergeNode joining both branches."""
        self._current_node = self._subroot.pop()
        node = nodes.MergeNode(name=f"merge{self.n_merge}")
        self.n_merge += 1
        node.parent, _ = self._get_leaves(self._current_node, [], [])
        for parent in node.parent:
            parent.children.append(node)
        self._current_node = node
        self.node_list[node.name] = node
        logger.debug("merge  %s  joins=%s", node.name, [p.name for p in node.parent])

    def enterObserve(self, ctx: SOGAParser.ObserveContext) -> None:
        """New ObserveNode; hard=True for 'hobserve', False for 'observe'."""
        node = nodes.ObserveNode(name=f"observe{self.n_observe}")
        node.hard = "hobserve" in ctx.getText()
        node.LBC = ctx.bexpr().getText()
        self.n_observe += 1
        node.parent.append(self._current_node)
        self._current_node.children.append(node)
        self._current_node = node
        self.node_list[node.name] = node
        logger.debug("observe %s  LBC=%r  hard=%s", node.name, node.LBC, node.hard)

    def enterPrune(self, ctx: SOGAParser.PruneContext) -> None:
        """New PruneNode that caps the number of GM components to Kmax."""
        node = nodes.PruneNode(name=f"prune{self.n_prune}")
        self.n_prune += 1
        node.parent, _ = self._get_leaves(self._current_node, [], [])
        for parent in node.parent:
            parent.children.append(node)
        self._current_node = node
        self.node_list[node.name] = node
        self._current_node.Kmax = int(ctx.NUM().getText())
        logger.debug("prune  %s  Kmax=%d", node.name, node.Kmax)

    def enterLoop(self, ctx: SOGAParser.LoopContext) -> None:
        """New LoopNode pushed onto subroot stack; stores loop variable and bound."""
        node = nodes.LoopNode(name=f"loop{self.n_loop}")
        self.n_loop += 1
        node.parent.append(self._current_node)
        self._current_node.children.append(node)
        self._current_node = node
        self._subroot.append(self._current_node)
        self.node_list[node.name] = node
        idx_name = ctx.IDV().getText()
        self._current_node.idx = idx_name
        self.data[idx_name] = [None]
        self._current_node.const = ctx.NUM().getText() if ctx.NUM() is not None else ctx.idd().getText()
        self._flag = True
        logger.debug("loop   %s  idx=%r  const=%r", node.name, node.idx, node.const)
        if ctx.block().instr(0).assignment() is None:
            self._create_skip()

    def exitLoop(self, ctx: SOGAParser.LoopContext) -> None:
        """Close the loop: wire the last body node back to the LoopNode, then add a skip."""
        if self._current_node.node_type != "state":
            self._create_skip()
        self._current_node.children.append(self._subroot[-1])
        self._subroot[-1].parent.append(self._current_node)
        self._current_node = self._subroot.pop()
        self._flag = False
        self._create_skip()

    def exitProgr(self, ctx: SOGAParser.ProgrContext) -> None:
        """Add an ExitNode linking all open leaves when the program ends."""
        node = nodes.ExitNode(name="exit")
        node.parent, _ = self._get_leaves(self._current_node, [], [])
        for parent in node.parent:
            parent.children.append(node)
        self._current_node = node
        self.node_list[node.name] = node
        logger.debug(
            "CFG built: %d nodes, vars=%s",
            len(self.node_list),
            self.ID_list,
        )

    def enterSymvars(self, ctx: SOGAParser.SymvarsContext) -> None:
        """Collect symbolic variable names that are not already tracked."""
        if ctx.IDV() is not None:
            var = ctx.IDV().getText()
            if var not in self.ID_list and var not in self.data:
                self.ID_list.append(var)

    def enterUniform(self, ctx: SOGAParser.UniformContext) -> None:
        pass

    def enterGm(self, ctx: SOGAParser.GmContext) -> None:
        pass

    def _get_leaves(
        self,
        node: nodes.CFGNode,
        leaves: list[nodes.CFGNode],
        checked: list[nodes.CFGNode],
    ) -> tuple[list[nodes.CFGNode], list[nodes.CFGNode]]:
        """Recursively collect all leaf nodes reachable from *node*."""
        checked.append(node)
        if not node.children:
            if node not in leaves:
                leaves.append(node)
        else:
            for child in node.children:
                if child not in checked:
                    leaves, checked = self._get_leaves(child, leaves, checked)
        return leaves, checked

    def _create_skip(self) -> None:
        """Insert a no-op StateNode (expr='skip') to preserve the branch condition."""
        node = nodes.StateNode(name=f"state{self.n_state}")
        self.n_state += 1
        node.cond = self._flag
        self._flag = None
        node.expr = "skip"
        node.parent.append(self._current_node)
        self._current_node.children.append(node)
        self._current_node = node
        self.node_list[node.name] = node
        logger.debug("skip   %s  cond=%s", node.name, node.cond)

    def edges(self) -> list[str]:
        """Return a list of edge strings '(parent,child)' for debugging."""
        return [f"({name},{child.name})" for name, node in self.node_list.items() for child in node.children]

    def deepcopy(self) -> ControlFlowGraph:
        return copy.deepcopy(self)
