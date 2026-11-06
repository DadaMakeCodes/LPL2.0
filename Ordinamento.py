"""Ordini monomiali e algoritmo di Buchberger.

Il nome del modulo è mantenuto per compatibilità con il progetto originario.
Le operazioni usano aritmetica esatta tramite ``fractions.Fraction``.
"""

from __future__ import annotations

from fractions import Fraction
import heapq
from itertools import count
from typing import Iterable, Optional

from monomial import Monomio
from polynomial import Polinomio


def isGreater(a: Monomio, b: Monomio) -> bool:
    """Confronta soltanto la parte monomiale, ignorando il coefficiente."""
    return a.order_key() > b.order_key()


def sort_monomials(monomials: Iterable[Monomio]) -> list[Monomio]:
    return sorted(list(monomials), key=lambda monomial: monomial.order_key(), reverse=True)


def normal_pol_form(polynomial: Polinomio) -> Polinomio:
    return Polinomio(sort_monomials(polynomial.terms))


def lead_term(polynomial: Polinomio) -> Optional[Monomio]:
    if polynomial.is_zero():
        return None
    return max(polynomial.terms, key=lambda monomial: monomial.order_key())


def lead_coeff(polynomial: Polinomio) -> Optional[Fraction]:
    term = lead_term(polynomial)
    return None if term is None else term.coeff


def lead_monomial(polynomial: Polinomio) -> Optional[Monomio]:
    term = lead_term(polynomial)
    return None if term is None else Monomio(Fraction(1), term.powers)


def is_divisible_mons(dividend: Monomio, divisor: Monomio) -> bool:
    """Vero quando la parte monomiale di ``divisor`` divide ``dividend``."""
    if dividend.is_zero() or divisor.is_zero():
        return False
    return all(
        dividend.powers.get(variable, 0) >= exponent
        for variable, exponent in divisor.powers.items()
    )


def division_mon(dividend: Monomio, divisor: Monomio) -> Monomio:
    if divisor.is_zero():
        raise ZeroDivisionError("Divisione per il monomio zero.")
    if not is_divisible_mons(dividend, divisor):
        raise ValueError(f"Il monomio {divisor} non divide {dividend}.")
    powers = {
        variable: exponent - divisor.powers.get(variable, 0)
        for variable, exponent in dividend.powers.items()
        if exponent - divisor.powers.get(variable, 0) > 0
    }
    return Monomio(dividend.coeff / divisor.coeff, powers)


def is_reducible_by(polynomial: Polinomio, reducer: Polinomio) -> bool:
    reducer_lt = lead_term(reducer)
    return reducer_lt is not None and any(
        is_divisible_mons(term, reducer_lt) for term in polynomial.terms
    )


def reduce_pol_by_pol(polynomial: Polinomio, reducer: Polinomio) -> Polinomio:
    return normal_form(polynomial, [reducer])


def normal_form(polynomial: Polinomio, basis: Iterable[Polinomio]) -> Polinomio:
    """Resto della divisione multivariata rispetto alla lista ``basis``."""
    divisors = [g for g in basis if not g.is_zero()]
    divisors = order_pols(divisors)
    pending = polynomial
    remainder = Polinomio.zero()

    while not pending.is_zero():
        pending_lt = lead_term(pending)
        assert pending_lt is not None

        reduced = False
        for divisor in divisors:
            divisor_lt = lead_term(divisor)
            assert divisor_lt is not None
            if is_divisible_mons(pending_lt, divisor_lt):
                quotient = division_mon(pending_lt, divisor_lt)
                pending = pending - Polinomio.from_monom(quotient) * divisor
                reduced = True
                break

        if not reduced:
            leading_polynomial = Polinomio.from_monom(pending_lt)
            remainder = remainder + leading_polynomial
            pending = pending - leading_polynomial

    return normal_pol_form(remainder)


# Nome storico mantenuto per compatibilità.
def reduce_by_set(polynomial: Polinomio, basis: Iterable[Polinomio]) -> Polinomio:
    return normal_form(polynomial, basis)


def gcd_mon(a: Monomio, b: Monomio) -> Monomio:
    common = set(a.powers) & set(b.powers)
    return Monomio(
        Fraction(1),
        {variable: min(a.powers[variable], b.powers[variable]) for variable in common},
    )


def are_coprime(a: Monomio, b: Monomio) -> bool:
    return not gcd_mon(a, b).powers


def mcm_mon(a: Monomio, b: Monomio) -> Monomio:
    variables = set(a.powers) | set(b.powers)
    return Monomio(
        Fraction(1),
        {
            variable: max(a.powers.get(variable, 0), b.powers.get(variable, 0))
            for variable in variables
        },
    )


def sPol(f: Polinomio, g: Polinomio) -> Polinomio:
    f_lt = lead_term(f)
    g_lt = lead_term(g)
    if f_lt is None or g_lt is None:
        return Polinomio.zero()
    common = mcm_mon(f_lt, g_lt)
    left = Polinomio.from_monom(division_mon(common, f_lt)) * f
    right = Polinomio.from_monom(division_mon(common, g_lt)) * g
    return normal_pol_form(left - right)


# Alias più idiomatico.
s_polynomial = sPol


def total_degree(monomial: Monomio) -> int:
    return sum(monomial.powers.values())


def poly_degree(polynomial: Polinomio) -> int:
    return -1 if polynomial.is_zero() else max(total_degree(m) for m in polynomial.terms)


def _sugar_degree(i: int, j: int, basis: list[Polinomio], sugars: list[int]) -> int:
    left = lead_term(basis[i])
    right = lead_term(basis[j])
    assert left is not None and right is not None
    common_degree = total_degree(mcm_mon(left, right))
    return max(
        common_degree - total_degree(left) + sugars[i],
        common_degree - total_degree(right) + sugars[j],
    )


def make_monic(polynomial: Polinomio) -> Polinomio:
    coefficient = lead_coeff(polynomial)
    if coefficient is None:
        return polynomial
    return polynomial.scalar_mul(Fraction(1, 1) / coefficient)


def _deduplicate(polynomials: Iterable[Polinomio]) -> list[Polinomio]:
    result: list[Polinomio] = []
    for polynomial in polynomials:
        if polynomial.is_zero():
            continue
        if not any(polynomial == previous for previous in result):
            result.append(polynomial)
    return result


def order_pols(polynomials: Iterable[Polinomio]) -> list[Polinomio]:
    def key(polynomial: Polinomio):
        leading = lead_term(polynomial)
        if leading is None:
            return ((), "")
        return (leading.order_key(), str(polynomial))

    return sorted(list(polynomials), key=key, reverse=True)


def grobner_basis(generators: Iterable[Polinomio]) -> list[Polinomio]:
    """Calcola una base di Gröbner con Buchberger e strategia sugar.

    Viene applicato il criterio del prodotto: una coppia con monomi principali
    coprimi ha S-polinomio che si riduce a zero e può essere saltata.
    """
    basis = _deduplicate(make_monic(p) for p in generators if not p.is_zero())
    if not basis:
        return []

    sugars = [poly_degree(polynomial) for polynomial in basis]
    queue: list[tuple[int, int, int, int]] = []
    sequence = count()

    def enqueue(i: int, j: int) -> None:
        heapq.heappush(
            queue,
            (_sugar_degree(i, j, basis, sugars), next(sequence), i, j),
        )

    for i in range(len(basis)):
        for j in range(i + 1, len(basis)):
            enqueue(i, j)

    while queue:
        sugar, _, i, j = heapq.heappop(queue)
        left_lt = lead_term(basis[i])
        right_lt = lead_term(basis[j])
        assert left_lt is not None and right_lt is not None

        if are_coprime(left_lt, right_lt):
            continue

        remainder = normal_form(sPol(basis[i], basis[j]), basis)
        if remainder.is_zero():
            continue
        remainder = make_monic(remainder)
        if any(remainder == existing for existing in basis):
            continue

        new_index = len(basis)
        basis.append(remainder)
        sugars.append(sugar)
        for old_index in range(new_index):
            enqueue(old_index, new_index)

    return order_pols(basis)


def reduced_grobner_basis(generators: Iterable[Polinomio]) -> list[Polinomio]:
    """Restituisce la base di Gröbner ridotta e monica."""
    basis = [make_monic(p) for p in grobner_basis(generators) if not p.is_zero()]
    if not basis:
        return []

    # Elimina elementi il cui monomio principale è multiplo di quello di un altro.
    minimal: list[Polinomio] = []
    for index, polynomial in enumerate(basis):
        leading = lead_term(polynomial)
        assert leading is not None
        redundant = False
        for other_index, other in enumerate(basis):
            if index == other_index:
                continue
            other_leading = lead_term(other)
            assert other_leading is not None
            if is_divisible_mons(leading, other_leading):
                # A parità di monomio principale, conserva un solo rappresentante.
                if leading.signature() != other_leading.signature() or other_index < index:
                    redundant = True
                    break
        if not redundant:
            minimal.append(polynomial)

    reduced: list[Polinomio] = []
    for index, polynomial in enumerate(minimal):
        others = minimal[:index] + minimal[index + 1 :]
        remainder = normal_form(polynomial, others)
        if not remainder.is_zero():
            remainder = make_monic(remainder)
            if not any(remainder == previous for previous in reduced):
                reduced.append(remainder)

    return order_pols(reduced)


def normalized_form(polynomials: Iterable[Polinomio]) -> list[Polinomio]:
    return [make_monic(p) for p in polynomials]


def remove_zero_polys(polynomials: Iterable[Polinomio]) -> list[Polinomio]:
    return [p for p in polynomials if not p.is_zero()]


def polinomial_sum(polynomials: Iterable[Polinomio]) -> Polinomio:
    result = Polinomio.zero()
    for polynomial in polynomials:
        result = result + polynomial
    return normal_pol_form(result)


def polinomial_product(polynomials: Iterable[Polinomio]) -> Polinomio:
    result = Polinomio.const(1)
    for polynomial in polynomials:
        result = result * polynomial
    return normal_pol_form(result)


def numerated_variables(prefix: str, count_value: int) -> list[str]:
    return [f"{prefix}{index + 1}" for index in range(int(count_value))]
