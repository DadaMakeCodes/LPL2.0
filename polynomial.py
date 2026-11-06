"""Polinomi multivariati sparsi a coefficienti razionali."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, Tuple

from lark import Lark, Transformer, v_args

from monomial import Monomio, sort_monomials
import state

POLY_DSL_GRAMMAR = r"""
?start: expr
?expr: sum
?sum: product ((PLUS|MINUS) product)*         -> sum_chain
?product: unary (STAR unary)*                  -> mul_chain
?unary: PLUS unary                             -> uplus
      | MINUS unary                            -> uminus
      | power
?power: atom (CIRCUMFLEX UNSIGNED_INT)?        -> pow
?atom: RATIONAL                                -> number_lit
     | VAR                                     -> var
     | "(" expr ")"                            -> group

PLUS: "+"
MINUS: "-"
STAR: "*"
CIRCUMFLEX: "^"
RATIONAL: /(?:0|[1-9]\d*)(?:\/(?:[1-9]\d*))?/
VAR: /[a-zA-Z][a-zA-Z0-9_]*/
UNSIGNED_INT: /0|[1-9]\d*/

%import common.WS
%ignore WS
"""


@dataclass(frozen=True, slots=True, eq=False)
class Polinomio:
    terms: tuple[Monomio, ...]

    def __init__(self, terms: Iterable[Monomio] | None = None):
        coefficients: Dict[Tuple[Tuple[str, int], ...], Fraction] = {}
        for monomial in terms or ():
            signature = monomial.signature()
            coefficients[signature] = (
                coefficients.get(signature, Fraction(0)) + monomial.coeff
            )
        cleaned = tuple(
            Monomio(coeff, dict(signature))
            for signature, coeff in sorted(coefficients.items())
            if coeff != 0
        )
        object.__setattr__(self, "terms", cleaned)

    @classmethod
    def zero(cls) -> "Polinomio":
        return cls(())

    @classmethod
    def const(cls, value: int | Fraction) -> "Polinomio":
        return cls((Monomio(Fraction(value), {}),))

    @classmethod
    def var(cls, name: str) -> "Polinomio":
        return cls((Monomio(Fraction(1), {name: 1}),))

    @classmethod
    def from_monom(cls, monomial: Monomio) -> "Polinomio":
        return cls.zero() if monomial.is_zero() else cls((monomial,))

    @classmethod
    def parse(cls, source: str) -> "Polinomio":
        parser = Lark(
            POLY_DSL_GRAMMAR,
            parser="lalr",
            lexer="contextual",
            transformer=PolinomTransformer(cls),
        )
        result: Polinomio = parser.parse(source)
        used = {v for term in result.terms for v in term.powers}
        invalid = sorted(used - set(state.ringvar))
        if invalid:
            raise ValueError(
                f"Il polinomio usa variabili non ammesse {invalid}. "
                f"Variabili ammesse: {state.ringvar}"
            )
        return result

    def coefficient_map(self) -> dict[Tuple[Tuple[str, int], ...], Fraction]:
        return {term.signature(): term.coeff for term in self.terms}

    def is_zero(self) -> bool:
        return not self.terms

    def ordered_terms(self) -> tuple[Monomio, ...]:
        return tuple(sort_monomials(self.terms))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Polinomio) and self.coefficient_map() == other.coefficient_map()

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.coefficient_map().items())))

    def __add__(self, other: object) -> "Polinomio":
        if not isinstance(other, Polinomio):
            return NotImplemented
        return Polinomio((*self.terms, *other.terms))

    def __sub__(self, other: object) -> "Polinomio":
        if not isinstance(other, Polinomio):
            return NotImplemented
        return Polinomio((*self.terms, *(-term for term in other.terms)))

    def __neg__(self) -> "Polinomio":
        return Polinomio((-term for term in self.terms))

    def __mul__(self, other: object) -> "Polinomio":
        if not isinstance(other, Polinomio):
            return NotImplemented
        if self.is_zero() or other.is_zero():
            return Polinomio.zero()
        return Polinomio(a * b for a in self.terms for b in other.terms)

    def scalar_mul(self, scalar: int | Fraction) -> "Polinomio":
        factor = Fraction(scalar)
        return Polinomio(Monomio(factor * term.coeff, term.powers) for term in self.terms)

    def __pow__(self, exponent: int) -> "Polinomio":
        n = int(exponent)
        if n < 0:
            raise ValueError("Esponenti negativi non supportati nei polinomi.")
        if n == 0:
            if self.is_zero():
                raise ValueError("0^0 non è definito nel DSL.")
            return Polinomio.const(1)
        if self.is_zero():
            return Polinomio.zero()

        result = Polinomio.const(1)
        base = self
        while n:
            if n & 1:
                result = result * base
            base = base * base
            n >>= 1
        return result

    def __str__(self) -> str:
        if self.is_zero():
            return "0"
        output: list[str] = []
        for index, term in enumerate(self.ordered_terms()):
            absolute = Monomio(abs(term.coeff), term.powers)
            rendered = str(absolute)
            if index == 0:
                output.append(rendered if term.coeff > 0 else f"-{rendered}")
            else:
                output.append(("+" if term.coeff > 0 else "-") + rendered)
        return "".join(output)

    def __repr__(self) -> str:
        return f"Polinomio({self.ordered_terms()!r})"


@v_args(inline=True)
class PolinomTransformer(Transformer):
    def __init__(self, polynomial_class: type[Polinomio]):
        super().__init__()
        self.P = polynomial_class

    def RATIONAL(self, token):
        return Fraction(str(token))

    def UNSIGNED_INT(self, token):
        return int(token)

    def number_lit(self, value):
        return self.P.const(value)

    def var(self, token):
        return self.P.var(str(token))

    def group(self, expression):
        return expression

    def uplus(self, *items):
        return items[-1]

    def uminus(self, *items):
        return -items[-1]

    def mul_chain(self, first, *tail):
        result = first
        for item in tail:
            if getattr(item, "type", None) == "STAR":
                continue
            result = result * item
        return result

    def sum_chain(self, first, *tail):
        if len(tail) % 2:
            raise ValueError(f"Sequenza somma non valida: {tail!r}")
        result = first
        for index in range(0, len(tail), 2):
            operator = tail[index].type
            term = tail[index + 1]
            result = result + term if operator == "PLUS" else result - term
        return result

    def pow(self, base, *tail):
        if not tail:
            return base
        return base ** int(tail[-1])


def normal_pol_form(polynomial: Polinomio) -> Polinomio:
    return Polinomio(polynomial.ordered_terms())
