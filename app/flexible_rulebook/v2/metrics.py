"""Exact gross completed-trade metrics for Flexible Rulebook v2."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .execution import CompletedTrade


@dataclass(frozen=True)
class PartitionMetrics:
    n: int
    win_rate: float | None
    total_return_pct: float
    mean_return_pct: float | None
    sharpe: float | None


def partition_metrics(trades: tuple[CompletedTrade, ...]) -> PartitionMetrics:
    """Return unrounded gross statistics; no certification or ranking is applied."""

    if not isinstance(trades, tuple) or any(not isinstance(item, CompletedTrade) for item in trades):
        raise ValueError("trades must be an immutable CompletedTrade tuple")
    returns = tuple(float(item.return_pct) for item in trades)
    if not all(math.isfinite(value) for value in returns):
        raise ValueError("completed trade returns must be finite")
    if not returns:
        return PartitionMetrics(0, None, 0.0, None, None)
    total = math.fsum(returns)
    mean = total / len(returns)
    sharpe = None
    if len(returns) >= 2:
        variance = math.fsum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        if variance > 0.0 and math.isfinite(variance):
            sharpe = mean / math.sqrt(variance)
    return PartitionMetrics(
        n=len(returns),
        win_rate=sum(value > 0.0 for value in returns) / len(returns) * 100.0,
        total_return_pct=total,
        mean_return_pct=mean,
        sharpe=sharpe,
    )


__all__ = ["PartitionMetrics", "partition_metrics"]
