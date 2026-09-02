"""Immutable data contracts passed between backtest phases."""

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Optional

from .config import (
    HORIZONS,
    ENTRY_GATE_NAMES,
    THEME_MODES,
    THEME_VARIANTS,
    RulebookSpec,
    _normalize_ticker,
    rulebook_for,
)

JOB_STATES = ("queued", "running", "done", "failed", "requires_regeneration")
EXIT_REASONS = ("stop_loss", "take_profit", "timeout")


def _json_date(value: date | datetime) -> str:
    return value.isoformat()


@dataclass(frozen=True)
class RulebookExecution:
    """One immutable V3 rulebook/treatment identity for a new execution."""

    rulebook: RulebookSpec
    selected_gates: tuple[str, ...]
    theme_variant: str = "no-background-theme"
    theme_mode: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.rulebook, RulebookSpec):
            raise ValueError("rulebook must be a RulebookSpec")
        if self.rulebook != rulebook_for(self.rulebook.horizon):
            raise ValueError("rulebook execution requires a registered rulebook")
        selected_gates = tuple(self.selected_gates)
        if not selected_gates or any(gate not in ENTRY_GATE_NAMES for gate in selected_gates):
            raise ValueError("selected_gates must contain registered rulebook gates")
        if selected_gates != tuple(sorted(set(selected_gates))):
            raise ValueError("selected_gates must be unique lexical order")
        object.__setattr__(self, "selected_gates", selected_gates)
        if self.theme_variant not in THEME_VARIANTS:
            raise ValueError(f"theme_variant must be one of {THEME_VARIANTS}")
        if self.theme_variant == "background-theme" and self.theme_mode != "AND":
            raise ValueError("background-theme requires theme_mode AND")
        if self.theme_variant == "no-background-theme" and self.theme_mode is not None:
            raise ValueError("no-background-theme cannot define theme_mode")

    @property
    def rule_id(self) -> str:
        gate_names = {
            "rulebook_adx_gate": "adx",
            "rulebook_joint_trend_pass": "joint_trend",
            "rulebook_rsi_upcross": "rsi_upcross",
            "rulebook_volume_gate": "volume",
        }
        return f"{self.rulebook.rule_id}__{'__'.join(gate_names[gate] for gate in self.selected_gates)}"

    @property
    def horizon(self) -> str:
        return self.rulebook.horizon

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "horizon": self.horizon,
            "selected_gates": list(self.selected_gates),
            "theme_variant": self.theme_variant,
            "theme_mode": self.theme_mode,
        }


@dataclass(frozen=True)
class IndicatorCombo:
    """Legacy score-combination value retained until the Task 3 replacement."""

    indicators: tuple[tuple[str, tuple[str, ...]], ...]
    threshold_score_buy: int
    adx_gate_mode: str
    horizon: str
    theme_variant: str = "no-background-theme"
    theme_mode: Optional[str] = None
    direction: str = "long"

    def __post_init__(self) -> None:
        if not self.indicators:
            raise ValueError("indicators must contain at least one dimension")
        if self.adx_gate_mode not in ("soft", "hard"):
            raise ValueError("adx_gate_mode must be soft or hard")
        if not isinstance(self.threshold_score_buy, int) or self.threshold_score_buy < 1:
            raise ValueError("threshold_score_buy must be a positive integer")
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        if self.theme_variant not in THEME_VARIANTS:
            raise ValueError(f"theme_variant must be one of {THEME_VARIANTS}")
        if self.theme_mode not in (None, *THEME_MODES):
            raise ValueError(f"theme_mode must be one of {THEME_MODES}")
        if self.theme_variant == "background-theme" and self.theme_mode is None:
            raise ValueError("background-theme requires theme_mode AND or OR")
        if self.theme_variant == "no-background-theme" and self.theme_mode is not None:
            raise ValueError("no-background-theme cannot define theme_mode")
        if self.direction != "long":
            raise ValueError("Phase 1 supports long direction only")

        normalized = []
        for dimension, names in self.indicators:
            if not dimension or not names:
                raise ValueError("indicator dimensions and names must not be empty")
            normalized.append((dimension, tuple(names)))
        object.__setattr__(self, "indicators", tuple(normalized))

    def to_dict(self) -> dict[str, object]:
        return {
            "indicators": {dimension: list(names) for dimension, names in self.indicators},
            "threshold_score_buy": self.threshold_score_buy,
            "adx_gate_mode": self.adx_gate_mode,
            "horizon": self.horizon,
            "theme_variant": self.theme_variant,
            "theme_mode": self.theme_mode,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class TradeEvent:
    """A completed long trade generated by one signal crossing."""

    signal_date: date
    entry_date: date
    entry_price: int
    atr: int
    stop_loss: int
    take_profit: int
    exit_date: date
    exit_price: int
    exit_reason: str
    return_pct: float
    source_window: tuple[date, date]
    maximum_adverse_excursion_pct: float | None = None

    def __post_init__(self) -> None:
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("trade prices must be positive")
        if self.atr < 0:
            raise ValueError("atr must not be negative")
        if self.exit_reason not in EXIT_REASONS:
            raise ValueError(f"exit_reason must be one of {EXIT_REASONS}")
        if len(self.source_window) != 2:
            raise ValueError("source_window must contain start and end dates")
        if (
            self.maximum_adverse_excursion_pct is not None
            and (
                not isfinite(float(self.maximum_adverse_excursion_pct))
                or float(self.maximum_adverse_excursion_pct) < 0.0
            )
        ):
            raise ValueError("maximum adverse excursion must be finite and non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "signal_date": _json_date(self.signal_date),
            "entry_date": _json_date(self.entry_date),
            "entry_price": self.entry_price,
            "atr": self.atr,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "exit_date": _json_date(self.exit_date),
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "return_pct": self.return_pct,
            "source_window": [_json_date(value) for value in self.source_window],
            "maximum_adverse_excursion_pct": self.maximum_adverse_excursion_pct,
        }


@dataclass(frozen=True)
class BatchTickerStatus:
    """One immutable ticker outcome inside a sequential batch job."""

    ticker: str
    attempts: int
    state: str
    output_paths: tuple[str, ...] = ()
    error_texts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        if self.state not in JOB_STATES:
            raise ValueError(f"state must be one of {JOB_STATES}")
        if self.state == "queued":
            if self.attempts != 0:
                raise ValueError("queued ticker status must have zero attempts")
        elif self.attempts not in (1, 2):
            raise ValueError("non-queued ticker status must have one or two attempts")
        object.__setattr__(self, "output_paths", tuple(self.output_paths))
        error_texts = tuple(self.error_texts)
        if any(not isinstance(error, str) or not error for error in error_texts):
            raise ValueError("error_texts must contain non-empty strings")
        if self.state == "failed" and not error_texts:
            raise ValueError("failed ticker status must include an error")
        object.__setattr__(self, "error_texts", error_texts)

    def to_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "attempts": self.attempts,
            "state": self.state,
            "output_paths": list(self.output_paths),
            "error_texts": list(self.error_texts),
        }


@dataclass(frozen=True)
class JobStatus:
    """JSON-safe state returned by the offline job runner."""

    job_id: str
    state: str
    progress: float = 0.0
    output_paths: tuple[str, ...] = ()
    error_text: Optional[str] = None
    ticker_results: tuple[BatchTickerStatus, ...] = ()

    def __post_init__(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id must not be empty")
        if self.state not in JOB_STATES:
            raise ValueError(f"state must be one of {JOB_STATES}")
        if not 0 <= self.progress <= 1:
            raise ValueError("progress must be between 0 and 1")
        object.__setattr__(self, "output_paths", tuple(self.output_paths))
        ticker_results = tuple(self.ticker_results)
        if any(not isinstance(result, BatchTickerStatus) for result in ticker_results):
            raise ValueError("ticker_results must contain BatchTickerStatus values")
        object.__setattr__(self, "ticker_results", ticker_results)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 5,
            "job_id": self.job_id,
            "state": self.state,
            "progress": self.progress,
            "output_paths": list(self.output_paths),
            "error_text": self.error_text,
            "ticker_results": [result.to_dict() for result in self.ticker_results],
        }
