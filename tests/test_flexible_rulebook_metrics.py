"""Exact gross metrics and qualification tests for Flexible Rulebook."""

from datetime import date
from dataclasses import dataclass
import math
import unittest

from flexible_rulebook.contracts import PartitionMetrics
from flexible_rulebook.execution import CompletedTrade
from flexible_rulebook.metrics import (
    compare_entry_timing,
    partition_metrics,
    qualifies,
    rank_qualified,
    select_timing_distinct_top_three,
)


def _trade(index: int, result: float) -> CompletedTrade:
    return CompletedTrade(
        trade_id=f"trade-{index}", signal_date=date(2020, 1, 1),
        entry_date=date(2020, 1, 2), exit_date=date(2020, 1, 3),
        signal_bar_ordinal=index * 3, entry_bar_ordinal=index * 3 + 1,
        exit_bar_ordinal=index * 3 + 2, entry_price=100, exit_price=100 + result,
        exit_reason="timeout", return_pct=result,
    )


class FlexibleRulebookMetricsTests(unittest.TestCase):
    def test_partition_metrics_preserve_unrounded_gross_values(self) -> None:
        metrics = partition_metrics((_trade(0, 10.123), _trade(1, -2.5), _trade(2, 20.0)))

        self.assertEqual(metrics.n, 3)
        self.assertEqual(metrics.win_rate, 2 / 3 * 100.0)
        expected_total = math.fsum((10.123, -2.5, 20.0))
        self.assertEqual(metrics.total_return_pct, expected_total)
        self.assertEqual(metrics.mean_return_pct, expected_total / 3)

    def test_qualification_requires_every_threshold_in_both_partitions(self) -> None:
        training = PartitionMetrics(12, 65.0, 180.0, 15.0, 1.0)
        weak_test = PartitionMetrics(11, 90.0, 330.0, 30.0, 3.0)
        good_test = PartitionMetrics(12, 65.0, 180.0, 15.0, None)

        self.assertFalse(qualifies(training, weak_test))
        self.assertTrue(qualifies(training, good_test))

    def test_rank_is_training_only_then_lexical_id(self) -> None:
        @dataclass(frozen=True)
        class Evaluation:
            rulebook_id: str
            training_metrics: PartitionMetrics
            test_metrics: PartitionMetrics
            ticker: str = "VCB"
            source_fingerprint: str = "source"
            split: str = "split"
            execution_revision: str = "execution"

        good = PartitionMetrics(12, 65.0, 180.0, 15.0, 1.0)
        ranked = rank_qualified((
            Evaluation("frb_b", good, PartitionMetrics(12, 99.0, 999.0, 99.0, 9.0)),
            Evaluation("frb_a", good, good),
        ))

        self.assertEqual([item.rulebook_id for item in ranked], ["frb_a", "frb_b"])

    def test_pairing_is_first_inclusive_overlap_and_rejects_mixed_scope(self) -> None:
        @dataclass(frozen=True)
        class Evaluation:
            rulebook_id: str
            training_metrics: PartitionMetrics
            test_metrics: PartitionMetrics
            training_trades: tuple[CompletedTrade, ...]
            test_trades: tuple[CompletedTrade, ...]
            ticker: str = "VCB"
            source_fingerprint: str = "source"
            split: str = "split"
            execution_revision: str = "execution"

        metrics = PartitionMetrics(12, 65.0, 180.0, 15.0, 1.0)
        left = Evaluation("frb_a", metrics, metrics, (_trade(0, 15), _trade(2, 15), _trade(4, 15)), ())
        right = Evaluation("frb_b", metrics, metrics, (_trade(0, 15), _trade(2, 15)), ())
        evidence = compare_entry_timing(left, right, "training")

        self.assertEqual((evidence.paired_count, evidence.unmatched_left_count, evidence.unmatched_right_count), (2, 1, 0))
        with self.assertRaisesRegex(ValueError, "selection scope"):
            compare_entry_timing(left, Evaluation("frb_c", metrics, metrics, (), (), ticker="FPT"), "training")

    def test_top_three_rejects_training_near_duplicate_at_75_percent(self) -> None:
        @dataclass(frozen=True)
        class Evaluation:
            rulebook_id: str
            training_metrics: PartitionMetrics
            test_metrics: PartitionMetrics
            training_trades: tuple[CompletedTrade, ...]
            test_trades: tuple[CompletedTrade, ...]
            ticker: str = "VCB"
            source_fingerprint: str = "source"
            split: str = "split"
            execution_revision: str = "execution"

        metrics = PartitionMetrics(12, 65.0, 180.0, 15.0, 1.0)
        base = tuple(_trade(index * 2, 15) for index in range(12))
        duplicate = tuple(_trade(index * 2, 15) for index in range(9)) + tuple(_trade(100 + index * 2, 15) for index in range(3))
        distinct = tuple(_trade(200 + index * 2, 15) for index in range(12))
        result = select_timing_distinct_top_three((
            Evaluation("frb_a", metrics, metrics, base, ()),
            Evaluation("frb_b", metrics, metrics, duplicate, ()),
            Evaluation("frb_c", metrics, metrics, distinct, ()),
        ))

        self.assertEqual([item.rulebook_id for item in result.selected], ["frb_a", "frb_c"])
        self.assertEqual(result.rejected[0].rulebook_id, "frb_b")


if __name__ == "__main__":
    unittest.main()
