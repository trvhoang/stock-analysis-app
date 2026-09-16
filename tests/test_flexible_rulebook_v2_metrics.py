"""Gross per-partition metric contracts for Flexible Rulebook v2."""

from datetime import date
import math
import unittest

from flexible_rulebook.v2.execution import CompletedTrade
from flexible_rulebook.v2.metrics import partition_metrics


def _trade(index: int, result: float) -> CompletedTrade:
    return CompletedTrade(
        trade_id=f"trade-{index}", signal_date=date(2026, 1, 5), entry_date=date(2026, 1, 6), exit_date=date(2026, 1, 7),
        signal_bar_ordinal=index * 3, entry_bar_ordinal=index * 3 + 1, exit_bar_ordinal=index * 3 + 2,
        entry_price=100, exit_price=100 + result, exit_reason="timeout", return_pct=result,
    )


class FlexibleRulebookV2MetricsTests(unittest.TestCase):
    def test_metrics_are_unrounded_gross_completed_trade_values_without_qualification(self) -> None:
        metrics = partition_metrics((_trade(0, 10.123), _trade(1, -2.5), _trade(2, 20.0)))

        expected_total = math.fsum((10.123, -2.5, 20.0))
        self.assertEqual((metrics.n, metrics.win_rate, metrics.total_return_pct, metrics.mean_return_pct), (3, 2 / 3 * 100.0, expected_total, expected_total / 3))
        self.assertIsNotNone(metrics.sharpe)

    def test_empty_and_single_trade_sharpe_are_not_available(self) -> None:
        empty = partition_metrics(())
        single = partition_metrics((_trade(0, 10.0),))

        self.assertEqual((empty.n, empty.win_rate, empty.total_return_pct, empty.mean_return_pct, empty.sharpe), (0, None, 0.0, None, None))
        self.assertEqual((single.n, single.win_rate, single.sharpe), (1, 100.0, None))


if __name__ == "__main__":
    unittest.main()
