"""Interfaccia a riga di comando di IdealDSL."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from dsl_parser import parse_program
from interpreter import IdealDSLError, Interpreter


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idealdsl",
        description="Interprete per il DSL degli ideali polinomiali.",
    )
    parser.add_argument("file", nargs="?", type=Path, help="programma .idl da eseguire")
    parser.add_argument("--repl", action="store_true", help="avvia la modalità interattiva")
    parser.add_argument("--ast", action="store_true", help="stampa l'AST prima dell'esecuzione")
    parser.add_argument("--check", action="store_true", help="controlla soltanto la sintassi")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10_000,
        help="limite di sicurezza per ogni ciclo while",
    )
    return parser


def execute_file(path: Path, arguments: argparse.Namespace) -> int:
    try:
        source = path.read_text(encoding="utf-8")
        program = parse_program(source)
        if arguments.ast:
            print(program)
        if not arguments.check:
            interpreter = Interpreter(
                base_dir=path.resolve().parent,
                max_loop_iterations=arguments.max_iterations,
            )
            interpreter.execute(program)
        return 0
    except (OSError, SyntaxError, IdealDSLError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def repl(max_iterations: int = 10_000) -> int:
    print("IdealDSL REPL")
    print("Inserire uno o più comandi; riga vuota o :run per eseguire, :quit per uscire.")
    interpreter = Interpreter(max_loop_iterations=max_iterations)
    buffer: list[str] = []

    while True:
        try:
            line = input("ideal> " if not buffer else "....> ")
        except EOFError:
            print()
            return 0

        stripped = line.strip()
        if stripped in {":quit", ":q", "exit"}:
            return 0
        if stripped == ":clear":
            buffer.clear()
            continue
        if stripped == ":help":
            print(":run esegue il buffer, :clear lo svuota, :quit termina.")
            continue

        should_run = stripped == ":run" or (not stripped and bool(buffer))
        if should_run:
            source = "\n".join(buffer)
            buffer.clear()
            try:
                interpreter.run(source)
            except (SyntaxError, IdealDSLError, ValueError) as error:
                print(f"error: {error}")
            continue

        if stripped:
            buffer.append(line)


def main(argv: list[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    if arguments.repl:
        return repl(arguments.max_iterations)
    if arguments.file is None:
        build_argument_parser().print_help()
        return 2
    return execute_file(arguments.file, arguments)


if __name__ == "__main__":
    raise SystemExit(main())
