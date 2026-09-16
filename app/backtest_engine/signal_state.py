"""Causal current-state assessment for one saved schema-5 signal candidate."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

import pandas as pd

from .config import HORIZONS, THEME_VARIANTS, rulebook_for
from .signal_combos import rulebook_entry_events


_EVENT_GATES = {"rulebook_rsi_upcross", "rulebook_volume_gate"}
_PERSISTENT_GATES = {"rulebook_joint_trend_pass", "rulebook_adx_gate"}
_FRESH = "fresh"
_ONGOING = "ongoing"
_WEAKENING = "weakening"
_INVALIDATED = "invalidated"


def _finite_number(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number) or not isfinite(float(number)):
        return None
    return float(number)


def _series(frame: pd.DataFrame, column: str) -> pd.Series | None:
    if column not in frame:
        return None
    return pd.to_numeric(frame[column], errors="coerce")


def _last_three_decline(values: pd.Series | None, event_position: int) -> bool:
    """Return true only for two observed consecutive adverse native-bar moves."""

    if values is None:
        return False
    observed = values.iloc[event_position:].dropna()
    if len(observed) < 3:
        return False
    tail = observed.iloc[-3:].to_numpy(dtype=float)
    return bool(tail[0] > tail[1] > tail[2])


def _joint_margin(frame: pd.DataFrame) -> pd.Series | None:
    required = (
        "rulebook_ma_fast",
        "rulebook_ma_slow",
        "rulebook_alligator_lips",
        "rulebook_alligator_teeth",
        "rulebook_alligator_jaw",
    )
    if any(column not in frame for column in required):
        return None
    ma_spread = _series(frame, "rulebook_ma_fast") - _series(frame, "rulebook_ma_slow")
    lip_spread = _series(frame, "rulebook_alligator_lips") - _series(frame, "rulebook_alligator_teeth")
    tooth_spread = _series(frame, "rulebook_alligator_teeth") - _series(frame, "rulebook_alligator_jaw")
    return pd.concat((ma_spread, lip_spread, tooth_spread), axis=1).min(axis=1)


def _source_facts(
    frame: pd.DataFrame,
    *,
    event_position: int,
    selected_gates: Sequence[str],
    preferred_variant: str,
    horizon: str,
    theme_eligible: pd.Series | None,
) -> tuple[dict[str, dict[str, object]], list[str]]:
    """Describe only source families used by the original candidate."""

    rulebook = rulebook_for(horizon)
    facts: dict[str, dict[str, object]] = {}
    hard_failures: list[str] = []
    last = frame.iloc[-1]

    if "rulebook_joint_trend_pass" in selected_gates:
        current_pass = bool(last.get("rulebook_joint_trend_pass", False))
        margin = _joint_margin(frame)
        available = margin is not None and margin.iloc[-1:].notna().all()
        deteriorating = _last_three_decline(margin, event_position) if available else True
        facts["joint_trend"] = {
            "holding": current_pass and not deteriorating,
            "deteriorating": deteriorating,
            "kind": "persistent",
        }
        if not current_pass or not available:
            hard_failures.append("joint_trend_failed")

    if "rulebook_adx_gate" in selected_gates:
        adx = _series(frame, "rulebook_adx_14")
        current = None if adx is None or adx.empty else _finite_number(adx.iloc[-1])
        current_pass = current is not None and current >= rulebook.adx_minimum
        deteriorating = _last_three_decline(adx, event_position) if current is not None else True
        facts["adx"] = {
            "holding": current_pass and not deteriorating,
            "deteriorating": deteriorating,
            "kind": "persistent",
        }
        if not current_pass:
            hard_failures.append("adx_below_minimum")

    if "rulebook_rsi_upcross" in selected_gates:
        rsi = _series(frame, "rulebook_rsi")
        current = None if rsi is None or rsi.empty else _finite_number(rsi.iloc[-1])
        current_pass = current is not None and current >= rulebook.rsi_upcross_level
        deteriorating = _last_three_decline(rsi, event_position) if current is not None else True
        facts["rsi"] = {
            "holding": current_pass and not deteriorating,
            "deteriorating": deteriorating,
            "kind": "persistent_after_event",
        }
        if not current_pass:
            hard_failures.append("rsi_below_entry_level")

    if "rulebook_volume_gate" in selected_gates:
        facts["volume"] = {
            # A breakout volume ratio is an event; later lower volume is neutral.
            "holding": bool(last.get("rulebook_volume_gate", False)),
            "deteriorating": False,
            "kind": "event",
        }

    if preferred_variant == "background-theme":
        current_theme = (
            False
            if theme_eligible is None or theme_eligible.empty
            else bool(theme_eligible.iloc[-1])
        )
        facts["theme"] = {
            "holding": current_theme,
            "deteriorating": not current_theme,
            "kind": "persistent",
        }
        if not current_theme:
            hard_failures.append("theme_failed")

    return facts, hard_failures


def assess_signal_state(
    frame: pd.DataFrame,
    entry_mask: pd.Series,
    selected_gates: Sequence[str],
    preferred_variant: str,
    horizon: str,
    *,
    theme_eligible: pd.Series | None = None,
) -> dict[str, object]:
    """Classify one current signal using its event-to-latest causal progression.

    Age raises continuation evidence requirements but never invalidates alone.
    The assessment is ephemeral: it never rewrites a saved artifact or metric.
    """

    if horizon not in HORIZONS or preferred_variant not in THEME_VARIANTS:
        raise ValueError("signal state identity is invalid")
    if not isinstance(frame, pd.DataFrame) or "date" not in frame:
        raise ValueError("signal state requires a dated frame")
    if not selected_gates:
        raise ValueError("signal state requires selected gates")
    invalid_gates = set(selected_gates).difference(_EVENT_GATES | _PERSISTENT_GATES)
    if invalid_gates:
        raise ValueError("signal state selected gates are invalid")
    if "rulebook_missing_required_input" not in frame:
        raise ValueError("signal state requires input availability")
    if len(frame) != len(entry_mask):
        raise ValueError("signal state entry mask does not align to frame")

    entries = pd.Series(entry_mask, index=frame.index).fillna(False).astype(bool)
    observed = ~frame["rulebook_missing_required_input"].fillna(True).astype(bool)
    events = rulebook_entry_events(entries, observed)
    event_positions = list(events[events].index)
    if not event_positions:
        return {
            "state": _INVALIDATED,
            "signal_date": None,
            "age_native_bars": None,
            "reasons": ["no_observed_entry_event"],
            "source_facts": {},
        }
    event_position = event_positions[-1]
    dates = pd.to_datetime(frame["date"], errors="coerce")
    signal_date = pd.Timestamp(dates.loc[event_position]).date().isoformat()
    age = int(len(frame) - 1 - frame.index.get_loc(event_position))
    signal_close = _finite_number(frame.loc[event_position].get("close"))
    signal_atr = _finite_number(frame.loc[event_position].get("ATR_14"))
    latest_close = _finite_number(frame.iloc[-1].get("close"))
    if signal_close is None or signal_atr is None or latest_close is None or signal_atr <= 0:
        return {
            "state": _INVALIDATED,
            "signal_date": signal_date,
            "age_native_bars": age,
            "reasons": ["missing_signal_price_or_atr"],
            "source_facts": {},
        }

    source_facts, hard_failures = _source_facts(
        frame,
        event_position=event_position,
        selected_gates=selected_gates,
        preferred_variant=preferred_variant,
        horizon=horizon,
        theme_eligible=theme_eligible,
    )
    post_signal_close = _series(frame, "close").iloc[event_position:]
    post_signal_high = float(post_signal_close.max())
    price_change_atr = (latest_close - signal_close) / signal_atr
    drawdown_atr = (latest_close - post_signal_high) / signal_atr
    recent_decline = _last_three_decline(post_signal_close, 0)
    price_positive = latest_close >= signal_close
    price_adverse = price_change_atr <= -0.5 or (recent_decline and drawdown_atr <= -0.5)
    price_severe = price_change_atr <= -1.5
    source_deteriorating = any(bool(fact["deteriorating"]) for fact in source_facts.values())
    persistent = [
        fact for fact in source_facts.values()
        if fact["kind"] in ("persistent", "persistent_after_event")
    ]
    source_support = (
        all(bool(fact["holding"]) for fact in persistent)
        if persistent
        else any(bool(fact["holding"]) for fact in source_facts.values())
    )

    reasons: list[str] = []
    if hard_failures:
        state = _INVALIDATED
        reasons.extend(hard_failures)
    elif price_severe and source_deteriorating:
        state = _INVALIDATED
        reasons.extend(("severe_adverse_price", "selected_source_deteriorating"))
    elif age == 0:
        state = _FRESH
        reasons.append("new_entry_event")
    elif age <= 3:
        if price_adverse or source_deteriorating:
            state = _WEAKENING
            if price_adverse:
                reasons.append("adverse_price")
            if source_deteriorating:
                reasons.extend(
                    f"{name}_deteriorating"
                    for name, fact in source_facts.items()
                    if bool(fact["deteriorating"])
                )
        else:
            state = _ONGOING
            reasons.extend(("price_holding", "selected_sources_holding"))
    elif age <= 6:
        if price_positive and source_support:
            state = _ONGOING
            reasons.extend(("price_continuing", "selected_sources_holding"))
        else:
            state = _WEAKENING
            reasons.append("insufficient_continuation_after_three_bars")
    elif price_positive and source_support:
        state = _ONGOING
        reasons.extend(("price_continuing", "selected_sources_holding"))
    else:
        state = _WEAKENING
        reasons.append("insufficient_independent_positive_facts")

    return {
        "state": state,
        "signal_date": signal_date,
        "age_native_bars": age,
        "price_change_atr": price_change_atr,
        "drawdown_from_post_signal_high_atr": drawdown_atr,
        "price_positive": price_positive,
        "source_support": source_support,
        "source_facts": source_facts,
        "reasons": reasons,
    }


__all__ = ["assess_signal_state"]
