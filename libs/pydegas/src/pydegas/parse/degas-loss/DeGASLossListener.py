# Generated from DeGASLoss.g4 by ANTLR 4.10.1
from antlr4 import *

if __name__ is not None and "." in __name__:
    from .DeGASLossParser import DeGASLossParser
else:
    from DeGASLossParser import DeGASLossParser


# This class defines a complete listener for a parse tree produced by DeGASLossParser.
class DeGASLossListener(ParseTreeListener):
    # Enter a parse tree produced by DeGASLossParser#program.
    def enterProgram(self, ctx: DeGASLossParser.ProgramContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#program.
    def exitProgram(self, ctx: DeGASLossParser.ProgramContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#lossDef.
    def enterLossDef(self, ctx: DeGASLossParser.LossDefContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#lossDef.
    def exitLossDef(self, ctx: DeGASLossParser.LossDefContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#lossBody.
    def enterLossBody(self, ctx: DeGASLossParser.LossBodyContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#lossBody.
    def exitLossBody(self, ctx: DeGASLossParser.LossBodyContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#assignment.
    def enterAssignment(self, ctx: DeGASLossParser.AssignmentContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#assignment.
    def exitAssignment(self, ctx: DeGASLossParser.AssignmentContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#returnExpr.
    def enterReturnExpr(self, ctx: DeGASLossParser.ReturnExprContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#returnExpr.
    def exitReturnExpr(self, ctx: DeGASLossParser.ReturnExprContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#paramList.
    def enterParamList(self, ctx: DeGASLossParser.ParamListContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#paramList.
    def exitParamList(self, ctx: DeGASLossParser.ParamListContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#param.
    def enterParam(self, ctx: DeGASLossParser.ParamContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#param.
    def exitParam(self, ctx: DeGASLossParser.ParamContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#typeAnn.
    def enterTypeAnn(self, ctx: DeGASLossParser.TypeAnnContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#typeAnn.
    def exitTypeAnn(self, ctx: DeGASLossParser.TypeAnnContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#expr.
    def enterExpr(self, ctx: DeGASLossParser.ExprContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#expr.
    def exitExpr(self, ctx: DeGASLossParser.ExprContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#addExpr.
    def enterAddExpr(self, ctx: DeGASLossParser.AddExprContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#addExpr.
    def exitAddExpr(self, ctx: DeGASLossParser.AddExprContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#mulExpr.
    def enterMulExpr(self, ctx: DeGASLossParser.MulExprContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#mulExpr.
    def exitMulExpr(self, ctx: DeGASLossParser.MulExprContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#powExpr.
    def enterPowExpr(self, ctx: DeGASLossParser.PowExprContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#powExpr.
    def exitPowExpr(self, ctx: DeGASLossParser.PowExprContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#unaryNeg.
    def enterUnaryNeg(self, ctx: DeGASLossParser.UnaryNegContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#unaryNeg.
    def exitUnaryNeg(self, ctx: DeGASLossParser.UnaryNegContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#unaryMathFunc.
    def enterUnaryMathFunc(self, ctx: DeGASLossParser.UnaryMathFuncContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#unaryMathFunc.
    def exitUnaryMathFunc(self, ctx: DeGASLossParser.UnaryMathFuncContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#unaryCall.
    def enterUnaryCall(self, ctx: DeGASLossParser.UnaryCallContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#unaryCall.
    def exitUnaryCall(self, ctx: DeGASLossParser.UnaryCallContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#mathFunc.
    def enterMathFunc(self, ctx: DeGASLossParser.MathFuncContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#mathFunc.
    def exitMathFunc(self, ctx: DeGASLossParser.MathFuncContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#callExpr.
    def enterCallExpr(self, ctx: DeGASLossParser.CallExprContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#callExpr.
    def exitCallExpr(self, ctx: DeGASLossParser.CallExprContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#distMean.
    def enterDistMean(self, ctx: DeGASLossParser.DistMeanContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#distMean.
    def exitDistMean(self, ctx: DeGASLossParser.DistMeanContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#distMeanIdx.
    def enterDistMeanIdx(self, ctx: DeGASLossParser.DistMeanIdxContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#distMeanIdx.
    def exitDistMeanIdx(self, ctx: DeGASLossParser.DistMeanIdxContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#distMargPdf.
    def enterDistMargPdf(self, ctx: DeGASLossParser.DistMargPdfContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#distMargPdf.
    def exitDistMargPdf(self, ctx: DeGASLossParser.DistMargPdfContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#distPdf.
    def enterDistPdf(self, ctx: DeGASLossParser.DistPdfContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#distPdf.
    def exitDistPdf(self, ctx: DeGASLossParser.DistPdfContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#distVar.
    def enterDistVar(self, ctx: DeGASLossParser.DistVarContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#distVar.
    def exitDistVar(self, ctx: DeGASLossParser.DistVarContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#distVarIdx.
    def enterDistVarIdx(self, ctx: DeGASLossParser.DistVarIdxContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#distVarIdx.
    def exitDistVarIdx(self, ctx: DeGASLossParser.DistVarIdxContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#trajCall.
    def enterTrajCall(self, ctx: DeGASLossParser.TrajCallContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#trajCall.
    def exitTrajCall(self, ctx: DeGASLossParser.TrajCallContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#aggSum.
    def enterAggSum(self, ctx: DeGASLossParser.AggSumContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#aggSum.
    def exitAggSum(self, ctx: DeGASLossParser.AggSumContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#aggMean.
    def enterAggMean(self, ctx: DeGASLossParser.AggMeanContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#aggMean.
    def exitAggMean(self, ctx: DeGASLossParser.AggMeanContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#aggMax.
    def enterAggMax(self, ctx: DeGASLossParser.AggMaxContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#aggMax.
    def exitAggMax(self, ctx: DeGASLossParser.AggMaxContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#aggMin.
    def enterAggMin(self, ctx: DeGASLossParser.AggMinContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#aggMin.
    def exitAggMin(self, ctx: DeGASLossParser.AggMinContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#constructExpr.
    def enterConstructExpr(self, ctx: DeGASLossParser.ConstructExprContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#constructExpr.
    def exitConstructExpr(self, ctx: DeGASLossParser.ConstructExprContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#indexLiteral.
    def enterIndexLiteral(self, ctx: DeGASLossParser.IndexLiteralContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#indexLiteral.
    def exitIndexLiteral(self, ctx: DeGASLossParser.IndexLiteralContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#indexRange.
    def enterIndexRange(self, ctx: DeGASLossParser.IndexRangeContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#indexRange.
    def exitIndexRange(self, ctx: DeGASLossParser.IndexRangeContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#indexSingle.
    def enterIndexSingle(self, ctx: DeGASLossParser.IndexSingleContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#indexSingle.
    def exitIndexSingle(self, ctx: DeGASLossParser.IndexSingleContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#indexVar.
    def enterIndexVar(self, ctx: DeGASLossParser.IndexVarContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#indexVar.
    def exitIndexVar(self, ctx: DeGASLossParser.IndexVarContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#intList.
    def enterIntList(self, ctx: DeGASLossParser.IntListContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#intList.
    def exitIntList(self, ctx: DeGASLossParser.IntListContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#primaryNumber.
    def enterPrimaryNumber(self, ctx: DeGASLossParser.PrimaryNumberContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#primaryNumber.
    def exitPrimaryNumber(self, ctx: DeGASLossParser.PrimaryNumberContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#primaryInteger.
    def enterPrimaryInteger(self, ctx: DeGASLossParser.PrimaryIntegerContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#primaryInteger.
    def exitPrimaryInteger(self, ctx: DeGASLossParser.PrimaryIntegerContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#primaryIdent.
    def enterPrimaryIdent(self, ctx: DeGASLossParser.PrimaryIdentContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#primaryIdent.
    def exitPrimaryIdent(self, ctx: DeGASLossParser.PrimaryIdentContext):
        pass

    # Enter a parse tree produced by DeGASLossParser#primaryParen.
    def enterPrimaryParen(self, ctx: DeGASLossParser.PrimaryParenContext):
        pass

    # Exit a parse tree produced by DeGASLossParser#primaryParen.
    def exitPrimaryParen(self, ctx: DeGASLossParser.PrimaryParenContext):
        pass


del DeGASLossParser
