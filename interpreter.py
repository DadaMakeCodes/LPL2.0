"""Interprete environment/store-based per IdealDSL."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Callable, TextIO, TypeAlias

import Ordinamento
from domain import Ideal, PolynomialRing
from dsl_ast import (
    Assert,
    Assignment,
    Binary,
    BoolLiteral,
    Call,
    Command,
    Expression,
    FunctionDeclaration,
    IdealLiteral,
    IfElse,
    IntLiteral,
    Let,
    PolynomialLiteral,
    Print,
    Program,
    Show,
    StringLiteral,
    Unary,
    VarDeclaration,
    Variable,
    Visualize,
    While,
)
from dsl_parser import parse_program
from polynomial import Polinomio


class IdealDSLError(Exception):
    """Errore semantico o di esecuzione del DSL."""


Value: TypeAlias = int | bool | str | Polinomio | Ideal
MemoryValue: TypeAlias = Value


@dataclass(frozen=True, slots=True)
class Loc:
    address: int


def _empty_store() -> Callable[[int], MemoryValue]:
    def lookup(address: int) -> MemoryValue:
        raise IdealDSLError(f"Locazione {address} non allocata.")

    return lookup


@dataclass(frozen=True, slots=True)
class StoreState:
    """Store funzionale più contatore della prossima locazione libera."""

    store: Callable[[int], MemoryValue] = field(default_factory=_empty_store)
    next_loc: int = 0

    def allocate(self, value: MemoryValue) -> tuple[Loc, "StoreState"]:
        location = Loc(self.next_loc)
        previous_store = self.store

        def updated_store(address: int) -> MemoryValue:
            if address == location.address:
                return value
            return previous_store(address)

        return location, StoreState(updated_store, self.next_loc + 1)

    def access(self, location: Loc | int) -> MemoryValue:
        address = location.address if isinstance(location, Loc) else int(location)
        return self.store(address)

    def update(self, location: Loc | int, value: MemoryValue) -> "StoreState":
        address = location.address if isinstance(location, Loc) else int(location)
        # Verifica che la cella esista prima di creare l'estensione funzionale.
        self.store(address)
        previous_store = self.store

        def updated_store(query: int) -> MemoryValue:
            if query == address:
                return value
            return previous_store(query)

        return StoreState(updated_store, self.next_loc)

    def deallocate_from(self, first_local_address: int) -> "StoreState":
        """Ripristina il puntatore dello stack per riusare le locazioni locali.

        Il vecchio store resta una funzione persistente, ma nessun ambiente
        raggiungibile conserva le locazioni locali. Una successiva allocazione
        alla stessa locazione ne sovrascrive funzionalmente il valore.
        """
        return StoreState(self.store, first_local_address)


@dataclass(frozen=True, slots=True)
class Builtin:
    name: str
    minimum_arity: int
    maximum_arity: int
    function: Callable[[tuple[Value, ...], "RuntimeContext"], Value]

    def invoke(self, arguments: tuple[Value, ...], context: "RuntimeContext") -> Value:
        count = len(arguments)
        if not self.minimum_arity <= count <= self.maximum_arity:
            expected = (
                str(self.minimum_arity)
                if self.minimum_arity == self.maximum_arity
                else f"{self.minimum_arity}..{self.maximum_arity}"
            )
            raise IdealDSLError(
                f"'{self.name}' richiede {expected} argomenti, ricevuti {count}."
            )
        try:
            return self.function(arguments, context)
        except IdealDSLError:
            raise
        except (ValueError, TypeError, ZeroDivisionError) as error:
            raise IdealDSLError(f"Errore in '{self.name}': {error}") from error


@dataclass(frozen=True, slots=True)
class Closure:
    declaration: FunctionDeclaration
    environment: "Environment"


DenotableValue: TypeAlias = Value | Loc | Builtin | Closure


def _empty_environment() -> Callable[[str], DenotableValue]:
    def lookup(name: str) -> DenotableValue:
        raise IdealDSLError(f"Identificatore non definito: '{name}'.")

    return lookup


@dataclass(frozen=True, slots=True)
class Environment:
    """Ambiente funzionale da identificatori a valori denotabili."""

    lookup_function: Callable[[str], DenotableValue] = field(
        default_factory=_empty_environment
    )

    def bind(self, name: str, value: DenotableValue) -> "Environment":
        previous_lookup = self.lookup_function

        def extended_lookup(query: str) -> DenotableValue:
            if query == name:
                return value
            return previous_lookup(query)

        return Environment(extended_lookup)

    def bind_many(self, values: dict[str, DenotableValue]) -> "Environment":
        frame = dict(values)
        previous_lookup = self.lookup_function

        def extended_lookup(query: str) -> DenotableValue:
            if query in frame:
                return frame[query]
            return previous_lookup(query)

        return Environment(extended_lookup)

    def lookup(self, name: str) -> DenotableValue:
        return self.lookup_function(name)


@dataclass(slots=True)
class RuntimeContext:
    ring: PolynomialRing | None = None
    output: TextIO = sys.stdout
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    max_loop_iterations: int = 10_000
    max_call_depth: int = 500

    def require_ring(self) -> PolynomialRing:
        if self.ring is None:
            raise IdealDSLError(
                "Prima di usare poly{...} o ideal{...} dichiarare un anello, "
                "per esempio: ring Q[x,y] order lex;"
            )
        return self.ring


# --------------------------- Value utilities ---------------------------
def value_type_name(value: object) -> str:
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "int"
    if type(value) is str:
        return "string"
    if isinstance(value, Polinomio):
        return "polynomial"
    if isinstance(value, Ideal):
        return "ideal"
    if isinstance(value, Closure):
        return "closure"
    if isinstance(value, Builtin):
        return "operator"
    if isinstance(value, Loc):
        return "location"
    return type(value).__name__


def format_value(value: Value) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    return str(value)


def describe_value(value: Value, context: RuntimeContext) -> str:
    if isinstance(value, Ideal):
        return value.describe()
    if isinstance(value, Polinomio):
        ring = context.require_ring()
        ring.activate()
        leading = Ordinamento.lead_term(value)
        return "\n".join(
            [
                f"Polinomio in {ring}",
                f"p = {value}",
                f"Numero di termini: {len(value.terms)}",
                f"Grado totale: {Ordinamento.poly_degree(value)}",
                f"Termine principale: {leading}",
            ]
        )
    return f"{value_type_name(value)}: {format_value(value)}"


def _expect_bool(value: Value, where: str) -> bool:
    if type(value) is not bool:
        raise IdealDSLError(
            f"{where} richiede un booleano, ricevuto {value_type_name(value)}."
        )
    return value


def _expect_int(value: Value, where: str) -> int:
    if type(value) is not int:
        raise IdealDSLError(
            f"{where} richiede un intero, ricevuto {value_type_name(value)}."
        )
    return value


def _expect_polynomial(value: Value, where: str) -> Polinomio:
    if not isinstance(value, Polinomio):
        raise IdealDSLError(
            f"{where} richiede un polinomio, ricevuto {value_type_name(value)}."
        )
    return value


def _expect_ideal(value: Value, where: str) -> Ideal:
    if not isinstance(value, Ideal):
        raise IdealDSLError(
            f"{where} richiede un ideale, ricevuto {value_type_name(value)}."
        )
    return value


def _expect_string(value: Value, where: str) -> str:
    if type(value) is not str:
        raise IdealDSLError(
            f"{where} richiede una stringa, ricevuto {value_type_name(value)}."
        )
    return value


# -------------------------- Primitive operators ------------------------
def _addition(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    left, right = arguments
    if type(left) is int and type(right) is int:
        return left + right
    if type(left) is str and type(right) is str:
        return left + right
    if isinstance(left, Polinomio) and isinstance(right, Polinomio):
        return left + right
    if isinstance(left, Ideal) and isinstance(right, Ideal):
        return left.sum(right)
    raise IdealDSLError(
        f"'+' non è definito per {value_type_name(left)} e {value_type_name(right)}."
    )


def _subtraction(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    left, right = arguments
    if type(left) is int and type(right) is int:
        return left - right
    if isinstance(left, Polinomio) and isinstance(right, Polinomio):
        return left - right
    raise IdealDSLError(
        f"'-' non è definito per {value_type_name(left)} e {value_type_name(right)}."
    )


def _multiplication(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    left, right = arguments
    if type(left) is int and type(right) is int:
        return left * right
    if isinstance(left, Polinomio) and isinstance(right, Polinomio):
        return left * right
    if type(left) is int and isinstance(right, Polinomio):
        return right.scalar_mul(left)
    if isinstance(left, Polinomio) and type(right) is int:
        return left.scalar_mul(right)
    if isinstance(left, Ideal) and isinstance(right, Ideal):
        return left.product(right)
    raise IdealDSLError(
        f"'*' non è definito per {value_type_name(left)} e {value_type_name(right)}."
    )


def _division(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    left, right = arguments
    left_int = _expect_int(left, "divisione")
    right_int = _expect_int(right, "divisione")
    if right_int == 0:
        raise IdealDSLError("Divisione per zero.")
    return left_int // right_int


def _modulo(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    left, right = arguments
    left_int = _expect_int(left, "modulo")
    right_int = _expect_int(right, "modulo")
    if right_int == 0:
        raise IdealDSLError("Modulo per zero.")
    return left_int % right_int


def _power(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    base, exponent_value = arguments
    exponent = _expect_int(exponent_value, "esponente")
    if exponent < 0:
        raise IdealDSLError("Gli esponenti negativi non sono supportati.")
    if type(base) is int:
        if base == 0 and exponent == 0:
            raise IdealDSLError("0^0 non è definito.")
        return base**exponent
    if isinstance(base, Polinomio):
        return base**exponent
    raise IdealDSLError(f"'^' non è definito per {value_type_name(base)}.")


def _unary_plus(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    (value,) = arguments
    if type(value) is int or isinstance(value, Polinomio):
        return value
    raise IdealDSLError(f"'u+' non è definito per {value_type_name(value)}.")


def _unary_minus(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    (value,) = arguments
    if type(value) is int:
        return -value
    if isinstance(value, Polinomio):
        return -value
    raise IdealDSLError(f"'u-' non è definito per {value_type_name(value)}.")


def _not(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return not _expect_bool(arguments[0], "not")


def _and(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_bool(arguments[0], "and") and _expect_bool(arguments[1], "and")


def _or(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_bool(arguments[0], "or") or _expect_bool(arguments[1], "or")


def _equals(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    left, right = arguments
    if isinstance(left, Ideal) and isinstance(right, Ideal):
        return left.equivalent(right)
    if type(left) is not type(right):
        return False
    return left == right


def _not_equals(arguments: tuple[Value, ...], context: RuntimeContext) -> Value:
    return not bool(_equals(arguments, context))


def _comparison(operator: str):
    def compare(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
        left, right = arguments
        if type(left) is int and type(right) is int:
            pass
        elif type(left) is str and type(right) is str:
            pass
        else:
            raise IdealDSLError(
                f"'{operator}' richiede due interi o due stringhe, ricevuti "
                f"{value_type_name(left)} e {value_type_name(right)}."
            )
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        raise AssertionError(operator)

    return compare


# -------------------------- Domain primitives --------------------------
def _groebner(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_ideal(arguments[0], "groebner").groebner()


def _reduced(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_ideal(arguments[0], "reduced").reduced()


def _contains(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    ideal = _expect_ideal(arguments[0], "contains")
    polynomial = _expect_polynomial(arguments[1], "contains")
    return ideal.contains(polynomial)


def _normal_form(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    polynomial = _expect_polynomial(arguments[0], "normalform")
    ideal = _expect_ideal(arguments[1], "normalform")
    return ideal.normal_form(polynomial)


def _ideal_sum(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_ideal(arguments[0], "ideal_sum").sum(
        _expect_ideal(arguments[1], "ideal_sum")
    )


def _ideal_product(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_ideal(arguments[0], "ideal_product").product(
        _expect_ideal(arguments[1], "ideal_product")
    )


def _subset(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_ideal(arguments[0], "subset").subset_of(
        _expect_ideal(arguments[1], "subset")
    )


def _equal_ideals(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return _expect_ideal(arguments[0], "equal").equivalent(
        _expect_ideal(arguments[1], "equal")
    )


def _generator_count(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return len(_expect_ideal(arguments[0], "generator_count").generators)


def _basis_size(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return len(_expect_ideal(arguments[0], "basis_size").reduced().generators)


def _leading_term(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    polynomial = _expect_polynomial(arguments[0], "leadterm")
    term = Ordinamento.lead_term(polynomial)
    return Polinomio.zero() if term is None else Polinomio.from_monom(term)


def _s_polynomial(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    left = _expect_polynomial(arguments[0], "spoly")
    right = _expect_polynomial(arguments[1], "spoly")
    return Ordinamento.s_polynomial(left, right)


def _degree(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    return Ordinamento.poly_degree(_expect_polynomial(arguments[0], "degree"))


def _is_zero(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    value = arguments[0]
    if type(value) is int:
        return value == 0
    if isinstance(value, Polinomio):
        return value.is_zero()
    if isinstance(value, Ideal):
        return value.is_zero()
    raise IdealDSLError(f"is_zero non è definito per {value_type_name(value)}.")


def _change_order(arguments: tuple[Value, ...], _: RuntimeContext) -> Value:
    ideal = _expect_ideal(arguments[0], "change_order")
    order = _expect_string(arguments[1], "change_order")
    changed = Ideal(ideal.ring.with_order(order), ideal.generators)
    return changed.reduced()


def _ring_name(arguments: tuple[Value, ...], context: RuntimeContext) -> Value:
    if arguments:
        ideal = _expect_ideal(arguments[0], "ring_name")
        return str(ideal.ring)
    return str(context.require_ring())


def _builtin(name: str, arity: int, function) -> Builtin:
    return Builtin(name, arity, arity, function)


def create_initial_environment() -> Environment:
    primitives: dict[str, Builtin] = {
        "+": _builtin("+", 2, _addition),
        "-": _builtin("-", 2, _subtraction),
        "*": _builtin("*", 2, _multiplication),
        "/": _builtin("/", 2, _division),
        "%": _builtin("%", 2, _modulo),
        "^": _builtin("^", 2, _power),
        "u+": _builtin("u+", 1, _unary_plus),
        "u-": _builtin("u-", 1, _unary_minus),
        "not": _builtin("not", 1, _not),
        "and": _builtin("and", 2, _and),
        "or": _builtin("or", 2, _or),
        "==": _builtin("==", 2, _equals),
        "!=": _builtin("!=", 2, _not_equals),
        "<": _builtin("<", 2, _comparison("<")),
        "<=": _builtin("<=", 2, _comparison("<=")),
        ">": _builtin(">", 2, _comparison(">")),
        ">=": _builtin(">=", 2, _comparison(">=")),
        "groebner": _builtin("groebner", 1, _groebner),
        "reduced": _builtin("reduced", 1, _reduced),
        "contains": _builtin("contains", 2, _contains),
        "normalform": _builtin("normalform", 2, _normal_form),
        "ideal_sum": _builtin("ideal_sum", 2, _ideal_sum),
        "ideal_product": _builtin("ideal_product", 2, _ideal_product),
        "subset": _builtin("subset", 2, _subset),
        "equal": _builtin("equal", 2, _equal_ideals),
        "generator_count": _builtin("generator_count", 1, _generator_count),
        "basis_size": _builtin("basis_size", 1, _basis_size),
        "leadterm": _builtin("leadterm", 1, _leading_term),
        "spoly": _builtin("spoly", 2, _s_polynomial),
        "degree": _builtin("degree", 1, _degree),
        "is_zero": _builtin("is_zero", 1, _is_zero),
        "change_order": _builtin("change_order", 2, _change_order),
        "ring_name": Builtin("ring_name", 0, 1, _ring_name),
    }
    return Environment().bind_many(primitives)


# ----------------------------- Evaluation ------------------------------
def _invoke_named(
    name: str,
    arguments: tuple[Value, ...],
    environment: Environment,
    state: StoreState,
    context: RuntimeContext,
    call_depth: int,
) -> Value:
    denotation = environment.lookup(name)
    if isinstance(denotation, Builtin):
        return denotation.invoke(arguments, context)
    if isinstance(denotation, Closure):
        declaration = denotation.declaration
        if len(arguments) != len(declaration.parameters):
            raise IdealDSLError(
                f"La funzione '{name}' richiede {len(declaration.parameters)} "
                f"argomenti, ricevuti {len(arguments)}."
            )
        if call_depth >= context.max_call_depth:
            raise IdealDSLError(
                f"Profondità massima di chiamata ({context.max_call_depth}) superata."
            )

        call_environment = denotation.environment.bind(declaration.name, denotation)
        call_state = state
        parameter_bindings: dict[str, Loc] = {}
        for parameter, value in zip(declaration.parameters, arguments):
            location, call_state = call_state.allocate(value)
            parameter_bindings[parameter] = location
        call_environment = call_environment.bind_many(parameter_bindings)
        return evaluate_expression(
            declaration.body,
            call_environment,
            call_state,
            context,
            call_depth=call_depth + 1,
        )
    raise IdealDSLError(
        f"'{name}' non è invocabile: denota {value_type_name(denotation)}."
    )


def evaluate_expression(
    expression: Expression,
    environment: Environment,
    state: StoreState,
    context: RuntimeContext,
    *,
    call_depth: int = 0,
) -> Value:
    match expression:
        case IntLiteral(value):
            return value
        case BoolLiteral(value):
            return value
        case StringLiteral(value):
            return value
        case PolynomialLiteral(source):
            return context.require_ring().parse_poly(source)
        case IdealLiteral(generators):
            ring = context.require_ring()
            return Ideal.from_strings(ring, generators)
        case Variable(name):
            denotation = environment.lookup(name)
            if isinstance(denotation, Loc):
                return state.access(denotation)
            if isinstance(denotation, (Closure, Builtin)):
                raise IdealDSLError(
                    f"'{name}' denota una {value_type_name(denotation)} e può essere "
                    "usato soltanto in posizione di chiamata."
                )
            return denotation
        case Let(name, value_expression, body):
            value = evaluate_expression(
                value_expression, environment, state, context, call_depth=call_depth
            )
            return evaluate_expression(
                body,
                environment.bind(name, value),
                state,
                context,
                call_depth=call_depth,
            )
        case Unary(operator, operand):
            value = evaluate_expression(
                operand, environment, state, context, call_depth=call_depth
            )
            return _invoke_named(
                "u+" if operator == "+" else "u-" if operator == "-" else operator,
                (value,),
                environment,
                state,
                context,
                call_depth,
            )
        case Binary("and", left_expression, right_expression):
            left = _expect_bool(
                evaluate_expression(
                    left_expression, environment, state, context, call_depth=call_depth
                ),
                "and",
            )
            if not left:
                return False
            right = evaluate_expression(
                right_expression, environment, state, context, call_depth=call_depth
            )
            return _invoke_named(
                "and", (left, right), environment, state, context, call_depth
            )
        case Binary("or", left_expression, right_expression):
            left = _expect_bool(
                evaluate_expression(
                    left_expression, environment, state, context, call_depth=call_depth
                ),
                "or",
            )
            if left:
                return True
            right = evaluate_expression(
                right_expression, environment, state, context, call_depth=call_depth
            )
            return _invoke_named(
                "or", (left, right), environment, state, context, call_depth
            )
        case Binary(operator, left_expression, right_expression):
            left = evaluate_expression(
                left_expression, environment, state, context, call_depth=call_depth
            )
            right = evaluate_expression(
                right_expression, environment, state, context, call_depth=call_depth
            )
            return _invoke_named(
                operator,
                (left, right),
                environment,
                state,
                context,
                call_depth,
            )
        case Call(name, argument_expressions):
            arguments = tuple(
                evaluate_expression(
                    argument,
                    environment,
                    state,
                    context,
                    call_depth=call_depth,
                )
                for argument in argument_expressions
            )
            return _invoke_named(
                name, arguments, environment, state, context, call_depth
            )
        case _:
            raise IdealDSLError(f"Espressione AST non riconosciuta: {expression!r}")


def execute_block(
    commands: tuple[Command, ...],
    outer_environment: Environment,
    state: StoreState,
    context: RuntimeContext,
) -> tuple[Environment, StoreState]:
    saved_next_location = state.next_loc
    _, block_state = execute_commands(commands, outer_environment, state, context)
    # Le estensioni dell'ambiente sono locali; gli aggiornamenti a celle esterne
    # restano, mentre le celle allocate nel blocco vengono deallocate.
    return outer_environment, block_state.deallocate_from(saved_next_location)


def execute_command(
    command: Command,
    environment: Environment,
    state: StoreState,
    context: RuntimeContext,
) -> tuple[Environment, StoreState]:
    match command:
        case VarDeclaration(name, expression):
            value = evaluate_expression(expression, environment, state, context)
            location, updated_state = state.allocate(value)
            return environment.bind(name, location), updated_state

        case Assignment(name, expression):
            denotation = environment.lookup(name)
            if not isinstance(denotation, Loc):
                raise IdealDSLError(
                    f"La destinazione '{name}' non è una variabile mutabile."
                )
            value = evaluate_expression(expression, environment, state, context)
            return environment, state.update(denotation, value)

        case FunctionDeclaration() as declaration:
            if len(set(declaration.parameters)) != len(declaration.parameters):
                raise IdealDSLError(
                    f"Parametri duplicati nella funzione '{declaration.name}': "
                    f"{declaration.parameters}."
                )
            closure = Closure(declaration, environment)
            return environment.bind(declaration.name, closure), state

        case Print(expression):
            value = evaluate_expression(expression, environment, state, context)
            print(format_value(value), file=context.output)
            return environment, state

        case Show(expression):
            value = evaluate_expression(expression, environment, state, context)
            print(describe_value(value, context), file=context.output)
            return environment, state

        case Visualize(expression, path):
            value = evaluate_expression(expression, environment, state, context)
            ideal = _expect_ideal(value, "visualize")
            destination = Path(path)
            if not destination.is_absolute():
                destination = context.base_dir / destination
            written = ideal.write_dot(destination)
            print(f"visualization: {written}", file=context.output)
            return environment, state

        case Assert(expression):
            value = evaluate_expression(expression, environment, state, context)
            if not _expect_bool(value, "assert"):
                raise IdealDSLError("Asserzione fallita.")
            return environment, state

        case IfElse(condition, then_branch, else_branch):
            condition_value = evaluate_expression(condition, environment, state, context)
            branch = then_branch if _expect_bool(condition_value, "if") else else_branch
            return execute_block(branch, environment, state, context)

        case While(condition, body):
            current_state = state
            iterations = 0
            while True:
                condition_value = _expect_bool(
                    evaluate_expression(condition, environment, current_state, context),
                    "while",
                )
                if not condition_value:
                    break
                if iterations >= context.max_loop_iterations:
                    raise IdealDSLError(
                        "Numero massimo di iterazioni superato "
                        f"({context.max_loop_iterations})."
                    )
                _, current_state = execute_block(
                    body, environment, current_state, context
                )
                iterations += 1
            return environment, current_state

        case _:
            raise IdealDSLError(f"Comando AST non riconosciuto: {command!r}")


def execute_commands(
    commands: tuple[Command, ...],
    environment: Environment,
    state: StoreState,
    context: RuntimeContext,
) -> tuple[Environment, StoreState]:
    current_environment = environment
    current_state = state
    for command in commands:
        current_environment, current_state = execute_command(
            command, current_environment, current_state, context
        )
    return current_environment, current_state


class Interpreter:
    """Interprete riutilizzabile, adatto sia a file sia a una REPL."""

    def __init__(
        self,
        *,
        output: TextIO = sys.stdout,
        base_dir: str | Path | None = None,
        max_loop_iterations: int = 10_000,
    ) -> None:
        self.environment = create_initial_environment()
        self.state = StoreState()
        self.context = RuntimeContext(
            output=output,
            base_dir=Path.cwd() if base_dir is None else Path(base_dir),
            max_loop_iterations=max_loop_iterations,
        )

    def execute(self, program: Program) -> tuple[Environment, StoreState]:
        if program.ring is not None:
            self.context.ring = PolynomialRing(
                program.ring.domain,
                program.ring.variables,
                program.ring.order,
            )
            self.context.ring.activate()
        self.environment, self.state = execute_commands(
            program.commands,
            self.environment,
            self.state,
            self.context,
        )
        return self.environment, self.state

    def run(self, source: str) -> tuple[Environment, StoreState]:
        return self.execute(parse_program(source))


def run_source(
    source: str,
    *,
    output: TextIO = sys.stdout,
    base_dir: str | Path | None = None,
) -> Interpreter:
    interpreter = Interpreter(output=output, base_dir=base_dir)
    interpreter.run(source)
    return interpreter
