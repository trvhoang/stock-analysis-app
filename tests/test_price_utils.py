"""Unit tests for shared BIGINT/UI price conversion helpers."""

from decimal import Decimal
import unittest

import pandas as pd

from commons.price_utils import (
    PRICE_OUTPUT_EXPORT,
    PRICE_OUTPUT_UI,
    prepare_price_for_output,
    price_from_ui_k_vnd,
)


class PriceUtilsTests(unittest.TestCase):
    def test_price_from_ui_k_vnd_returns_exact_raw_bigint(self) -> None:
        self.assertEqual(price_from_ui_k_vnd("20.125"), 20_125)
        self.assertEqual(price_from_ui_k_vnd(Decimal("0.001")), 1)

    def test_price_from_ui_k_vnd_rejects_more_than_three_decimal_places(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most three"):
            price_from_ui_k_vnd("20.1251")

    def test_price_from_ui_k_vnd_rejects_non_positive_and_non_finite_values(self) -> None:
        for value in (0, -1, "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                price_from_ui_k_vnd(value)

    def test_price_from_ui_k_vnd_rejects_sub_milli_unit_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most three"):
            price_from_ui_k_vnd("0.0001")

    def test_prepare_price_for_output_ui_scales_without_mutating_input(self) -> None:
        values = pd.Series([20_000, 20_125], index=["a", "b"], dtype="int64")
        converted = prepare_price_for_output(values, PRICE_OUTPUT_UI)
        pd.testing.assert_series_equal(
            converted,
            pd.Series([20.0, 20.125], index=["a", "b"], dtype="float64"),
        )
        pd.testing.assert_series_equal(values, pd.Series([20_000, 20_125], index=["a", "b"], dtype="int64"))

    def test_prepare_price_for_output_export_preserves_raw_values(self) -> None:
        values = pd.Series([20_000, 20_125], dtype="int64")
        exported = prepare_price_for_output(values, PRICE_OUTPUT_EXPORT)
        self.assertIs(exported, values)

    def test_prepare_price_for_output_rejects_unknown_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported price output"):
            prepare_price_for_output([20_000], "database")


if __name__ == "__main__":
    unittest.main()
