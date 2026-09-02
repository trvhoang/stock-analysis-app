"""Focused contracts for market suggestion page orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest

from pages.suggestion_visualization import suggestion_page


class SuggestionVisualizationTests(unittest.TestCase):
    @patch("pages.suggestion_visualization.st")
    @patch("pages.suggestion_visualization.get_all_tickers", return_value=[])
    def test_empty_universe_warns_without_starting_analysis(self, tickers, streamlit) -> None:
        streamlit.columns.return_value = tuple(MagicMock() for _ in range(4))
        streamlit.number_input.side_effect = (5, 5, 1000, 1)
        streamlit.button.return_value = True

        suggestion_page(MagicMock())

        tickers.assert_called_once()
        streamlit.warning.assert_called_once_with(
            "No tickers found with the specified volume threshold."
        )

    @patch("pages.suggestion_visualization.st")
    @patch("pages.suggestion_visualization.analyze_ticker")
    @patch("pages.suggestion_visualization.get_all_tickers", return_value=["FPT", "VCB"])
    def test_suggestion_page_projects_all_four_rankings(self, tickers, analyze, streamlit) -> None:
        streamlit.columns.return_value = tuple(MagicMock() for _ in range(4))
        streamlit.number_input.side_effect = (5, 10, 1000, 1)
        streamlit.button.return_value = True
        analyze.side_effect = [
            {
                "ticker": "FPT", "exchange": "HSX", "current_delta": 2.0,
                "possibility_up": 72.0, "possibility_down": 5.0,
                "max_up_delta": 15.0, "min_down_delta": -4.0,
                "total_signals": 20, "stat_trend": "Strong Up", "tech_trend": "Up",
            },
            {
                "ticker": "VCB", "exchange": "HNX", "current_delta": -2.0,
                "possibility_up": 5.0, "possibility_down": 75.0,
                "max_up_delta": 4.0, "min_down_delta": -15.0,
                "total_signals": 10, "stat_trend": "Strong Down", "tech_trend": "Down",
            },
        ]
        engine = MagicMock()

        suggestion_page(engine)

        tickers.assert_called_once_with(engine, 1_000_000, 1)
        self.assertEqual(analyze.call_count, 2)
        self.assertEqual(streamlit.dataframe.call_count, 4)
        for call in streamlit.dataframe.call_args_list:
            self.assertTrue(call.kwargs["use_container_width"])
        headings = [call.args[0] for call in streamlit.subheader.call_args_list]
        self.assertEqual(
            headings,
            [
                "Top 5 Tickers by Possibility of Up",
                "Top 5 Tickers by Delta of Up",
                "Top 5 Tickers by Possibility of Down",
                "Top 5 Tickers by Delta of Down",
            ],
        )


if __name__ == "__main__":
    unittest.main()
