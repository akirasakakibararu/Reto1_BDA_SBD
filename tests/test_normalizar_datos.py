import unittest
from decimal import Decimal

from scripts.procesamiento.normalizar_datos import normalize_code, parse_number


class NormalizeCodeTests(unittest.TestCase):
    def test_numeric_code_keeps_leading_zeroes(self) -> None:
        self.assertEqual(normalize_code(1002), "01002")

    def test_invalid_code_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_code("100200")


class ParseNumberTests(unittest.TestCase):
    def test_spanish_thousands_and_decimal_separators(self) -> None:
        self.assertEqual(parse_number("20.828,00"), Decimal("20828.00"))

    def test_explicit_missing_marker_is_preserved_as_null(self) -> None:
        self.assertIsNone(parse_number("-"))

    def test_population_must_be_an_integer(self) -> None:
        with self.assertRaises(ValueError):
            parse_number("4.591,5", integer=True)


if __name__ == "__main__":
    unittest.main()
