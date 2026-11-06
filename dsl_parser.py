"""Parser Lark per IdealDSL."""

from __future__ import annotations

import ast as python_ast
from functools import lru_cache

from lark import Lark, Transformer, v_args
from lark.exceptions import UnexpectedInput

from dsl_ast import (
    Assert,
    Assignment,
    Binary,
    BoolLiteral,
    Call,
    FunctionDeclaration,
    IdealLiteral,
    IfElse,
    IntLiteral,
    Let,
    PolynomialLiteral,
    Print,
    Program,
    RingDeclaration,
    Show,
    StringLiteral,
    Unary,
    VarDeclaration,
    Variable,
    Visualize,
    While,
)

IDEAL_DSL_GRAMMAR = r"""
start: ring_decl? statement*

ring_decl: "ring" NAME "[" name_list "]" ("order" NAME)? ";"
name_list: NAME ("," NAME)*

?statement: simple_statement ";"
          | if_statement
          | while_statement

?simple_statement: "var" NAME "=" expr                         -> var_decl
                 | NAME "<-" expr                              -> assignment
                 | "print" expr                                -> print_stmt
                 | "show" expr                                 -> show_stmt
                 | "visualize" expr "to" ESCAPED_STRING        -> visualize_stmt
                 | "assert" expr                               -> assert_stmt
                 | "function" NAME "(" param_list? ")" "=" expr -> function_decl

if_statement: "if" expr "then" then_block "else" else_block "endif" ";"?
then_block: statement*
else_block: statement*

while_statement: "while" expr "do" while_block "done" ";"?
while_block: statement*

param_list: NAME ("," NAME)*

?expr: let_expr
?let_expr: "let" NAME "=" expr "in" expr                       -> let_expr
         | or_expr
?or_expr: and_expr (OR and_expr)*                              -> binary_chain
?and_expr: equality (AND equality)*                            -> binary_chain
?equality: comparison (EQ_OP comparison)*                      -> binary_chain
?comparison: sum (COMP_OP sum)*                                -> binary_chain
?sum: term (ADD_OP term)*                                      -> binary_chain
?term: factor (MUL_OP factor)*                                 -> binary_chain
?factor: UNARY_OP factor                                       -> unary_expr
       | power
?power: atom (POW factor)?                                     -> power_expr

?atom: INT                                                     -> int_lit
     | "true"                                                  -> true_lit
     | "false"                                                 -> false_lit
     | ESCAPED_STRING                                          -> string_lit
     | polynomial_literal
     | ideal_literal
     | function_call
     | NAME                                                    -> variable
     | "(" expr ")"                                           -> grouped

function_call: NAME "(" argument_list? ")"
argument_list: expr ("," expr)*

polynomial_literal: "poly" "{" POLY_TEXT "}"
ideal_literal: "ideal" "{" ideal_items? "}"
ideal_items: POLY_TEXT (";" POLY_TEXT)*

OR.2: "or"
AND.2: "and"
EQ_OP: "==" | "!="
COMP_OP: "<=" | ">=" | "<" | ">"
ADD_OP: "+" | "-"
MUL_OP: "*" | "/" | "%"
UNARY_OP.2: "not" | "+" | "-"
POW: "^"

POLY_TEXT: /[^{};]+/
INT: /0|[1-9]\d*/
NAME: /[A-Za-z_][A-Za-z0-9_]*/

%import common.ESCAPED_STRING
%import common.WS
%ignore WS
%ignore /\/\/[^\n]*/
%ignore /#[^\n]*/
"""


@v_args(inline=True)
class IdealDSLTransformer(Transformer):
    def start(self, *items):
        ring = items[0] if items and isinstance(items[0], RingDeclaration) else None
        commands = items[1:] if ring is not None else items
        return Program(ring, tuple(commands))

    def name_list(self, *names):
        return tuple(str(name) for name in names)

    def ring_decl(self, domain, variables, order=None):
        return RingDeclaration(
            str(domain),
            tuple(variables),
            "lex" if order is None else str(order),
        )

    def then_block(self, *commands):
        return tuple(commands)

    def else_block(self, *commands):
        return tuple(commands)

    def while_block(self, *commands):
        return tuple(commands)

    def param_list(self, *names):
        return tuple(str(name) for name in names)

    def var_decl(self, name, expression):
        return VarDeclaration(str(name), expression)

    def assignment(self, name, expression):
        return Assignment(str(name), expression)

    def print_stmt(self, expression):
        return Print(expression)

    def show_stmt(self, expression):
        return Show(expression)

    def visualize_stmt(self, expression, path):
        return Visualize(expression, python_ast.literal_eval(str(path)))

    def assert_stmt(self, expression):
        return Assert(expression)

    def function_decl(self, name, *items):
        if len(items) == 1:
            parameters: tuple[str, ...] = ()
            body = items[0]
        elif len(items) == 2:
            parameters = tuple(items[0])
            body = items[1]
        else:
            raise ValueError(f"Dichiarazione di funzione non valida: {items!r}")
        return FunctionDeclaration(str(name), parameters, body)

    def if_statement(self, condition, then_branch, else_branch):
        return IfElse(condition, tuple(then_branch), tuple(else_branch))

    def while_statement(self, condition, body):
        return While(condition, tuple(body))

    def int_lit(self, token):
        return IntLiteral(int(token))

    def true_lit(self):
        return BoolLiteral(True)

    def false_lit(self):
        return BoolLiteral(False)

    def string_lit(self, token):
        return StringLiteral(python_ast.literal_eval(str(token)))

    def polynomial_literal(self, token):
        source = str(token).strip()
        if not source:
            raise ValueError("Un letterale poly non può essere vuoto.")
        return PolynomialLiteral(source)

    def ideal_items(self, *items):
        return tuple(str(item).strip() for item in items if str(item).strip())

    def ideal_literal(self, items=None):
        return IdealLiteral(()) if items is None else IdealLiteral(tuple(items))

    def variable(self, token):
        return Variable(str(token))

    def grouped(self, expression):
        return expression

    def let_expr(self, name, value, body):
        return Let(str(name), value, body)

    def unary_expr(self, operator, operand):
        return Unary(str(operator), operand)

    def power_expr(self, base, *tail):
        if not tail:
            return base
        # tail contiene POW e operando.
        return Binary("^", base, tail[-1])

    def binary_chain(self, first, *tail):
        if len(tail) % 2:
            raise ValueError(f"Catena binaria non valida: {tail!r}")
        result = first
        for index in range(0, len(tail), 2):
            result = Binary(str(tail[index]), result, tail[index + 1])
        return result

    def argument_list(self, *arguments):
        return tuple(arguments)

    def function_call(self, name, arguments=None):
        return Call(str(name), () if arguments is None else tuple(arguments))


@lru_cache(maxsize=1)
def _parser() -> Lark:
    return Lark(
        IDEAL_DSL_GRAMMAR,
        start="start",
        parser="lalr",
        lexer="contextual",
        transformer=IdealDSLTransformer(),
    )


def parse_program(source: str) -> Program:
    try:
        return _parser().parse(source)
    except UnexpectedInput as error:
        context = error.get_context(source, span=50)
        raise SyntaxError(
            f"Errore di sintassi alla riga {error.line}, colonna {error.column}:\n{context}"
        ) from error
