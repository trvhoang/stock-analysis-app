import unittest

import pandas as pd

from pages.technical_visualization import (
    TECHNICAL_CHART_OPTIONS,
    TECHNICAL_INDICATOR_TABS,
    build_price_candlestick,
    get_ma_pair_options,
    get_indicator_chart_spec,
    parse_ma_pair,
    _report_name,
)


class TestTechnicalVisualizationUI(unittest.TestCase):
    def test_overview_is_first_and_all_eight_indicators_have_detail_tabs(self):
        self.assertEqual(
            TECHNICAL_INDICATOR_TABS,
            (
                "Overview",
                "MA",
                "MA Cross",
                "RSI",
                "Stochastic",
                "ADX",
                "OBV",
                "ATR",
                "Bollinger Bands",
            ),
        )
        self.assertEqual(TECHNICAL_CHART_OPTIONS, TECHNICAL_INDICATOR_TABS[1:])
        self.assertNotIn("Ichimoku", TECHNICAL_INDICATOR_TABS)

    def test_chart_specs_keep_base_chart_and_select_one_indicator(self):
        expected_specs = {
            "MA": ("overlay", ["SMA_5", "SMA_10"]),
            "MA Cross": ("overlay", ["SMA_5", "SMA_10", "cross_5_10"]),
            "RSI": ("panel", ["RSI_14"]),
            "Stochastic": ("panel", ["%K", "%D"]),
            "ADX": ("panel", ["ADX_14", "DMP_14", "DMN_14"]),
            "OBV": ("panel", ["OBV"]),
            "ATR": ("panel", ["ATR_14"]),
            "Bollinger Bands": (
                "panel",
                ["BBM_20_2", "BBU_20_2", "BBL_20_2", "BBB_20_2", "BBP_20_2"],
            ),
        }

        for indicator, (kind, columns) in expected_specs.items():
            with self.subTest(indicator=indicator):
                spec = get_indicator_chart_spec(indicator, 5, 10)
                self.assertEqual(spec["kind"], kind)
                self.assertEqual(spec["columns"], columns)

        self.assertIsNone(get_indicator_chart_spec("Unknown", 5, 10))

    def test_ma_pair_widget_uses_string_values_and_preserves_tuple_parameters(self):
        self.assertEqual(
            get_ma_pair_options("Day"),
            ("5-10 Cross", "10-20 Cross", "20-60 Cross"),
        )
        self.assertEqual(parse_ma_pair("5-10 Cross"), (5, 10))
        self.assertEqual(parse_ma_pair("20-60 Cross"), (20, 60))
        self.assertIsNone(parse_ma_pair(None))

    def test_report_names_match_snapshot_aliases(self):
        self.assertEqual(_report_name("MA Cross"), "MA cross")
        self.assertEqual(_report_name("Bollinger Bands"), "Bollinger")

    def test_candlestick_hover_uses_supported_scaled_text(self):
        frame = pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-08-01")],
                "open": [50.3],
                "high": [51.0],
                "low": [49.8],
                "close": [50.7],
            }
        )

        trace = build_price_candlestick(frame)
        trace_json = trace.to_plotly_json()

        self.assertNotIn("hovertemplate", trace_json)
        self.assertEqual(trace_json["hoverinfo"], "text")
        self.assertEqual(
            trace_json["text"][0],
            "Date: 2026-08-01<br>Open: 50.30k<br>High: 51.00k<br>Low: 49.80k<br>Close: 50.70k",
        )


if __name__ == "__main__":
    unittest.main()
