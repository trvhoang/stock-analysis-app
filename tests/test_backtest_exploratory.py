"""Exploratory schema-5 baseline-control train/test contracts."""

from datetime import date, timedelta
import unittest

import pandas as pd

from backtest_engine.config import rulebook_for
from backtest_engine.exploratory import (
    EvaluationSplit,
    build_exploratory_candidate,
    execute_partition,
    partition_metrics,
    rank_top_candidates,
    split_native_frame,
)
from backtest_engine.models import RulebookExecution, TradeEvent
from backtest_engine.rolling_window import Window, partition_completed_events


def _event(day: date, return_pct: float) -> TradeEvent:
    return TradeEvent(
        signal_date=day,
        entry_date=day + timedelta(days=1),
        entry_price=100,
        atr=10,
        stop_loss=85,
        take_profit=125,
        exit_date=day + timedelta(days=2),
        exit_price=100 + return_pct,
        exit_reason="timeout",
        return_pct=return_pct,
        source_window=(day, day + timedelta(days=2)),
    )


def _execution(gates, theme_variant="no-background-theme") -> RulebookExecution:
    return RulebookExecution(
        rulebook_for("swing"),
        gates,
        theme_variant=theme_variant,
        theme_mode="AND" if theme_variant == "background-theme" else None,
    )


class ExploratoryEvaluationTests(unittest.TestCase):
    def test_calendar_split_uses_requested_ten_year_train_and_five_year_test(self):
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2011-01-03", "2020-12-31", "2021-01-04", "2025-12-31"]
                )
            }
        )

        split = split_native_frame(
            frame,
            requested_start=date(2011, 1, 3),
            requested_end=date(2026, 1, 3),
        )

        self.assertEqual(split.method, "calendar_10y_5y")
        self.assertEqual(split.train_start, date(2011, 1, 3))
        self.assertEqual(split.train_end, date(2020, 12, 31))
        self.assertEqual(split.test_start, date(2021, 1, 4))
        self.assertEqual(split.test_end, date(2025, 12, 31))

    def test_fallback_split_uses_chronological_sixty_five_percent(self):
        frame = pd.DataFrame(
            {"date": pd.to_datetime(["2020-01-01", "2020-07-01", "2021-01-01"])}
        )

        split = split_native_frame(
            frame,
            requested_start=date(2010, 1, 1),
            requested_end=date(2025, 1, 1),
        )

        self.assertEqual(split.method, "chronological_65_35")
        self.assertEqual(split.train_end, date(2020, 7, 1))
        self.assertEqual(split.test_start, date(2021, 1, 1))

    def test_calendar_split_requires_terminal_coverage(self):
        frame = pd.DataFrame(
            {"date": pd.date_range("2011-09-01", "2022-01-03", freq="B")}
        )

        split = split_native_frame(
            frame,
            requested_start=date(2011, 9, 1),
            requested_end=date(2026, 9, 1),
        )

        self.assertEqual("chronological_65_35", split.method)

    def test_partition_drops_trade_when_entry_crosses_boundary(self):
        crossing = TradeEvent(
            signal_date=date(2020, 12, 31),
            entry_date=date(2021, 1, 4),
            entry_price=100,
            atr=10,
            stop_loss=85,
            take_profit=125,
            exit_date=date(2021, 1, 8),
            exit_price=110,
            exit_reason="timeout",
            return_pct=10.0,
            source_window=(date(2020, 12, 31), date(2021, 1, 8)),
        )
        train = Window(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"))

        self.assertEqual(partition_completed_events((crossing,), train), [])

    def test_partition_drops_trade_when_exit_crosses_boundary(self):
        crossing = TradeEvent(
            signal_date=date(2020, 12, 28),
            entry_date=date(2020, 12, 29),
            entry_price=100,
            atr=10,
            stop_loss=85,
            take_profit=125,
            exit_date=date(2021, 1, 4),
            exit_price=110,
            exit_reason="timeout",
            return_pct=10.0,
            source_window=(date(2020, 12, 28), date(2021, 1, 4)),
        )
        train = Window(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"))

        self.assertEqual(partition_completed_events((crossing,), train), [])

    def test_execute_partition_cannot_use_an_exit_beyond_its_supplied_end(self):
        dates = pd.bdate_range("2025-01-01", periods=10)
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": [100] * 10,
                "high": [105] * 10,
                "low": [95] * 10,
                "close": [100] * 10,
                "ATR_14": [10] * 10,
            }
        )
        frame.loc[6, "low"] = 80
        entries = pd.Series(False, index=frame.index)
        entries.loc[1] = True

        events = execute_partition(
            frame,
            _execution(("rulebook_adx_gate",)),
            entries,
            start=dates[0].date(),
            end=dates[5].date(),
        )

        self.assertEqual((), events)

    def test_partition_metrics_marks_p_value_na_at_or_below_block_size(self):
        events = tuple(_event(date(2020, 1, 1) + timedelta(days=index * 3), 1.0 if index % 2 else -0.5) for index in range(5))

        metrics = partition_metrics(
            events,
            permutation_count=1000,
            permutation_seed=42,
            permutation_block_size=20,
        )

        self.assertEqual(metrics.n, 5)
        self.assertIsNone(metrics.p_value)
        self.assertEqual(metrics.p_value_status, "not_estimated_n_le_block_size")

    def test_candidate_with_unavailable_themed_dsr_persists_and_prefers_no_theme(self):
        no_theme_events = tuple(
            _event(date(2020, 1, 1) + timedelta(days=index * 3), value)
            for index, value in enumerate((2.0, -1.0, 1.0, 2.0, -0.5))
        )
        candidate = build_exploratory_candidate(
            _execution(("rulebook_rsi_upcross",)),
            _execution(("rulebook_rsi_upcross",), "background-theme"),
            no_theme_events,
            (_event(date(2020, 2, 1), 1.0),),
            (),
            (),
            permutation_count=1000,
            permutation_seed=42,
            permutation_block_size=20,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.preferred_variant, "no-background-theme")
        self.assertEqual(candidate.themed.dsr_status, "unavailable")
        self.assertEqual(candidate.themed.training.n, 1)
        self.assertEqual(candidate.no_theme.training.n, 5)
        self.assertEqual(candidate.to_dict()["candidate_role"], "baseline_control")

    def test_exact_rank_tie_uses_lexical_identity_and_hard_stops_at_three(self):
        events = tuple(
            _event(date(2020, 1, 1) + timedelta(days=index * 3), value)
            for index, value in enumerate((1.0, -0.5, 1.0, 1.0, -0.5))
        )
        candidates = []
        for gate in (
            "rulebook_volume_gate",
            "rulebook_rsi_upcross",
            "rulebook_joint_trend_pass",
            "rulebook_adx_gate",
        ):
            candidates.append(build_exploratory_candidate(
                _execution((gate,)),
                _execution((gate,), "background-theme"),
                events,
                events,
                (),
                (),
                permutation_count=1000,
                permutation_seed=42,
                permutation_block_size=20,
            ))

        self.assertEqual(
            [candidate.rule_id for candidate in rank_top_candidates(candidates)],
            [
                "swing_rulebook_v5__adx",
                "swing_rulebook_v5__joint_trend",
                "swing_rulebook_v5__rsi_upcross",
            ],
        )

    def test_rank_uses_unrounded_training_metrics_then_lexical_id(self):
        no_theme_events = tuple(
            _event(date(2020, 1, 1) + timedelta(days=index * 3), value)
            for index, value in enumerate((1.000001, -0.5, 1.0, 1.0, -0.5))
        )
        themed_events = tuple(
            _event(date(2020, 1, 1) + timedelta(days=index * 3), value)
            for index, value in enumerate((1.0, -0.5, 1.0, 1.0, -0.5))
        )
        adx = build_exploratory_candidate(
            _execution(("rulebook_adx_gate",)),
            _execution(("rulebook_adx_gate",), "background-theme"),
            no_theme_events, themed_events, (), (),
            permutation_count=1000, permutation_seed=42, permutation_block_size=20,
        )
        volume = build_exploratory_candidate(
            _execution(("rulebook_volume_gate",)),
            _execution(("rulebook_volume_gate",), "background-theme"),
            no_theme_events, themed_events, (), (),
            permutation_count=1000, permutation_seed=42, permutation_block_size=20,
        )

        self.assertEqual(
            [candidate.rule_id for candidate in rank_top_candidates((volume, adx))],
            ["swing_rulebook_v5__adx", "swing_rulebook_v5__volume"],
        )


if __name__ == "__main__":
    unittest.main()
