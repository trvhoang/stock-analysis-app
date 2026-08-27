"""Finite fast-first Swing catalog v1 tests."""

import unittest
from decimal import Decimal

from flexible_rulebook.catalog import catalog_revision_1, feature_profile


class FlexibleRulebookCatalogTests(unittest.TestCase):
    def test_catalog_v1_locks_fast_first_instances_and_subset_caps(self) -> None:
        catalog = catalog_revision_1()

        self.assertEqual(catalog.revision, "flexible-swing-catalog-v1")
        self.assertEqual(catalog.buy_ema_pairs, ((3, 8), (5, 13), (5, 21), (8, 21)))
        self.assertEqual(catalog.rsi_periods, (5, 9, 14))
        self.assertEqual(catalog.rsi_levels, (50, 52, 55))
        self.assertEqual(catalog.max_buy_predicates, 2)
        self.assertEqual(catalog.max_gate_filter_predicates, 2)
        self.assertEqual(catalog.timeout_bars, (10, 15, 22, 30))
        self.assertEqual(catalog.atr_stop_multipliers, (Decimal("2.0"),))
        self.assertEqual(catalog.atr_target_multipliers, (Decimal("3.0"),))
        self.assertEqual(catalog.atr_trailing_multipliers, (None,))
        self.assertEqual({spec.family for spec in feature_profile(catalog).primitive_specs}, {"adx", "atr", "breakout", "ema", "relative_volume", "rsi"})


if __name__ == "__main__":
    unittest.main()
