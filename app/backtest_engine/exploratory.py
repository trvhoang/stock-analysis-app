"""Pure schema-5 exploratory rulebook evaluation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from math import isfinite
from typing import Literal, Sequence

import pandas as pd

from .models import RulebookExecution, TradeEvent
from .rolling_window import Window, partition_completed_events, run_rulebook_trade_sequence
from .signal_combos import generate_rulebook_executions, rulebook_entry_signal
from .validation import (
    calculate_deflated_sharpe,
    calculate_unannualized_sharpe,
    moving_block_permutation_test,
)


P_VALUE_NA = "not_estimated_n_le_block_size"
P_VALUE_INFORMATIONAL = "informational"
DSR_AVAILABLE = "available"
DSR_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class EvaluationSplit:
    """Actual native-bar boundaries for one train/test evaluation."""

    method: Literal["calendar_10y_5y", "chronological_65_35"]
    train_start: date
    train_end: date
    test_start: date
    test_end: date

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "train": {"start": self.train_start.isoformat(), "end": self.train_end.isoformat()},
            "test": {"start": self.test_start.isoformat(), "end": self.test_end.isoformat()},
        }


@dataclass(frozen=True)
class PartitionMetrics:
    """Exact gross metrics and informational p-value for one partition."""

    n: int
    win_rate: float
    profit_pct: float
    sharpe: float | None
    p_value: float | None
    p_value_status: Literal["not_estimated_n_le_block_size", "informational"]

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "win_rate": self.win_rate,
            "profit_pct": self.profit_pct,
            "sharpe": self.sharpe,
            "p_value": self.p_value,
            "p_value_status": self.p_value_status,
        }


@dataclass(frozen=True)
class TreatmentEvaluation:
    """One treatment's split metrics and training-only DSR selection evidence."""

    execution: RulebookExecution
    training: PartitionMetrics
    test: PartitionMetrics
    training_returns: tuple[float, ...]
    training_dsr: float | None = None
    dsr_status: Literal["available", "unavailable"] = DSR_UNAVAILABLE

    def to_dict(self) -> dict[str, object]:
        return {
            "theme_variant": self.execution.theme_variant,
            "theme_mode": self.execution.theme_mode,
            "training": self.training.to_dict(),
            "test": self.test.to_dict(),
            "training_dsr": self.training_dsr,
            "dsr_status": self.dsr_status,
        }


@dataclass(frozen=True)
class ExploratoryCandidate:
    """One persisted no-theme-n>=5 gate subset and both paired treatments."""

    rule_id: str
    selected_gates: tuple[str, ...]
    no_theme: TreatmentEvaluation
    themed: TreatmentEvaluation
    preferred_variant: str

    @property
    def preferred(self) -> TreatmentEvaluation:
        return self.themed if self.preferred_variant == "background-theme" else self.no_theme

    def to_dict(self) -> dict[str, object]:
        return {
            "rulebook_id": self.rule_id,
            "candidate_role": "baseline_control",
            "selected_gates": list(self.selected_gates),
            "preferred_variant": self.preferred_variant,
            "treatments": {
                "no-background-theme": self.no_theme.to_dict(),
                "background-theme": self.themed.to_dict(),
            },
        }


@dataclass(frozen=True)
class ExploratoryEvaluation:
    """All persisted candidates and deterministic Top-3 IDs for one run."""

    split: EvaluationSplit
    candidates: tuple[ExploratoryCandidate, ...]
    top_rulebook_ids: tuple[str, ...]


def _native_dates(frame: pd.DataFrame) -> pd.Series:
    if not isinstance(frame, pd.DataFrame) or "date" not in frame or frame.empty:
        raise ValueError("native frame must contain at least one date")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any() or not dates.is_monotonic_increasing:
        raise ValueError("native frame dates must be valid and ascending")
    return dates


def _is_full_fifteen_year_request(requested_start: date, requested_end: date) -> bool:
    return (
        pd.Timestamp(requested_start) + pd.DateOffset(years=15)
        <= pd.Timestamp(requested_end) + pd.Timedelta(days=7)
    )


def split_native_frame(
    frame: pd.DataFrame,
    *,
    requested_start: date,
    requested_end: date,
) -> EvaluationSplit:
    """Choose calendar 10y/5y or chronological 65%/35% native boundaries."""

    dates = _native_dates(frame)
    first, last = dates.iloc[0], dates.iloc[-1]
    requested_start_at = pd.Timestamp(requested_start)
    if (
        _is_full_fifteen_year_request(requested_start, requested_end)
        and first <= requested_start_at + pd.Timedelta(days=7)
        and last >= pd.Timestamp(requested_end) - pd.Timedelta(days=7)
    ):
        cutoff = pd.Timestamp(requested_end) - pd.DateOffset(years=5)
        method: Literal["calendar_10y_5y", "chronological_65_35"] = "calendar_10y_5y"
    else:
        cutoff = first + (last - first) * 0.65
        method = "chronological_65_35"
    test_dates = dates.loc[dates >= cutoff]
    if test_dates.empty:
        raise ValueError("native frame has no test bars after split boundary")
    test_start = test_dates.iloc[0]
    train_dates = dates.loc[dates < test_start]
    if train_dates.empty:
        raise ValueError("native frame has no training bars before split boundary")
    return EvaluationSplit(
        method,
        train_dates.iloc[0].date(),
        train_dates.iloc[-1].date(),
        test_start.date(),
        dates.iloc[-1].date(),
    )


def partition_metrics(
    events: Sequence[TradeEvent],
    *,
    permutation_count: int,
    permutation_seed: int,
    permutation_block_size: int,
) -> PartitionMetrics:
    """Return exact gross metrics and only non-degenerate informational p-values."""

    returns = tuple(float(event.return_pct) for event in events)
    n = len(returns)
    win_rate = sum(value > 0 for value in returns) / n * 100.0 if n else 0.0
    profit_pct = float(sum(returns))
    sharpe = calculate_unannualized_sharpe(returns) if n >= 2 else None
    if n <= permutation_block_size:
        return PartitionMetrics(n, win_rate, profit_pct, sharpe, None, P_VALUE_NA)
    permutation = moving_block_permutation_test(
        returns,
        count=permutation_count,
        seed=permutation_seed,
        block_size=permutation_block_size,
    )
    return PartitionMetrics(
        n, win_rate, profit_pct, sharpe, permutation.p_value, P_VALUE_INFORMATIONAL
    )


def _treatment_evaluation(
    execution: RulebookExecution,
    training_events: Sequence[TradeEvent],
    test_events: Sequence[TradeEvent],
    *,
    permutation_count: int,
    permutation_seed: int,
    permutation_block_size: int,
) -> TreatmentEvaluation:
    returns = tuple(float(event.return_pct) for event in training_events)
    return TreatmentEvaluation(
        execution=execution,
        training=partition_metrics(
            training_events,
            permutation_count=permutation_count,
            permutation_seed=permutation_seed,
            permutation_block_size=permutation_block_size,
        ),
        test=partition_metrics(
            test_events,
            permutation_count=permutation_count,
            permutation_seed=permutation_seed,
            permutation_block_size=permutation_block_size,
        ),
        training_returns=returns,
    )


def _with_training_dsr(
    no_theme: TreatmentEvaluation,
    themed: TreatmentEvaluation,
) -> tuple[TreatmentEvaluation, TreatmentEvaluation]:
    if (
        no_theme.training.sharpe is None
        or themed.training.sharpe is None
        or not isfinite(no_theme.training.sharpe)
        or not isfinite(themed.training.sharpe)
    ):
        return no_theme, themed
    trial_sharpes = (no_theme.training.sharpe, themed.training.sharpe)
    try:
        no_theme_dsr = calculate_deflated_sharpe(no_theme.training_returns, trial_sharpes)
        themed_dsr = calculate_deflated_sharpe(themed.training_returns, trial_sharpes)
    except ValueError:
        return no_theme, themed
    if not isfinite(no_theme_dsr) or not isfinite(themed_dsr):
        return no_theme, themed
    return (
        replace(no_theme, training_dsr=no_theme_dsr, dsr_status=DSR_AVAILABLE),
        replace(themed, training_dsr=themed_dsr, dsr_status=DSR_AVAILABLE),
    )


def build_exploratory_candidate(
    no_theme_execution: RulebookExecution,
    themed_execution: RulebookExecution,
    no_theme_training_events: Sequence[TradeEvent],
    themed_training_events: Sequence[TradeEvent],
    no_theme_test_events: Sequence[TradeEvent],
    themed_test_events: Sequence[TradeEvent],
    *,
    permutation_count: int,
    permutation_seed: int,
    permutation_block_size: int,
) -> ExploratoryCandidate | None:
    """Build one candidate only when no-theme training has the locked minimum n."""

    if no_theme_execution.theme_variant != "no-background-theme":
        raise ValueError("no_theme_execution must be no-background-theme")
    if themed_execution.theme_variant != "background-theme":
        raise ValueError("themed_execution must be background-theme")
    if (
        no_theme_execution.rulebook != themed_execution.rulebook
        or no_theme_execution.selected_gates != themed_execution.selected_gates
    ):
        raise ValueError("paired executions must share one rulebook gate subset")
    no_theme = _treatment_evaluation(
        no_theme_execution,
        no_theme_training_events,
        no_theme_test_events,
        permutation_count=permutation_count,
        permutation_seed=permutation_seed,
        permutation_block_size=permutation_block_size,
    )
    themed = _treatment_evaluation(
        themed_execution,
        themed_training_events,
        themed_test_events,
        permutation_count=permutation_count,
        permutation_seed=permutation_seed,
        permutation_block_size=permutation_block_size,
    )
    if no_theme.training.n < no_theme_execution.rulebook.min_n:
        return None
    no_theme, themed = _with_training_dsr(no_theme, themed)
    preferred_variant = (
        "background-theme"
        if (
            themed.dsr_status == DSR_AVAILABLE
            and no_theme.dsr_status == DSR_AVAILABLE
            and themed.training_dsr is not None
            and no_theme.training_dsr is not None
            and themed.training_dsr > no_theme.training_dsr
        )
        else "no-background-theme"
    )
    return ExploratoryCandidate(
        no_theme_execution.rule_id,
        no_theme_execution.selected_gates,
        no_theme,
        themed,
        preferred_variant,
    )


def execute_partition(
    frame: pd.DataFrame,
    execution: RulebookExecution,
    entries: pd.Series,
    *,
    start: date,
    end: date,
) -> tuple[TradeEvent, ...]:
    """Run one split independently flat while retaining prebuilt causal inputs."""

    dates = _native_dates(frame)
    mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
    partition = frame.loc[mask].reset_index(drop=True)
    partition_entries = pd.Series(entries, index=frame.index).loc[mask].reset_index(drop=True)
    events = run_rulebook_trade_sequence(partition, execution, partition_entries)
    return tuple(
        partition_completed_events(events, Window(pd.Timestamp(start), pd.Timestamp(end)))
    )


def evaluate_exploratory_candidates(
    frame: pd.DataFrame,
    *,
    horizon: str,
    requested_start: date,
    requested_end: date,
    theme_eligible: pd.Series,
    permutation_count: int,
    permutation_seed: int,
    permutation_block_size: int,
) -> ExploratoryEvaluation:
    """Evaluate all gate subsets with both treatments and return persisted candidates."""

    split = split_native_frame(
        frame, requested_start=requested_start, requested_end=requested_end
    )
    candidates = []
    executions = generate_rulebook_executions(horizon)
    for position in range(0, len(executions), 2):
        no_theme_execution, themed_execution = executions[position : position + 2]
        no_theme_entries = rulebook_entry_signal(frame, no_theme_execution)
        themed_entries = rulebook_entry_signal(
            frame, themed_execution, theme_eligible=theme_eligible
        )
        candidate = build_exploratory_candidate(
            no_theme_execution,
            themed_execution,
            execute_partition(
                frame, no_theme_execution, no_theme_entries,
                start=split.train_start, end=split.train_end,
            ),
            execute_partition(
                frame, themed_execution, themed_entries,
                start=split.train_start, end=split.train_end,
            ),
            execute_partition(
                frame, no_theme_execution, no_theme_entries,
                start=split.test_start, end=split.test_end,
            ),
            execute_partition(
                frame, themed_execution, themed_entries,
                start=split.test_start, end=split.test_end,
            ),
            permutation_count=permutation_count,
            permutation_seed=permutation_seed,
            permutation_block_size=permutation_block_size,
        )
        if candidate is not None:
            candidates.append(candidate)
    ranked = rank_top_candidates(candidates)
    return ExploratoryEvaluation(
        split,
        tuple(candidates),
        tuple(candidate.rule_id for candidate in ranked),
    )


def rank_top_candidates(
    candidates: Sequence[ExploratoryCandidate],
) -> tuple[ExploratoryCandidate, ...]:
    """Return at most three candidates by locked unrounded training ordering."""

    return tuple(
        sorted(
            (candidate for candidate in candidates if candidate is not None),
            key=lambda candidate: (
                -candidate.preferred.training.win_rate,
                -candidate.preferred.training.profit_pct,
                -float(candidate.preferred.training.sharpe or 0.0),
                candidate.rule_id,
            ),
        )[:3]
    )


__all__ = [
    "DSR_AVAILABLE",
    "DSR_UNAVAILABLE",
    "EvaluationSplit",
    "ExploratoryCandidate",
    "ExploratoryEvaluation",
    "P_VALUE_INFORMATIONAL",
    "P_VALUE_NA",
    "PartitionMetrics",
    "TreatmentEvaluation",
    "build_exploratory_candidate",
    "evaluate_exploratory_candidates",
    "execute_partition",
    "partition_metrics",
    "rank_top_candidates",
    "split_native_frame",
]
