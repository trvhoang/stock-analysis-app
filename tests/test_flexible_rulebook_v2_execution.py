"""Causal native-bar execution contracts for Flexible Rulebook v2."""

from datetime import date, timedelta
from decimal import Decimal
import unittest

import numpy as np

from flexible_rulebook.v2.contracts import AtrExitV2, PredicateV2, RulebookDefinitionV2
from flexible_rulebook.v2.execution import CompletedTrade, execute_rulebook
from flexible_rulebook.v2.history import NativeBar, NativePartition


class FlexibleRulebookV2ExecutionTests(unittest.TestCase):
    def _definition(self, *, atr_exit: AtrExitV2 | None = None, max_hold_bars: int = 4) -> RulebookDefinitionV2:
        return RulebookDefinitionV2(
            horizon="swing",
            entry_operator="all",
            buy_predicates=(PredicateV2(
                role="buy", family="rsi", family_revision="rsi-wilder-sma-seeded-v1",
                settings={"period": 9}, operator="upcross", condition={"threshold": 52},
            ),),
            technical_exits=(PredicateV2(
                role="technical_sell", family="rsi", family_revision="rsi-wilder-sma-seeded-v1",
                settings={"period": 9}, operator="downcross", condition={"threshold": 48},
            ),),
            atr_exit=atr_exit,
            max_hold_bars=max_hold_bars,
        )

    def _bars(self, opens: list[int], highs: list[int] | None = None, lows: list[int] | None = None) -> tuple[NativeBar, ...]:
        start = date(2026, 1, 5)
        return tuple(
            NativeBar(
                ordinal=index,
                bucket_label=start + timedelta(days=index),
                first_session=start + timedelta(days=index),
                last_session=start + timedelta(days=index),
                open=value,
                high=(highs or opens)[index],
                low=(lows or opens)[index],
                close=value,
                volume=100,
            )
            for index, value in enumerate(opens)
        )

    @staticmethod
    def _partition(bars: tuple[NativeBar, ...]) -> NativePartition:
        return NativePartition(
            label="training", start_ordinal=0, end_ordinal=len(bars) - 1,
            start_bucket=bars[0].bucket_label, end_bucket=bars[-1].bucket_label,
            start_session=bars[0].first_session, end_session=bars[-1].last_session,
            row_count=len(bars),
        )

    def test_next_open_entry_frozen_signal_atr_and_stop_first_collision_after_minimum_hold(self) -> None:
        bars = self._bars(
            [10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            [10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200],
            [9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_000],
        )
        result = execute_rulebook(
            bars, np.array([False, False, True, False, False, False, False]), None,
            self._definition(atr_exit=AtrExitV2(stop_multiplier=Decimal("1.5"), target_multiplier=Decimal("2.5"))),
            self._partition(bars), atr_values=np.array([100.0, 100.0, 10.0, 100.0, 100.0, 100.0, 100.0]),
        )

        self.assertEqual(1, len(result))
        trade = result[0]
        self.assertEqual((trade.signal_date, trade.entry_date, trade.entry_price), (date(2026, 1, 7), date(2026, 1, 8), 10_100))
        self.assertEqual((trade.exit_date, trade.exit_reason, trade.exit_price), (date(2026, 1, 11), "stop_loss", 10_085.0))

    def test_technical_exit_is_queued_at_close_then_fills_next_eligible_native_open_without_recheck(self) -> None:
        bars = self._bars([10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100])
        result = execute_rulebook(
            bars, np.array([False, False, True, False, False, True, False]),
            np.array([False, False, False, False, False, True, False]),
            self._definition(), self._partition(bars),
        )

        self.assertEqual((result[0].exit_date, result[0].exit_reason, result[0].exit_price), (date(2026, 1, 11), "technical_exit", 10_100.0))

    def test_timeout_closes_at_last_session_suppresses_open_signals_and_allows_exit_bar_reentry(self) -> None:
        bars = self._bars([10_000] * 11)
        result = execute_rulebook(
            bars,
            np.array([False, False, True, False, True, False, True, False, False, False, False]),
            None, self._definition(max_hold_bars=4), self._partition(bars),
        )

        self.assertEqual(2, len(result))
        self.assertEqual((result[0].signal_bar_ordinal, result[0].exit_bar_ordinal, result[0].exit_reason), (2, 6, "timeout"))
        self.assertEqual((result[1].signal_bar_ordinal, result[1].entry_bar_ordinal, result[1].exit_bar_ordinal), (6, 7, 10))

    def test_midterm_uses_actual_last_signal_session_and_actual_first_fill_session_not_friday_labels(self) -> None:
        bars = (
            NativeBar(0, date(2026, 1, 9), date(2026, 1, 5), date(2026, 1, 8), 10_000, 10_100, 9_900, 10_000, 100),
            NativeBar(1, date(2026, 1, 16), date(2026, 1, 12), date(2026, 1, 16), 10_100, 10_200, 10_000, 10_100, 100),
            NativeBar(2, date(2026, 1, 23), date(2026, 1, 19), date(2026, 1, 23), 10_100, 10_200, 10_000, 10_100, 100),
            NativeBar(3, date(2026, 1, 30), date(2026, 1, 26), date(2026, 1, 30), 10_100, 10_200, 10_000, 10_100, 100),
            NativeBar(4, date(2026, 2, 6), date(2026, 2, 2), date(2026, 2, 6), 10_100, 10_200, 10_000, 10_100, 100),
        )
        partition = NativePartition("test", 0, 4, bars[0].bucket_label, bars[-1].bucket_label, bars[0].first_session, bars[-1].last_session, 5)
        definition = self._definition(max_hold_bars=4)
        result = execute_rulebook(
            bars, np.array([True, False, False, False, False]), np.array([False, False, False, True, False]),
            definition, partition,
        )

        self.assertEqual((result[0].signal_date, result[0].entry_date, result[0].exit_date), (date(2026, 1, 8), date(2026, 1, 12), date(2026, 2, 2)))

    def test_gap_stop_uses_raw_open_and_trailing_stop_uses_only_prior_high_water(self) -> None:
        gap_bars = self._bars(
            [10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_000],
            [10_010] * 7, [9_990] * 7,
        )
        gap = execute_rulebook(
            gap_bars, np.array([False, False, True, False, False, False, False]), None,
            self._definition(atr_exit=AtrExitV2(stop_multiplier=Decimal("1.5"))), self._partition(gap_bars),
            atr_values=np.array([10.0] * 7),
        )[0]
        self.assertEqual((gap.exit_reason, gap.exit_price), ("stop_loss", 10_000.0))

        trailing_bars = self._bars(
            [10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            [10_010, 10_010, 10_010, 10_100, 10_200, 10_150, 10_500],
            [9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_000],
        )
        trailing = execute_rulebook(
            trailing_bars, np.array([False, False, True, False, False, False, False]), None,
            self._definition(atr_exit=AtrExitV2(trailing_multiplier=Decimal("1.5"))), self._partition(trailing_bars),
            atr_values=np.array([10.0] * 7),
        )[0]
        self.assertEqual((trailing.exit_reason, trailing.exit_price), ("stop_loss", 10_100.0))

    def test_deadline_technical_exit_precedes_price_and_partition_starts_flat(self) -> None:
        bars = self._bars(
            [10_000, 10_000, 10_000, 10_100, 10_100, 10_100, 10_100],
            [10_010, 10_010, 10_010, 10_110, 10_110, 10_110, 10_200],
            [9_990, 9_990, 9_990, 10_090, 10_090, 10_090, 10_000],
        )
        result = execute_rulebook(
            bars, np.array([False, False, True, False, False, True, False]),
            np.array([False, False, False, False, False, True, False]),
            self._definition(atr_exit=AtrExitV2(stop_multiplier=Decimal("1.5"), target_multiplier=Decimal("2.5"))),
            self._partition(bars), atr_values=np.array([10.0] * 7),
        )
        self.assertEqual("technical_exit", result[0].exit_reason)

        test_partition = NativePartition("test", 3, 6, bars[3].bucket_label, bars[6].bucket_label, bars[3].first_session, bars[6].last_session, 4)
        self.assertEqual((), execute_rulebook(
            bars, np.array([False, False, True, False, False, False, False]), None,
            self._definition(), test_partition,
        ))

    def test_no_technical_exit_definition_cannot_be_forced_to_sell_by_an_external_mask(self) -> None:
        bars = self._bars([10_000] * 7)
        buy = PredicateV2(
            role="buy", family="rsi", family_revision="rsi-wilder-sma-seeded-v1",
            settings={"period": 9}, operator="upcross", condition={"threshold": 52},
        )
        definition = RulebookDefinitionV2("swing", "all", (buy,), max_hold_bars=4)
        result = execute_rulebook(
            bars, np.array([False, False, True, False, False, True, False]),
            np.array([False, False, False, False, False, True, False]),
            definition, self._partition(bars),
        )

        self.assertEqual("timeout", result[0].exit_reason)

    def test_sparse_and_dense_entry_streams_do_not_create_overlapping_open_trades(self) -> None:
        bars = self._bars([10_000] * 7)
        sparse = execute_rulebook(
            bars, np.array([False, False, True, False, False, False, False]), None,
            self._definition(), self._partition(bars),
        )
        dense = execute_rulebook(
            bars, np.array([False, True, True, True, True, True, True]), None,
            self._definition(), self._partition(bars),
        )

        self.assertEqual(1, len(sparse))
        self.assertEqual(1, len(dense))
        self.assertEqual((2, 3, 6), (sparse[0].signal_bar_ordinal, sparse[0].entry_bar_ordinal, sparse[0].exit_bar_ordinal))
        self.assertEqual((1, 2, 5), (dense[0].signal_bar_ordinal, dense[0].entry_bar_ordinal, dense[0].exit_bar_ordinal))


if __name__ == "__main__":
    unittest.main()
