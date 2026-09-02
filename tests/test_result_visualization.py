"""Focused Result-page query and display contracts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest

import pandas as pd

from pages.result_visualization import result_page


class ResultVisualizationTests(unittest.TestCase):
    @patch("pages.result_visualization.st")
    @patch("pages.result_visualization.pd.read_sql")
    def test_result_page_uses_bound_raw_connection_queries_and_closes_once(
        self, read_sql, streamlit
    ) -> None:
        streamlit.number_input.return_value = 3
        streamlit.columns.return_value = (MagicMock(), MagicMock())
        read_sql.side_effect = [
            pd.DataFrame({"ticker": ["FPT"], "total_volume": [1_000]}),
            pd.DataFrame({"ticker": ["FPT"], "total_value": [20_000], "avg_price": [20_000]}),
        ]
        engine = MagicMock()

        result_page(engine)

        self.assertEqual(read_sql.call_count, 2)
        first_query, connection = read_sql.call_args_list[0].args
        second_query = read_sql.call_args_list[1].args[0]
        params = read_sql.call_args_list[0].kwargs["params"]
        self.assertIn("ticker <> 'VNINDEX'", first_query)
        self.assertIn("ticker <> 'VNINDEX'", second_query)
        self.assertIn("%(start_date)s", first_query)
        self.assertIn("%(current_date)s", second_query)
        self.assertEqual(set(params), {"start_date", "current_date"})
        self.assertIs(connection, engine.raw_connection.return_value)
        engine.raw_connection.return_value.close.assert_called_once_with()
        self.assertEqual(streamlit.dataframe.call_count, 2)
        for call in streamlit.dataframe.call_args_list:
            self.assertTrue(call.kwargs["use_container_width"])

    @patch("pages.result_visualization.st")
    @patch("pages.result_visualization.pd.read_sql", side_effect=RuntimeError("db unavailable"))
    def test_result_page_closes_connection_when_query_fails(self, _read_sql, streamlit) -> None:
        streamlit.number_input.return_value = 1
        engine = MagicMock()

        with self.assertRaisesRegex(RuntimeError, "db unavailable"):
            result_page(engine)

        engine.raw_connection.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
