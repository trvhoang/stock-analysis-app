"""Causal raw-array feature tests for Flexible Rulebook."""

from datetime import date, timedelta
from decimal import Decimal
import unittest
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from flexible_rulebook.contracts import (
    FeatureBuildContract,
    FeatureProfile,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
)
from flexible_rulebook.features import (
    build_feature_store,
    inspect_primitive_cache,
    resolve_feature_store,
    compose_entry_mask,
    compose_technical_exit_mask,
    primitive_mask,
)
from flexible_rulebook.history import HistorySnapshot


class FlexibleRulebookFeatureTests(unittest.TestCase):
    def _snapshot(self, *, closes: list[int], volumes: list[int] | None = None) -> HistorySnapshot:
        start = date(2026, 1, 2)
        dates = [start + timedelta(days=index) for index in range(len(closes))]
        frame = pd.DataFrame({
            "date": dates,
            "open": closes,
            "high": [value + 2 for value in closes],
            "low": [value - 2 for value in closes],
            "close": closes,
            "volume": volumes or [100 for _ in closes],
        })
        return HistorySnapshot(
            ticker="VCB",
            frame=frame,
            fingerprint="a" * 64,
            quality_state="eligible",
            requested_start=dates[0],
            requested_as_of=dates[-1],
            first_date=dates[0],
            as_of_date=dates[-1],
            evidence_prefix_fingerprint="a" * 64,
        )

    @staticmethod
    def _contract() -> FeatureBuildContract:
        return FeatureBuildContract()

    @staticmethod
    def _relative_volume(window: int = 3) -> PrimitiveSpec:
        return PrimitiveSpec("relative_volume", "prior-window-v1", (("window", window),))

    @staticmethod
    def _breakout(lookback: int = 3) -> PrimitiveSpec:
        return PrimitiveSpec("breakout", "prior-extrema-v1", (("lookback", lookback),))

    @staticmethod
    def _rsi(period: int = 3) -> PrimitiveSpec:
        return PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", period),))

    def test_relative_volume_excludes_current_bar_from_baseline(self) -> None:
        spec = self._relative_volume()
        store = build_feature_store(
            self._snapshot(closes=[100, 101, 102, 103], volumes=[10, 10, 10, 100]),
            self._contract(),
            FeatureProfile((spec,)),
        )

        self.assertEqual(store.array_for(spec, "relative_volume")[3], 10.0)

    def test_breakout_uses_prior_high_not_current_high(self) -> None:
        spec = self._breakout()
        store = build_feature_store(
            self._snapshot(closes=[100, 101, 102, 105]), self._contract(), FeatureProfile((spec,)),
        )
        predicate = PredicateSpec("buy", spec, (("direction", "up"),))

        self.assertTrue(primitive_mask(store, predicate)[3])

    def test_raw_arrays_are_read_only_and_do_not_share_frame_memory(self) -> None:
        spec = self._rsi()
        snapshot = self._snapshot(closes=[100, 101, 102, 103])
        store = build_feature_store(snapshot, self._contract(), FeatureProfile((spec,)))
        snapshot.frame.loc[0, "close"] = 999

        self.assertFalse(store.close.flags.writeable)
        self.assertEqual(store.close[0], 100)
        with self.assertRaises(ValueError):
            store.close[0] = 999

    def test_raw_bigint_values_above_float_precision_remain_exact(self) -> None:
        spec = self._rsi()
        huge = 9_007_199_254_740_993
        store = build_feature_store(
            self._snapshot(closes=[huge, huge + 1, huge + 2, huge + 3]),
            self._contract(),
            FeatureProfile((spec,)),
        )

        self.assertEqual(store.close.tolist(), [huge, huge + 1, huge + 2, huge + 3])

    def test_non_integral_raw_price_is_rejected_instead_of_truncated(self) -> None:
        spec = self._rsi()
        snapshot = self._snapshot(closes=[100, 101, 102, 103])
        snapshot.frame["close"] = snapshot.frame["close"].astype(object)
        snapshot.frame.loc[1, "close"] = "101.5"

        with self.assertRaisesRegex(ValueError, "raw integer"):
            build_feature_store(snapshot, self._contract(), FeatureProfile((spec,)))

    def test_zero_technical_sell_predicates_has_no_exit_mask(self) -> None:
        buy_spec = self._breakout()
        definition = RulebookDefinition(
            buy_predicates=(PredicateSpec("buy", buy_spec, (("direction", "up"),)),),
            max_hold_bars=22,
        )
        store = build_feature_store(
            self._snapshot(closes=[100, 101, 102, 105]), self._contract(), FeatureProfile((buy_spec,)),
        )

        self.assertIsNone(compose_technical_exit_mask(store, definition))
        self.assertTrue(compose_entry_mask(store, definition)[3])

    def test_rsi_threshold_changes_reuse_same_base_array(self) -> None:
        spec = self._rsi()
        store = build_feature_store(
            self._snapshot(closes=[100, 99, 98, 100, 104, 106]), self._contract(), FeatureProfile((spec,)),
        )
        low = PredicateSpec("buy", spec, (("cross", "up"), ("level", Decimal("50"))))
        high = PredicateSpec("buy", spec, (("cross", "up"), ("level", Decimal("70"))))

        self.assertIs(store.array_for(spec, "rsi"), store.array_for(spec, "rsi"))
        self.assertEqual(primitive_mask(store, low).dtype, np.dtype(bool))
        self.assertEqual(primitive_mask(store, high).dtype, np.dtype(bool))

    def test_exact_24_hour_component_offers_reuse_but_older_component_rebuilds(self) -> None:
        rsi = self._rsi()
        snapshot = self._snapshot(closes=[100, 99, 98, 100, 104, 106])
        now = pd.Timestamp("2026-02-01T12:00:00+07:00").to_pydatetime()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolve_feature_store(snapshot, self._contract(), FeatureProfile((rsi,)), root, choice="rebuild", now=now)
            offer = inspect_primitive_cache(snapshot, self._contract(), FeatureProfile((rsi,)), root, now=now + timedelta(hours=24))
            stale = inspect_primitive_cache(snapshot, self._contract(), FeatureProfile((rsi,)), root, now=now + timedelta(hours=24, microseconds=1))

        self.assertTrue(offer.choice_required)
        self.assertFalse(stale.choice_required)
        self.assertEqual(len(offer.reusable_keys), 1)
        self.assertEqual(len(stale.stale_keys), 1)

    def test_reuse_and_rebuild_keep_identical_component_receipt(self) -> None:
        rsi = self._rsi(); volume = self._relative_volume()
        snapshot = self._snapshot(closes=[100, 99, 98, 100, 104, 106])
        now = pd.Timestamp("2026-02-01T12:00:00+07:00").to_pydatetime()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); profile = FeatureProfile((rsi, volume))
            rebuilt = resolve_feature_store(snapshot, self._contract(), profile, root, choice="rebuild", now=now)
            reused = resolve_feature_store(snapshot, self._contract(), profile, root, choice="reuse", now=now + timedelta(minutes=1))

        self.assertEqual(rebuilt.receipt.to_identity_dict(), reused.receipt.to_identity_dict())
        self.assertTrue(np.array_equal(
            rebuilt.store.array_for(rsi, "rsi"), reused.store.array_for(rsi, "rsi"), equal_nan=True,
        ))


if __name__ == "__main__":
    unittest.main()
