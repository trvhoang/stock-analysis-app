"""Read-only schema-5 exploratory diagnostics; never inspect or write artifacts."""

import pandas as pd

from .config import BacktestConfig, ENTRY_GATE_NAMES, rulebook_for
from .data_quality import audit_history, validate_ohlcv
from .exploratory import evaluate_exploratory_candidates
from .indicators import build_rulebook_frame
from .pipeline import (
    _build_confirmation_frame,
    _load_validated_history,
    _requested_dates,
    _theme_signal,
)
from .timeframes import latest_common_completed_bar


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


def _frame_from_supplied_history(
    config: BacktestConfig,
    raw_history: pd.DataFrame,
    common_as_of,
):
    quality = validate_ohlcv(raw_history)
    if not quality.is_valid or quality.valid_frame is None:
        raise ValueError("invalid backtest data: " + "; ".join(quality.errors))
    validated = quality.valid_frame
    return (
        build_rulebook_frame(
            validated,
            rulebook_for(config.horizon),
            common_as_of=common_as_of,
        ),
        audit_history(config.ticker, validated),
        validated,
    )


def collect_rulebook_diagnostics(config: BacktestConfig, engine, *, raw_history: pd.DataFrame | None = None, vnindex_history: pd.DataFrame | None = None) -> dict[str, object]:
    """Report the all-subset paired evaluation without writes or binary decisions."""

    if raw_history is None:
        raw_history = _load_validated_history(config.ticker, config, engine)
    sources = {config.ticker: raw_history}
    if vnindex_history is not None:
        quality = validate_ohlcv(vnindex_history)
        if not quality.is_valid or quality.valid_frame is None:
            raise ValueError("invalid VN-Index data: " + "; ".join(quality.errors))
        vnindex_history = quality.valid_frame
        sources["VNINDEX"] = vnindex_history
    _, requested_end = _requested_dates(config)
    common_as_of = latest_common_completed_bar(sources, requested_end)
    frame, audit, raw_history = _frame_from_supplied_history(
        config,
        raw_history,
        common_as_of,
    )
    if vnindex_history is None:
        theme_eligible = pd.Series(False, index=frame.index, dtype=bool)
        theme_source = "unavailable; themed evidence has zero eligible entries"
    else:
        theme_eligible = _theme_signal(
            frame,
            _build_confirmation_frame(
                vnindex_history,
                config.horizon,
                common_as_of=common_as_of,
            ),
        )
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
