from __future__ import annotations

from io import StringIO
from pathlib import Path
import tempfile
import unittest

from interpreter import IdealDSLError, Interpreter


class DSLTests(unittest.TestCase):
    def run_program(self, source: str, base_dir: Path | None = None):
        output = StringIO()
        interpreter = Interpreter(output=output, base_dir=base_dir)
        interpreter.run(source)
        return output.getvalue(), interpreter

    def test_arithmetic_precedence_booleans_and_let(self):
        output, _ = self.run_program(
            "print 1+2*3; print -2^2; print not false and true; "
            "print let x=2 in x^3;"
        )
        self.assertEqual(output.splitlines(), ["7", "-4", "true", "8"])

    def test_domain_literals_and_primitives(self):
        output, _ = self.run_program(
            "ring Q[x,y] order lex;"
            "var I=ideal{x^2-y; x*y-1};"
            "print reduced(I);"
            "print contains(I, poly{x^3-x*y});"
        )
        self.assertEqual(output.splitlines(), ["<x-y^2, y^3-1>", "true"])

    def test_lexical_scope_for_closure(self):
        output, _ = self.run_program(
            "var x=10; function f(y)=x+y; var x=100; print f(1);"
        )
        self.assertEqual(output.strip(), "11")

    def test_block_scope_and_while_state(self):
        output, interpreter = self.run_program(
            "var i=0; var sum=0;"
            "while i<3 do var local=i+10; sum<-sum+i; i<-i+1; done;"
            "print sum; print i;"
        )
        self.assertEqual(output.splitlines(), ["3", "3"])
        # Soltanto i e sum restano allocati: local viene deallocata a ogni iterazione.
        self.assertEqual(interpreter.state.next_loc, 2)

    def test_function_and_let_on_ideals(self):
        output, _ = self.run_program(
            "ring Q[x,y];"
            "function canon(I)=reduced(I);"
            "var I=ideal{x^2-y;x*y-1};"
            "print let G=canon(I) in generator_count(G);"
        )
        self.assertEqual(output.strip(), "2")

    def test_visualization_writes_dot(self):
        with tempfile.TemporaryDirectory() as directory:
            output, _ = self.run_program(
                "ring Q[x,y]; var I=ideal{x;y}; visualize I to \"graph.dot\";",
                Path(directory),
            )
            destination = Path(directory) / "graph.dot"
            self.assertTrue(destination.exists())
            self.assertIn("digraph PolynomialIdeal", destination.read_text())
            self.assertIn("visualization:", output)

    def test_undeclared_assignment_is_rejected(self):
        with self.assertRaises(IdealDSLError):
            self.run_program("x<-1;")

    def test_domain_literal_requires_ring(self):
        with self.assertRaises(IdealDSLError):
            self.run_program("print poly{x};")


if __name__ == "__main__":
    unittest.main()
