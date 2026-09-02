"""Controlled schema-5 experiments isolated from canonical Backtest products."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Sequence

import pandas as pd

from .config import (
    BACKTEST_RESULT_DIR,
    DEFAULT_SIGNAL_DIR,
    BacktestConfig,
    _normalize_ticker,
    rulebook_for,
)
from .evidence import assess_evidence
from .exploratory import EvaluationSplit, execute_partition, split_native_frame
from .models import RulebookExecution, TradeEvent
from .persistence import load_rulebook_result, signal_artifact_path
from .pipeline import (
    _build_confirmation_frame,
    _load_validated_history,
    _prepare_ticker,
    _theme_signal,
)
from .research import (
    MIDTERM_CONTROL,
    MIDTERM_VARIANT,
    SWING_CONTROL,
    SWING_VARIANT,
    ResearchDefinition,
    ResearchEvaluation,
    definition_entry_signal,
    evaluate_research_treatments,
)
from .timeframes import latest_common_completed_bar


BASELINE_VERIFICATION_SHA256 = "fc55e501084744d148098d3be3250488192e9dea51d0e332ead3a276f7d8ca9c"
RESEARCH_CONTRACT_VERSION = "backtest_research_schema5_v1"
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class ResearchPrerequisiteError(RuntimeError):
    """The experiment was not run because frozen prerequisite evidence failed."""


@dataclass(frozen=True)
class ResearchRequest:
    """Explicit bounded scope for one controlled, non-product experiment."""

    ticker: str
    horizon: str
    start_date: date
    end_date: date
    permutation_count: int
    permutation_seed: int
    permutation_block_size: int
    output_dir: str
    persist: bool = False
    baseline_verification_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        rulebook_for(self.horizon)
        if not isinstance(self.start_date, date) or not isinstance(self.end_date, date):
            raise ValueError("start_date and end_date must be dates")
        if self.start_date > self.end_date:
            raise ValueError("start_date must not exceed end_date")
        if self.permutation_count < 1 or self.permutation_block_size < 1:
            raise ValueError("permutation settings must be positive")
        if not isinstance(self.permutation_seed, int):
            raise ValueError("permutation_seed must be an integer")
        if not isinstance(self.output_dir, str) or not self.output_dir.strip():
            raise ValueError("output_dir must be explicit non-empty text")
        object.__setattr__(self, "output_dir", self.output_dir.strip())
        if self.baseline_verification_sha256 is not None:
            normalized = str(self.baseline_verification_sha256).strip().lower()
            if not _SHA256_PATTERN.fullmatch(normalized):
                raise ValueError("baseline_verification_sha256 must be a SHA-256 digest")
            object.__setattr__(self, "baseline_verification_sha256", normalized)

    def to_identity_dict(self) -> dict[str, object]:
        return {
            "request_type": "backtest_research_v5",
            "ticker": self.ticker,
            "horizon": self.horizon,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "permutation_count": self.permutation_count,
            "permutation_seed": self.permutation_seed,
            "permutation_block_size": self.permutation_block_size,
            "baseline_verification_sha256": self.baseline_verification_sha256,
        }

    @property
    def request_id(self) -> str:
        return "btrq_" + sha256(_canonical_bytes(self.to_identity_dict())).hexdigest()


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _safe_output_directory(value: str) -> Path:
    output = Path(value).resolve()
    canonical_root = Path(BACKTEST_RESULT_DIR).resolve()
    if output == canonical_root or canonical_root in output.parents:
        raise ValueError("research output cannot use the canonical Backtest result tree")
    return output


def _write_immutable(payload: dict[str, object], output_dir: Path) -> Path:
    """Atomically create one content-addressed file without overwriting evidence."""

    serialized = _canonical_bytes(payload)
    artifact_id = "btre_" + sha256(serialized).hexdigest()
    target = output_dir / f"{artifact_id}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{artifact_id}.",
            suffix=".tmp",
            dir=output_dir,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, target)
        except FileExistsError:
            if target.read_bytes() != serialized:
                raise RuntimeError("immutable research artifact identity collision")
        return target
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _not_run_document(request: ResearchRequest, reason: str) -> dict[str, object]:
    return {
        "schema_version": 5,
        "contract_version": RESEARCH_CONTRACT_VERSION,
        "terminal_state": "not_run",
        "promotion_status": "research_only",
        "evaluation_label": "Exploratory — gross",
        "partition_labels": {
            "training": "in-sample",
            "test": "historical test — previously observed",
        },
        "request_id": request.request_id,
        "request": request.to_identity_dict(),
        "prerequisite_failure": reason,
    }


def _stop_not_run(
    request: ResearchRequest,
    output_dir: Path,
    reason: str,
) -> None:
    if request.persist:
        _write_immutable(_not_run_document(request, reason), output_dir)
    raise ResearchPrerequisiteError(reason)


def _definitions(horizon: str) -> tuple[ResearchDefinition, ResearchDefinition]:
    return (
        (SWING_CONTROL, SWING_VARIANT)
        if horizon == "swing"
        else (MIDTERM_CONTROL, MIDTERM_VARIANT)
    )


def _with_bar_level_mae(
    frame: pd.DataFrame,
    events: Sequence[TradeEvent],
) -> tuple[TradeEvent, ...]:
    """Attach conservative daily-bar MAE using lows through the completed exit bar."""

    dates = pd.to_datetime(frame["date"], errors="coerce")
    lows = pd.to_numeric(frame["low"], errors="coerce")
    enriched = []
    for event in events:
        mask = dates.ge(pd.Timestamp(event.entry_date)) & dates.le(pd.Timestamp(event.exit_date))
        observed_lows = lows.loc[mask]
        if observed_lows.empty or observed_lows.isna().any():
            raise ValueError("MAE requires every native low from entry through exit")
        entry_price = float(event.entry_price)
        mae = max(0.0, (entry_price - float(observed_lows.min())) / entry_price * 100.0)
        enriched.append(replace(event, maximum_adverse_excursion_pct=mae))
    return tuple(enriched)


def _execute_events(
    frame: pd.DataFrame,
    execution: RulebookExecution,
    entries: pd.Series,
    *,
    start: date,
    end: date,
) -> tuple[TradeEvent, ...]:
    return _with_bar_level_mae(
        frame,
        execute_partition(frame, execution, entries, start=start, end=end),
    )


def _validate_midterm_prerequisite(
    request: ResearchRequest,
    frame: pd.DataFrame,
    confirmation: pd.DataFrame,
    evidence: dict[str, object],
    common_as_of: date,
) -> None:
    """Require the frozen report, current canonical baseline, and shared W-FRI labels."""

    if request.baseline_verification_sha256 != BASELINE_VERIFICATION_SHA256:
        raise ResearchPrerequisiteError("Mid-term baseline verification hash is not approved")
    ticker_dates = pd.DatetimeIndex(pd.to_datetime(frame["date"], errors="coerce"))
    theme_dates = pd.DatetimeIndex(pd.to_datetime(confirmation["date"], errors="coerce"))
    if (
        ticker_dates.hasnans
        or theme_dates.hasnans
        or any(value.weekday() != 4 for value in ticker_dates)
        or any(value.weekday() != 4 for value in theme_dates)
        or not set(ticker_dates).issubset(set(theme_dates))
    ):
        raise ResearchPrerequisiteError("Mid-term ticker/theme W-FRI date identity failed")
    path = signal_artifact_path(request.ticker, "midterm", DEFAULT_SIGNAL_DIR)
    try:
        baseline = load_rulebook_result(path)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
        raise ResearchPrerequisiteError("current schema-5 Mid-term baseline is unavailable") from error
    baseline_evidence = baseline.get("evidence_eligibility")
    if (
        baseline.get("schema_version") != 5
        or baseline.get("terminal_state") != "success"
        or baseline.get("ticker") != request.ticker
        or baseline.get("horizon") != "midterm"
        or not isinstance(baseline_evidence, dict)
        or baseline_evidence.get("common_as_of") != common_as_of.isoformat()
        or baseline_evidence.get("ticker_fingerprint") != evidence.get("ticker_fingerprint")
        or baseline_evidence.get("vnindex_fingerprint") != evidence.get("vnindex_fingerprint")
    ):
        raise ResearchPrerequisiteError("current schema-5 Mid-term baseline identity changed")


def _complete_document(
    request: ResearchRequest,
    common_as_of: date,
    evidence: dict[str, object],
    audit_status: str,
    split: EvaluationSplit,
    evaluation: ResearchEvaluation,
    selection_fingerprint: str,
) -> dict[str, object]:
    return {
        "schema_version": 5,
        "contract_version": RESEARCH_CONTRACT_VERSION,
        "terminal_state": "complete",
        "promotion_status": "research_only",
        "evaluation_label": "Exploratory — gross",
        "partition_labels": {
            "training": "in-sample",
            "test": "historical test — previously observed",
        },
        "request_id": request.request_id,
        "request": request.to_identity_dict(),
        "common_as_of": common_as_of.isoformat(),
        "audit_status": audit_status,
        "evidence_eligibility": evidence,
        "baseline_verification_sha256": request.baseline_verification_sha256,
        "split": split.to_dict(),
        "definitions": [evaluation.control.to_dict(), evaluation.variant.to_dict()],
        "selection_frozen_before_test_sha256": selection_fingerprint,
        "evaluation": evaluation.to_dict(),
    }


def run_controlled_experiment(
    request: ResearchRequest,
    engine,
) -> ResearchEvaluation:
    """Run one approved experiment without reading test until training is frozen."""

    if not isinstance(request, ResearchRequest):
        raise ValueError("request must be a ResearchRequest")
    output_dir = _safe_output_directory(request.output_dir)
    if (
        request.horizon == "midterm"
        and request.baseline_verification_sha256 != BASELINE_VERIFICATION_SHA256
    ):
        _stop_not_run(
            request,
            output_dir,
            "Mid-term baseline verification hash is not approved",
        )

    config = BacktestConfig(
        ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        horizon=request.horizon,
        permutation_count=request.permutation_count,
        permutation_seed=request.permutation_seed,
        permutation_block_size=request.permutation_block_size,
    )
    ticker_source = _load_validated_history(request.ticker, config, engine)
    vnindex_source = _load_validated_history("VNINDEX", config, engine)
    common_as_of = latest_common_completed_bar(
        {request.ticker: ticker_source, "VNINDEX": vnindex_source},
        request.end_date,
    )
    frame, audit, ticker_history = _prepare_ticker(
        request.ticker,
        config,
        engine,
        common_as_of=common_as_of,
        raw_history=ticker_source,
    )
    evidence_value = assess_evidence(
        ticker_history,
        vnindex_source,
        common_as_of,
        ticker=request.ticker,
        audit_eligible=audit.status == "clean",
    )
    evidence = evidence_value.to_dict()
    if not evidence_value.eligible:
        _stop_not_run(
            request,
            output_dir,
            "source evidence is ineligible: " + ", ".join(evidence.get("reasons", ())),
        )
    confirmation = _build_confirmation_frame(
        vnindex_source,
        request.horizon,
        common_as_of=common_as_of,
    )
    if request.horizon == "midterm":
        try:
            _validate_midterm_prerequisite(
                request,
                frame,
                confirmation,
                evidence,
                common_as_of,
            )
        except ResearchPrerequisiteError as error:
            _stop_not_run(request, output_dir, str(error))

    split = split_native_frame(
        frame,
        requested_start=request.start_date,
        requested_end=request.end_date,
    )
    control, variant = _definitions(request.horizon)
    theme = _theme_signal(frame, confirmation)
    control_no_theme = definition_entry_signal(frame, control)
    control_themed = control_no_theme & theme
    variant_no_theme = definition_entry_signal(frame, variant)
    variant_themed = variant_no_theme & theme
    execution = RulebookExecution(
        rulebook_for(request.horizon),
        ("rulebook_rsi_upcross",),
    )

    # Finish every training execution and freeze selection before test execution.
    training = (
        _execute_events(frame, execution, control_no_theme, start=split.train_start, end=split.train_end),
        _execute_events(frame, execution, control_themed, start=split.train_start, end=split.train_end),
        _execute_events(frame, execution, variant_no_theme, start=split.train_start, end=split.train_end),
        _execute_events(frame, execution, variant_themed, start=split.train_start, end=split.train_end),
    )
    native_dates = tuple(pd.to_datetime(frame["date"]).dt.date)
    training_evaluation = evaluate_research_treatments(
        control,
        variant,
        *training,
        native_dates,
    )
    frozen_selection = training_evaluation.selection_to_dict()
    selection_fingerprint = sha256(_canonical_bytes(frozen_selection)).hexdigest()

    historical_test = (
        _execute_events(frame, execution, control_no_theme, start=split.test_start, end=split.test_end),
        _execute_events(frame, execution, control_themed, start=split.test_start, end=split.test_end),
        _execute_events(frame, execution, variant_no_theme, start=split.test_start, end=split.test_end),
        _execute_events(frame, execution, variant_themed, start=split.test_start, end=split.test_end),
    )
    evaluation = evaluate_research_treatments(
        control,
        variant,
        *training,
        native_dates,
        control_no_theme_test=historical_test[0],
        control_themed_test=historical_test[1],
        variant_no_theme_test=historical_test[2],
        variant_themed_test=historical_test[3],
    )
    if evaluation.selection_to_dict() != frozen_selection:
        raise RuntimeError("historical test changed the frozen training selection")
    if request.persist:
        _write_immutable(
            _complete_document(
                request,
                common_as_of,
                evidence,
                audit.status,
                split,
                evaluation,
                selection_fingerprint,
            ),
            output_dir,
        )
    return evaluation


__all__ = [
    "BASELINE_VERIFICATION_SHA256",
    "RESEARCH_CONTRACT_VERSION",
    "ResearchPrerequisiteError",
    "ResearchRequest",
    "run_controlled_experiment",
]
