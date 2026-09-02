"""Isolated schema-5 staged research; never a canonical product rulebook."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
import json
from math import fsum, isfinite
from statistics import median

import pandas as pd

from .config import HORIZONS
from .indicators import series_upcross
from .models import TradeEvent
from .validation import calculate_deflated_sharpe, calculate_unannualized_sharpe


_CONFIRMATIONS = ("adx_directional", "relative_volume", "vnindex_and")


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _event_time(value: object, field: str) -> pd.Timestamp:
    converted = pd.Timestamp(value)
    if pd.isna(converted):
        raise ValueError(f"trade {field} must be a valid date")
    return converted.normalize()


@dataclass(frozen=True)
class ResearchDefinition:
    """One immutable setup-trigger-confirmation definition for staged research."""

    definition_id: str
    horizon: str
    setup: str | None
    trigger: str | None
    confirmations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.definition_id, str) or not self.definition_id.strip():
            raise ValueError("definition_id is required")
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        if not isinstance(self.setup, str) or not self.setup.strip() or not isinstance(self.trigger, str) or not self.trigger.strip():
            raise ValueError("setup and trigger are required")
        confirmations = tuple(self.confirmations)
        if confirmations != tuple(sorted(set(confirmations))):
            raise ValueError("confirmations must be unique lexical order")
        if any(item not in _CONFIRMATIONS for item in confirmations):
            raise ValueError("confirmation is not approved for staged research")
        object.__setattr__(self, "definition_id", self.definition_id.strip())
        object.__setattr__(self, "setup", self.setup.strip())
        object.__setattr__(self, "trigger", self.trigger.strip())
        object.__setattr__(self, "confirmations", confirmations)

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "schema_version": 5,
            "candidate_role": "research_only",
            "definition_id": self.definition_id,
            "horizon": self.horizon,
            "setup": self.setup,
            "trigger": self.trigger,
            "confirmations": list(self.confirmations),
        }

    @property
    def research_definition_id(self) -> str:
        digest = sha256(_canonical_json(self.to_identity_dict()).encode("utf-8")).hexdigest()
        return f"btr_{digest}"

    def to_dict(self) -> dict[str, object]:
        return {
            **self.to_identity_dict(),
            "research_definition_id": self.research_definition_id,
        }


SWING_CONTROL = ResearchDefinition(
    definition_id="swing_joint_rsi52_control_v1",
    horizon="swing",
    setup="ema5_13_and_alligator_up",
    trigger="rsi9_upcross_52",
    confirmations=(),
)
SWING_VARIANT = ResearchDefinition(
    definition_id="swing_ema_rsi52_variant_v1",
    horizon="swing",
    setup="ema5_above_ema13",
    trigger="rsi9_upcross_52",
    confirmations=(),
)
MIDTERM_CONTROL = ResearchDefinition(
    definition_id="midterm_joint_rsi65_control_v1",
    horizon="midterm",
    setup="sma8_21_and_alligator_up",
    trigger="rsi14_upcross_65",
    confirmations=(),
)
MIDTERM_VARIANT = ResearchDefinition(
    definition_id="midterm_joint_close_sma8_variant_v1",
    horizon="midterm",
    setup="sma8_21_and_alligator_up",
    trigger="close_upcross_sma8",
    confirmations=(),
)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        raise ValueError(f"research frame is missing {column}")
    return pd.to_numeric(frame[column], errors="coerce")


def definition_entry_signal(
    frame: pd.DataFrame,
    definition: ResearchDefinition,
    *,
    theme_eligible: pd.Series | None = None,
) -> pd.Series:
    """Return one causal BUY event for an approved staged definition."""

    if not isinstance(frame, pd.DataFrame) or not isinstance(definition, ResearchDefinition):
        raise ValueError("research entry requires a frame and ResearchDefinition")
    fast = _numeric(frame, "rulebook_ma_fast")
    slow = _numeric(frame, "rulebook_ma_slow")
    if definition.setup in ("ema5_13_and_alligator_up", "sma8_21_and_alligator_up"):
        lips = _numeric(frame, "rulebook_alligator_lips")
        teeth = _numeric(frame, "rulebook_alligator_teeth")
        jaw = _numeric(frame, "rulebook_alligator_jaw")
        setup = fast.gt(slow) & lips.gt(teeth) & teeth.gt(jaw)
    elif definition.setup == "ema5_above_ema13":
        setup = fast.gt(slow)
    else:
        raise ValueError("research setup is not implemented")

    if definition.trigger in ("rsi9_upcross_52", "rsi14_upcross_65"):
        if "rulebook_rsi_upcross" not in frame:
            raise ValueError("research frame is missing rulebook_rsi_upcross")
        trigger = frame["rulebook_rsi_upcross"].fillna(False).astype(bool)
    elif definition.trigger == "close_upcross_sma8":
        trigger = series_upcross(_numeric(frame, "close"), fast)
    else:
        raise ValueError("research trigger is not implemented")

    signal = setup.fillna(False).astype(bool) & trigger
    for confirmation in definition.confirmations:
        if confirmation == "adx_directional":
            if "rulebook_adx_gate" not in frame:
                raise ValueError("research frame is missing rulebook_adx_gate")
            signal &= (
                frame["rulebook_adx_gate"].fillna(False).astype(bool)
                & _numeric(frame, "rulebook_plus_di_14").gt(
                    _numeric(frame, "rulebook_minus_di_14")
                )
            )
        elif confirmation == "relative_volume":
            if "rulebook_volume_gate" not in frame:
                raise ValueError("research frame is missing rulebook_volume_gate")
            signal &= frame["rulebook_volume_gate"].fillna(False).astype(bool)
        elif confirmation == "vnindex_and":
            if theme_eligible is None or not frame.index.equals(theme_eligible.index):
                raise ValueError("VN-Index confirmation requires aligned theme evidence")
            signal &= theme_eligible.fillna(False).astype(bool)
    if "rulebook_missing_required_input" in frame:
        signal &= ~frame["rulebook_missing_required_input"].fillna(True).astype(bool)
    return signal.fillna(False).astype(bool)


@dataclass(frozen=True)
class MatchedTradePair:
    """The first deterministic inclusive overlap for one control/variant trade."""

    control: TradeEvent
    variant: TradeEvent
    variant_signal_lead_bars: int
    overlap_start: pd.Timestamp
    overlap_end: pd.Timestamp

    def to_dict(self) -> dict[str, object]:
        return {
            "control_signal_date": _event_time(self.control.signal_date, "signal_date").date().isoformat(),
            "variant_signal_date": _event_time(self.variant.signal_date, "signal_date").date().isoformat(),
            "variant_signal_lead_bars": self.variant_signal_lead_bars,
            "overlap_start": self.overlap_start.date().isoformat(),
            "overlap_end": self.overlap_end.date().isoformat(),
        }


def _validated_events(events: Sequence[TradeEvent], label: str) -> tuple[TradeEvent, ...]:
    if isinstance(events, (str, bytes)):
        raise ValueError(f"{label} trades must be an ordered sequence")
    values = tuple(events)
    if any(not isinstance(event, TradeEvent) for event in values):
        raise ValueError(f"{label} trades must contain TradeEvent values")
    keys = tuple(
        (
            _event_time(event.entry_date, "entry_date"),
            _event_time(event.exit_date, "exit_date"),
            _event_time(event.signal_date, "signal_date"),
        )
        for event in values
    )
    if keys != tuple(sorted(keys)):
        raise ValueError(f"{label} trades must be ordered by entry and exit")
    return values


def pair_first_overlaps(
    control: Sequence[TradeEvent],
    variant: Sequence[TradeEvent],
    native_dates: Sequence[date],
) -> tuple[MatchedTradePair, ...]:
    """Pair first inclusive entry-to-exit overlaps with a two-pointer scan."""

    control_events = _validated_events(control, "control")
    variant_events = _validated_events(variant, "variant")
    clock = tuple(_event_time(value, "native date") for value in native_dates)
    if not clock or clock != tuple(sorted(set(clock))):
        raise ValueError("native dates must be ascending unique values")
    positions = {value: index for index, value in enumerate(clock)}
    for event in (*control_events, *variant_events):
        signal = _event_time(event.signal_date, "signal_date")
        if signal not in positions:
            raise ValueError("trade signal date is absent from native dates")

    pairs: list[MatchedTradePair] = []
    control_index = variant_index = 0
    while control_index < len(control_events) and variant_index < len(variant_events):
        control_event = control_events[control_index]
        variant_event = variant_events[variant_index]
        control_entry = _event_time(control_event.entry_date, "entry_date")
        control_exit = _event_time(control_event.exit_date, "exit_date")
        variant_entry = _event_time(variant_event.entry_date, "entry_date")
        variant_exit = _event_time(variant_event.exit_date, "exit_date")
        if control_exit < variant_entry:
            control_index += 1
            continue
        if variant_exit < control_entry:
            variant_index += 1
            continue
        control_signal = _event_time(control_event.signal_date, "signal_date")
        variant_signal = _event_time(variant_event.signal_date, "signal_date")
        pairs.append(
            MatchedTradePair(
                control_event,
                variant_event,
                positions[control_signal] - positions[variant_signal],
                max(control_entry, variant_entry),
                min(control_exit, variant_exit),
            )
        )
        control_index += 1
        variant_index += 1
    return tuple(pairs)


@dataclass(frozen=True)
class YearOmissionMetrics:
    omitted_year: int
    n: int
    win_rate: float
    profit_pct: float
    sharpe: float | None
    positive: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "omitted_year": self.omitted_year,
            "n": self.n,
            "win_rate": self.win_rate,
            "profit_pct": self.profit_pct,
            "sharpe": self.sharpe,
            "positive": self.positive,
        }


@dataclass(frozen=True)
class ResearchMetrics:
    n: int
    win_rate: float
    profit_pct: float
    sharpe: float | None
    mean_mae_pct: float | None
    stop_loss_rate: float
    maximum_drawdown_pct: float
    distinct_years: int
    absolute_pnl_concentration: float
    positive_year_omission_count: int
    year_omissions: tuple[YearOmissionMetrics, ...]

    def rank_key(self) -> tuple[float, float, float]:
        return self.win_rate, self.profit_pct, float(self.sharpe or 0.0)

    def to_dict(self) -> dict[str, object]:
        return {
            "n": self.n,
            "win_rate": self.win_rate,
            "profit_pct": self.profit_pct,
            "sharpe": self.sharpe,
            "mean_mae_pct": self.mean_mae_pct,
            "stop_loss_rate": self.stop_loss_rate,
            "maximum_drawdown_pct": self.maximum_drawdown_pct,
            "distinct_years": self.distinct_years,
            "absolute_pnl_concentration": self.absolute_pnl_concentration,
            "positive_year_omission_count": self.positive_year_omission_count,
            "year_omissions": [item.to_dict() for item in self.year_omissions],
        }


@dataclass(frozen=True)
class ResearchTreatmentEvidence:
    """Both partitions plus training-only DSR for one definition treatment."""

    definition_id: str
    theme_variant: str
    training: ResearchMetrics
    test: ResearchMetrics
    training_dsr: float | None
    dsr_status: str
    selected: bool

    def training_to_dict(self) -> dict[str, object]:
        return {
            "definition_id": self.definition_id,
            "theme_variant": self.theme_variant,
            "training": self.training.to_dict(),
            "training_dsr": self.training_dsr,
            "dsr_status": self.dsr_status,
            "selected": self.selected,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.training_to_dict(), "test": self.test.to_dict()}


def _basic_metrics(events: Sequence[TradeEvent]) -> tuple[int, float, float, float | None]:
    returns = tuple(float(event.return_pct) for event in events)
    if not all(isfinite(value) and value > -100.0 for value in returns):
        raise ValueError("research returns must be finite and greater than -100 percent")
    n = len(returns)
    profit = float(fsum(returns))
    win_rate = sum(value > 0.0 for value in returns) / n * 100.0 if n else 0.0
    sharpe = calculate_unannualized_sharpe(returns) if n >= 2 else None
    return n, win_rate, profit, sharpe


def leave_one_year_out(events: Sequence[TradeEvent]) -> tuple[YearOmissionMetrics, ...]:
    """Omit each completed-exit calendar year without tuning any parameter."""

    values = _validated_events(events, "year-omission")
    years = tuple(sorted({_event_time(event.exit_date, "exit_date").year for event in values}))
    result = []
    for year in years:
        retained = tuple(
            event for event in values
            if _event_time(event.exit_date, "exit_date").year != year
        )
        n, win_rate, profit, sharpe = _basic_metrics(retained)
        result.append(YearOmissionMetrics(year, n, win_rate, profit, sharpe, profit > 0.0))
    return tuple(result)


def _maximum_drawdown(returns: Sequence[float]) -> float:
    equity = peak = 1.0
    maximum = 0.0
    for value in returns:
        equity *= 1.0 + float(value) / 100.0
        peak = max(peak, equity)
        if peak > 0.0:
            maximum = max(maximum, (peak - equity) / peak * 100.0)
    return float(maximum)


def research_metrics(events: Sequence[TradeEvent]) -> ResearchMetrics:
    """Return unrounded gross training diagnostics for completed trades."""

    values = _validated_events(events, "research")
    n, win_rate, profit, sharpe = _basic_metrics(values)
    maes = tuple(event.maximum_adverse_excursion_pct for event in values)
    mean_mae = (
        float(fsum(float(value) for value in maes) / n)
        if n and all(value is not None for value in maes)
        else None
    )
    stop_rate = sum(event.exit_reason == "stop_loss" for event in values) / n * 100.0 if n else 0.0
    annual_profit: dict[int, float] = defaultdict(float)
    for event in values:
        annual_profit[_event_time(event.exit_date, "exit_date").year] += float(event.return_pct)
    absolute_annual = tuple(abs(value) for value in annual_profit.values())
    denominator = fsum(absolute_annual)
    concentration = max(absolute_annual, default=0.0) / denominator if denominator else 0.0
    omissions = leave_one_year_out(values)
    return ResearchMetrics(
        n=n,
        win_rate=win_rate,
        profit_pct=profit,
        sharpe=sharpe,
        mean_mae_pct=mean_mae,
        stop_loss_rate=stop_rate,
        maximum_drawdown_pct=_maximum_drawdown(tuple(float(event.return_pct) for event in values)),
        distinct_years=len(annual_profit),
        absolute_pnl_concentration=float(concentration),
        positive_year_omission_count=sum(item.positive for item in omissions),
        year_omissions=omissions,
    )


@dataclass(frozen=True)
class ResearchEvaluation:
    """Training-selected research evidence with test retained as observation only."""

    control: ResearchDefinition
    variant: ResearchDefinition
    control_training: ResearchMetrics
    variant_training: ResearchMetrics
    control_test: ResearchMetrics
    variant_test: ResearchMetrics
    matched_pairs: tuple[MatchedTradePair, ...]
    unmatched_control_count: int
    unmatched_variant_count: int
    median_variant_signal_lead_bars: float | None
    training_accepted: bool
    acceptance_failures: tuple[str, ...]
    selected_definition_id: str
    control_preferred_treatment: str = "no-background-theme"
    variant_preferred_treatment: str = "no-background-theme"
    treatments: tuple[ResearchTreatmentEvidence, ...] = ()

    @property
    def candidate_role(self) -> str:
        return "research_only"

    def selection_to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 5,
            "candidate_role": "research_only",
            "horizon": self.control.horizon,
            "control_definition_id": self.control.research_definition_id,
            "variant_definition_id": self.variant.research_definition_id,
            "training_accepted": self.training_accepted,
            "acceptance_failures": list(self.acceptance_failures),
            "selected_definition_id": self.selected_definition_id,
            "control_training": self.control_training.to_dict(),
            "variant_training": self.variant_training.to_dict(),
            "matched_pair_count": len(self.matched_pairs),
            "unmatched_control_count": self.unmatched_control_count,
            "unmatched_variant_count": self.unmatched_variant_count,
            "median_variant_signal_lead_bars": self.median_variant_signal_lead_bars,
            "control_preferred_treatment": self.control_preferred_treatment,
            "variant_preferred_treatment": self.variant_preferred_treatment,
            "treatment_training": [item.training_to_dict() for item in self.treatments],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self.selection_to_dict(),
            "control_test": self.control_test.to_dict(),
            "variant_test": self.variant_test.to_dict(),
            "matched_pairs": [pair.to_dict() for pair in self.matched_pairs],
            "treatments": [item.to_dict() for item in self.treatments],
        }


def evaluate_research_pair(
    control: ResearchDefinition,
    variant: ResearchDefinition,
    control_training: Sequence[TradeEvent],
    variant_training: Sequence[TradeEvent],
    native_dates: Sequence[date],
    *,
    control_test: Sequence[TradeEvent] = (),
    variant_test: Sequence[TradeEvent] = (),
) -> ResearchEvaluation:
    """Select from training only; historical-test evidence cannot alter selection."""

    if not isinstance(control, ResearchDefinition) or not isinstance(variant, ResearchDefinition):
        raise ValueError("research evaluation requires two definitions")
    if control.horizon != variant.horizon:
        raise ValueError("research definitions must share one horizon")
    approved_pairs = {
        "swing": (
            SWING_CONTROL.research_definition_id,
            SWING_VARIANT.research_definition_id,
        ),
        "midterm": (
            MIDTERM_CONTROL.research_definition_id,
            MIDTERM_VARIANT.research_definition_id,
        ),
    }
    if (
        control.research_definition_id,
        variant.research_definition_id,
    ) != approved_pairs[control.horizon]:
        raise ValueError("research evaluation requires the approved experiment pair")
    control_events = _validated_events(control_training, "control training")
    variant_events = _validated_events(variant_training, "variant training")
    control_test_events = _validated_events(control_test, "control test")
    variant_test_events = _validated_events(variant_test, "variant test")
    pairs = pair_first_overlaps(control_events, variant_events, native_dates)
    leads = tuple(pair.variant_signal_lead_bars for pair in pairs)
    median_lead = float(median(leads)) if leads else None
    control_metrics = research_metrics(control_events)
    variant_metrics = research_metrics(variant_events)
    failures = []
    if variant_metrics.rank_key() <= control_metrics.rank_key():
        failures.append("training_rank_not_superior")
    if control.horizon == "swing":
        if len(pairs) < 5:
            failures.append("matched_pairs_lt_5")
        if median_lead is None or median_lead < 1.0:
            failures.append("median_signal_lead_lt_1")
        if control_metrics.mean_mae_pct is None or variant_metrics.mean_mae_pct is None:
            failures.append("mae_unavailable")
        elif variant_metrics.mean_mae_pct > control_metrics.mean_mae_pct:
            failures.append("mae_worse")
        if variant_metrics.stop_loss_rate > control_metrics.stop_loss_rate:
            failures.append("stop_loss_rate_worse")
    elif control.horizon == "midterm":
        if variant_metrics.distinct_years < control_metrics.distinct_years:
            failures.append("distinct_years_fewer")
        if variant_metrics.absolute_pnl_concentration > control_metrics.absolute_pnl_concentration:
            failures.append("absolute_pnl_concentration_worse")
    if variant_metrics.maximum_drawdown_pct > control_metrics.maximum_drawdown_pct:
        failures.append("maximum_drawdown_worse")
    if (
        variant_metrics.positive_year_omission_count
        < control_metrics.positive_year_omission_count
    ):
        failures.append("positive_year_omission_count_fewer")
    accepted = not failures
    return ResearchEvaluation(
        control=control,
        variant=variant,
        control_training=control_metrics,
        variant_training=variant_metrics,
        control_test=research_metrics(control_test_events),
        variant_test=research_metrics(variant_test_events),
        matched_pairs=pairs,
        unmatched_control_count=len(control_events) - len(pairs),
        unmatched_variant_count=len(variant_events) - len(pairs),
        median_variant_signal_lead_bars=median_lead,
        training_accepted=accepted,
        acceptance_failures=tuple(failures),
        selected_definition_id=(
            variant.research_definition_id if accepted else control.research_definition_id
        ),
    )


def _select_treatment(
    definition: ResearchDefinition,
    no_theme_training: Sequence[TradeEvent],
    themed_training: Sequence[TradeEvent],
    no_theme_test: Sequence[TradeEvent],
    themed_test: Sequence[TradeEvent],
) -> tuple[str, tuple[TradeEvent, ...], tuple[TradeEvent, ...], tuple[ResearchTreatmentEvidence, ...]]:
    no_training = _validated_events(no_theme_training, "no-theme training")
    theme_training = _validated_events(themed_training, "themed training")
    no_test = _validated_events(no_theme_test, "no-theme test")
    theme_test = _validated_events(themed_test, "themed test")
    no_metrics = research_metrics(no_training)
    theme_metrics = research_metrics(theme_training)
    no_dsr = theme_dsr = None
    dsr_status = "unavailable"
    if (
        no_metrics.sharpe is not None
        and theme_metrics.sharpe is not None
        and isfinite(no_metrics.sharpe)
        and isfinite(theme_metrics.sharpe)
    ):
        trials = (no_metrics.sharpe, theme_metrics.sharpe)
        try:
            no_dsr = calculate_deflated_sharpe(
                tuple(float(event.return_pct) for event in no_training), trials
            )
            theme_dsr = calculate_deflated_sharpe(
                tuple(float(event.return_pct) for event in theme_training), trials
            )
        except ValueError:
            no_dsr = theme_dsr = None
        else:
            if isfinite(no_dsr) and isfinite(theme_dsr):
                dsr_status = "available"
            else:
                no_dsr = theme_dsr = None
    preferred = (
        "background-theme"
        if dsr_status == "available" and theme_dsr is not None and no_dsr is not None and theme_dsr > no_dsr
        else "no-background-theme"
    )
    evidence = (
        ResearchTreatmentEvidence(
            definition.research_definition_id,
            "no-background-theme",
            no_metrics,
            research_metrics(no_test),
            no_dsr,
            dsr_status,
            preferred == "no-background-theme",
        ),
        ResearchTreatmentEvidence(
            definition.research_definition_id,
            "background-theme",
            theme_metrics,
            research_metrics(theme_test),
            theme_dsr,
            dsr_status,
            preferred == "background-theme",
        ),
    )
    return (
        preferred,
        theme_training if preferred == "background-theme" else no_training,
        theme_test if preferred == "background-theme" else no_test,
        evidence,
    )


def evaluate_research_treatments(
    control: ResearchDefinition,
    variant: ResearchDefinition,
    control_no_theme_training: Sequence[TradeEvent],
    control_themed_training: Sequence[TradeEvent],
    variant_no_theme_training: Sequence[TradeEvent],
    variant_themed_training: Sequence[TradeEvent],
    native_dates: Sequence[date],
    *,
    control_no_theme_test: Sequence[TradeEvent] = (),
    control_themed_test: Sequence[TradeEvent] = (),
    variant_no_theme_test: Sequence[TradeEvent] = (),
    variant_themed_test: Sequence[TradeEvent] = (),
) -> ResearchEvaluation:
    """Choose each definition's treatment by training DSR, then compare training."""

    control_preferred, control_training, control_test, control_evidence = _select_treatment(
        control,
        control_no_theme_training,
        control_themed_training,
        control_no_theme_test,
        control_themed_test,
    )
    variant_preferred, variant_training, variant_test, variant_evidence = _select_treatment(
        variant,
        variant_no_theme_training,
        variant_themed_training,
        variant_no_theme_test,
        variant_themed_test,
    )
    evaluation = evaluate_research_pair(
        control,
        variant,
        control_training,
        variant_training,
        native_dates,
        control_test=control_test,
        variant_test=variant_test,
    )
    return replace(
        evaluation,
        control_preferred_treatment=control_preferred,
        variant_preferred_treatment=variant_preferred,
        treatments=(*control_evidence, *variant_evidence),
    )


__all__ = [
    "MIDTERM_CONTROL",
    "MIDTERM_VARIANT",
    "MatchedTradePair",
    "ResearchDefinition",
    "ResearchEvaluation",
    "ResearchMetrics",
    "ResearchTreatmentEvidence",
    "SWING_CONTROL",
    "SWING_VARIANT",
    "YearOmissionMetrics",
    "definition_entry_signal",
    "evaluate_research_pair",
    "evaluate_research_treatments",
    "leave_one_year_out",
    "pair_first_overlaps",
    "research_metrics",
]
