import math
import unittest

import pandas as pd

from pages.analyze_visualization import (
    build_historical_context_query,
    build_historical_technical_score_table,
)
from commons.technical_analysis import (
    calculate_ma_cross,
    calculate_ma_cross_trend,
    calculate_ma_trend,
    calculate_rsi,
    calculate_rsi_trend,
    calculate_stochastic,
    calculate_stochastic_trend,
)


def _make_ohlcv_frame(rows=90):
    close = [100 + (0.12 * index) + (8 * math.sin(index / 3)) for index in range(rows)]
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=rows, freq="D"),
            "open": [value - 0.5 for value in close],
            "high": [value + 1 for value in close],
            "low": [value - 1 for value in close],
            "close": close,
            "volume": [1000 + index for index in range(rows)],
        }
    )


def _prepare_indicators(frame, short_ma=5, long_ma=10):
    prepared, _ = calculate_stochastic(frame.copy())
    prepared, _ = calculate_rsi(prepared, length=14)
    prepared = calculate_ma_cross(prepared, [(short_ma, long_ma)])
    return prepared


def _reference_prefix_score(prepared, index, short_ma=5, long_ma=10):
    if index < 10:
        return None

    prefix = prepared.iloc[: index + 1]
    cross_col = f"cross_{short_ma}_{long_ma}"
    trends = [
        calculate_stochastic_trend(prefix),
        calculate_rsi_trend(prefix),
        calculate_ma_trend(prefix, f"SMA_{short_ma}", f"SMA_{long_ma}"),
        calculate_ma_cross_trend(prefix, cross_col),
    ]
    trend_points = {
        "Strong Up": 4,
        "Overbought (Up)": 4,
        "Up": 3,
        "Sideways": 2,
        "Unknown": 2,
        "None": 2,
        "Down": 1,
        "Strong Down": 0,
        "Oversold (Down)": 0,
    }
    total_points = sum(trend_points.get(trend, 2) for trend in trends)
    return round((total_points / 16) * 100, 2)


class TestHistoricalTechnicalContext(unittest.TestCase):
    def test_historical_context_query_uses_bound_ticker_parameter(self):
        query = build_historical_context_query()

        self.assertIn("%(ticker)s", query)
        self.assertNotIn(":ticker", query)

    def test_precomputed_scores_match_existing_prefix_scores(self):
        prepared = _prepare_indicators(_make_ohlcv_frame())
        expected = [
            _reference_prefix_score(prepared, index)
            for index in range(len(prepared))
        ]

        actual = build_historical_technical_score_table(
            _make_ohlcv_frame(),
            5,
            10,
        )

        self.assertEqual(actual.name, "Technical score")
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual.tolist(), expected):
            if expected_value is None:
                self.assertTrue(pd.isna(actual_value))
            else:
                self.assertEqual(actual_value, expected_value)
