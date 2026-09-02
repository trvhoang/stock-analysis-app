"""Fresh source-verified current-bar replay for one schema-5 rulebook."""

from collections.abc import Mapping
from datetime import date
from datetime import datetime

import pandas as pd
import pytz

from .config import DEFAULT_SIGNAL_DIR, HORIZONS, _normalize_ticker, rulebook_for
from .data_quality import audit_history, load_ticker_history, validate_ohlcv
from .evidence import EvidenceEligibility, assess_evidence
from .indicators import build_rulebook_frame
from .models import RulebookExecution
from .persistence import (
    load_rulebook_result,
    signal_artifact_path,
    write_regeneration_marker,
)
from .result_store import ensure_result_root
from .signal_combos import rulebook_entry_signal
from .timeframes import latest_common_completed_bar


_MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")


def load_current_rulebook_document(ticker: str, horizon: str, output_dir: str = DEFAULT_SIGNAL_DIR) -> dict[str, object] | None:
    """Load one canonical schema-5 aggregate without probing legacy filenames."""

    normalized = _normalize_ticker(ticker)
    if horizon not in HORIZONS:
        raise ValueError("schema-5 rulebook horizon is invalid")
    path = signal_artifact_path(normalized, horizon, str(ensure_result_root(output_dir)))
    return None if not path.is_file() else load_rulebook_result(path)


def _fresh_bounds() -> tuple[object, object]:
    end = datetime.now(_MARKET_TIMEZONE).date()
    return (pd.Timestamp(end) - pd.DateOffset(years=15)).date(), end


def _load_raw(
    ticker: str,
    engine,
    *,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    default_start, default_end = _fresh_bounds()
    start = start or default_start
    end = end or default_end
    raw = load_ticker_history(ticker, start, end, engine)
    quality = validate_ohlcv(raw)
    if not quality.is_valid or quality.valid_frame is None:
        raise ValueError(f"invalid fresh {ticker} data: " + "; ".join(quality.errors))
    return quality.valid_frame


def _replay_bounds(document: Mapping[str, object]) -> tuple[date, date]:
    requested = document.get("requested_date_range")
    if not isinstance(requested, Mapping) or not isinstance(requested.get("start"), str):
        raise ValueError("schema-5 result has no replayable requested start date")
    try:
        start = date.fromisoformat(requested["start"])
    except ValueError as error:
        raise ValueError("schema-5 requested start date is invalid") from error
    return start, _fresh_bounds()[1]


def validate_current_evidence(
    document: Mapping[str, object],
    ticker_raw: pd.DataFrame,
    vnindex_raw: pd.DataFrame,
) -> EvidenceEligibility:
    """Recompute the document's full source identity through today's common bar."""

    ticker = _normalize_ticker(document.get("ticker"))
    _, requested_end = _fresh_bounds()
    common_as_of = latest_common_completed_bar(
        {ticker: ticker_raw, "VNINDEX": vnindex_raw},
        requested_end,
    )
    audit = audit_history(ticker, ticker_raw)
    return assess_evidence(
        ticker_raw,
        vnindex_raw,
        common_as_of,
        ticker=ticker,
        audit_eligible=audit.status == "clean",
    )


def _evidence_matches_frozen(
    frozen: object,
    current: EvidenceEligibility,
) -> bool:
    return isinstance(frozen, Mapping) and dict(frozen) == current.to_dict()


def _number(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _theme_facts(
    ticker_dates: pd.Series,
    horizon: str,
    vnindex_raw: pd.DataFrame,
    common_as_of,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    rulebook = rulebook_for(horizon)
    vn_frame = build_rulebook_frame(
        vnindex_raw,
        rulebook,
        common_as_of=common_as_of,
    )
    native = vn_frame[["date", "close"]].copy()
    native["vnindex_theme_sma"] = native["close"].rolling(rulebook.theme_sma_window).mean()
    aligned = pd.merge_asof(
        pd.DataFrame({"date": pd.to_datetime(ticker_dates)}).sort_values("date"),
        native.sort_values("date"), on="date", direction="backward",
    )
    close = aligned["close"].reset_index(drop=True)
    sma = aligned["vnindex_theme_sma"].reset_index(drop=True)
    return close, sma, (close > sma).fillna(False).astype(bool)


def _current_rulebook_facts(
    ticker: str,
    horizon: str,
    selected_gates: tuple[str, ...],
    preferred_variant: str,
    engine,
    *,
    ticker_raw: pd.DataFrame | None = None,
    vnindex_raw: pd.DataFrame | None = None,
    common_as_of: date | None = None,
) -> dict[str, object]:
    rulebook = rulebook_for(horizon)
    ticker_raw = _load_raw(ticker, engine) if ticker_raw is None else ticker_raw
    sources = {ticker: ticker_raw}
    if preferred_variant == "background-theme":
        vnindex_raw = _load_raw("VNINDEX", engine) if vnindex_raw is None else vnindex_raw
        sources["VNINDEX"] = vnindex_raw
    if common_as_of is None:
        _, requested_end = _fresh_bounds()
        common_as_of = latest_common_completed_bar(sources, requested_end)
    frame = build_rulebook_frame(
        ticker_raw,
        rulebook,
        common_as_of=common_as_of,
    ).reset_index(drop=True)
    if frame.empty:
        raise ValueError("fresh rulebook frame is empty")
    theme_close = theme_sma = theme_eligible = None
    if preferred_variant == "background-theme":
        theme_close, theme_sma, theme_eligible = _theme_facts(
            frame["date"],
            horizon,
            vnindex_raw,
            common_as_of,
        )
    execution = RulebookExecution(
        rulebook, selected_gates, preferred_variant,
        "AND" if preferred_variant == "background-theme" else None,
    )
    entries = rulebook_entry_signal(frame, execution, theme_eligible=theme_eligible)
    last = frame.iloc[-1]
    gate_facts = {gate: bool(last.get(gate, False)) for gate in selected_gates}
    result = {
        "as_of_date": pd.Timestamp(last["date"]).date().isoformat(),
        "latest_close": _number(last.get("close")),
        "latest_atr": _number(last.get("ATR_14")),
        "literal_entry": bool(entries.iloc[-1]),
        "missing_required_input": bool(last.get("rulebook_missing_required_input", True)),
        "gate_facts": gate_facts,
        # The corrected baseline owns no technical SELL or deterioration predicate.
        "technical_exit": False,
        "deteriorated": False,
    }
    if preferred_variant == "background-theme":
        result.update({
            "vnindex_close": _number(theme_close.iloc[-1]),
            "vnindex_theme_sma": _number(theme_sma.iloc[-1]),
            "theme_eligible": bool(theme_eligible.iloc[-1]),
        })
    return result


def _top_candidate(document: dict[str, object], rulebook_id: str) -> dict[str, object]:
    if rulebook_id not in document["top_rulebook_ids"]:
        raise ValueError("rulebook_id is not a Top-3 candidate")
    candidate = next(
        (item for item in document["candidates"] if item["rulebook_id"] == rulebook_id), None
    )
    if not isinstance(candidate, dict):
        raise ValueError("Top-3 candidate is absent from schema-5 aggregate")
    return candidate


def check_current_situation(
    ticker: str,
    *,
    horizon: str,
    rulebook_id: str,
    engine,
    output_dir: str | None = None,
) -> dict[str, object]:
    """Replay one schema-5 Top-3 preferred treatment against fresh data."""

    normalized = _normalize_ticker(ticker)
    document = load_current_rulebook_document(normalized, horizon, output_dir or DEFAULT_SIGNAL_DIR)
    if document is None or document["terminal_state"] != "success":
        return {"ticker": normalized, "horizon": horizon, "candidate": None, "current": None, "reason": "No current schema-5 exploratory rulebook exists."}
    start, end = _replay_bounds(document)
    ticker_raw = _load_raw(normalized, engine, start=start, end=end)
    vnindex_raw = _load_raw("VNINDEX", engine, start=start, end=end)
    current_evidence = validate_current_evidence(document, ticker_raw, vnindex_raw)
    if not _evidence_matches_frozen(
        document.get("evidence_eligibility"), current_evidence
    ):
        path = signal_artifact_path(
            normalized,
            horizon,
            str(ensure_result_root(output_dir or DEFAULT_SIGNAL_DIR)),
        )
        write_regeneration_marker(
            path,
            normalized,
            horizon,
            reason="Source history changed; regenerate Backtest schema 5.",
        )
        return {
            "ticker": normalized,
            "horizon": horizon,
            "candidate": None,
            "current": None,
            "reason": "source_history_changed",
            "evidence_eligibility": current_evidence.to_dict(),
        }
    candidate = _top_candidate(document, rulebook_id)
    preferred_variant = candidate["preferred_variant"]
    current = _current_rulebook_facts(
        normalized,
        horizon,
        tuple(candidate["selected_gates"]),
        preferred_variant,
        engine,
        ticker_raw=ticker_raw,
        vnindex_raw=vnindex_raw,
        common_as_of=current_evidence.common_as_of,
    )
    return {
        "ticker": normalized,
        "horizon": horizon,
        "candidate": candidate,
        "preferred_variant": preferred_variant,
        "current": current,
        "audit_eligibility": document["audit_eligibility"],
        "evidence_eligibility": current_evidence.to_dict(),
        "evaluation_label": document["evaluation_label"],
        "partition_labels": dict(document["partition_labels"]),
    }


__all__ = [
    "check_current_situation",
    "load_current_rulebook_document",
    "validate_current_evidence",
]
