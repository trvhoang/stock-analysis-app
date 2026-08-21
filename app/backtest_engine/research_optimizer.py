"""Read-only VCB rulebook-gate research primitives."""

from dataclasses import dataclass, replace
from itertools import combinations
from math import isfinite
from typing import Sequence

import pandas as pd

from .config import HORIZONS, THEME_VARIANTS, rulebook_for
from .models import RulebookExecution, TradeEvent
from .rolling_window import run_rulebook_trade_sequence
from .validation import (
    calculate_deflated_sharpe,
    calculate_probabilistic_sharpe,
    calculate_unannualized_sharpe,
    moving_block_permutation_test,
)


_GATE_COLUMNS = (
    ("rsi_upcross", "rulebook_rsi_upcross"),
    ("joint_trend", "rulebook_joint_trend_pass"),
    ("volume", "rulebook_volume_gate"),
    ("adx", "rulebook_adx_gate"),
)
_GATE_NAMES = tuple(name for name, _column in _GATE_COLUMNS)
_GATE_COLUMN_BY_NAME = dict(_GATE_COLUMNS)
_MISSING_INPUT_COLUMN = "rulebook_missing_required_input"
_MIN_COMPLETED_EXITS = 5
_SCORE_CUTOFF = 0.95
_PERMUTATION_COUNT = 1000
_PERMUTATION_SEED = 42
_PERMUTATION_BLOCK_SIZE = 20
_PERMUTATION_ALPHA = 0.05


@dataclass(frozen=True)
class ResearchCandidate:
    """One ordered V3-gate subset evaluated only by the research optimizer."""

    horizon: str
    theme_variant: str
    gates: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        if self.theme_variant not in THEME_VARIANTS:
            raise ValueError(f"theme_variant must be one of {THEME_VARIANTS}")
        gates = tuple(self.gates)
        canonical_gates = tuple(name for name in _GATE_NAMES if name in gates)
        if (
            not gates
            or len(gates) != len(set(gates))
            or gates != canonical_gates
        ):
            raise ValueError("gates must be a non-empty canonical unique selection")
        object.__setattr__(self, "gates", gates)

    @property
    def identity(self) -> str:
        """Return stable identity without changing any V3 execution identity."""

        return f"{self.horizon}:{self.theme_variant}:{'+'.join(self.gates)}"


@dataclass(frozen=True)
class ResearchResult:
    """One research candidate's exact raw metrics and terminal eligibility."""

    candidate: ResearchCandidate
    events: tuple[TradeEvent, ...]
    returns: tuple[float, ...]
    n: int
    win_rate: float
    profit_pct: float
    sharpe: float | None
    psr: float | None = None
    dsr: float | None = None
    permutation_p_value: float | None = None
    trial_count: int = 0
    state: str = "pending"
    reason: str | None = None

    @classmethod
    def from_events(
        cls,
        candidate: ResearchCandidate,
        events: Sequence[TradeEvent],
    ) -> "ResearchResult":
        """Create a raw result without applying search-family eligibility."""

        values = tuple(float(event.return_pct) for event in events)
        n = len(values)
        finite_returns = all(isfinite(value) for value in values)
        sharpe = (
            calculate_unannualized_sharpe(values)
            if n >= 2 and finite_returns
            else None
        )
        return cls(
            candidate=candidate,
            events=tuple(events),
            returns=values,
            n=n,
            win_rate=(sum(value > 0 for value in values) / n * 100.0) if n else 0.0,
            profit_pct=float(sum(values)),
            sharpe=sharpe,
        )


def enumerate_candidates(horizon: str) -> tuple[ResearchCandidate, ...]:
    """Return all non-empty ordered gate subsets for both registered treatments."""

    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    candidates = []
    for length in range(1, len(_GATE_NAMES) + 1):
        for gates in combinations(_GATE_NAMES, length):
            candidates.extend(
                (
                    ResearchCandidate(horizon, "no-background-theme", gates),
                    ResearchCandidate(horizon, "background-theme", gates),
                )
            )
    return tuple(candidates)


def candidate_entry_signal(
    frame: pd.DataFrame,
    candidate: ResearchCandidate,
    theme_signal: pd.Series | None = None,
) -> pd.Series:
    """Return a missing-input-safe selected-gate signal with optional theme AND."""

    if not isinstance(frame, pd.DataFrame):
        raise ValueError("frame must be a pandas DataFrame")
    if not isinstance(candidate, ResearchCandidate):
        raise ValueError("candidate must be a ResearchCandidate")
    required_columns = (
        _MISSING_INPUT_COLUMN,
        *(_GATE_COLUMN_BY_NAME[gate] for gate in candidate.gates),
    )
    missing_columns = [column for column in required_columns if column not in frame]
    if missing_columns:
        raise ValueError(
            "frame missing required research columns: " + ", ".join(missing_columns)
        )

    entry = ~frame[_MISSING_INPUT_COLUMN].fillna(True).astype(bool)
    for gate in candidate.gates:
        entry &= frame[_GATE_COLUMN_BY_NAME[gate]].fillna(False).astype(bool)

    if candidate.theme_variant == "background-theme":
        if not isinstance(theme_signal, pd.Series):
            raise ValueError("background-theme candidate requires a theme Series")
        if not theme_signal.index.equals(frame.index):
            raise ValueError("theme Series index must exactly match frame index")
        entry &= theme_signal.fillna(False).astype(bool)

    return entry.fillna(False).astype(bool).rename(None)


def _execution_for(candidate: ResearchCandidate) -> RulebookExecution:
    """Return only the registered V3 treatment identity for a candidate."""

    rulebook = rulebook_for(candidate.horizon)
    if candidate.theme_variant == "no-background-theme":
        return RulebookExecution(rulebook)
    return RulebookExecution(
        rulebook,
        theme_variant="background-theme",
        theme_mode="AND",
    )


def evaluate_horizon(
    frame: pd.DataFrame,
    horizon: str,
    theme_signal: pd.Series | None = None,
) -> tuple[ResearchResult, ...]:
    """Execute every research candidate through unchanged native V3 execution."""

    results = []
    for candidate in enumerate_candidates(horizon):
        execution = _execution_for(candidate)
        entry_signal = candidate_entry_signal(frame, candidate, theme_signal)
        events = run_rulebook_trade_sequence(frame, execution, entry_signal)
        results.append(ResearchResult.from_events(candidate, events))
    return apply_search_statistics(tuple(results))


def apply_search_statistics(
    results: Sequence[ResearchResult],
) -> tuple[ResearchResult, ...]:
    """Apply one full same-horizon DSR family without V3 certification rules."""

    values = tuple(results)
    if not values:
        return ()
    if any(not isinstance(result, ResearchResult) for result in values):
        raise ValueError("results must contain ResearchResult values")
    horizons = {result.candidate.horizon for result in values}
    if len(horizons) != 1:
        raise ValueError("research statistics require one horizon per family")

    family = tuple(
        result
        for result in values
        if result.n >= _MIN_COMPLETED_EXITS
        and result.sharpe is not None
        and isfinite(result.sharpe)
    )
    family_sharpes = tuple(result.sharpe for result in family)
    finalized = []
    for result in values:
        if result.n < _MIN_COMPLETED_EXITS:
            finalized.append(
                replace(
                    result,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="min_n",
                )
            )
            continue
        if result.sharpe is None or not isfinite(result.sharpe):
            finalized.append(
                replace(
                    result,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="non_finite_sharpe",
                )
            )
            continue

        try:
            psr = calculate_probabilistic_sharpe(result.returns)
        except ValueError:
            finalized.append(
                replace(
                    result,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="psr_error",
                )
            )
            continue
        if psr < _SCORE_CUTOFF:
            finalized.append(
                replace(
                    result,
                    psr=psr,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="psr",
                )
            )
            continue
        if len(family_sharpes) < 2:
            finalized.append(
                replace(
                    result,
                    psr=psr,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="dsr_unavailable",
                )
            )
            continue

        try:
            dsr = calculate_deflated_sharpe(result.returns, family_sharpes)
        except ValueError:
            finalized.append(
                replace(
                    result,
                    psr=psr,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="dsr_error",
                )
            )
            continue
        if dsr < _SCORE_CUTOFF:
            finalized.append(
                replace(
                    result,
                    psr=psr,
                    dsr=dsr,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="dsr",
                )
            )
            continue

        try:
            permutation = moving_block_permutation_test(
                result.returns,
                count=_PERMUTATION_COUNT,
                seed=_PERMUTATION_SEED,
                block_size=_PERMUTATION_BLOCK_SIZE,
            )
        except ValueError:
            finalized.append(
                replace(
                    result,
                    psr=psr,
                    dsr=dsr,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="permutation_error",
                )
            )
            continue
        if permutation.p_value > _PERMUTATION_ALPHA:
            finalized.append(
                replace(
                    result,
                    psr=psr,
                    dsr=dsr,
                    permutation_p_value=permutation.p_value,
                    trial_count=len(family_sharpes),
                    state="ineligible",
                    reason="permutation",
                )
            )
            continue
        finalized.append(
            replace(
                result,
                psr=psr,
                dsr=dsr,
                permutation_p_value=permutation.p_value,
                trial_count=len(family_sharpes),
                state="eligible",
                reason=None,
            )
        )
    return tuple(finalized)


def rank_winners(
    results: Sequence[ResearchResult],
) -> dict[str, tuple[ResearchResult, ...]]:
    """Return exact-value winners for each metric, retaining every tie."""

    eligible = tuple(result for result in results if result.state == "eligible")
    rankings = {}
    for metric in ("win_rate", "profit_pct", "sharpe"):
        if not eligible:
            rankings[metric] = ()
            continue
        best = max(getattr(result, metric) for result in eligible)
        rankings[metric] = tuple(
            result for result in eligible if getattr(result, metric) == best
        )
    return rankings


__all__ = [
    "ResearchCandidate",
    "ResearchResult",
    "apply_search_statistics",
    "candidate_entry_signal",
    "enumerate_candidates",
    "evaluate_horizon",
    "rank_winners",
]
