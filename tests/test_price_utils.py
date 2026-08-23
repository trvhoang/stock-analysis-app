import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from commons.price_utils import (
    PRICE_OUTPUT_EXPORT,
    PRICE_OUTPUT_UI,
    price_from_ui_k_vnd,
    prepare_price_for_output,
)
from commons.technical_analysis import fetch_data


class TestPriceUtils(unittest.TestCase):
    def test_ui_context_scales_price_to_k_vnd(self):
        result = prepare_price_for_output(
            pd.Series([50300, 121350]),
            PRICE_OUTPUT_UI,
        )

        self.assertEqual(result.tolist(), [50.3, 121.35])

    def test_export_context_preserves_original_price(self):
        source = pd.Series([50300, 121350])

        result = prepare_price_for_output(source, PRICE_OUTPUT_EXPORT)

        pd.testing.assert_series_equal(result, source)

    def test_price_from_ui_k_vnd_converts_exactly_to_raw_bigint(self):
        self.assertEqual(price_from_ui_k_vnd("50.3"), 50300)
        self.assertEqual(price_from_ui_k_vnd("121.35"), 121350)

    def test_price_from_ui_k_vnd_rejects_invalid_non_positive_and_overprecise_values(self):
        for value in ("", "not-a-price", "0", "-1", "50.3000", "0.0001"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    price_from_ui_k_vnd(value)

    @patch("commons.technical_analysis.pd.read_sql")
    def test_fetch_data_scales_ui_prices_and_preserves_volume(self, mock_read_sql):
        mock_read_sql.return_value = pd.DataFrame(
            {
                "date": ["2026-07-30", "2026-07-31"],
                "open": [49900, 50300],
                "high": [50100, 50600],
                "low": [49500, 50000],
                "close": [50000, 50300],
                "volume": [2000000, 2500000],
            }
        )

        engine = MagicMock()
        result = fetch_data("FPT", "Day", 2, engine)

        self.assertEqual(
            result.loc[1, ["open", "high", "low", "close"]].tolist(),
            [50.3, 50.6, 50.0, 50.3],
        )
        self.assertEqual(result.loc[1, "volume"], 2500000)
        engine.raw_connection.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
