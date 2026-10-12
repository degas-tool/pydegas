"""Loss DSL: compile a DeGASLoss text definition into a PyTorch LossFunction."""

from __future__ import annotations

import importlib
import logging
from typing import Any

import torch
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from pydegas.exceptions import LossCompileError
from pydegas.mixtures.distribution import Dist
from pydegas.optimize.losses import LossFunction


logger = logging.getLogger(__name__)

_loss_parse = importlib.import_module("pydegas.parse.degas-loss")
_Lexer = _loss_parse.DeGASLossLexer
_Parser = _loss_parse.DeGASLossParser

_MATH_OPS: dict[str, Any] = {
    "log": torch.log,
    "exp": torch.exp,
    "abs": torch.abs,
    "sqrt": torch.sqrt,
}


class _CollectingErrorListener(ErrorListener):
    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e) -> None:
        self.errors.append(f"line {line}:{column} {msg}")


class _LossEvaluator:
    """Evaluates a LossBodyContext given a scope of bound variables."""

    def __init__(self, scope: dict[str, Any]) -> None:
        self._scope = scope

    def visit(self, tree: Any) -> Any:
        if tree is None:
            return None
        return tree.accept(self)

    # top-level body

    def visitLossBody(self, ctx: Any) -> torch.Tensor:
        for asgn in ctx.assignment():
            self.visitAssignment(asgn)
        return self.visitReturnExpr(ctx.returnExpr())

    def visitAssignment(self, ctx: Any) -> None:
        self._scope[ctx.IDENT().getText()] = self.visit(ctx.expr())

    def visitReturnExpr(self, ctx: Any) -> torch.Tensor:
        return self.visit(ctx.getChild(0))

    # expression hierarchy

    def visitExpr(self, ctx: Any) -> torch.Tensor:
        return self.visit(ctx.getChild(0))

    def visitAddExpr(self, ctx: Any) -> torch.Tensor:
        if ctx.getChildCount() == 1:
            return self.visit(ctx.getChild(0))
        left = self.visit(ctx.getChild(0))
        op = ctx.getChild(1).getText()
        right = self.visit(ctx.getChild(2))
        return left + right if op == "+" else left - right

    def visitMulExpr(self, ctx: Any) -> torch.Tensor:
        if ctx.getChildCount() == 1:
            return self.visit(ctx.getChild(0))
        left = self.visit(ctx.getChild(0))
        op = ctx.getChild(1).getText()
        right = self.visit(ctx.getChild(2))
        return left * right if op == "*" else left / right

    def visitPowExpr(self, ctx: Any) -> torch.Tensor:
        if ctx.getChildCount() == 1:
            return self.visit(ctx.getChild(0))
        return self.visit(ctx.getChild(0)) ** self.visit(ctx.getChild(2))

    # unaryExpr labeled alternatives

    def visitUnaryNeg(self, ctx: Any) -> torch.Tensor:
        return -self.visit(ctx.unaryExpr())

    def visitUnaryMathFunc(self, ctx: Any) -> torch.Tensor:
        func = ctx.mathFunc().getText()
        if func not in _MATH_OPS:
            raise LossCompileError(f"Unknown math function: {func!r}")
        return _MATH_OPS[func](self.visit(ctx.expr()))

    def visitUnaryCall(self, ctx: Any) -> torch.Tensor:
        return self.visit(ctx.getChild(0))

    def visitCallExpr(self, ctx: Any) -> torch.Tensor:
        return self.visit(ctx.getChild(0))

    # distCall labeled alternatives

    def visitDistMean(self, ctx: Any) -> torch.Tensor:
        return self._dist(ctx).gm.mean()

    def visitDistMeanIdx(self, ctx: Any) -> torch.Tensor:
        return self._dist(ctx).gm.mean()[self.visit(ctx.indexExpr())]

    def visitDistMargPdf(self, ctx: Any) -> torch.Tensor:
        dist = self._resolve(ctx.IDENT(0).getText())
        data = self._resolve(ctx.IDENT(1).getText())
        idx = self.visit(ctx.indexExpr())
        return dist.gm.marg_pdf(data, idx)

    def visitDistPdf(self, ctx: Any) -> torch.Tensor:
        dist = self._resolve(ctx.IDENT(0).getText())
        data = self._resolve(ctx.IDENT(1).getText())
        return dist.gm.pdf(data)

    def visitDistVar(self, ctx: Any) -> torch.Tensor:
        return torch.diag(self._dist(ctx).gm.cov())

    def visitDistVarIdx(self, ctx: Any) -> torch.Tensor:
        return torch.diag(self._dist(ctx).gm.cov())[self.visit(ctx.indexExpr())]

    # trajCall

    def visitTrajCall(self, ctx: Any) -> torch.Tensor:
        traj = self._resolve(ctx.IDENT().getText())
        return traj[:, self.visit(ctx.indexExpr())]

    # aggCall labeled alternatives

    def visitAggSum(self, ctx: Any) -> torch.Tensor:
        return torch.sum(self.visit(ctx.expr()))

    def visitAggMean(self, ctx: Any) -> torch.Tensor:
        return torch.mean(self.visit(ctx.expr()).float())

    def visitAggMax(self, ctx: Any) -> torch.Tensor:
        return torch.max(self.visit(ctx.expr()))

    def visitAggMin(self, ctx: Any) -> torch.Tensor:
        return torch.min(self.visit(ctx.expr()))

    # constructExpr

    def visitConstructExpr(self, ctx: Any) -> torch.Tensor:
        idx = self.visit(ctx.indexExpr())
        n = len(idx) if isinstance(idx, list) else 1
        return torch.ones(n)

    # indexExpr labeled alternatives

    def visitIndexLiteral(self, ctx: Any) -> list[int]:
        return [int(t.getText()) for t in ctx.intList().INTEGER()]

    def visitIndexRange(self, ctx: Any) -> list[int]:
        return list(range(int(ctx.INTEGER(0).getText()), int(ctx.INTEGER(1).getText())))

    def visitIndexSingle(self, ctx: Any) -> int:
        return int(ctx.INTEGER().getText())

    def visitIndexVar(self, ctx: Any) -> Any:
        return self._resolve(ctx.IDENT().getText())

    # primary labeled alternatives

    def visitPrimaryNumber(self, ctx: Any) -> torch.Tensor:
        return torch.tensor(float(ctx.NUMBER().getText()))

    def visitPrimaryInteger(self, ctx: Any) -> torch.Tensor:
        return torch.tensor(float(ctx.INTEGER().getText()))

    def visitPrimaryIdent(self, ctx: Any) -> Any:
        return self._resolve(ctx.IDENT().getText())

    def visitPrimaryParen(self, ctx: Any) -> torch.Tensor:
        return self.visit(ctx.expr())

    # helpers

    def _dist(self, ctx: Any) -> Dist:
        return self._resolve(ctx.IDENT().getText())

    def _resolve(self, name: str) -> Any:
        if name not in self._scope:
            raise LossCompileError(f"Undefined variable {name!r} in loss body.")
        return self._scope[name]


def _parse(source: str) -> tuple[Any, list[str]]:
    listener = _CollectingErrorListener()

    lexer = _Lexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(listener)

    stream = CommonTokenStream(lexer)

    parser = _Parser(stream)
    parser.removeErrorListeners()
    parser.addErrorListener(listener)

    return parser.program(), listener.errors


def validate_loss(source: str) -> list[str]:
    """Return a list of syntax error messages; empty means the source is valid."""
    _, errors = _parse(source)
    return errors


def extract_params(source: str) -> list[dict[str, str | None]]:
    """Parse *source* and return non-dist parameter definitions.

    Returns ``[{"name": str, "type": str | None}, ...]`` for every parameter
    that is not annotated as ``dist``.  Returns an empty list on syntax errors.
    """
    tree, errors = _parse(source)
    if errors:
        return []
    loss_defs = list(tree.lossDef())
    if not loss_defs:
        return []
    result = []
    for p in loss_defs[0].paramList().param():
        name = p.IDENT().getText()
        type_ann = p.typeAnn().getText() if p.typeAnn() else None
        if type_ann == "dist" or (type_ann is None and name == "dist"):
            continue
        result.append({"name": name, "type": type_ann})
    return result


def compile_loss(source: str, **bindings: Any) -> LossFunction:
    """Parse and compile a DeGASLoss definition to a LossFunction.

    Parameters not annotated as ``dist`` must be supplied as keyword arguments
    via *bindings*. The returned callable accepts a single ``Dist`` and returns
    a scalar ``torch.Tensor``.

    Raises ``LossCompileError`` on syntax errors or missing bindings.
    """
    tree, errors = _parse(source)
    if errors:
        raise LossCompileError("Loss DSL syntax errors:\n" + "\n".join(errors))

    loss_defs = list(tree.lossDef())
    if not loss_defs:
        raise LossCompileError("No loss definition found in source.")
    if len(loss_defs) > 1:
        logger.warning("Multiple loss definitions; using the first one.")

    loss_def = loss_defs[0]
    name = loss_def.IDENT().getText()

    params: list[tuple[str, str | None]] = [
        (p.IDENT().getText(), p.typeAnn().getText() if p.typeAnn() else None) for p in loss_def.paramList().param()
    ]

    dist_param = next(
        (n for n, t in params if t == "dist" or (t is None and n == "dist")),
        None,
    )
    if dist_param is None:
        raise LossCompileError(
            f"Loss {name!r} has no parameter annotated as 'dist'. "
            "Add ': dist' to the parameter that receives the output distribution."
        )

    missing = [n for n, t in params if n != dist_param and n not in bindings]
    if missing:
        raise LossCompileError(
            f"Loss {name!r} requires bindings for: {missing}. Pass them as keyword arguments to compile_loss()."
        )

    body_ctx = loss_def.lossBody()
    outer_scope = dict(bindings)

    def _loss_fn(dist: Dist) -> torch.Tensor:
        scope = {**outer_scope, dist_param: dist}
        return _LossEvaluator(scope).visit(body_ctx)

    _loss_fn.__name__ = name
    return _loss_fn
