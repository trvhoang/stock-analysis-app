"""Observable v2 feature-cache and predicate contracts."""

import unittest

import pandas as pd

from flexible_rulebook.v2.contracts import PredicateV2
from flexible_rulebook.v2.features import FeatureStore, component_cache_key


def make_ohlcv(rows=12):
    close = [10.0, 11.0, 14.0, 13.0, 15.0, 14.0, 18.0, 19.0, 17.0, 20.0, 21.0, 22.0][:rows]
    return pd.DataFrame(
        {
            "high": [value + 1.0 for value in close],
            "low": [value - 1.0 for value in close],
            "close": close,
            "volume": [100, 120, 140, 180, 200, 170, 220, 240, 180, 260, 280, 300][:rows],
        }
    )


def predicate(family, revision, settings, operator, condition=None, *, role="buy", lookback=None):
    return PredicateV2(
        role=role,
        family=family,
        family_revision=revision,
        settings=settings,
        operator=operator,
        condition={} if condition is None else condition,
        direction_lookback=lookback,
    )


class FeatureStoreTests(unittest.TestCase):
    def test_threshold_only_changes_reuse_one_component_but_rebuild_the_mask(self):
        store = FeatureStore(make_ohlcv())
        low = predicate("rsi", "rsi-wilder-sma-seeded-v1", {"period": 3}, "above", {"threshold": 70})
        high = predicate("rsi", "rsi-wilder-sma-seeded-v1", {"period": 3}, "above", {"threshold": 85})

        self.assertEqual(component_cache_key(low), component_cache_key(high))
        self.assertIs(store.component(low), store.component(high))
        self.assertNotEqual(store.evaluate(low).mask.tolist(), store.evaluate(high).mask.tolist())

    def test_cross_support_and_direction_are_exact_boolean_facts(self):
        store = FeatureStore(make_ohlcv())
        cross = predicate("rsi", "rsi-wilder-sma-seeded-v1", {"period": 3}, "upcross", {"threshold": 70})
        evaluated = store.evaluate(cross)
        self.assertEqual([False, False, False, False, False, False, True, False, False, True, False, False], evaluated.mask.tolist())
        self.assertEqual([False, False, False, False, True, False, True, True, False, True, True, True], evaluated.support.tolist())

        flat_then_rising = FeatureStore(
            pd.DataFrame(
                {
                    "high": [11.0, 11.0, 11.0, 12.0],
                    "low": [9.0, 9.0, 9.0, 10.0],
                    "close": [10.0, 10.0, 10.0, 11.0],
                    "volume": [100, 100, 100, 100],
                }
            )
        )
        rising = predicate("ema", "ema-close-adjust-false-v1", {"period": 2}, "rising", lookback=1)
        direction = flat_then_rising.evaluate(rising)
        self.assertFalse(bool(direction.mask.iloc[2]))  # Equal finite values never pass.
        self.assertTrue(bool(direction.mask.iloc[3]))

    def test_warmup_is_false_and_reports_explicit_unavailability(self):
        store = FeatureStore(make_ohlcv(rows=3))
        too_early = predicate("rsi", "rsi-wilder-sma-seeded-v1", {"period": 3}, "above", {"threshold": 50})

        result = store.evaluate(too_early)

        self.assertEqual([False, False, False], result.mask.tolist())
        self.assertEqual([False, False, False], result.support.tolist())
        self.assertIn("unavailable:rsi", result.diagnostics)

    def test_alligator_spread_direction_requires_an_explicit_lookback(self):
        store = FeatureStore(make_ohlcv())
        opening_without_lookback = predicate(
            "alligator",
            "alligator-hl2-smma-v1",
            {"jaw_period": 4, "teeth_period": 3, "lips_period": 2, "jaw_offset": 2, "teeth_offset": 1, "lips_offset": 0},
            "opening",
        )

        with self.assertRaisesRegex(ValueError, "direction_lookback"):
            store.evaluate(opening_without_lookback)

    def test_every_registered_family_builds_a_component_from_its_math_settings(self):
        store = FeatureStore(make_ohlcv())
        examples = (
            predicate("sma", "sma-close-v1", {"fast_period": 2, "slow_period": 3}, "bullish_state"),
            predicate("ema", "ema-close-adjust-false-v1", {"fast_period": 2, "slow_period": 3}, "bullish_state"),
            predicate("rsi", "rsi-wilder-sma-seeded-v1", {"period": 3}, "above", {"threshold": 50}),
            predicate("alligator", "alligator-hl2-smma-v1", {"jaw_period": 4, "teeth_period": 3, "lips_period": 2, "jaw_offset": 2, "teeth_offset": 1, "lips_offset": 0}, "bullish_alignment"),
            predicate("adx_dmi", "adx-dmi-wilder-sma-seeded-v1", {"period": 3}, "above", {"threshold": 20}),
            predicate("stochastic", "stochastic-sma-v1", {"k_period": 3, "k_smoothing": 2, "d_period": 2}, "bullish_state"),
            predicate("breakout", "prior-extrema-v1", {"period": 3}, "crosses_above"),
            predicate("relative_volume", "relative-volume-prior-window-v1", {"period": 3}, "above", {"threshold": 1.2}),
            predicate("obv", "obv-close-direction-v1", {"period": 3}, "bullish_state"),
            predicate("atr", "atr-wilder-sma-seeded-v1", {"period": 3}, "rising", role="gate", lookback=1),
            predicate("bollinger", "bollinger-close-sample-v1", {"period": 3, "multiplier": 2.0}, "crosses_above"),
            predicate("supertrend", "supertrend-hl2-wilder-v1", {"period": 3, "multiplier": 2.0}, "bullish_state"),
        )

        for item in examples:
            with self.subTest(family=item.family):
                component = store.component(item)
                self.assertEqual(len(store.frame), len(component))
                self.assertFalse(component.empty)

    def test_appending_future_rows_cannot_rewrite_a_prior_predicate_mask(self):
        source = make_ohlcv(rows=10)
        future = pd.concat(
            [source, pd.DataFrame({"high": [100.0], "low": [90.0], "close": [95.0], "volume": [10_000]})],
            ignore_index=True,
        )
        item = predicate("rsi", "rsi-wilder-sma-seeded-v1", {"period": 3}, "above", {"threshold": 70})

        before = FeatureStore(source).evaluate(item)
        after = FeatureStore(future).evaluate(item)

        pd.testing.assert_series_equal(before.mask, after.mask.iloc[: len(before.mask)].reset_index(drop=True))
        pd.testing.assert_series_equal(before.support, after.support.iloc[: len(before.support)].reset_index(drop=True))

    def test_store_validates_predicates_against_its_native_horizon(self):
        store = FeatureStore(make_ohlcv(), horizon="midterm")
        item = predicate("rsi", "rsi-wilder-sma-seeded-v1", {"period": 3}, "above", {"threshold": 50})

        self.assertTrue(store.evaluate(item).mask.iloc[-1])


if __name__ == "__main__":
    unittest.main()
