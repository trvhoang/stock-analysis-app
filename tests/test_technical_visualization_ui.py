import inspect
import unittest

import pandas as pd
from plotly.subplots import make_subplots

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - host-only fallback
    AppTest = None

from pages import technical_visualization
from pages.technical_visualization import (
    TECHNICAL_CHART_OPTIONS,
    TECHNICAL_INDICATOR_TABS,
    _add_selected_indicator,
    build_price_candlestick,
    get_ma_pair_options,
    get_indicator_chart_spec,
    parse_ma_pair,
    _report_name,
)


class TestTechnicalVisualizationUI(unittest.TestCase):
    @unittest.skipIf(AppTest is None, "Streamlit AppTest runtime is unavailable")
    def test_horizon_ui_analyzes_a_swing_snapshot_without_sidebar_controls(self):
        app = AppTest.from_string(
            """
import pandas as pd
from pages import technical_visualization as page

dates = pd.bdate_range("2025-01-02", periods=100)
close = pd.Series(range(100000, 110000, 100))
source = pd.DataFrame({
    "date": dates,
    "open": close - 50,
    "high": close + 100,
    "low": close - 100,
    "close": close,
    "volume": 1000000,
})
page.fetch_horizon_source = lambda ticker, horizon, engine: source
page.technical_analysis_page(object())
"""
        )

        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.text_input), 1)
        self.assertEqual(app.text_input[0].label, "Ticker")
        self.assertEqual([item.label for item in app.selectbox], ["Horizon"])
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn("Show one indicator", [item.label for item in app.selectbox])
        self.assertEqual(len(app.tabs), 10)

    def test_technical_session_cleanup_is_namespaced(self):
        state = {
            "tech_df": object(),
            "tech_ticker": "FPT",
            "tech_snapshot": object(),
            "tech_snapshot_params": ("FPT", "Swing", 100),
            "tech_raw_history": {("FPT", "Swing", 100): object()},
            "backtest_job": "keep",
        }

        technical_visualization.clear_technical_session_state(state)

        self.assertEqual({"backtest_job": "keep"}, state)

    def test_raw_history_cache_uses_one_technical_namespace(self):
        source = inspect.getsource(technical_visualization.technical_analysis_page)

        self.assertIn("TECHNICAL_RAW_HISTORY_KEY", source)
        self.assertNotIn("st.session_state[data_key]", source)

    def test_controls_and_outputs_use_the_streamlit_162_presentation_contract(self):
        source = inspect.getsource(technical_visualization.technical_analysis_page)

        self.assertEqual(1, source.count('key="technical_clear_cache"'))
        self.assertIn('"clear_cache"', source)
        self.assertIn('help="Clear Technical Analyze cached data"', source)
        self.assertIn(
            'st.button("Analyze", icon=":material/query_stats:")',
            source,
        )
        self.assertIn('st.plotly_chart(fig, width="stretch")', source)
        self.assertNotIn("use_container_width", source)
        self.assertNotIn("clear_cache_sidebar", source)
        self.assertNotIn("clear_cache_input", source)
        self.assertNotIn("st.sidebar", source)
        self.assertIn('st.text_input("Ticker", value="FPT")', source)
        self.assertIn('st.selectbox("Horizon", ("Swing", "Mid-term")', source)
        self.assertNotIn("Max Time (Lookback)", source)
        self.assertNotIn("MA Cross Pair", source)

    def test_overview_is_first_and_existing_indicators_plus_alligator_have_detail_tabs(self):
        self.assertEqual(
            TECHNICAL_INDICATOR_TABS,
            (
                "Overview",
                "MA",
                "MA Cross",
                "Alligator",
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
            "Alligator": (
                "overlay",
                ["ALLIGATOR_LIPS", "ALLIGATOR_TEETH", "ALLIGATOR_JAW"],
            ),
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
        self.assertEqual(
            get_indicator_chart_spec("MA", 5, 13, ma_kind="EMA")["columns"],
            ["EMA_5", "EMA_13"],
        )

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

    def test_selected_indicator_adds_overlay_cross_markers_and_panel_thresholds(self):
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-08-01", "2026-08-02"]),
                "low": [49.0, 50.0], "high": [51.0, 52.0],
                "SMA_5": [50.0, 51.0], "SMA_10": [49.5, 50.5],
                "cross_5_10": [1, -1], "RSI_14": [45.0, 55.0],
                "ALLIGATOR_LIPS": [50.5, 51.5],
                "ALLIGATOR_TEETH": [50.0, 51.0],
                "ALLIGATOR_JAW": [49.5, 50.5],
            }
        )
        figure = make_subplots(rows=2, cols=1)
        _add_selected_indicator(
            figure, frame, "MA Cross", get_indicator_chart_spec("MA Cross", 5, 10), 1, 5, 10
        )
        self.assertEqual([trace.name for trace in figure.data], ["SMA 5", "SMA 10", "Golden Cross", "Death Cross"])

        panel = make_subplots(rows=2, cols=1)
        _add_selected_indicator(panel, frame, "RSI", get_indicator_chart_spec("RSI", 5, 10), 2, 5, 10)
        self.assertEqual([trace.name for trace in panel.data], ["RSI 14"])
        self.assertEqual(len(panel.layout.shapes), 2)

        alligator = make_subplots(rows=2, cols=1)
        _add_selected_indicator(
            alligator,
            frame,
            "Alligator",
            get_indicator_chart_spec("Alligator", 5, 10),
            1,
            5,
            10,
        )
        self.assertEqual(
            [trace.name for trace in alligator.data],
            ["Alligator Lips", "Alligator Teeth", "Alligator Jaw"],
        )

    def test_selected_indicator_is_noop_when_required_columns_are_missing(self):
        figure = make_subplots(rows=2, cols=1)
        _add_selected_indicator(
            figure,
            pd.DataFrame({"date": pd.to_datetime(["2026-08-01"]), "close": [50.0]}),
            "RSI",
            get_indicator_chart_spec("RSI", 5, 10),
            2,
            5,
            10,
        )
        self.assertEqual(len(figure.data), 0)


if __name__ == "__main__":
    unittest.main()
