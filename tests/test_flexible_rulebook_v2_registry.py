"""Metadata and bounds for user-authored Flexible v2 indicators."""

from __future__ import annotations

import unittest

from flexible_rulebook.v2.contracts import PredicateV2
from flexible_rulebook.v2.registry import DEFAULT_INDICATOR_REGISTRY


class FlexibleRulebookV2RegistryTests(unittest.TestCase):
    def test_registry_exposes_the_approved_indicator_families_and_roles(self) -> None:
        self.assertEqual(
            set(DEFAULT_INDICATOR_REGISTRY.families),
            {
                "sma", "ema", "rsi", "alligator", "adx_dmi", "stochastic",
                "breakout", "relative_volume", "obv", "atr", "bollinger", "supertrend",
            },
        )
        self.assertIn("technical_sell", DEFAULT_INDICATOR_REGISTRY.for_family("supertrend").roles)
        self.assertNotIn("buy", DEFAULT_INDICATOR_REGISTRY.for_family("atr").roles)

    def test_registry_enforces_parameter_bounds_and_cross_parameter_rules(self) -> None:
        invalid_rsi = PredicateV2(
            role="buy",
            family="rsi",
            family_revision="rsi-wilder-sma-seeded-v1",
            settings={"period": 101},
            operator="upcross",
            condition={"threshold": 52},
        )
        with self.assertRaisesRegex(ValueError, "period"):
            DEFAULT_INDICATOR_REGISTRY.validate_predicate(invalid_rsi, horizon="swing")

        invalid_ema = PredicateV2(
            role="gate",
            family="ema",
            family_revision="ema-close-adjust-false-v1",
            settings={"fast_period": 13, "slow_period": 5},
            operator="bullish_state",
        )
        with self.assertRaisesRegex(ValueError, "fast_period"):
            DEFAULT_INDICATOR_REGISTRY.validate_predicate(invalid_ema, horizon="swing")

    def test_registry_rejects_unknown_settings_operators_and_timeframe_mismatch(self) -> None:
        invalid_setting = PredicateV2(
            role="buy",
            family="rsi",
            family_revision="rsi-wilder-sma-seeded-v1",
            settings={"period": 9, "secret": 1},
            operator="upcross",
            condition={"threshold": 52},
        )
        with self.assertRaisesRegex(ValueError, "unknown setting"):
            DEFAULT_INDICATOR_REGISTRY.validate_predicate(invalid_setting, horizon="swing")

        invalid_operator = PredicateV2(
            role="buy",
            family="rsi",
            family_revision="rsi-wilder-sma-seeded-v1",
            settings={"period": 9},
            operator="bullish_state",
        )
        with self.assertRaisesRegex(ValueError, "does not support operator"):
            DEFAULT_INDICATOR_REGISTRY.validate_predicate(invalid_operator, horizon="swing")

        with self.assertRaisesRegex(ValueError, "does not support horizon"):
            DEFAULT_INDICATOR_REGISTRY.validate_predicate(
                PredicateV2(
                    role="buy",
                    family="sma",
                    family_revision="sma-close-v1",
                    settings={"period": 8},
                    operator="above",
                    condition={"threshold": 1},
                ),
                horizon="unknown",
            )

    def test_registry_has_declared_warmup_outputs_and_support_projection(self) -> None:
        bollinger = DEFAULT_INDICATOR_REGISTRY.for_family("bollinger")
        supertrend = DEFAULT_INDICATOR_REGISTRY.for_family("supertrend")

        self.assertGreater(bollinger.warmup_bars({"period": 20, "multiplier": 2}), 0)
        self.assertIn("percent_b", bollinger.output_names)
        self.assertEqual(bollinger.input_series, ("close",))
        self.assertEqual(supertrend.input_series, ("high", "low", "close"))
        self.assertEqual(supertrend.support_projection, "state_or_direction")
        self.assertIn("direction_flip", supertrend.operators)


if __name__ == "__main__":
    unittest.main()
