"""Compatibilità con il parser di anelli e ideali del progetto originario."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domain import Ideal, PolynomialRing
from polynomial import Polinomio


def _split_top_level_commas(source: str) -> list[str]:
    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    for character in source:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("Parentesi non bilanciate.")
        if character == "," and depth == 0:
            part = "".join(buffer).strip()
            if part:
                parts.append(part)
            buffer.clear()
        else:
            buffer.append(character)
    if depth != 0:
        raise ValueError("Parentesi non bilanciate.")
    tail = "".join(buffer).strip()
    if tail:
        parts.append(tail)
    return parts


@dataclass(frozen=True, slots=True)
class Ambiente:
    ring: PolynomialRing

    @classmethod
    def from_ring_string(cls, ring_source: str, order: str = "lex") -> "Ambiente":
        return cls(PolynomialRing.parse(ring_source, order=order))

    def parse_poly(self, source: str) -> Polinomio:
        return self.ring.parse_poly(source)

    def parse_ideal(self, source: str) -> "Ideale":
        return Ideale.parse(source, env=self)


@dataclass(frozen=True, slots=True)
class Ideale:
    env: Ambiente
    generators: tuple[Polinomio, ...]

    @classmethod
    def parse(cls, source: str, env: Ambiente) -> "Ideale":
        raw = source.strip()
        if not (raw.startswith("<") and raw.endswith(">")):
            raise ValueError(
                f"Ideale non valido: {source!r}; atteso <p1,...,pn>."
            )
        inside = raw[1:-1].strip()
        if not inside or inside == "0":
            return cls(env, ())
        generators = tuple(env.parse_poly(item) for item in _split_top_level_commas(inside))
        return cls(env, generators)

    def as_domain_value(self) -> Ideal:
        return Ideal(self.env.ring, self.generators)

    def __str__(self) -> str:
        return str(self.as_domain_value())
