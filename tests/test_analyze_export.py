import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from pages.analyze_visualization import (
    EXPORT_FORM_LABEL,
    get_export_form_container,
    build_export_filename,
    fetch_export_history,
    format_export_dataframe,
    validate_export_inputs,
)


class TestAnalyzeExport(unittest.TestCase):
    @patch("pages.analyze_visualization.st.expander")
    def test_export_form_uses_native_collapsible_container(self, mock_expander):
        get_export_form_container()

        mock_expander.assert_called_once_with(EXPORT_FORM_LABEL, expanded=True)

    def test_validate_export_inputs_normalizes_ticker_and_unit(self):
        values, error = validate_export_inputs(" fpt ", 2, "MONTHS")

        self.assertEqual(
            values,
            {"ticker": "FPT", "range_value": 2, "range_unit": "months"},
        )
        self.assertIsNone(error)

    def test_validate_export_inputs_rejects_invalid_values(self):
        invalid_inputs = [
            ("", 2, "days"),
            ("FPT", 0, "days"),
            ("FPT", 2, "weeks"),
        ]

        for ticker, range_value, range_unit in invalid_inputs:
            with self.subTest(ticker=ticker, range_value=range_value, range_unit=range_unit):
                values, error = validate_export_inputs(ticker, range_value, range_unit)
                self.assertIsNone(values)
                self.assertTrue(error)

    @patch("pages.analyze_visualization.pd.read_sql")
    def test_fetch_export_history_uses_bounded_parameterized_query(self, mock_read_sql):
        mock_read_sql.return_value = pd.DataFrame(
            {"ticker": ["FPT"], "trading_date": [date(2026, 7, 31)], "close": [100000]}
        )
        engine = MagicMock()

        result = fetch_export_history("FPT", 3, "years", engine)

        self.assertEqual(len(result), 1)
        query, connection = mock_read_sql.call_args.args
        params = mock_read_sql.call_args.kwargs["params"]
        self.assertIn("latest_record", query)
        self.assertIn("%(ticker)s", query)
        self.assertIn("%(range_value)s", query)
        self.assertIn("%(range_unit)s", query)
        self.assertEqual(params, {"ticker": "FPT", "range_value": 3, "range_unit": "years"})
        self.assertIs(connection, engine.raw_connection.return_value)
        engine.raw_connection.return_value.close.assert_called_once_with()

    @patch("pages.analyze_visualization.pd.read_sql")
    def test_fetch_export_history_rejects_invalid_input_before_query(self, mock_read_sql):
        with self.assertRaises(ValueError):
            fetch_export_history("", 3, "days", MagicMock())

        mock_read_sql.assert_not_called()

    @patch("pages.analyze_visualization.pd.read_sql", side_effect=RuntimeError("db unavailable"))
    def test_fetch_export_history_closes_connection_on_database_error(self, mock_read_sql):
        engine = MagicMock()

        with self.assertRaisesRegex(RuntimeError, "db unavailable"):
            fetch_export_history("FPT", 3, "days", engine)

        engine.raw_connection.return_value.close.assert_called_once_with()

    def test_format_export_dataframe_scales_close_and_calculates_change(self):
        source = pd.DataFrame(
            {
                "ticker": ["FPT", "FPT"],
                "trading_date": [date(2026, 7, 30), date(2026, 7, 31)],
                "close": [100000, 110000],
            }
        )

        result = format_export_dataframe(source, include_percentage_change=True)

        self.assertEqual(
            list(result.columns),
            ["ticker", "trading_date", "close_price", "percentage_change"],
        )
        self.assertEqual(result["close_price"].tolist(), [100.0, 110.0])
        self.assertTrue(pd.isna(result.loc[0, "percentage_change"]))
        self.assertEqual(result.loc[1, "percentage_change"], 10.0)

    def test_format_export_dataframe_omits_optional_change(self):
        source = pd.DataFrame(
            {"ticker": ["FPT"], "trading_date": [date(2026, 7, 31)], "close": [100000]}
        )

        result = format_export_dataframe(source, include_percentage_change=False)

        self.assertEqual(list(result.columns), ["ticker", "trading_date", "close_price"])

    def test_format_export_dataframe_keeps_required_columns_for_empty_history(self):
        source = pd.DataFrame(columns=["ticker", "trading_date", "close"])

        result = format_export_dataframe(source, include_percentage_change=True)

        self.assertEqual(
            list(result.columns),
            ["ticker", "trading_date", "close_price", "percentage_change"],
        )
        self.assertTrue(result.empty)

    def test_build_export_filename_is_deterministic(self):
        self.assertEqual(
            build_export_filename("FPT", 3, "months"),
            "FPT_3_months_price_history.csv",
        )


if __name__ == "__main__":
    unittest.main()
