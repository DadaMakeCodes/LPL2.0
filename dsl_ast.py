"""Albero sintattico astratto del linguaggio IdealDSL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


# ----------------------------- Expressions -----------------------------
@dataclass(frozen=True, slots=True)
class IntLiteral:
    value: int


@dataclass(frozen=True, slots=True)
class BoolLiteral:
    value: bool


@dataclass(frozen=True, slots=True)
class StringLiteral:
    value: str


@dataclass(frozen=True, slots=True)
class PolynomialLiteral:
    source: str


@dataclass(frozen=True, slots=True)
class IdealLiteral:
    generators: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Variable:
    name: str


@dataclass(frozen=True, slots=True)
class Let:
    name: str
    value: "Expression"
    body: "Expression"


@dataclass(frozen=True, slots=True)
class Unary:
    operator: str
    operand: "Expression"


@dataclass(frozen=True, slots=True)
class Binary:
    operator: str
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True, slots=True)
class Call:
    name: str
    arguments: tuple["Expression", ...]


Expression: TypeAlias = (
    IntLiteral
    | BoolLiteral
    | StringLiteral
    | PolynomialLiteral
    | IdealLiteral
    | Variable
    | Let
    | Unary
    | Binary
    | Call
)


# ------------------------------- Commands ------------------------------
@dataclass(frozen=True, slots=True)
class VarDeclaration:
    name: str
    expression: Expression


@dataclass(frozen=True, slots=True)
class Assignment:
    name: str
    expression: Expression


@dataclass(frozen=True, slots=True)
class Print:
    expression: Expression


@dataclass(frozen=True, slots=True)
class Show:
    expression: Expression


@dataclass(frozen=True, slots=True)
class Visualize:
    expression: Expression
    path: str


@dataclass(frozen=True, slots=True)
class Assert:
    expression: Expression


@dataclass(frozen=True, slots=True)
class FunctionDeclaration:
    name: str
    parameters: tuple[str, ...]
    body: Expression


@dataclass(frozen=True, slots=True)
class IfElse:
    condition: Expression
    then_branch: tuple["Command", ...]
    else_branch: tuple["Command", ...]


@dataclass(frozen=True, slots=True)
class While:
    condition: Expression
    body: tuple["Command", ...]


Command: TypeAlias = (
    VarDeclaration
    | Assignment
    | Print
    | Show
    | Visualize
    | Assert
    | FunctionDeclaration
    | IfElse
    | While
)


@dataclass(frozen=True, slots=True)
class RingDeclaration:
    domain: str
    variables: tuple[str, ...]
    order: str = "lex"


@dataclass(frozen=True, slots=True)
class Program:
    ring: RingDeclaration | None
    commands: tuple[Command, ...]
