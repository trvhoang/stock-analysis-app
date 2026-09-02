"""Exact semantic parity gates for schema-5 runtime optimizations."""

from contextlib import ExitStack
from datetime import date
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import backtest_engine.exploratory as exploratory
import backtest_engine.indicators as indicators
from scripts.profile_backtest_schema5 import _stable_digest, _timing_summary
from backtest_engine.config import rulebook_for
from backtest_engine.models import RulebookExecution
from backtest_engine.rolling_window import (
    run_rulebook_trade_sequence,
    run_rulebook_trade_sequence_reference,
)
from backtest_engine.validation import (
    moving_block_permutation_test,
    moving_block_permutation_test_reference,
)


def _execution(horizon: str = "swing") -> RulebookExecution:
    return RulebookExecution(rulebook_for(horizon), ("rulebook_rsi_upcross",))


def _trade_frame(horizon: str = "swing", periods: int = 35) -> pd.DataFrame:
    frequency = "B" if horizon == "swing" else "W-FRI"
    dates = pd.date_range("2025-01-03", periods=periods, freq=frequency)
    return pd.DataFrame(
        {
            "date": dates,
            "open": [100.0] * periods,
            "high": [101.0] * periods,
            "low": [99.0] * periods,
            "close": [100.0] * periods,
            "ATR_14": [2.0] * periods,
        }
    )


class PermutationParityTests(unittest.TestCase):
    def test_vectorized_blocks_preserve_every_reference_value(self):
        cases = (
            ((1.0, -0.5, 2.0, -1.0, 0.25), 37, 42, 3),
            (tuple((index % 7 - 3) / 10 for index in range(41)), 101, 9, 20),
            ((1.0, 1.0, 1.0, 1.0), 25, 0, 9),
        )
        for returns, count, seed, block in cases:
            with self.subTest(n=len(returns), count=count, seed=seed, block=block):
                self.assertEqual(
                    moving_block_permutation_test_reference(
                        returns, count=count, seed=seed, block_size=block
                    ),
                    moving_block_permutation_test(
                        returns, count=count, seed=seed, block_size=block
                    ),
                )


class TradeExecutorParityTests(unittest.TestCase):
    def _assert_trace(self, frame: pd.DataFrame, entries: pd.Series, horizon: str = "swing"):
        expected = run_rulebook_trade_sequence_reference(frame, _execution(horizon), entries)
        actual = run_rulebook_trade_sequence(frame, _execution(horizon), entries)
        self.assertEqual(
            [event.to_dict() for event in expected],
            [event.to_dict() for event in actual],
        )

    def test_sparse_dense_empty_and_invalid_signal_traces_match(self):
        frame = _trade_frame()
        cases = {
            "empty": (),
            "sparse": (1, 27),
            "dense": tuple(range(1, 30)),
        }
        for label, positions in cases.items():
            with self.subTest(label=label):
                entries = pd.Series(False, index=frame.index)
                entries.loc[list(positions)] = True
                self._assert_trace(frame, entries)
        invalid = frame.copy()
        invalid.loc[2, "open"] = np.nan
        entries = pd.Series(False, index=invalid.index)
        entries.loc[[1, 4]] = True
        self._assert_trace(invalid, entries)

    def test_gap_collision_target_deadline_and_incomplete_traces_match(self):
        cases = []
        collision = _trade_frame()
        collision.loc[5, ["low", "high"]] = [90.0, 110.0]
        cases.append(("collision", collision))
        gap_stop = _trade_frame()
        gap_stop.loc[5, ["open", "low"]] = [95.0, 94.0]
        cases.append(("gap_stop", gap_stop))
        target_gap = _trade_frame()
        target_gap.loc[5, ["open", "high"]] = [108.0, 109.0]
        cases.append(("target_gap", target_gap))
        cases.append(("deadline", _trade_frame()))
        cases.append(("incomplete", _trade_frame(periods=20)))
        for label, frame in cases:
            with self.subTest(label=label):
                entries = pd.Series(False, index=frame.index)
                entries.loc[1] = True
                self._assert_trace(frame, entries)

    def test_weekly_clock_trace_matches(self):
        frame = _trade_frame("midterm", 25)
        frame.loc[3, "high"] = 110.0
        entries = pd.Series(False, index=frame.index)
        entries.loc[[1, 10]] = True
        self._assert_trace(frame, entries, "midterm")


class WilderParityTests(unittest.TestCase):
    def test_smma_and_wilder_series_preserve_index_nan_and_values(self):
        values = pd.Series(
            [1.0, 2.0, 3.0, 4.0, np.nan, 6.0, 7.0, 8.0, 9.0, 10.0],
            index=pd.Index(range(10, 20), name="row"),
        )
        pd.testing.assert_series_equal(
            indicators._smma_reference(values, 3),
            indicators._smma(values, 3),
            check_exact=True,
        )
        pd.testing.assert_series_equal(
            indicators._wilder_average_reference(values, 3, seed_start=0),
            indicators._wilder_average(values, 3, seed_start=0),
            check_exact=True,
        )

    def test_full_indicator_frames_are_exact_for_daily_and_weekly(self):
        periods = 180
        base = np.linspace(90.0, 130.0, periods) + np.sin(np.arange(periods) / 3)
        raw = pd.DataFrame(
            {
                "date": pd.bdate_range("2024-01-02", periods=periods),
                "open": base,
                "high": base + 2.0,
                "low": base - 2.0,
                "close": base + np.cos(np.arange(periods) / 5),
                "volume": 1000 + np.arange(periods) * 3,
            }
        )
        common = raw["date"].iloc[-1].date()
        for horizon in ("swing", "midterm"):
            with self.subTest(horizon=horizon):
                with patch.object(indicators, "_smma", indicators._smma_reference), patch.object(
                    indicators, "_wilder_average", indicators._wilder_average_reference
                ):
                    expected = indicators.build_rulebook_frame(
                        raw, rulebook_for(horizon), common_as_of=common
                    )
                actual = indicators.build_rulebook_frame(
                    raw, rulebook_for(horizon), common_as_of=common
                )
                pd.testing.assert_frame_equal(expected, actual, check_exact=True)


class EndToEndParityTests(unittest.TestCase):
    def test_candidate_metrics_treatments_and_top_three_are_byte_exact(self):
        periods = 240
        frame = _trade_frame(periods=periods)
        index = np.arange(periods)
        frame["rulebook_adx_gate"] = index % 2 == 0
        frame["rulebook_joint_trend_pass"] = index % 3 != 0
        frame["rulebook_rsi_upcross"] = index % 5 == 1
        frame["rulebook_volume_gate"] = index % 4 != 0
        frame["rulebook_missing_required_input"] = False
        theme = pd.Series(index % 3 != 1, index=frame.index, dtype=bool)
        arguments = dict(
            frame=frame,
            horizon="swing",
            requested_start=frame["date"].iloc[0].date(),
            requested_end=frame["date"].iloc[-1].date(),
            theme_eligible=theme,
            permutation_count=41,
            permutation_seed=42,
            permutation_block_size=5,
        )
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    exploratory,
                    "run_rulebook_trade_sequence",
                    run_rulebook_trade_sequence_reference,
                )
            )
            stack.enter_context(
                patch.object(
                    exploratory,
                    "moving_block_permutation_test",
                    moving_block_permutation_test_reference,
                )
            )
            expected = exploratory.evaluate_exploratory_candidates(**arguments)
        actual = exploratory.evaluate_exploratory_candidates(**arguments)

        def serialized(value):
            return json.dumps(
                {
                    "split": value.split.to_dict(),
                    "candidates": [candidate.to_dict() for candidate in value.candidates],
                    "top_rulebook_ids": list(value.top_rulebook_ids),
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )

        self.assertEqual(serialized(expected), serialized(actual))


class RuntimeProfilerContractTests(unittest.TestCase):
    def test_digest_is_canonical_and_timing_summary_reports_p50_p95(self):
        self.assertEqual(
            _stable_digest({"b": [2, 1], "a": 3}),
            _stable_digest({"a": 3, "b": [2, 1]}),
        )
        self.assertEqual(
            _timing_summary((5.0, 1.0, 4.0, 2.0, 3.0)),
            {"p50_seconds": 3.0, "p95_seconds": 4.8},
        )


if __name__ == "__main__":
    unittest.main()
