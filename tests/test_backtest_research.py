"""Isolated schema-5 staged-research contracts and training-only selection."""

from dataclasses import replace
from datetime import date
import json
import math
import unittest
from unittest.mock import patch

import pandas as pd

from backtest_engine.models import TradeEvent
from backtest_engine.research import (
    MIDTERM_CONTROL,
    MIDTERM_VARIANT,
    SWING_CONTROL,
    SWING_VARIANT,
    ResearchDefinition,
    definition_entry_signal,
    evaluate_research_pair,
    evaluate_research_treatments,
    leave_one_year_out,
    pair_first_overlaps,
    research_metrics,
)


def _trade(
    signal_date: str,
    exit_date: str,
    *,
    return_pct: float = 10.0,
    mae_pct: float = 2.0,
    exit_reason: str = "timeout",
) -> TradeEvent:
    signal = pd.Timestamp(signal_date)
    entry = signal + pd.offsets.BDay(1)
    exit_at = pd.Timestamp(exit_date)
    return TradeEvent(
        signal_date=signal,
        entry_date=entry,
        entry_price=100,
        atr=10,
        stop_loss=85,
        take_profit=125,
        exit_date=exit_at,
        exit_price=max(1, int(round(100 + return_pct))),
        exit_reason=exit_reason,
        return_pct=return_pct,
        source_window=(signal, exit_at),
        maximum_adverse_excursion_pct=mae_pct,
    )


class ResearchDefinitionTests(unittest.TestCase):
    def test_identity_is_immutable_content_hash_and_role_is_research_only(self):
        same = ResearchDefinition(
            definition_id=SWING_CONTROL.definition_id,
            horizon=SWING_CONTROL.horizon,
            setup=SWING_CONTROL.setup,
            trigger=SWING_CONTROL.trigger,
            confirmations=SWING_CONTROL.confirmations,
        )
        changed = replace(same, confirmations=("relative_volume",))

        self.assertEqual(SWING_CONTROL.research_definition_id, same.research_definition_id)
        self.assertNotEqual(same.research_definition_id, changed.research_definition_id)
        self.assertRegex(same.research_definition_id, r"^btr_[0-9a-f]{64}$")
        self.assertEqual("research_only", same.to_dict()["candidate_role"])
        self.assertEqual(same.to_dict(), json.loads(json.dumps(same.to_dict())))

    def test_setup_and_trigger_are_required_before_optional_confirmations(self):
        with self.assertRaisesRegex(ValueError, "setup and trigger are required"):
            ResearchDefinition(
                definition_id="bad",
                horizon="swing",
                setup=None,
                trigger=None,
                confirmations=("adx_directional",),
            )
        with self.assertRaisesRegex(ValueError, "lexical"):
            replace(SWING_CONTROL, confirmations=("relative_volume", "adx_directional"))

    def test_only_the_two_approved_experiment_pairs_are_declared(self):
        self.assertEqual(
            (SWING_CONTROL.setup, SWING_CONTROL.trigger),
            ("ema5_13_and_alligator_up", "rsi9_upcross_52"),
        )
        self.assertEqual(
            (SWING_VARIANT.setup, SWING_VARIANT.trigger),
            ("ema5_above_ema13", "rsi9_upcross_52"),
        )
        self.assertEqual(
            (MIDTERM_CONTROL.setup, MIDTERM_CONTROL.trigger),
            ("sma8_21_and_alligator_up", "rsi14_upcross_65"),
        )
        self.assertEqual(
            (MIDTERM_VARIANT.setup, MIDTERM_VARIANT.trigger),
            ("sma8_21_and_alligator_up", "close_upcross_sma8"),
        )

    def test_entry_signal_requires_directional_setup_and_one_bar_trigger(self):
        frame = pd.DataFrame(
            {
                "close": [9.0, 11.0, 12.0],
                "rulebook_ma_fast": [10.0, 10.0, 11.0],
                "rulebook_ma_slow": [8.0, 8.0, 9.0],
                "rulebook_alligator_lips": [3.0, 3.0, 3.0],
                "rulebook_alligator_teeth": [2.0, 2.0, 2.0],
                "rulebook_alligator_jaw": [1.0, 1.0, 1.0],
                "rulebook_rsi_upcross": [False, True, True],
                "rulebook_missing_required_input": [False, False, True],
            }
        )

        pd.testing.assert_series_equal(
            definition_entry_signal(frame, SWING_CONTROL),
            pd.Series([False, True, False], dtype=bool),
        )
        pd.testing.assert_series_equal(
            definition_entry_signal(frame, MIDTERM_VARIANT),
            pd.Series([False, True, False], dtype=bool),
        )


class ResearchPairingTests(unittest.TestCase):
    def test_first_overlap_pairing_is_deterministic_and_inclusive(self):
        native_dates = tuple(pd.bdate_range("2020-01-01", "2020-02-14").date)
        control = (
            _trade("2020-01-06", "2020-01-20"),
            _trade("2020-02-03", "2020-02-10"),
        )
        variant = (
            _trade("2020-01-03", "2020-01-08"),
            _trade("2020-02-05", "2020-02-12"),
        )

        pairs = pair_first_overlaps(control, variant, native_dates)

        self.assertEqual(2, len(pairs))
        self.assertEqual(1, pairs[0].variant_signal_lead_bars)
        self.assertEqual(-2, pairs[1].variant_signal_lead_bars)
        self.assertEqual(pd.Timestamp("2020-01-07"), pairs[0].overlap_start)
        self.assertEqual(pd.Timestamp("2020-01-08"), pairs[0].overlap_end)

    def test_pairing_leaves_nonoverlapping_trades_unmatched(self):
        native_dates = tuple(pd.bdate_range("2020-01-01", "2020-02-28").date)
        control = (
            _trade("2020-01-02", "2020-01-06"),
            _trade("2020-02-03", "2020-02-10"),
        )
        variant = (_trade("2020-01-20", "2020-01-24"),)

        pairs = pair_first_overlaps(control, variant, native_dates)

        self.assertEqual((), pairs)

    def test_pairing_rejects_unsorted_or_incomplete_native_clock(self):
        trade = _trade("2020-01-06", "2020-01-10")
        with self.assertRaisesRegex(ValueError, "ascending unique"):
            pair_first_overlaps((trade,), (trade,), (date(2020, 1, 7), date(2020, 1, 6)))
        with self.assertRaisesRegex(ValueError, "signal date"):
            pair_first_overlaps((trade,), (trade,), (date(2020, 1, 7), date(2020, 1, 8)))


class ResearchMetricTests(unittest.TestCase):
    def test_metrics_cover_mae_drawdown_stop_rate_years_and_concentration(self):
        events = (
            _trade("2019-12-20", "2020-01-03", return_pct=10.0, mae_pct=3.0),
            _trade(
                "2020-02-03",
                "2020-02-07",
                return_pct=-5.0,
                mae_pct=8.0,
                exit_reason="stop_loss",
            ),
            _trade("2021-01-04", "2021-01-08", return_pct=20.0, mae_pct=1.0),
        )

        metrics = research_metrics(events)

        self.assertEqual(3, metrics.n)
        self.assertEqual(2 / 3 * 100.0, metrics.win_rate)
        self.assertEqual(25.0, metrics.profit_pct)
        self.assertEqual(4.0, metrics.mean_mae_pct)
        self.assertEqual(1 / 3 * 100.0, metrics.stop_loss_rate)
        self.assertAlmostEqual(5.0, metrics.maximum_drawdown_pct)
        self.assertEqual(2, metrics.distinct_years)
        self.assertEqual(0.8, metrics.absolute_pnl_concentration)

    def test_year_omission_uses_completed_exit_calendar_year(self):
        events = (
            _trade("2019-12-20", "2020-01-03", return_pct=5.0),
            _trade("2020-12-29", "2021-01-05", return_pct=-1.0),
            _trade("2021-02-01", "2021-02-05", return_pct=4.0),
        )

        omissions = leave_one_year_out(events)

        self.assertEqual((2020, 2021), tuple(item.omitted_year for item in omissions))
        self.assertEqual((3.0, 5.0), tuple(item.profit_pct for item in omissions))
        self.assertTrue(all(item.positive for item in omissions))

    def test_missing_mae_is_explicitly_unavailable(self):
        event = replace(
            _trade("2020-01-06", "2020-01-10"),
            maximum_adverse_excursion_pct=None,
        )
        self.assertIsNone(research_metrics((event,)).mean_mae_pct)


class ResearchSelectionTests(unittest.TestCase):
    @staticmethod
    def _swing_events(*, variant: bool) -> tuple[TradeEvent, ...]:
        control_signals = pd.bdate_range("2020-01-06", periods=5, freq="10B")
        returns = (2.0, 2.0, -0.5, 2.0, -0.5) if variant else (1.0, 1.0, -1.0, 1.0, -1.0)
        events = []
        for index, signal in enumerate(control_signals):
            actual_signal = signal - pd.offsets.BDay(1) if variant else signal
            exit_at = signal + pd.offsets.BDay(4)
            events.append(
                _trade(
                    actual_signal.strftime("%Y-%m-%d"),
                    exit_at.strftime("%Y-%m-%d"),
                    return_pct=returns[index],
                    mae_pct=3.0 if variant else 4.0,
                    exit_reason="stop_loss" if (not variant and index in (2, 4)) else "timeout",
                )
            )
        return tuple(events)

    def test_swing_acceptance_requires_timing_rank_and_no_worse_risk(self):
        native_dates = tuple(pd.bdate_range("2019-12-01", "2020-04-30").date)
        result = evaluate_research_pair(
            SWING_CONTROL,
            SWING_VARIANT,
            self._swing_events(variant=False),
            self._swing_events(variant=True),
            native_dates,
            control_test=(_trade("2021-01-04", "2021-01-08", return_pct=99.0),),
            variant_test=(_trade("2021-01-04", "2021-01-08", return_pct=-99.0),),
        )

        self.assertTrue(result.training_accepted)
        self.assertEqual(SWING_VARIANT.research_definition_id, result.selected_definition_id)
        self.assertEqual(5, len(result.matched_pairs))
        self.assertEqual(1.0, result.median_variant_signal_lead_bars)

    def test_test_partition_cannot_change_training_selection(self):
        native_dates = tuple(pd.bdate_range("2019-12-01", "2020-04-30").date)
        common = dict(
            control=SWING_CONTROL,
            variant=SWING_VARIANT,
            control_training=self._swing_events(variant=False),
            variant_training=self._swing_events(variant=True),
            native_dates=native_dates,
        )
        first = evaluate_research_pair(
            **common,
            control_test=(_trade("2021-01-04", "2021-01-08", return_pct=99.0),),
            variant_test=(_trade("2021-01-04", "2021-01-08", return_pct=-99.0),),
        )
        second = evaluate_research_pair(
            **common,
            control_test=(_trade("2021-01-04", "2021-01-08", return_pct=-99.0),),
            variant_test=(_trade("2021-01-04", "2021-01-08", return_pct=99.0),),
        )

        self.assertEqual(first.selection_to_dict(), second.selection_to_dict())

    def test_evaluation_rejects_an_unapproved_experiment_pair(self):
        unapproved = replace(SWING_VARIANT, definition_id="unapproved")
        with self.assertRaisesRegex(ValueError, "approved experiment pair"):
            evaluate_research_pair(
                SWING_CONTROL,
                unapproved,
                (),
                (),
                (date(2020, 1, 2),),
            )

    def test_midterm_acceptance_requires_dispersion_and_concentration_safety(self):
        control = (
            _trade("2018-01-02", "2018-01-12", return_pct=4.0, mae_pct=4.0),
            _trade("2019-01-02", "2019-01-11", return_pct=-1.0, mae_pct=4.0),
            _trade("2020-01-02", "2020-01-10", return_pct=2.0, mae_pct=4.0),
        )
        variant = (
            _trade("2018-01-02", "2018-01-12", return_pct=4.0, mae_pct=3.0),
            _trade("2019-01-02", "2019-01-11", return_pct=1.0, mae_pct=3.0),
            _trade("2020-01-02", "2020-01-10", return_pct=3.0, mae_pct=3.0),
        )
        native_dates = tuple(pd.bdate_range("2017-12-01", "2020-02-01").date)

        result = evaluate_research_pair(
            MIDTERM_CONTROL,
            MIDTERM_VARIANT,
            control,
            variant,
            native_dates,
        )

        self.assertTrue(result.training_accepted)
        self.assertEqual(MIDTERM_VARIANT.research_definition_id, result.selected_definition_id)
        self.assertLessEqual(
            result.variant_training.absolute_pnl_concentration,
            result.control_training.absolute_pnl_concentration,
        )
        self.assertEqual("research_only", result.to_dict()["candidate_role"])

    def test_training_dsr_selects_treatment_and_test_cannot_reverse_it(self):
        native_dates = tuple(pd.bdate_range("2019-12-01", "2021-02-28").date)
        control = self._swing_events(variant=False)
        variant = self._swing_events(variant=True)
        weak_test = (_trade("2021-01-04", "2021-01-08", return_pct=-20.0),)
        strong_test = (_trade("2021-01-04", "2021-01-08", return_pct=20.0),)
        arguments = dict(
            control=SWING_CONTROL,
            variant=SWING_VARIANT,
            control_no_theme_training=control,
            control_themed_training=control,
            variant_no_theme_training=variant,
            variant_themed_training=variant,
            native_dates=native_dates,
        )
        with patch(
            "backtest_engine.research.calculate_deflated_sharpe",
            side_effect=(0.1, 0.9, 0.8, 0.2),
        ):
            first = evaluate_research_treatments(
                **arguments,
                control_no_theme_test=strong_test,
                control_themed_test=weak_test,
                variant_no_theme_test=weak_test,
                variant_themed_test=strong_test,
            )
        with patch(
            "backtest_engine.research.calculate_deflated_sharpe",
            side_effect=(0.1, 0.9, 0.8, 0.2),
        ):
            second = evaluate_research_treatments(
                **arguments,
                control_no_theme_test=weak_test,
                control_themed_test=strong_test,
                variant_no_theme_test=strong_test,
                variant_themed_test=weak_test,
            )

        self.assertEqual("background-theme", first.control_preferred_treatment)
        self.assertEqual("no-background-theme", first.variant_preferred_treatment)
        self.assertEqual(first.selection_to_dict(), second.selection_to_dict())


if __name__ == "__main__":
    unittest.main()
