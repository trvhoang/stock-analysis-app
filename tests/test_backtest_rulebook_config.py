"""Immutable V3 horizon-rulebook configuration contracts."""

from dataclasses import FrozenInstanceError, fields, replace
import unittest

from backtest_engine.config import (
    ENTRY_GATE_NAMES,
    BacktestBatchConfig,
    BacktestConfig,
    RulebookSpec,
    rulebook_for,
)
from backtest_engine.models import RulebookExecution


class BacktestRulebookConfigTests(unittest.TestCase):
    def test_swing_rulebook_is_the_approved_daily_contract(self):
        rule = rulebook_for("swing")

        self.assertIsInstance(rule, RulebookSpec)
        self.assertEqual(rule.rule_id, "swing_rulebook_v5")
        self.assertEqual(rule.native_timeframe, "daily")
        self.assertEqual((rule.ma_kind, rule.ma_pair), ("EMA", (5, 13)))
        self.assertEqual((rule.rsi_period, rule.rsi_upcross), (9, 52))
        self.assertEqual(rule.alligator_periods, (8, 5, 3))
        self.assertEqual(rule.alligator_lags, (5, 3, 2))
        self.assertEqual((rule.volume_window, rule.volume_multiplier), (10, 1.15))
        self.assertEqual((rule.adx_period, rule.adx_minimum), (14, 17))
        self.assertTrue(rule.joint_trend_required)
        self.assertEqual(
            (rule.min_exit_offset_bars, rule.min_hold_bars, rule.max_hold_bars),
            (3, 4, 22),
        )
        self.assertEqual(rule.min_n, 5)
        self.assertEqual(rule.theme_sma_window, 50)

    def test_midterm_rulebook_is_weekly_and_never_or_themed(self):
        rule = rulebook_for("midterm")

        self.assertEqual(rule.rule_id, "midterm_rulebook_v5")
        self.assertEqual(rule.native_timeframe, "weekly")
        self.assertEqual(rule.weekly_frequency, "W-FRI")
        self.assertEqual((rule.ma_kind, rule.ma_pair), ("SMA", (8, 21)))
        self.assertEqual((rule.rsi_period, rule.rsi_upcross), (14, 65))
        self.assertEqual(rule.alligator_periods, (13, 8, 5))
        self.assertEqual(rule.alligator_lags, (8, 5, 3))
        self.assertEqual((rule.volume_window, rule.volume_multiplier), (8, 1.3))
        self.assertEqual(rule.adx_minimum, 20)
        self.assertEqual(
            (rule.min_exit_offset_bars, rule.min_hold_bars, rule.max_hold_bars),
            (1, 2, 16),
        )
        self.assertEqual(rule.min_n, 5)
        self.assertEqual(rule.theme_sma_window, 20)
        with self.assertRaisesRegex(ValueError, "AND"):
            RulebookExecution(
                rule, ENTRY_GATE_NAMES,
                theme_variant="background-theme",
                theme_mode="OR",
            )

    def test_execution_identity_accepts_only_registered_rulebook_and_and_theme(self):
        swing = rulebook_for("swing")
        no_theme = RulebookExecution(
            swing, ("rulebook_adx_gate", "rulebook_rsi_upcross")
        )
        themed = RulebookExecution(
            swing, ("rulebook_adx_gate", "rulebook_rsi_upcross"),
            theme_variant="background-theme",
            theme_mode="AND",
        )

        self.assertEqual(
            no_theme.to_dict(),
            {
                "rule_id": "swing_rulebook_v5__adx__rsi_upcross",
                "horizon": "swing",
                "selected_gates": ["rulebook_adx_gate", "rulebook_rsi_upcross"],
                "theme_variant": "no-background-theme",
                "theme_mode": None,
            },
        )
        self.assertEqual(themed.rule_id, "swing_rulebook_v5__adx__rsi_upcross")
        self.assertEqual(themed.horizon, "swing")
        with self.assertRaises(FrozenInstanceError):
            swing.min_n = 1
        with self.assertRaisesRegex(ValueError, "registered"):
            RulebookExecution(replace(swing, min_n=1), ENTRY_GATE_NAMES)

    def test_execution_rejects_unknown_or_nonlexical_gate_subset(self):
        swing = rulebook_for("swing")
        with self.assertRaisesRegex(ValueError, "selected_gates"):
            RulebookExecution(swing, ("rulebook_not_a_gate",))
        with self.assertRaisesRegex(ValueError, "lexical"):
            RulebookExecution(
                swing, ("rulebook_rsi_upcross", "rulebook_adx_gate")
            )

    def test_request_configs_cannot_override_rule_owned_values_or_emit_v2(self):
        rule_owned = {
            "min_n", "max_hold_bars", "threshold_score_buy", "atr_period",
            "theme_variant", "theme_mode", "include_theme", "deflated_sharpe_cutoff",
            "permutation_alpha",
        }
        config_fields = {field.name for field in fields(BacktestConfig)}
        batch_fields = {field.name for field in fields(BacktestBatchConfig)}

        self.assertFalse(rule_owned & config_fields)
        self.assertFalse(rule_owned & batch_fields)
        with self.assertRaises(TypeError):
            BacktestConfig.for_ticker("FPT", min_n=1)
        with self.assertRaises(TypeError):
            BacktestBatchConfig(tickers=("FPT",), max_hold_bars=1)

        self.assertEqual(
            BacktestConfig.for_ticker("FPT").to_dict()["request_type"],
            "backtest_single_v5",
        )
        self.assertEqual(
            BacktestBatchConfig(tickers=("FPT",)).to_dict()["request_type"],
            "backtest_batch_v5",
        )


if __name__ == "__main__":
    unittest.main()
