"""Configurazione globale dell'anello polinomiale e dell'ordine monomiale.

Il modulo mantiene una piccola configurazione globale per compatibilità con il
nucleo algebrico originario. I valori di dominio ``PolynomialRing`` riattivano
la propria configurazione prima di ogni calcolo, quindi ideali appartenenti ad
anelli differenti non vengono confrontati accidentalmente.
"""

from __future__ import annotations

from typing import Iterable

SUPPORTED_ORDERS = ("lex", "deglex", "degrevlex")

ringvar: list[str] = ["x", "y", "z"]
order_name: str = "lex"

# Compatibilità con la versione precedente, che esponeva una matrice M.
# Il nuovo comparatore usa direttamente ``order_name``.
M: list[list[float]] = []


def configure_ring(variables: Iterable[str], order: str = "lex") -> None:
    """Imposta variabili e ordine, validando la configurazione."""
    global ringvar, order_name, M

    vars_list = [str(v).strip() for v in variables]
    if not vars_list:
        raise ValueError("L'anello deve contenere almeno una variabile.")
    if any(not v for v in vars_list):
        raise ValueError("I nomi delle variabili non possono essere vuoti.")
    if len(set(vars_list)) != len(vars_list):
        raise ValueError(f"Variabili duplicate nell'anello: {vars_list}")

    normalized = order.lower()
    aliases = {
        "grlex": "deglex",
        "gradedlex": "deglex",
        "grevlex": "degrevlex",
        "degrev": "degrevlex",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_ORDERS:
        raise ValueError(
            f"Ordine monomiale non supportato: {order!r}. "
            f"Valori ammessi: {', '.join(SUPPORTED_ORDERS)}"
        )

    ringvar = vars_list
    order_name = normalized
    M = []


def monomial_key(exponents: Iterable[int]) -> tuple:
    """Restituisce una chiave confrontabile per l'ordine monomiale attivo.

    Le chiavi più grandi corrispondono ai monomi più grandi.
    """
    exps = tuple(int(e) for e in exponents)
    if len(exps) != len(ringvar):
        raise ValueError(
            f"Vettore degli esponenti lungo {len(exps)}, atteso {len(ringvar)}."
        )

    if order_name == "lex":
        return exps
    if order_name == "deglex":
        return (sum(exps), exps)
    if order_name == "degrevlex":
        # A parità di grado, nell'ultima variabile in cui differiscono è
        # maggiore il monomio con esponente minore.
        return (sum(exps), tuple(-e for e in reversed(exps)))
    raise AssertionError(f"Ordine interno inatteso: {order_name}")


# API di compatibilità con il vecchio progetto.
def lexGraph() -> list[list[float]]:
    n = len(ringvar)
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def Matrix_Prod(
    A: list[list[float]], B: list[list[float]]
) -> list[list[float]]:
    if not A or not B:
        return []
    if len(A[0]) != len(B):
        raise ValueError("Dimensioni incompatibili per il prodotto di matrici.")
    return [
        [sum(A[i][k] * B[k][j] for k in range(len(B))) for j in range(len(B[0]))]
        for i in range(len(A))
    ]


def Matrix_degLex() -> list[list[float]]:
    n = len(ringvar)
    return [[1.0] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def Matrix_AntiLex() -> list[list[float]]:
    n = len(ringvar)
    return [[1.0 if j == n - 1 - i else 0.0 for j in range(n)] for i in range(n)]


def Matrix_AntiDegLex() -> list[list[float]]:
    return Matrix_Prod(Matrix_AntiLex(), Matrix_degLex())
