"""Fresh current-bar replay for one preferred schema-4 rulebook."""

from datetime import datetime

import pandas as pd
import pytz

from .config import DEFAULT_SIGNAL_DIR, HORIZONS, _normalize_ticker, rulebook_for
from .data_quality import load_ticker_history, validate_ohlcv
from .indicators import build_rulebook_frame
from .models import RulebookExecution
from .persistence import load_rulebook_result, signal_artifact_path
from .result_store import ensure_result_root
from .signal_combos import rulebook_entry_signal


_MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")


def load_current_rulebook_document(ticker: str, horizon: str, output_dir: str = DEFAULT_SIGNAL_DIR) -> dict[str, object] | None:
    """Load one canonical schema-4 aggregate without probing legacy filenames."""

    normalized = _normalize_ticker(ticker)
    if horizon not in HORIZONS:
        raise ValueError("schema-4 rulebook horizon is invalid")
    path = signal_artifact_path(normalized, horizon, str(ensure_result_root(output_dir)))
    return None if not path.is_file() else load_rulebook_result(path)


def _fresh_bounds() -> tuple[object, object]:
    end = datetime.now(_MARKET_TIMEZONE).date()
    return (pd.Timestamp(end) - pd.DateOffset(years=15)).date(), end


def _load_raw(ticker: str, engine) -> pd.DataFrame:
    start, end = _fresh_bounds()
    raw = load_ticker_history(ticker, start, end, engine)
    quality = validate_ohlcv(raw)
    if not quality.is_valid:
        raise ValueError(f"invalid fresh {ticker} data: " + "; ".join(quality.errors))
    return raw


def _number(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _theme_facts(ticker_dates: pd.Series, horizon: str, engine) -> tuple[pd.Series, pd.Series, pd.Series]:
    rulebook = rulebook_for(horizon)
    vn_frame = build_rulebook_frame(_load_raw("VNINDEX", engine), rulebook)
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
) -> dict[str, object]:
    rulebook = rulebook_for(horizon)
    frame = build_rulebook_frame(_load_raw(ticker, engine), rulebook).reset_index(drop=True)
    if frame.empty:
        raise ValueError("fresh rulebook frame is empty")
    theme_close = theme_sma = theme_eligible = None
    if preferred_variant == "background-theme":
        theme_close, theme_sma, theme_eligible = _theme_facts(frame["date"], horizon, engine)
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
        raise ValueError("Top-3 candidate is absent from schema-4 aggregate")
    return candidate


def check_current_situation(
    ticker: str,
    *,
    horizon: str,
    rulebook_id: str,
    engine,
    output_dir: str | None = None,
) -> dict[str, object]:
    """Replay one schema-4 Top-3 preferred treatment against fresh data."""

    normalized = _normalize_ticker(ticker)
    document = load_current_rulebook_document(normalized, horizon, output_dir or DEFAULT_SIGNAL_DIR)
    if document is None or document["terminal_state"] != "success":
        return {"ticker": normalized, "horizon": horizon, "candidate": None, "current": None, "reason": "No current schema-4 exploratory rulebook exists."}
    candidate = _top_candidate(document, rulebook_id)
    preferred_variant = candidate["preferred_variant"]
    current = _current_rulebook_facts(
        normalized, horizon, tuple(candidate["selected_gates"]), preferred_variant, engine
    )
    return {
        "ticker": normalized,
        "horizon": horizon,
        "candidate": candidate,
        "preferred_variant": preferred_variant,
        "current": current,
        "audit_eligibility": document["audit_eligibility"],
        "evaluation_label": document["evaluation_label"],
    }


__all__ = ["check_current_situation", "load_current_rulebook_document"]
