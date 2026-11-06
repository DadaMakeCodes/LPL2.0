"""Monomi a coefficienti razionali."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, Tuple

from lark import Lark, Transformer, v_args

import state

MONOM_DSL_GRAMMAR = r"""
?start: expr
?expr: product
?product: unary ("*" unary)*                  -> mul
?unary: "+" unary                              -> uplus
      | "-" unary                              -> uminus
      | power
?power: atom ("^" UNSIGNED_INT)?              -> pow
?atom: RATIONAL                                -> number_lit
     | VAR                                     -> var
     | "(" expr ")"                            -> group

RATIONAL: /(?:0|[1-9]\d*)(?:\/(?:[1-9]\d*))?/
VAR: /[a-zA-Z][a-zA-Z0-9_]*/
UNSIGNED_INT: /0|[1-9]\d*/

%import common.WS
%ignore WS
"""


@v_args(inline=True)
class MonomTransformer(Transformer):
    @staticmethod
    def _normalize(value: tuple[Fraction, dict[str, int]]):
        coeff, powers = Fraction(value[0]), dict(value[1])
        if coeff == 0:
            return Fraction(0), {}
        return coeff, {v: int(e) for v, e in powers.items() if int(e) > 0}

    def RATIONAL(self, token):
        return Fraction(str(token))

    def UNSIGNED_INT(self, token):
        return int(token)

    def number_lit(self, value):
        return Fraction(value), {}

    def var(self, token):
        return Fraction(1), {str(token): 1}

    def group(self, value):
        return self._normalize(value)

    def uplus(self, value):
        return self._normalize(value)

    def uminus(self, value):
        coeff, powers = self._normalize(value)
        return -coeff, powers

    def mul(self, first, *rest):
        coeff, powers = self._normalize(first)
        for item in rest:
            other_coeff, other_powers = self._normalize(item)
            coeff *= other_coeff
            if coeff == 0:
                return Fraction(0), {}
            for variable, exponent in other_powers.items():
                powers[variable] = powers.get(variable, 0) + exponent
        return self._normalize((coeff, powers))

    def pow(self, base, exponent=None):
        coeff, powers = self._normalize(base)
        if exponent is None:
            return coeff, powers
        n = int(exponent)
        if n == 0:
            if coeff == 0:
                raise ValueError("0^0 non è definito nel DSL.")
            return Fraction(1), {}
        if coeff == 0:
            return Fraction(0), {}
        return coeff**n, {v: e * n for v, e in powers.items()}


@dataclass(frozen=True, slots=True)
class Monomio:
    coeff: Fraction
    powers: Dict[str, int]

    _parser = Lark(
        MONOM_DSL_GRAMMAR,
        parser="lalr",
        lexer="contextual",
        transformer=MonomTransformer(),
    )

    def __post_init__(self) -> None:
        coeff = Fraction(self.coeff)
        raw = dict(self.powers or {})
        if coeff == 0:
            object.__setattr__(self, "coeff", Fraction(0))
            object.__setattr__(self, "powers", {})
            return

        cleaned: dict[str, int] = {}
        for variable, exponent in raw.items():
            exp = int(exponent)
            if exp < 0:
                raise ValueError("Esponenti negativi non supportati nei monomi.")
            if exp > 0:
                cleaned[str(variable)] = exp
        object.__setattr__(self, "coeff", coeff)
        object.__setattr__(self, "powers", cleaned)

    @classmethod
    def parse(cls, source: str) -> "Monomio":
        coeff, powers = cls._parser.parse(source)
        invalid = sorted(set(powers) - set(state.ringvar))
        if invalid:
            raise ValueError(
                f"Variabili non ammesse nel monomio: {invalid}. "
                f"Variabili ammesse: {state.ringvar}"
            )
        return cls(coeff, powers)

    def is_zero(self) -> bool:
        return self.coeff == 0

    def degree_vector(self) -> tuple[int, ...]:
        extra = set(self.powers) - set(state.ringvar)
        if extra:
            raise ValueError(
                f"Il monomio contiene variabili fuori dall'anello attivo: {sorted(extra)}"
            )
        return tuple(self.powers.get(v, 0) for v in state.ringvar)

    # Nome mantenuto per compatibilità con il progetto originario.
    def grado(self) -> list[int]:
        return list(self.degree_vector())

    def order_key(self) -> tuple:
        return state.monomial_key(self.degree_vector())

    def signature(self) -> Tuple[Tuple[str, int], ...]:
        """Firma canonica indipendente dall'ordine monomiale attivo."""
        return tuple(sorted(self.powers.items()))

    def ordered_items(self) -> Tuple[Tuple[str, int], ...]:
        position = {name: i for i, name in enumerate(state.ringvar)}
        return tuple(
            sorted(
                self.powers.items(),
                key=lambda item: (position.get(item[0], len(position)), item[0]),
            )
        )

    def to_list(self) -> list:
        return [self.coeff, dict(self.powers)]

    def __neg__(self) -> "Monomio":
        return Monomio(-self.coeff, dict(self.powers))

    def __mul__(self, other: object) -> "Monomio":
        if not isinstance(other, Monomio):
            return NotImplemented
        if self.is_zero() or other.is_zero():
            return Monomio(Fraction(0), {})
        powers = dict(self.powers)
        for variable, exponent in other.powers.items():
            powers[variable] = powers.get(variable, 0) + exponent
        return Monomio(self.coeff * other.coeff, powers)

    def __pow__(self, exponent: int) -> "Monomio":
        n = int(exponent)
        if n < 0:
            raise ValueError("Esponenti negativi non supportati nei monomi.")
        if n == 0:
            if self.is_zero():
                raise ValueError("0^0 non è definito nel DSL.")
            return Monomio(Fraction(1), {})
        if self.is_zero():
            return Monomio(Fraction(0), {})
        return Monomio(
            self.coeff**n,
            {variable: power * n for variable, power in self.powers.items()},
        )

    def __str__(self) -> str:
        if self.is_zero():
            return "0"
        if not self.powers:
            return str(self.coeff)

        core = "*".join(
            variable if exponent == 1 else f"{variable}^{exponent}"
            for variable, exponent in self.ordered_items()
        )
        if self.coeff == 1:
            return core
        if self.coeff == -1:
            return f"-{core}"
        return f"{self.coeff}*{core}"

    def __repr__(self) -> str:
        return f"Monomio(coeff={self.coeff!r}, powers={dict(self.signature())!r})"


def isMonGreater(a: Monomio, b: Monomio) -> bool:
    return a.order_key() > b.order_key()


def isGreater(a: str, b: str) -> bool:
    return isMonGreater(
        Monomio(Fraction(1), {a: 1}),
        Monomio(Fraction(1), {b: 1}),
    )


def sort_monomials(monomials: Iterable[Monomio]) -> list[Monomio]:
    return sorted(list(monomials), key=lambda m: m.order_key(), reverse=True)
