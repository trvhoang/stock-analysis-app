"""Daily flat-to-flat execution tests for Flexible Rulebook."""

from datetime import date, timedelta
from dataclasses import replace
from decimal import Decimal
import unittest

import numpy as np
import pandas as pd

from flexible_rulebook.contracts import (
    EvaluationPartition,
    FeatureBuildContract,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
)
from flexible_rulebook.execution import build_event_exit_plan, event_plan_is_compatible, execute_rulebook, execute_rulebook_reference, ExecutionInterrupted
from flexible_rulebook.features import FeatureStore
from flexible_rulebook.history import HistorySnapshot


class FlexibleRulebookExecutionTests(unittest.TestCase):
    @staticmethod
    def _readonly(values: list[int] | list[float], dtype: object) -> np.ndarray:
        array = np.array(values, dtype=dtype)
        array.setflags(write=False)
        return array

    def _store(self, *, opens: list[int], highs: list[int], lows: list[int]) -> FeatureStore:
        start = date(2026, 1, 2)
        dates = tuple(start + timedelta(days=index) for index in range(len(opens)))
        frame = pd.DataFrame({
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": opens,
            "volume": [100] * len(opens),
        })
        snapshot = HistorySnapshot(
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
        atr14 = PrimitiveSpec("atr", "atr-wilder-v1", (("period", 14),))
        return FeatureStore(
            snapshot=snapshot,
            dates=dates,
            open=self._readonly(opens, np.int64),
            high=self._readonly(highs, np.int64),
            low=self._readonly(lows, np.int64),
            close=self._readonly(opens, np.int64),
            volume=self._readonly([100] * len(opens), np.int64),
            components={atr14: {"atr": self._readonly([10.0] * len(opens), np.float64)}},
        )

    @staticmethod
    def _definition() -> RulebookDefinition:
        rsi = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        return RulebookDefinition(
            buy_predicates=(PredicateSpec("buy", rsi, (("cross", "up"), ("level", Decimal("52")))),),
            atr_stop_multiplier=Decimal("1.5"),
            atr_target_multiplier=Decimal("2.5"),
            max_hold_bars=4,
        )

    @staticmethod
    def _partition(store: FeatureStore) -> EvaluationPartition:
        return EvaluationPartition(
            label="training",
            start=store.dates[0],
            end=store.dates[-1],
            start_ordinal=0,
            end_ordinal=len(store.dates) - 1,
            row_count=len(store.dates),
        )

    def test_buy_at_close_signal_enters_next_raw_open(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200],
            lows=[9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_090],
        )
        entry_mask = np.array([False, False, True, False, False, False, False])

        trade = execute_rulebook(store, entry_mask, None, self._definition(), self._partition(store))[0]

        self.assertEqual(
            (trade.signal_date, trade.entry_date, trade.entry_price),
            (date(2026, 1, 4), date(2026, 1, 5), 10_100),
        )
        self.assertEqual((trade.exit_date, trade.exit_reason, trade.exit_price), (date(2026, 1, 8), "take_profit", 10_125.0))

    def test_stop_first_and_minimum_hold_block_early_exit(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_110],
            lows=[9_990, 9_990, 9_990, 10_000, 10_000, 10_000, 10_000],
        )
        entry_mask = np.array([False, False, True, False, False, False, False])

        trade = execute_rulebook(store, entry_mask, None, self._definition(), self._partition(store))[0]

        self.assertEqual((trade.exit_date, trade.exit_reason, trade.exit_price), (date(2026, 1, 8), "stop_loss", 10_085.0))

    def test_technical_signal_at_close_e_plus_2_fills_open_e_plus_3_without_recheck(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_110],
            lows=[9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_090],
        )
        entry_mask = np.array([False, False, True, False, False, False, False])
        technical = np.array([False, False, False, False, False, True, False])

        trade = execute_rulebook(store, entry_mask, technical, self._definition(), self._partition(store))[0]

        self.assertEqual((trade.exit_date, trade.exit_reason, trade.exit_price), (date(2026, 1, 8), "technical_exit", 10_100.0))

    def test_blocked_technical_exit_is_discarded_not_deferred(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_110],
            lows=[9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_090],
        )
        entry_mask = np.array([False, False, True, False, False, False, False])
        technical = np.array([False, False, False, True, False, False, False])

        trade = execute_rulebook(store, entry_mask, technical, self._definition(), self._partition(store))[0]

        self.assertEqual((trade.exit_date, trade.exit_reason), (date(2026, 1, 8), "timeout"))

    def test_partition_starts_flat_and_drops_crossing_trade(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200],
            lows=[9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_090],
        )
        partition = EvaluationPartition("test", store.dates[3], store.dates[-1], 3, 6, 4)
        entry_mask = np.array([False, False, True, False, False, False, False])

        self.assertEqual(execute_rulebook(store, entry_mask, None, self._definition(), partition), ())

    def test_interruption_returns_uncommitted_sentinel(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200],
            lows=[9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_090],
        )

        result = execute_rulebook(
            store, np.zeros(7, dtype=bool), None, self._definition(), self._partition(store), should_stop=lambda: True,
        )

        self.assertIsInstance(result, ExecutionInterrupted)

    def test_gap_stop_fills_raw_open_not_threshold(self) -> None:
        store = self._store(opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_000], highs=[10_010]*7, lows=[9_990]*7)
        trade = execute_rulebook(store, np.array([False, False, True, False, False, False, False]), None, self._definition(), self._partition(store))[0]
        self.assertEqual((trade.exit_reason, trade.exit_price), ("stop_loss", 10_000.0))

    def test_event_plan_falls_back_to_exact_reference(self) -> None:
        store = self._store(opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100], highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200], lows=[9_990]*7)
        entries = np.array([False, False, True, False, False, False, False])
        partition = self._partition(store)
        plan = build_event_exit_plan(store, entries, None, self._definition(), partition, "receipt")
        self.assertIsNotNone(plan)
        self.assertEqual(
            execute_rulebook(store, entries, None, self._definition(), partition, event_plan=plan, receipt_digest="receipt"),
            execute_rulebook_reference(store, entries, None, self._definition(), partition),
        )

    def test_event_plan_identity_mismatch_uses_reference(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200], lows=[10_090] * 7,
        )
        entries = np.array([False, False, True, False, False, False, False])
        partition = self._partition(store)
        technical = np.zeros(7, dtype=bool)
        plan = build_event_exit_plan(store, entries, technical, self._definition(), partition, "receipt-a")

        self.assertEqual(
            execute_rulebook(store, entries, technical, self._definition(), partition, event_plan=plan, receipt_digest="receipt-b"),
            execute_rulebook_reference(store, entries, technical, self._definition(), partition),
        )

    def test_event_plan_rejects_source_receipt_mask_and_partition_mismatch(self) -> None:
        store = self._store(
            opens=[10_000] * 7, highs=[10_010] * 7, lows=[9_990] * 7,
        )
        entries = np.array([False, False, True, False, False, False, False])
        technical = np.zeros(7, dtype=bool)
        partition = self._partition(store)
        plan = build_event_exit_plan(store, entries, technical, self._definition(), partition, "receipt")
        assert plan is not None

        self.assertTrue(event_plan_is_compatible(plan, store, entries, technical, self._definition(), partition, "receipt"))
        self.assertFalse(event_plan_is_compatible(replace(plan, source_fingerprint="b" * 64), store, entries, technical, self._definition(), partition, "receipt"))
        self.assertFalse(event_plan_is_compatible(plan, store, entries, technical, self._definition(), partition, "other"))
        self.assertFalse(event_plan_is_compatible(plan, store, entries, None, self._definition(), partition, "receipt"))
        other_partition = EvaluationPartition("test", store.dates[1], store.dates[-1], 1, 6, 6)
        self.assertFalse(event_plan_is_compatible(plan, store, entries, technical, self._definition(), other_partition, "receipt"))

    def test_trailing_stop_uses_prior_high_water_not_current_high(self) -> None:
        definition = RulebookDefinition(
            buy_predicates=self._definition().buy_predicates,
            atr_trailing_multiplier=Decimal("1.5"),
            max_hold_bars=4,
        )
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_400],
            highs=[10_010, 10_010, 10_010, 10_100, 10_150, 10_150, 10_500],
            lows=[9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_300],
        )

        trade = execute_rulebook(
            store, np.array([False, False, True, False, False, False, False]), None, definition, self._partition(store),
        )[0]

        self.assertEqual((trade.exit_reason, trade.exit_price), ("timeout", 10_400.0))

    def test_deadline_technical_then_price_then_timeout_precedence(self) -> None:
        store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200], lows=[10_090] * 7,
        )
        entries = np.array([False, False, True, False, False, False, False])
        queued = np.array([False, False, False, False, False, True, False])
        technical = execute_rulebook(store, entries, queued, self._definition(), self._partition(store))[0]
        price = execute_rulebook(store, entries, None, self._definition(), self._partition(store))[0]
        timeout_store = self._store(
            opens=[10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            highs=[10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_110], lows=[10_090] * 7,
        )
        timeout = execute_rulebook(
            timeout_store, entries, np.array([False, False, False, False, False, False, True]), self._definition(), self._partition(timeout_store),
        )[0]

        self.assertEqual(technical.exit_reason, "technical_exit")
        self.assertEqual(price.exit_reason, "take_profit")
        self.assertEqual(timeout.exit_reason, "timeout")

    def test_sparse_and_dense_entry_masks_match_reference(self) -> None:
        store = self._store(
            opens=[10_000] * 10, highs=[10_010] * 10, lows=[9_990] * 10,
        )
        partition = self._partition(store)
        for entries in (
            np.array([False, False, True, False, False, False, False, False, False, False]),
            np.array([False, True, True, True, True, True, True, True, True, False]),
        ):
            self.assertEqual(
                execute_rulebook(store, entries, None, self._definition(), partition),
                execute_rulebook_reference(store, entries, None, self._definition(), partition),
            )


if __name__ == "__main__":
    unittest.main()
