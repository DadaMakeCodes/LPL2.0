from __future__ import annotations

import unittest

import Ordinamento
from domain import Ideal, PolynomialRing
from polynomial import Polinomio


class AlgebraTests(unittest.TestCase):
    def test_rational_coefficients_and_normalization(self):
        ring = PolynomialRing("Q", ("x", "y"), "lex")
        polynomial = ring.parse_poly("1/2*x + 1/2*x - y + y")
        self.assertEqual(polynomial, ring.parse_poly("x"))
        self.assertEqual(str(polynomial), "x")

    def test_orders_choose_expected_leading_term(self):
        lex = PolynomialRing("Q", ("x", "y", "z"), "lex")
        p = lex.parse_poly("x^2 + z^3")
        self.assertEqual(str(Ordinamento.lead_term(p)), "x^2")

        deglex = lex.with_order("deglex")
        p = deglex.parse_poly("x^2 + z^3")
        self.assertEqual(str(Ordinamento.lead_term(p)), "z^3")

    def test_reduced_grobner_basis(self):
        ring = PolynomialRing("Q", ("x", "y"), "lex")
        ideal = Ideal.from_strings(ring, ("x^2-y", "x*y-1"))
        basis = ideal.reduced()
        expected = Ideal.from_strings(ring, ("x-y^2", "y^3-1"))
        self.assertTrue(basis.equivalent(expected))
        self.assertEqual([str(p) for p in basis.generators], ["x-y^2", "y^3-1"])

    def test_membership_and_normal_form(self):
        ring = PolynomialRing("Q", ("x", "y"), "lex")
        ideal = Ideal.from_strings(ring, ("x^2-y", "x*y-1"))
        self.assertTrue(ideal.contains(ring.parse_poly("x^3-x*y")))
        self.assertFalse(ideal.contains(ring.parse_poly("x")))
        self.assertEqual(
            ideal.normal_form(ring.parse_poly("x^4")),
            ring.parse_poly("y^2"),
        )

    def test_ideal_sum_product_and_subset(self):
        ring = PolynomialRing("Q", ("x", "y"), "lex")
        left = Ideal.from_strings(ring, ("x",))
        right = Ideal.from_strings(ring, ("y",))
        self.assertTrue(left.product(right).contains(ring.parse_poly("x*y")))
        self.assertTrue(left.product(right).subset_of(left))
        self.assertTrue(left.sum(right).contains(ring.parse_poly("x+y")))


if __name__ == "__main__":
    unittest.main()
