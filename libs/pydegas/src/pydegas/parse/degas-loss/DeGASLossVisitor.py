# Generated from DeGASLoss.g4 by ANTLR 4.10.1
from antlr4 import *

if __name__ is not None and "." in __name__:
    from .DeGASLossParser import DeGASLossParser
else:
    from DeGASLossParser import DeGASLossParser

# This class defines a complete generic visitor for a parse tree produced by DeGASLossParser.


class DeGASLossVisitor(ParseTreeVisitor):
    # Visit a parse tree produced by DeGASLossParser#program.
    def visitProgram(self, ctx: DeGASLossParser.ProgramContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#lossDef.
    def visitLossDef(self, ctx: DeGASLossParser.LossDefContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#lossBody.
    def visitLossBody(self, ctx: DeGASLossParser.LossBodyContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#assignment.
    def visitAssignment(self, ctx: DeGASLossParser.AssignmentContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#returnExpr.
    def visitReturnExpr(self, ctx: DeGASLossParser.ReturnExprContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#paramList.
    def visitParamList(self, ctx: DeGASLossParser.ParamListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#param.
    def visitParam(self, ctx: DeGASLossParser.ParamContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#typeAnn.
    def visitTypeAnn(self, ctx: DeGASLossParser.TypeAnnContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#expr.
    def visitExpr(self, ctx: DeGASLossParser.ExprContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#addExpr.
    def visitAddExpr(self, ctx: DeGASLossParser.AddExprContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#mulExpr.
    def visitMulExpr(self, ctx: DeGASLossParser.MulExprContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#powExpr.
    def visitPowExpr(self, ctx: DeGASLossParser.PowExprContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#unaryNeg.
    def visitUnaryNeg(self, ctx: DeGASLossParser.UnaryNegContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#unaryMathFunc.
    def visitUnaryMathFunc(self, ctx: DeGASLossParser.UnaryMathFuncContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#unaryCall.
    def visitUnaryCall(self, ctx: DeGASLossParser.UnaryCallContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#mathFunc.
    def visitMathFunc(self, ctx: DeGASLossParser.MathFuncContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#callExpr.
    def visitCallExpr(self, ctx: DeGASLossParser.CallExprContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#distMean.
    def visitDistMean(self, ctx: DeGASLossParser.DistMeanContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#distMeanIdx.
    def visitDistMeanIdx(self, ctx: DeGASLossParser.DistMeanIdxContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#distMargPdf.
    def visitDistMargPdf(self, ctx: DeGASLossParser.DistMargPdfContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#distPdf.
    def visitDistPdf(self, ctx: DeGASLossParser.DistPdfContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#distVar.
    def visitDistVar(self, ctx: DeGASLossParser.DistVarContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#distVarIdx.
    def visitDistVarIdx(self, ctx: DeGASLossParser.DistVarIdxContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#trajCall.
    def visitTrajCall(self, ctx: DeGASLossParser.TrajCallContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#aggSum.
    def visitAggSum(self, ctx: DeGASLossParser.AggSumContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#aggMean.
    def visitAggMean(self, ctx: DeGASLossParser.AggMeanContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#aggMax.
    def visitAggMax(self, ctx: DeGASLossParser.AggMaxContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#aggMin.
    def visitAggMin(self, ctx: DeGASLossParser.AggMinContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#constructExpr.
    def visitConstructExpr(self, ctx: DeGASLossParser.ConstructExprContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#indexLiteral.
    def visitIndexLiteral(self, ctx: DeGASLossParser.IndexLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#indexRange.
    def visitIndexRange(self, ctx: DeGASLossParser.IndexRangeContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#indexSingle.
    def visitIndexSingle(self, ctx: DeGASLossParser.IndexSingleContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#indexVar.
    def visitIndexVar(self, ctx: DeGASLossParser.IndexVarContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#intList.
    def visitIntList(self, ctx: DeGASLossParser.IntListContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#primaryNumber.
    def visitPrimaryNumber(self, ctx: DeGASLossParser.PrimaryNumberContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#primaryInteger.
    def visitPrimaryInteger(self, ctx: DeGASLossParser.PrimaryIntegerContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#primaryIdent.
    def visitPrimaryIdent(self, ctx: DeGASLossParser.PrimaryIdentContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by DeGASLossParser#primaryParen.
    def visitPrimaryParen(self, ctx: DeGASLossParser.PrimaryParenContext):
        return self.visitChildren(ctx)


del DeGASLossParser
