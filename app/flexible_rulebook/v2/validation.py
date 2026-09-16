"""Boolean support projections and current BUY eligibility for Flexible v2."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Mapping

import pandas as pd

from .contracts import PredicateV2, RulebookDefinitionV2
from .features import PredicateEvaluation


_TREND_STATES = {"Fresh", "On-going", "Weakening", "Invalidated"}


def _boolean(values: pd.Series, name: str) -> pd.Series:
    if not isinstance(values, pd.Series):
        raise ValueError(f"{name} must be a pandas Series")
    return values.fillna(False).astype(bool)


@dataclass(frozen=True)
class RulebookComposition:
    """Causal entry/exit masks plus Boolean support facts owned by a rulebook."""

    entry_mask: pd.Series
    technical_exit_mask: pd.Series
    support_facts: tuple[pd.Series, ...]
    gate_support_facts: tuple[pd.Series, ...]

    def support_percentage(self, ordinal: int) -> float:
        if not self.support_facts:
            raise ValueError("rulebook composition requires support facts")
        return sum(bool(fact.iloc[ordinal]) for fact in self.support_facts) / len(self.support_facts) * 100.0

    def live_entry_support(self, ordinal: int) -> bool:
        return all(bool(fact.iloc[ordinal]) for fact in self.support_facts[: len(self.support_facts) - len(self.gate_support_facts)])

    def all_gates_support(self, ordinal: int) -> bool:
        return all(bool(fact.iloc[ordinal]) for fact in self.gate_support_facts)


def compose_rulebook(
    definition: RulebookDefinitionV2,
    evaluations: Mapping[PredicateV2, PredicateEvaluation],
) -> RulebookComposition:
    """Apply ALL/ANY BUY, ALL gates, ANY technical SELL using exact causal masks."""

    if not isinstance(definition, RulebookDefinitionV2):
        raise ValueError("definition must be RulebookDefinitionV2")
    predicates = (*definition.buy_predicates, *definition.gates, *definition.technical_exits)
    if any(predicate not in evaluations for predicate in predicates):
        raise ValueError("every rulebook predicate requires a PredicateEvaluation")
    if any(not isinstance(evaluations[predicate], PredicateEvaluation) for predicate in predicates):
        raise ValueError("predicate evaluations must be typed")
    reference = _boolean(evaluations[definition.buy_predicates[0]].mask, "buy mask")
    if any(len(evaluations[predicate].mask) != len(reference) for predicate in predicates):
        raise ValueError("predicate evaluations must share one native-bar length")
    buy_events = tuple(_boolean(evaluations[predicate].mask, "buy mask") for predicate in definition.buy_predicates)
    buy_support = tuple(_boolean(evaluations[predicate].support, "buy support") for predicate in definition.buy_predicates)
    entry = buy_events[0].copy()
    for mask in buy_events[1:]:
        entry = entry & mask if definition.entry_operator == "all" else entry | mask
    gate_masks = tuple(_boolean(evaluations[predicate].mask, "gate mask") for predicate in definition.gates)
    gate_support = tuple(_boolean(evaluations[predicate].support, "gate support") for predicate in definition.gates)
    for mask in gate_masks:
        entry = entry & mask
    if definition.entry_operator == "all":
        support_facts = (*buy_support, *gate_support)
    else:
        combined_buy_support = buy_support[0].copy()
        for support in buy_support[1:]:
            combined_buy_support = combined_buy_support | support
        support_facts = (combined_buy_support, *gate_support)
    technical = pd.Series(False, index=reference.index, dtype=bool)
    for predicate in definition.technical_exits:
        technical = technical | _boolean(evaluations[predicate].mask, "technical exit mask")
    return RulebookComposition(entry.astype(bool), technical.astype(bool), tuple(support_facts), gate_support)


def classify_monitoring(support_percentage: Decimal | float | int, trend_state: str) -> str:
    """Map unrounded Boolean support to the only three Flexible UI classes."""

    if trend_state not in _TREND_STATES:
        raise ValueError("trend_state is unsupported")
    try:
        support = Decimal(str(support_percentage))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("support_percentage must be finite") from error
    if not support.is_finite() or support < 0 or support > 100:
        raise ValueError("support_percentage must be from 0 through 100")
    if trend_state in {"Weakening", "Invalidated"} or support < Decimal("65"):
        return "No Match"
    if support <= Decimal("85"):
        return "Nearly Match"
    return "Closely Match"


def determine_buy_action(
    *,
    has_prior_event: bool,
    trend_state: str,
    live_entry_support: bool,
    all_gates_support: bool,
    evidence_available: bool,
    is_listed: bool,
    has_open_position: bool,
) -> str:
    """Keep current BUY advice distinct from historical artifact metrics."""

    if trend_state not in _TREND_STATES:
        raise ValueError("trend_state is unsupported")
    if has_open_position:
        return "HOLD"
    if all((
        has_prior_event,
        trend_state in {"Fresh", "On-going"},
        live_entry_support,
        all_gates_support,
        evidence_available,
        is_listed,
    )):
        return "can BUY"
    return "expired BUY"


def assess_progressive_state(
    *,
    has_prior_event: bool,
    age_native_bars: int | None,
    price_change_atr: float,
    drawdown_from_high_atr: float,
    recent_price_decline: bool,
    source_support: bool,
    gates_support: bool,
) -> str:
    """Classify causal post-entry progression without distance-to-threshold math.

    A current entry is Fresh.  Later bars need price and registry-owned support
    to remain On-going; absent or failed required gates invalidate immediately.
    Age raises the continuation proof required after three native bars but is
    never the sole reason a signal becomes invalid.
    """

    if not has_prior_event:
        return "Invalidated"
    if isinstance(age_native_bars, bool) or not isinstance(age_native_bars, int) or age_native_bars < 0:
        raise ValueError("age_native_bars must be a non-negative integer")
    values = (price_change_atr, drawdown_from_high_atr)
    if any(
        not isinstance(item, (int, float))
        or isinstance(item, bool)
        or not isfinite(float(item))
        for item in values
    ):
        raise ValueError("price progression values must be numeric")
    if not gates_support:
        return "Invalidated"
    severe_adverse = price_change_atr <= -1.5 and not source_support
    if severe_adverse:
        return "Invalidated"
    if age_native_bars == 0:
        return "Fresh"
    adverse_price = price_change_atr <= -0.5 or (
        recent_price_decline and drawdown_from_high_atr <= -0.5
    )
    if age_native_bars <= 3:
        return "Weakening" if adverse_price or not source_support else "On-going"
    return "On-going" if price_change_atr >= 0 and source_support else "Weakening"


__all__ = [
    "RulebookComposition",
    "assess_progressive_state",
    "classify_monitoring",
    "compose_rulebook",
    "determine_buy_action",
]
