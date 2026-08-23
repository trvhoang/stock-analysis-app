"""Read-only VCB rulebook-gate research primitives."""

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from itertools import combinations
from math import isfinite
from typing import Sequence

import pandas as pd

from .config import HORIZONS, THEME_VARIANTS, rulebook_for
from .data_quality import audit_history, load_ticker_history, validate_ohlcv
from .indicators import build_rulebook_frame
from .models import RulebookExecution, TradeEvent
from .rolling_window import run_rulebook_trade_sequence
from .validation import (
    calculate_deflated_sharpe,
    calculate_probabilistic_sharpe,
    calculate_unannualized_sharpe,
    moving_block_permutation_test,
)
from .vnindex_theme import align_vnindex_asof, build_vnindex_confirmation


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


@dataclass(frozen=True)
class ResearchRun:
    """Complete read-only VCB research output, ready for Markdown rendering."""

    as_of: date
    source_start: date
    source_end: date
    vcb_rows: int
    vnindex_rows: int
    vcb_audit: object
    swing_results: tuple[ResearchResult, ...]
    midterm_results: tuple[ResearchResult, ...]


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
    selected_gates = tuple(sorted(_GATE_COLUMN_BY_NAME[gate] for gate in candidate.gates))
    if candidate.theme_variant == "no-background-theme":
        return RulebookExecution(rulebook, selected_gates)
    return RulebookExecution(
        rulebook,
        selected_gates,
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


def _research_bounds(as_of: date) -> tuple[date, date]:
    """Return the fixed full-history research request window."""

    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    return (pd.Timestamp(as_of) - pd.DateOffset(years=15)).date(), as_of


def _require_valid_history(ticker: str, raw_history: pd.DataFrame) -> None:
    """Reject invalid raw OHLCV before any research frame is built."""

    quality = validate_ohlcv(raw_history)
    if not quality.is_valid:
        raise ValueError(
            f"invalid {ticker} research data: " + "; ".join(quality.errors)
        )


def _source_bounds(raw_history: pd.DataFrame) -> tuple[date, date]:
    """Return validated raw-history bounds for transparent report metadata."""

    dates = pd.to_datetime(raw_history["date"], errors="coerce")
    if dates.empty or dates.isna().any():
        raise ValueError("validated research history has no usable dates")
    return dates.min().date(), dates.max().date()


def _theme_signal_for_frame(
    ticker_frame: pd.DataFrame,
    vnindex_raw: pd.DataFrame,
    horizon: str,
) -> pd.Series:
    """Build the existing causal VNIndex confirmation aligned to one V3 frame."""

    confirmation = build_vnindex_confirmation(vnindex_raw, horizon)
    confirmation_frame = pd.DataFrame(
        {
            "date": pd.DatetimeIndex(confirmation.index),
            "close": confirmation.to_numpy(),
        }
    )
    aligned = align_vnindex_asof(ticker_frame[["date"]], confirmation_frame)
    if "vnindex_close" not in aligned or len(aligned) != len(ticker_frame):
        raise ValueError("VNIndex confirmation did not align to ticker frame")
    return pd.Series(
        aligned["vnindex_close"].fillna(False).to_numpy(),
        index=ticker_frame.index,
        dtype=bool,
    )


def collect_research_from_histories(
    vcb_raw: pd.DataFrame,
    vnindex_raw: pd.DataFrame,
    as_of: date,
) -> ResearchRun:
    """Evaluate both horizons from one already-loaded VCB and VNIndex history."""

    _require_valid_history("VCB", vcb_raw)
    _require_valid_history("VNINDEX", vnindex_raw)
    source_start, source_end = _source_bounds(vcb_raw)
    audit = audit_history("VCB", vcb_raw)
    results_by_horizon = {}
    for horizon in HORIZONS:
        frame = build_rulebook_frame(vcb_raw, rulebook_for(horizon))
        theme_signal = _theme_signal_for_frame(frame, vnindex_raw, horizon)
        results_by_horizon[horizon] = evaluate_horizon(frame, horizon, theme_signal)
    return ResearchRun(
        as_of=as_of,
        source_start=source_start,
        source_end=source_end,
        vcb_rows=len(vcb_raw),
        vnindex_rows=len(vnindex_raw),
        vcb_audit=audit,
        swing_results=results_by_horizon["swing"],
        midterm_results=results_by_horizon["midterm"],
    )


def collect_vcb_research(engine, as_of: date) -> ResearchRun:
    """Load VCB and VNIndex once each, then run in-memory research."""

    start_date, end_date = _research_bounds(as_of)
    vcb_raw = load_ticker_history("VCB", start_date, end_date, engine)
    vnindex_raw = load_ticker_history("VNINDEX", start_date, end_date, engine)
    return collect_research_from_histories(vcb_raw, vnindex_raw, as_of)


def _display(value: object) -> str:
    """Return exact machine values without formatting-based winner ambiguity."""

    return "-" if value is None else repr(value)


def _winner_rows(results: Sequence[ResearchResult]) -> list[str]:
    """Render consolidated exact winners, including multiple metric labels."""

    metric_winners = rank_winners(results)
    labels_by_candidate: dict[ResearchCandidate, list[str]] = {}
    for metric, winners in metric_winners.items():
        for winner in winners:
            labels_by_candidate.setdefault(winner.candidate, []).append(metric)
    if not labels_by_candidate:
        return ["| no eligible candidate | - | - | - | - |"]

    result_by_candidate = {result.candidate: result for result in results}
    rows = []
    for candidate, labels in labels_by_candidate.items():
        result = result_by_candidate[candidate]
        rows.append(
            "| "
            + " / ".join(labels)
            + f" | {candidate.identity} | {result.n} | "
            + f"{_display(result.win_rate)} | {_display(result.profit_pct)} | "
            + f"{_display(result.sharpe)} |"
        )
    return rows


def _horizon_markdown(horizon: str, results: Sequence[ResearchResult]) -> list[str]:
    """Render one complete horizon result, including every rejection."""

    values = tuple(results)
    rejections = Counter(result.reason or "eligible" for result in values)
    lines = [
        f"## {horizon.title() if horizon == 'midterm' else 'Swing'}",
        "",
        f"Candidates: {len(values)}. Rejection funnel: "
        + ", ".join(f"{reason}={count}" for reason, count in sorted(rejections.items())),
        "",
        "### Exact winners",
        "",
        "| Won metric(s) | Candidate | n | Win rate % | Profit % | Sharpe |",
        "|---|---|---:|---:|---:|---:|",
        *_winner_rows(values),
        "",
        "### Candidate audit",
        "",
        "| Candidate | State | Reason | n | Win rate % | Profit % | Sharpe | PSR | DSR | Permutation p | DSR trials |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in values:
        lines.append(
            f"| {result.candidate.identity} | {result.state} | "
            f"{result.reason or '-'} | {result.n} | {_display(result.win_rate)} | "
            f"{_display(result.profit_pct)} | {_display(result.sharpe)} | "
            f"{_display(result.psr)} | {_display(result.dsr)} | "
            f"{_display(result.permutation_p_value)} | {result.trial_count} |"
        )
    return lines


def render_markdown(run: ResearchRun) -> str:
    """Return one host-capturable in-sample research report."""

    if not isinstance(run, ResearchRun):
        raise ValueError("run must be a ResearchRun")
    audit_status = getattr(run.vcb_audit, "status", "unknown")
    audit_errors = tuple(getattr(run.vcb_audit, "errors", ()))
    lines = [
        "# VCB 15-Year Signal Optimizer Research",
        "",
        "> **in-sample research only.** This is not V3 certification, "
        "out-of-sample validation, trading advice, or a production signal.",
        "",
        "## Scope and fixed method",
        "",
        f"- As of: {run.as_of.isoformat()}",
        f"- VCB source bounds: {run.source_start.isoformat()} to {run.source_end.isoformat()}",
        f"- Raw rows: VCB {run.vcb_rows}; VNINDEX {run.vnindex_rows}",
        f"- VCB audit: {audit_status}; errors: {repr(audit_errors)}",
        "- Candidate grid: 15 non-empty four-gate subsets × no-theme and VNIndex AND = 30 per horizon.",
        "- Native V3 execution unchanged: next native open, ATR exits, stop-first, one flat-to-flat trade sequence, and horizon-owned timeout.",
        "- Eligibility: n >= 5, PSR >= 0.95, DSR >= 0.95, moving-block permutation p <= 0.05.",
        "- Permutation: 1,000 draws, seed 42, block size 20.",
        "- DSR family: every same-horizon n >= 5 finite-Sharpe candidate before PSR, DSR, or permutation filtering.",
        "- Ranking: exact unrounded win rate %, profit_pct as sum of per-trade returns, and unannualized Sharpe.",
        "- No V3 artifact, job, DB row, configuration, or persistence path changed.",
        "",
    ]
    lines.extend(_horizon_markdown("swing", run.swing_results))
    lines.append("")
    lines.extend(_horizon_markdown("midterm", run.midterm_results))
    return "\n".join(lines) + "\n"


def _parse_as_of(value: str) -> date:
    """Parse one explicit research as-of date."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("as-of must be YYYY-MM-DD") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Run the explicit manual database-read research command."""

    parser = argparse.ArgumentParser(description="Run read-only VCB signal research")
    parser.add_argument("--as-of", required=True, type=_parse_as_of)
    arguments = parser.parse_args(argv)

    from pages.data_preparation import get_engine_with_retry
    from .pipeline import _database_url

    engine = get_engine_with_retry(_database_url())
    try:
        run = collect_vcb_research(engine, arguments.as_of)
    finally:
        engine.dispose()
    print(render_markdown(run), end="")
    return 0


__all__ = [
    "ResearchCandidate",
    "ResearchResult",
    "ResearchRun",
    "apply_search_statistics",
    "candidate_entry_signal",
    "collect_research_from_histories",
    "collect_vcb_research",
    "enumerate_candidates",
    "evaluate_horizon",
    "main",
    "rank_winners",
    "render_markdown",
]


if __name__ == "__main__":
    raise SystemExit(main())
