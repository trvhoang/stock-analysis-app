"""Read-only source-calendar and trajectory traces for saved schema-5 candidates."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytz

from commons.trading_calendar import align_to_vnindex_calendar

from .config import DEFAULT_SIGNAL_DIR, HORIZONS, _normalize_ticker, rulebook_for
from .indicators import build_rulebook_frame
from .models import RulebookExecution
from .persistence import load_rulebook_result, signal_artifact_path
from .signal_combos import rulebook_entry_events, rulebook_entry_signal
from .timeframes import latest_common_completed_bar
from .validation_advice import monitoring_match_level
from .vnindex_theme import align_vnindex_asof, build_vnindex_confirmation
from .data_quality import load_ticker_history


_HCM = pytz.timezone("Asia/Ho_Chi_Minh")
_TRACE_COLUMNS = (
    "date",
    "close",
    "rulebook_rsi",
    "rulebook_adx_14",
    "rulebook_joint_trend_pass",
    "rulebook_rsi_upcross",
    "rulebook_volume_gate",
    "rulebook_adx_gate",
)


def _date_only(value: object, name: str) -> date:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"{name} must be a valid date")
    return pd.Timestamp(parsed).date()


def _number(value: object) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(numeric) else float(numeric)


def _candidate_execution(horizon: str, candidate: Mapping[str, object]) -> RulebookExecution:
    if horizon not in HORIZONS:
        raise ValueError("candidate horizon is invalid")
    gates = candidate.get("selected_gates")
    preferred_variant = candidate.get("preferred_variant")
    if not isinstance(gates, list) or not isinstance(preferred_variant, str):
        raise ValueError("candidate has no usable selected gates or treatment")
    execution = RulebookExecution(
        rulebook_for(horizon),
        tuple(gates),
        preferred_variant,
        "AND" if preferred_variant == "background-theme" else None,
    )
    if candidate.get("rulebook_id") != execution.rule_id:
        raise ValueError("candidate rulebook identity is invalid")
    return execution


def summarize_entry_events(
    frame: pd.DataFrame,
    entry_mask: pd.Series,
    *,
    trace_start: date | None = None,
) -> dict[str, object]:
    """Summarize causal entry edges without changing a level-entry rulebook."""

    if not isinstance(frame, pd.DataFrame) or "date" not in frame:
        raise ValueError("diagnostic frame requires dates")
    if "rulebook_missing_required_input" not in frame:
        raise ValueError("diagnostic frame requires missing-input facts")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any() or len(dates) != len(entry_mask):
        raise ValueError("diagnostic entry series does not align to native dates")
    observed = ~frame["rulebook_missing_required_input"].fillna(True).astype(bool)
    entries = pd.Series(entry_mask, index=frame.index).fillna(False).astype(bool)
    events = rulebook_entry_events(entries, observed)
    event_positions = list(events[events].index)
    latest_position = event_positions[-1] if event_positions else None
    native_dates = pd.Series(dates.to_numpy(), index=frame.index)
    trace_cutoff = None if trace_start is None else pd.Timestamp(_date_only(trace_start, "trace_start"))
    trace = []
    for index in frame.index:
        if trace_cutoff is not None and native_dates.loc[index] < trace_cutoff:
            continue
        record: dict[str, object] = {
            "date": native_dates.loc[index].date().isoformat(),
            "observed": bool(observed.loc[index]),
            "entry_level": bool(entries.loc[index]),
            "entry_event": bool(events.loc[index]),
        }
        for column in _TRACE_COLUMNS:
            if column == "date" or column not in frame:
                continue
            value = frame.loc[index, column]
            record[column] = bool(value) if isinstance(value, bool) else _number(value)
        trace.append(record)
    return {
        "latest_entry_is_event": bool(events.iloc[-1]) if not events.empty else False,
        "latest_entry_level": bool(entries.iloc[-1]) if not entries.empty else False,
        "latest_event_date": (
            None if latest_position is None else native_dates.loc[latest_position].date().isoformat()
        ),
        "age_native_bars": (
            None if latest_position is None else len(frame) - 1 - frame.index.get_loc(latest_position)
        ),
        "observed_event_count": len(event_positions),
        "trace": trace,
    }


def trajectory_facts(
    frame: pd.DataFrame,
    selected_gates: tuple[str, ...],
    horizon: str,
) -> dict[str, bool | None]:
    """Report causal direction facts; ADX alone never establishes a decline."""

    rulebook = rulebook_for(horizon)
    gates = set(selected_gates)
    close = pd.to_numeric(frame.get("close"), errors="coerce")
    joint = frame.get("rulebook_joint_trend_pass")
    close_declines = None
    if isinstance(close, pd.Series) and len(close) >= 4 and close.iloc[-4:].notna().all():
        trailing = close.iloc[-4:].tolist()
        close_declines = all(later < earlier for earlier, later in zip(trailing, trailing[1:]))
    joint_fails = None
    if isinstance(joint, pd.Series) and not joint.empty and not pd.isna(joint.iloc[-1]):
        joint_fails = not bool(joint.iloc[-1])
    rsi_below = None
    if "rulebook_rsi_upcross" in gates:
        rsi = pd.to_numeric(frame.get("rulebook_rsi"), errors="coerce")
        if isinstance(rsi, pd.Series) and not rsi.empty and not pd.isna(rsi.iloc[-1]):
            rsi_below = bool(rsi.iloc[-1] < rulebook.rsi_upcross_level)
    adx_falls = None
    if "rulebook_adx_gate" in gates:
        adx = pd.to_numeric(frame.get("rulebook_adx_14"), errors="coerce")
        if isinstance(adx, pd.Series) and len(adx) >= 2 and adx.iloc[-2:].notna().all():
            adx_falls = bool(
                adx.iloc[-1] < rulebook.adx_minimum and adx.iloc[-1] < adx.iloc[-2]
            )
    trajectory_a = None if close_declines is None or joint_fails is None else close_declines and joint_fails
    trajectory_b = None if trajectory_a is None or rsi_below is None else trajectory_a and rsi_below
    trajectory_c = None if trajectory_a is None or adx_falls is None else trajectory_a and adx_falls
    return {
        "close_declines_three_bars": close_declines,
        "joint_trend_fails": joint_fails,
        "rsi_below_entry_level": rsi_below,
        "adx_below_minimum_and_falling": adx_falls,
        "trajectory_a": trajectory_a,
        "trajectory_b": trajectory_b,
        "trajectory_c": trajectory_c,
    }


def _theme_eligible(frame: pd.DataFrame, vnindex_raw: pd.DataFrame, horizon: str, common_as_of: date) -> pd.Series:
    rulebook = rulebook_for(horizon)
    confirmation = build_vnindex_confirmation(vnindex_raw, horizon, common_as_of=common_as_of)
    confirmation_frame = pd.DataFrame({
        "date": pd.DatetimeIndex(confirmation.index),
        "close": confirmation.to_numpy(),
    })
    aligned = align_vnindex_asof(frame[["date"]], confirmation_frame)
    return aligned["vnindex_close"].fillna(False).astype(bool)


def diagnose_candidate(
    ticker: str,
    *,
    horizon: str,
    candidate: Mapping[str, object],
    ticker_raw: pd.DataFrame,
    vnindex_raw: pd.DataFrame,
    requested_end: date,
    trace_start: date | None = None,
) -> dict[str, object]:
    """Build one read-only, calendar-filtered trace for a saved candidate."""

    normalized = _normalize_ticker(ticker)
    execution = _candidate_execution(horizon, candidate)
    source_dates = pd.to_datetime(ticker_raw.get("date"), errors="coerce")
    if source_dates.empty or source_dates.isna().any():
        raise ValueError("ticker source has no usable dates")
    prepared, calendar, outside = align_to_vnindex_calendar(
        ticker_raw,
        vnindex_raw,
        start=source_dates.min().date(),
        end=_date_only(requested_end, "requested_end"),
    )
    common_as_of = latest_common_completed_bar(
        {normalized: prepared, "VNINDEX": vnindex_raw},
        _date_only(requested_end, "requested_end"),
    )
    frame = build_rulebook_frame(
        prepared,
        execution.rulebook,
        common_as_of=common_as_of,
    ).reset_index(drop=True)
    if frame.empty:
        raise ValueError("calendar-filtered native rulebook frame is empty")
    themed = None
    if execution.theme_variant == "background-theme":
        themed = _theme_eligible(frame, vnindex_raw, horizon, common_as_of)
    entries = rulebook_entry_signal(frame, execution, theme_eligible=themed)
    gate_facts = {
        gate: bool(frame[gate].iloc[-1])
        for gate in execution.selected_gates
        if gate in frame
    }
    current = {"gate_facts": gate_facts}
    if themed is not None:
        current["theme_eligible"] = bool(themed.iloc[-1])
    monitoring = monitoring_match_level(
        horizon,
        execution.selected_gates,
        execution.theme_variant,
        current,
        execution.rulebook,
    )
    return {
        "ticker": normalized,
        "horizon": horizon,
        "rulebook_id": execution.rule_id,
        "selected_gates": list(execution.selected_gates),
        "preferred_variant": execution.theme_variant,
        "common_as_of": common_as_of.isoformat(),
        "current_native_bar": pd.Timestamp(frame["date"].iloc[-1]).date().isoformat(),
        "native_bar_count": len(frame),
        "calendar": {
            "assumed_non_sessions": [value.isoformat() for value in calendar.assumed_non_sessions],
            "excluded_ticker_dates": [value.isoformat() for value in outside],
        },
        "gate_facts": gate_facts,
        "monitoring": None if monitoring is None else {
            "match_level": monitoring[0],
            "classification": monitoring[1],
        },
        "entry": summarize_entry_events(frame, entries, trace_start=trace_start),
        "trajectory": trajectory_facts(frame, execution.selected_gates, horizon),
    }


def audit_saved_candidates(
    engine: object,
    *,
    signal_dir: str = DEFAULT_SIGNAL_DIR,
    trace_overrides: Mapping[str, date] | None = None,
    as_of: date | None = None,
) -> dict[str, object]:
    """Inspect every saved Top-3 candidate without touching result artifacts."""

    end = _date_only(as_of, "as_of") if as_of is not None else datetime.now(_HCM).date()
    root = Path(signal_dir)
    records: list[dict[str, object]] = []
    if not root.exists():
        return {"write_boundary": {"database": False, "jobs": False, "artifacts": False}, "candidates": records}
    normalized_overrides = {
        _normalize_ticker(ticker): _date_only(value, "trace override")
        for ticker, value in (trace_overrides or {}).items()
    }
    source_cache: dict[tuple[str, date], pd.DataFrame] = {}
    for ticker_dir in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name):
        try:
            ticker = _normalize_ticker(ticker_dir.name)
        except ValueError:
            continue
        for horizon in HORIZONS:
            path = signal_artifact_path(ticker, horizon, str(root))
            if not path.is_file():
                continue
            try:
                document = load_rulebook_result(path)
            except (OSError, ValueError, TypeError) as error:
                records.append({"ticker": ticker, "horizon": horizon, "availability": "unavailable", "reason": str(error)})
                continue
            if document.get("terminal_state") != "success":
                continue
            requested = document.get("requested_date_range")
            if not isinstance(requested, Mapping) or not isinstance(requested.get("start"), str):
                records.append({"ticker": ticker, "horizon": horizon, "availability": "unavailable", "reason": "artifact has no requested start"})
                continue
            try:
                start = date.fromisoformat(requested["start"])
                key = (ticker, start)
                ticker_raw = source_cache.setdefault(key, load_ticker_history(ticker, start, end, engine))
                vnindex_raw = source_cache.setdefault(("VNINDEX", start), load_ticker_history("VNINDEX", start, end, engine))
                candidate_by_id = {item["rulebook_id"]: item for item in document["candidates"]}
                for rulebook_id in document["top_rulebook_ids"]:
                    candidate = candidate_by_id[rulebook_id]
                    records.append({
                        "availability": "available",
                        **diagnose_candidate(
                            ticker,
                            horizon=horizon,
                            candidate=candidate,
                            ticker_raw=ticker_raw,
                            vnindex_raw=vnindex_raw,
                            requested_end=end,
                            trace_start=normalized_overrides.get(ticker),
                        ),
                    })
            except (OSError, ValueError, TypeError, KeyError) as error:
                records.append({"ticker": ticker, "horizon": horizon, "availability": "unavailable", "reason": str(error)})
    return {
        "write_boundary": {"database": False, "jobs": False, "artifacts": False},
        "candidates": records,
    }


__all__ = [
    "audit_saved_candidates",
    "diagnose_candidate",
    "summarize_entry_events",
    "trajectory_facts",
]
