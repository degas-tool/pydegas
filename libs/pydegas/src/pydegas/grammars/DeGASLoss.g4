// DeGASLoss.g4
// ANTLR4 grammar for defining loss functions in DeGAS
// (https://github.com/frarandone/DeGAS)
//
// A loss is a named function taking typed parameters (including a Dist object)
// and returning a scalar expression. The body consists of zero or more
// sequential assignments followed by a single return expression.
//
// Example:
//
//   loss L2_distance(traj_set: traj_set, dist: dist) =
//       idx = [1,2,3,4,5,6,7,8,9];
//       sum( (traj_set[:, idx] - dist.mean[idx]) ^ 2 )
//
//   loss signal_error(dist: dist, target: scalar, T: int) =
//       idx = range(1, T);
//       sum( (dist.mean[idx] - ones(idx) * target) ^ 2 )
//
//   loss neg_log_likelihood(traj_set: traj_set, dist: dist, idx: index_list) =
//       - sum( log( dist.marg_pdf(traj_set[:, idx], idx) ) )

grammar DeGASLoss;


// ─────────────────────────────────────────────
//  TOP LEVEL
// ─────────────────────────────────────────────

// A file may define one or more loss functions.
program
    : lossDef+ EOF
    ;

// loss <name>(<params>) = <body>
lossDef
    : LOSS IDENT LPAREN paramList RPAREN ASSIGN lossBody
    ;

// Zero or more assignments, then a final return expression.
lossBody
    : assignment* returnExpr
    ;

// <id> = <expr> ;
assignment
    : IDENT ASSIGN expr SEMICOLON
    ;

// The final expression whose value is the loss scalar (no semicolon).
returnExpr
    : expr
    ;


// ─────────────────────────────────────────────
//  PARAMETER LIST
// ─────────────────────────────────────────────

paramList
    : param (COMMA param)*
    |                           // empty parameter list
    ;

param
    : IDENT (COLON typeAnn)?
    ;

// Type annotations (optional; useful for validation and documentation)
typeAnn
    : DIST
    | TRAJ_SET
    | INDEX_LIST
    | SCALAR
    | INT_TYPE
    ;


// ─────────────────────────────────────────────
//  EXPRESSIONS
// ─────────────────────────────────────────────

expr
    : addExpr
    ;

// Addition / subtraction  (left-associative)
addExpr
    : addExpr (PLUS | MINUS) mulExpr
    | mulExpr
    ;

// Multiplication / division  (left-associative)
mulExpr
    : mulExpr (STAR | SLASH) powExpr
    | powExpr
    ;

// Power  (right-associative)
powExpr
    : unaryExpr CARET powExpr
    | unaryExpr
    ;

// Unary minus and math functions
unaryExpr
    : MINUS unaryExpr               # unaryNeg
    | mathFunc LPAREN expr RPAREN   # unaryMathFunc
    | callExpr                      # unaryCall
    ;

// One-argument mathematical functions
mathFunc
    : LOG
    | EXP
    | ABS
    | SQRT
    ;


// ─────────────────────────────────────────────
//  BUILT-IN CALLS
// ─────────────────────────────────────────────

callExpr
    : distCall
    | trajCall
    | aggCall
    | constructExpr
    | primary
    ;

// Distribution accessors: dist.mean(), dist.mean[idx], dist.marg_pdf(X, idx), etc.
distCall
    : IDENT DOT MEAN LPAREN RPAREN                               # distMean
    | IDENT DOT MEAN LBRACKET indexExpr RBRACKET                 # distMeanIdx
    | IDENT DOT MARG_PDF LPAREN IDENT COMMA indexExpr RPAREN     # distMargPdf
    | IDENT DOT PDF LPAREN IDENT RPAREN                          # distPdf
    | IDENT DOT VAR LPAREN RPAREN                                # distVar
    | IDENT DOT VAR LBRACKET indexExpr RBRACKET                  # distVarIdx
    ;

// Trajectory slice: traj_set[:, idx]
trajCall
    : IDENT LBRACKET COLON COMMA indexExpr RBRACKET
    ;

// Aggregation over a tensor expression
aggCall
    : SUM      LPAREN expr RPAREN   # aggSum
    | MEAN_AGG LPAREN expr RPAREN   # aggMean
    | MAX      LPAREN expr RPAREN   # aggMax
    | MIN      LPAREN expr RPAREN   # aggMin
    ;

// ones(indexExpr) — produces a tensor of ones shaped like the index
constructExpr
    : ONES LPAREN indexExpr RPAREN
    ;


// ─────────────────────────────────────────────
//  INDEX EXPRESSIONS
// ─────────────────────────────────────────────

indexExpr
    : LBRACKET intList RBRACKET                      # indexLiteral
    | RANGE LPAREN INTEGER COMMA INTEGER RPAREN      # indexRange
    | INTEGER                                        # indexSingle
    | IDENT                                          # indexVar
    ;

intList
    : INTEGER (COMMA INTEGER)*
    ;


// ─────────────────────────────────────────────
//  PRIMARY (atoms)
// ─────────────────────────────────────────────

primary
    : NUMBER                    # primaryNumber
    | INTEGER                   # primaryInteger
    | IDENT                     # primaryIdent
    | LPAREN expr RPAREN        # primaryParen
    ;


// ─────────────────────────────────────────────
//  KEYWORDS
// ─────────────────────────────────────────────

LOSS        : 'loss' ;

// Type annotations
DIST        : 'dist' ;
TRAJ_SET    : 'traj_set' ;
INDEX_LIST  : 'index_list' ;
SCALAR      : 'scalar' ;
INT_TYPE    : 'int' ;

// Distribution accessors
MEAN        : 'mean' ;
MARG_PDF    : 'marg_pdf' ;
PDF         : 'pdf' ;
VAR         : 'var' ;

// Math functions
LOG         : 'log' ;
EXP         : 'exp' ;
ABS         : 'abs' ;
SQRT        : 'sqrt' ;

// Aggregation
SUM         : 'sum' ;
MEAN_AGG    : 'mean_agg' ;
MAX         : 'max' ;
MIN         : 'min' ;

// Index / tensor helpers
RANGE       : 'range' ;
ONES        : 'ones' ;


// ─────────────────────────────────────────────
//  OPERATORS AND PUNCTUATION
// ─────────────────────────────────────────────

ASSIGN      : '=' ;
SEMICOLON   : ';' ;
PLUS        : '+' ;
MINUS       : '-' ;
STAR        : '*' ;
SLASH       : '/' ;
CARET       : '^' ;
DOT         : '.' ;
COMMA       : ',' ;
COLON       : ':' ;
LPAREN      : '(' ;
RPAREN      : ')' ;
LBRACKET    : '[' ;
RBRACKET    : ']' ;


// ─────────────────────────────────────────────
//  LITERALS
// ─────────────────────────────────────────────

// Floating-point literal (must be matched before INTEGER)
NUMBER
    : [0-9]+ '.' [0-9]*
    | '.' [0-9]+
    | [0-9]+ '.' [0-9]* [eE] [+-]? [0-9]+
    | [0-9]+ [eE] [+-]? [0-9]+
    ;

INTEGER
    : [0-9]+
    ;

// Identifiers — declared after all keywords so keywords take priority
IDENT
    : [a-zA-Z_] [a-zA-Z0-9_]*
    ;


// ─────────────────────────────────────────────
//  WHITESPACE AND COMMENTS
// ─────────────────────────────────────────────

WS
    : [ \t\r\n]+ -> skip
    ;

LINE_COMMENT
    : '//' ~[\r\n]* -> skip
    ;

BLOCK_COMMENT
    : '/*' .*? '*/' -> skip
    ;
