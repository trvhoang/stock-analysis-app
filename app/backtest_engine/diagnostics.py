"""Read-only schema-4 exploratory diagnostics; never inspect or write artifacts."""

import pandas as pd

from .config import BacktestConfig, ENTRY_GATE_NAMES, rulebook_for
from .data_quality import audit_history, validate_ohlcv
from .exploratory import evaluate_exploratory_candidates
from .indicators import build_rulebook_frame
from .pipeline import _build_confirmation_frame, _prepare_ticker, _theme_signal


def _iso_date(value: object) -> str | None:
    return None if value is None else pd.Timestamp(value).date().isoformat()


def _audit_report(audit) -> dict[str, object]:
    return {
        "status": audit.status, "errors": list(getattr(audit, "errors", ())),
        "warnings": list(getattr(audit, "warnings", ())),
        "source_row_count": getattr(audit, "source_row_count", None),
        "first_date": _iso_date(getattr(audit, "first_date", None)),
        "last_date": _iso_date(getattr(audit, "last_date", None)),
    }


def _frame_from_supplied_history(config: BacktestConfig, raw_history: pd.DataFrame):
    quality = validate_ohlcv(raw_history)
    if not quality.is_valid:
        raise ValueError("invalid backtest data: " + "; ".join(quality.errors))
    return build_rulebook_frame(raw_history, rulebook_for(config.horizon)), audit_history(config.ticker, raw_history)


def collect_rulebook_diagnostics(config: BacktestConfig, engine, *, raw_history: pd.DataFrame | None = None, vnindex_history: pd.DataFrame | None = None) -> dict[str, object]:
    """Report the all-subset paired evaluation without writes or binary decisions."""

    if raw_history is None:
        frame, audit, raw_history = _prepare_ticker(config.ticker, config, engine)
    else:
        frame, audit = _frame_from_supplied_history(config, raw_history)
    if vnindex_history is None:
        theme_eligible = pd.Series(False, index=frame.index, dtype=bool)
        theme_source = "unavailable; themed evidence has zero eligible entries"
    else:
        quality = validate_ohlcv(vnindex_history)
        if not quality.is_valid:
            raise ValueError("invalid VN-Index data: " + "; ".join(quality.errors))
        theme_eligible = _theme_signal(frame, _build_confirmation_frame(vnindex_history, config.horizon))
        theme_source = "provided VN-Index history"
    end = config.end_date or pd.Timestamp(raw_history["date"].iloc[-1]).date()
    start = config.start_date or pd.Timestamp(raw_history["date"].iloc[0]).date()
    evaluation = evaluate_exploratory_candidates(
        frame, horizon=config.horizon, requested_start=start, requested_end=end,
        theme_eligible=theme_eligible, permutation_count=config.permutation_count,
        permutation_seed=config.permutation_seed, permutation_block_size=config.permutation_block_size,
    )
    gate_rejections = {
        gate: int((~frame[gate].fillna(False).astype(bool)).sum())
        for gate in ENTRY_GATE_NAMES
    }
    return {
        "ticker": config.ticker, "horizon": config.horizon,
        "audit": _audit_report(audit),
        "write_boundary": {"database": False, "jobs": False, "artifacts": False},
        "evaluation_label": "Exploratory — gross",
        "theme_treatments": ["no-background-theme", "background-theme:AND"],
        "theme_source": theme_source,
        "split": evaluation.split.to_dict(),
        "candidate_count": len(evaluation.candidates),
        "top_rulebook_ids": list(evaluation.top_rulebook_ids),
        "gate_rejections": gate_rejections,
        "p_value_policy": "informational; N/A when n is at most block size",
    }


def collect_backtest_diagnostics(config: BacktestConfig, engine, *, raw_history: pd.DataFrame | None = None, vnindex_history: pd.DataFrame | None = None) -> dict[str, object]:
    return collect_rulebook_diagnostics(config, engine, raw_history=raw_history, vnindex_history=vnindex_history)


__all__ = ["collect_backtest_diagnostics", "collect_rulebook_diagnostics"]
