"""API procedurale per operazioni su ideali.

Non esegue più input interattivo all'importazione: l'interfaccia utente è nel
DSL e nel modulo ``main.py``.
"""

from __future__ import annotations

from typing import Iterable

import Ordinamento
from domain import Ideal, PolynomialRing
from polynomial import Polinomio


def Isum(left: Ideal, right: Ideal) -> Ideal:
    return left.sum(right)


def Imul(left: Ideal, right: Ideal) -> Ideal:
    return left.product(right)


def isEqual(left: Ideal, right: Ideal) -> bool:
    return left.equivalent(right)


def is_pol_in_ideal(polynomial: Polinomio, ideal: Ideal) -> bool:
    return ideal.contains(polynomial)


def isIinJ(left: Ideal, right: Ideal) -> bool:
    return left.subset_of(right)


def isEqual2(left: Ideal, right: Ideal) -> bool:
    return left.equivalent(right)


# Funzioni di compatibilità per chi usa ancora liste di polinomi.
def list_sum(
    left: Iterable[Polinomio],
    right: Iterable[Polinomio],
) -> list[Polinomio]:
    return Ordinamento.reduced_grobner_basis([*left, *right])


def list_product(
    left: Iterable[Polinomio],
    right: Iterable[Polinomio],
) -> list[Polinomio]:
    return [a * b for a in left for b in right]
