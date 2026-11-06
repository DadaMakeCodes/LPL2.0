"""Valori specifici del dominio: anelli, polinomi e ideali."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Literal

import Ordinamento
from monomial import Monomio
from polynomial import Polinomio
import state

BasisKind = Literal["generators", "grobner", "reduced"]


@dataclass(frozen=True, slots=True)
class PolynomialRing:
    domain: str
    variables: tuple[str, ...]
    order: str = "lex"

    def __post_init__(self) -> None:
        domain = self.domain.lstrip("\\").upper()
        if domain == "QQ": #EDIT : da togliere
            domain = "Q"
        if domain not in {"Q", "R"}:
            raise ValueError(
                f"Dominio {self.domain!r} non supportato. Usare Q (o R come etichetta)."
            )

        variables = tuple(str(v).strip() for v in self.variables)
        if not variables:
            raise ValueError("L'anello deve avere almeno una variabile.")
        invalid = [
            variable
            for variable in variables
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable)
        ]
        if invalid:
            raise ValueError(f"Nomi di variabile non validi: {invalid}")
        if len(set(variables)) != len(variables):
            raise ValueError(f"Variabili duplicate: {variables}")

        normalized_order = self.order.lower()
        aliases = {"grlex": "deglex", "grevlex": "degrevlex"}
        normalized_order = aliases.get(normalized_order, normalized_order)
        if normalized_order not in state.SUPPORTED_ORDERS:
            raise ValueError(
                f"Ordine {self.order!r} non supportato. "
                f"Usare {', '.join(state.SUPPORTED_ORDERS)}."
            )

        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "variables", variables)
        object.__setattr__(self, "order", normalized_order)

    @classmethod
    def parse(cls, source: str, order: str = "lex") -> "PolynomialRing":
        match = re.fullmatch(r"\s*\\?([A-Za-z]+)\s*\[\s*(.*?)\s*\]\s*", source)
        if not match:
            raise ValueError(
                f"Formato anello non valido: {source!r}; atteso Q[x,y]."
            )
        variables = tuple(part.strip() for part in match.group(2).split(","))
        return cls(match.group(1), variables, order)

    def activate(self) -> None:
        state.configure_ring(self.variables, self.order)

    def parse_poly(self, source: str) -> Polinomio:
        self.activate()
        return Polinomio.parse(source.strip())

    def compatible_with(self, other: "PolynomialRing") -> bool:
        return self.domain == other.domain and self.variables == other.variables

    def with_order(self, order: str) -> "PolynomialRing":
        return PolynomialRing(self.domain, self.variables, order)

    def __str__(self) -> str:
        return f"{self.domain}[{','.join(self.variables)}]/{self.order}"


@dataclass(frozen=True, slots=True, eq=False)
class Ideal:
    ring: PolynomialRing
    generators: tuple[Polinomio, ...]
    basis_kind: BasisKind = "generators"

    def __init__(
        self,
        ring: PolynomialRing,
        generators: Iterable[Polinomio],
        basis_kind: BasisKind = "generators",
    ):
        ring.activate()
        unique: list[Polinomio] = []
        for polynomial in generators:
            used_variables = {
                variable
                for monomial in polynomial.terms
                for variable in monomial.powers
            }
            extra = sorted(used_variables - set(ring.variables))
            if extra:
                raise ValueError(
                    f"Il generatore {polynomial} usa variabili fuori da {ring}: {extra}."
                )
            if polynomial.is_zero():
                continue
            if not any(polynomial == previous for previous in unique):
                unique.append(polynomial)
        object.__setattr__(self, "ring", ring)
        object.__setattr__(self, "generators", tuple(unique))
        object.__setattr__(self, "basis_kind", basis_kind)

    @classmethod
    def from_strings(
        cls,
        ring: PolynomialRing,
        generators: Iterable[str],
    ) -> "Ideal":
        return cls(ring, (ring.parse_poly(source) for source in generators))

    def _activate(self) -> None:
        self.ring.activate()

    def _require_compatible(self, other: "Ideal") -> None:
        if not self.ring.compatible_with(other.ring):
            raise ValueError(
                f"Ideali in anelli incompatibili: {self.ring} e {other.ring}."
            )

    def is_zero(self) -> bool:
        return not self.generators

    def groebner(self) -> "Ideal":
        self._activate()
        return Ideal(
            self.ring,
            Ordinamento.grobner_basis(self.generators),
            basis_kind="grobner",
        )

    def reduced(self) -> "Ideal":
        self._activate()
        return Ideal(
            self.ring,
            Ordinamento.reduced_grobner_basis(self.generators),
            basis_kind="reduced",
        )

    def normal_form(self, polynomial: Polinomio) -> Polinomio:
        self._activate()
        return Ordinamento.normal_form(polynomial, self.reduced().generators)

    def contains(self, polynomial: Polinomio) -> bool:
        return self.normal_form(polynomial).is_zero()

    def sum(self, other: "Ideal", *, reduce_result: bool = True) -> "Ideal":
        self._require_compatible(other)
        result = Ideal(self.ring, (*self.generators, *other.generators))
        return result.reduced() if reduce_result else result

    def product(self, other: "Ideal", *, reduce_result: bool = True) -> "Ideal":
        self._require_compatible(other)
        products = (
            Ordinamento.normal_pol_form(left * right)
            for left in self.generators
            for right in other.generators
        )
        result = Ideal(self.ring, products)
        return result.reduced() if reduce_result else result

    def subset_of(self, other: "Ideal") -> bool:
        self._require_compatible(other)
        other_basis = other.reduced()
        return all(other_basis.contains(generator) for generator in self.generators)

    def equivalent(self, other: "Ideal") -> bool:
        self._require_compatible(other)
        return self.subset_of(other) and other.subset_of(self)

    def leading_terms(self) -> tuple[Monomio, ...]:
        self._activate()
        return tuple(
            term
            for polynomial in self.generators
            if (term := Ordinamento.lead_term(polynomial)) is not None
        )

    def used_variables(self) -> tuple[str, ...]:
        used = {
            variable
            for polynomial in self.generators
            for monomial in polynomial.terms
            for variable in monomial.powers
        }
        return tuple(v for v in self.ring.variables if v in used)

    def describe(self) -> str:
        self._activate()
        title = {
            "generators": "insieme di generatori",
            "grobner": "base di Gröbner",
            "reduced": "base di Gröbner ridotta",
        }[self.basis_kind]
        lines = [
            f"Ideale in {self.ring}",
            f"Rappresentazione: {title}",
            f"Numero di generatori: {len(self.generators)}",
        ]
        if not self.generators:
            lines.append("  <0>")
            return "\n".join(lines)
        for index, polynomial in enumerate(self.generators, start=1):
            leading = Ordinamento.lead_term(polynomial)
            lines.append(f"  g{index} = {polynomial}    LT={leading}")
        return "\n".join(lines)

    @staticmethod
    def _dot_escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')

    def to_dot(self) -> str:
        """Crea una visualizzazione Graphviz senza dipendenze esterne."""
        self._activate()
        lines = [
            "digraph PolynomialIdeal {",
            "  rankdir=LR;",
            '  graph [fontname="Helvetica"];',
            '  node [fontname="Helvetica"];',
            f'  ideal [shape=box, style="rounded", label="Ideal\\n{self._dot_escape(str(self.ring))}\\n{self.basis_kind}"];',
        ]

        for variable in self.ring.variables:
            lines.append(
                f'  var_{variable} [shape=ellipse, label="{self._dot_escape(variable)}"];'
            )

        if not self.generators:
            lines.append('  zero [shape=plaintext, label="0"];')
            lines.append("  ideal -> zero;")
        else:
            for index, polynomial in enumerate(self.generators, start=1):
                leading = Ordinamento.lead_term(polynomial)
                poly_label = self._dot_escape(f"g{index}: {polynomial}")
                lines.append(f'  g{index} [shape=box, label="{poly_label}"];')
                lines.append(f"  ideal -> g{index};")
                if leading is not None:
                    leading_label = self._dot_escape(f"LT: {leading}")
                    lines.append(
                        f'  lt{index} [shape=diamond, label="{leading_label}"];'
                    )
                    lines.append(f"  g{index} -> lt{index};")
                    for variable, exponent in leading.ordered_items():
                        lines.append(
                            f'  lt{index} -> var_{variable} [label="{exponent}"];'
                        )
        lines.append("}")
        return "\n".join(lines) + "\n"

    def write_dot(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_dot(), encoding="utf-8")
        return destination

    def __str__(self) -> str:
        if not self.generators:
            return "<0>"
        return "<" + ", ".join(str(g) for g in self.generators) + ">"

    def __repr__(self) -> str:
        return (
            f"Ideal(ring={self.ring!r}, generators={self.generators!r}, "
            f"basis_kind={self.basis_kind!r})"
        )
