"""Strict bridge from published Flexible v2 evidence to Backtest artifacts.

Flexible evidence is intentionally stored in a sibling root and uses its own
schema.  Standard schema-5 files therefore remain unmodified and cannot be
mistaken for Flexible output by the existing Backtest readers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable

import pytz

from flexible_rulebook.v2.contracts import (
    EvaluationResult,
    PublishedRulebook,
    canonical_json,
    semantic_digest as rulebook_semantic_digest,
)
from flexible_rulebook.v2.service import PublishedCollectionItem, evaluate_published_collection
from flexible_rulebook.v2.service import inspect_current_definition
from flexible_rulebook.v2.storage import (
    definition_from_document,
    evaluation_id_for,
    resolve_v2_root,
)

from .config import HORIZONS, _normalize_ticker


_SCHEMA_VERSION = 1
_ARTIFACT_KIND = "flexible_rulebook_signal_v1"
_MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")
_RULEBOOK_ID = re.compile(r"^frb2_[0-9a-f]{64}$")
_EVALUATION_ID = re.compile(r"^frev2_[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_EVENT_FIELDS = {"signal_date", "signal_bar_ordinal"}


@dataclass(frozen=True)
class FlexibleCollectionOutcome:
    """One published rulebook/ticker collection terminal result."""

    rulebook_id: str
    ticker: str
    terminal_state: str
    artifact_path: Path | None = None
    message: str = ""


def flexible_signal_artifact_root(signal_dir: str | Path) -> Path:
    """Keep Flexible files outside the Standard ticker namespace."""

    root = Path(signal_dir).expanduser()
    if not root.name:
        raise ValueError("signal_dir must name a result directory")
    return root.parent / f"{root.name}-flexible"


def flexible_signal_artifact_path(
    ticker: str,
    horizon: str,
    rulebook_id: str,
    signal_dir: str | Path,
) -> Path:
    """Return the isolated current artifact path for one Flexible ticker/horizon."""

    normalized = _normalize_ticker(ticker)
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    if not isinstance(rulebook_id, str) or not _RULEBOOK_ID.fullmatch(rulebook_id):
        raise ValueError("rulebook_id must be a full frb2_ SHA-256 identifier")
    return flexible_signal_artifact_root(signal_dir) / normalized / (
        f"{normalized}_flexible_signals_{horizon}__{rulebook_id.removeprefix('frb2_')}.json"
    )


def _json_safe(value: Any) -> Any:
    """Convert v2 immutable evidence to strict JSON without losing Decimal identity."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        # Match v2 persistence exactly: bare JSON numbers would lose the
        # immutable definition/evaluation scalar type and can change its hash.
        return json.loads(canonical_json(value))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    return value


def _require_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _normalized_events(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for event in events:
        if not isinstance(event, Mapping) or set(event) != _EVENT_FIELDS:
            raise ValueError("current_signal_events require signal_date and signal_bar_ordinal")
        raw_date = event["signal_date"]
        if isinstance(raw_date, datetime):
            signal_date = raw_date.date()
        elif type(raw_date) is date:
            signal_date = raw_date
        elif isinstance(raw_date, str):
            try:
                signal_date = date.fromisoformat(raw_date)
            except ValueError as error:
                raise ValueError("current_signal_events signal_date must be an ISO date") from error
        else:
            raise ValueError("current_signal_events signal_date must be an ISO date")
        ordinal = event["signal_bar_ordinal"]
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise ValueError("current_signal_events signal_bar_ordinal must be non-negative")
        normalized.append({"signal_date": signal_date.isoformat(), "signal_bar_ordinal": ordinal})
    return normalized


def build_flexible_signal_artifact(
    published: PublishedRulebook,
    evaluation: EvaluationResult,
    *,
    evaluation_id: str,
    current_signal_events: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build one validated Flexible artifact without using Standard schema-5."""

    if not isinstance(published, PublishedRulebook):
        raise ValueError("published must be PublishedRulebook")
    if not isinstance(evaluation, EvaluationResult) or not evaluation.is_completed:
        raise ValueError("evaluation must be a completed EvaluationResult")
    if evaluation.semantic_digest != published.definition.semantic_digest:
        raise ValueError("evaluation semantic digest must match the published rulebook")
    if not isinstance(evaluation_id, str) or not _EVALUATION_ID.fullmatch(evaluation_id):
        raise ValueError("evaluation_id must be a full frev2_ SHA-256 identifier")
    expected_evaluation_id = evaluation_id_for(published.rulebook_id, evaluation)
    if evaluation_id != expected_evaluation_id:
        raise ValueError("evaluation_id does not match the supplied evaluation evidence")

    source = _json_safe(evaluation.source)
    if not isinstance(source, dict):  # EvaluationResult guarantees a mapping; keep artifact defensive.
        raise ValueError("evaluation source must be a mapping")
    source_fingerprint = _require_digest(source.get("source_fingerprint"), "source_fingerprint")
    calendar_fingerprint = _require_digest(source.get("calendar_fingerprint"), "calendar_fingerprint")
    snapshot_fingerprint = _require_digest(source.get("snapshot_fingerprint"), "snapshot_fingerprint")

    return {
        "schema_version": _SCHEMA_VERSION,
        "artifact_kind": _ARTIFACT_KIND,
        "terminal_state": "success",
        "removal_reason": None,
        "ticker": evaluation.ticker,
        "horizon": published.definition.horizon,
        "evaluation_label": "Exploratory — gross",
        "rulebook_id": published.rulebook_id,
        "semantic_digest": published.definition.semantic_digest,
        "rulebook_definition": _json_safe(published.definition.to_semantic_dict()),
        "evaluation_reference": {
            "evaluation_id": evaluation_id,
            "source_fingerprint": source_fingerprint,
            "calendar_fingerprint": calendar_fingerprint,
            "snapshot_fingerprint": snapshot_fingerprint,
        },
        "evaluation": {
            "source": source,
            "split": _json_safe(evaluation.split),
            "metrics": _json_safe(evaluation.metrics),
            "trades": _json_safe(evaluation.trades),
            "warnings": list(evaluation.warnings),
            "terminal_state": evaluation.terminal_state,
        },
        "current_signal_events": _normalized_events(current_signal_events),
        "evaluated_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
    }


def _validate_artifact(payload: object) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("Flexible signal artifact must be an object")
    expected_fields = {
        "schema_version",
        "artifact_kind",
        "terminal_state",
        "removal_reason",
        "ticker",
        "horizon",
        "evaluation_label",
        "rulebook_id",
        "semantic_digest",
        "rulebook_definition",
        "evaluation_reference",
        "evaluation",
        "current_signal_events",
        "evaluated_at",
    }
    if set(payload) != expected_fields:
        raise ValueError("Flexible signal artifact has an invalid schema")
    if payload.get("schema_version") != _SCHEMA_VERSION or payload.get("artifact_kind") != _ARTIFACT_KIND:
        raise ValueError("Flexible signal artifact has unsupported schema or kind")
    terminal_state = payload.get("terminal_state")
    if terminal_state not in {"success", "empty"}:
        raise ValueError("Flexible signal artifact terminal state is invalid")
    removal_reason = payload.get("removal_reason")
    if terminal_state == "success" and removal_reason is not None:
        raise ValueError("Flexible success artifact cannot have a removal reason")
    if terminal_state == "empty" and (
        not isinstance(removal_reason, str) or not removal_reason.strip()
    ):
        raise ValueError("Flexible empty artifact requires a removal reason")
    ticker = _normalize_ticker(payload.get("ticker"))
    if ticker != payload.get("ticker"):
        raise ValueError("Flexible signal artifact ticker must be normalized")
    horizon = payload.get("horizon")
    if horizon not in HORIZONS:
        raise ValueError("Flexible signal artifact horizon is invalid")
    if payload.get("evaluation_label") != "Exploratory — gross":
        raise ValueError("Flexible signal artifact label is invalid")
    rulebook_id = payload.get("rulebook_id")
    if not isinstance(rulebook_id, str) or not _RULEBOOK_ID.fullmatch(rulebook_id):
        raise ValueError("Flexible signal artifact rulebook_id is invalid")
    semantic_digest_value = _require_digest(payload.get("semantic_digest"), "semantic_digest")
    if rulebook_id.removeprefix("frb2_") != semantic_digest_value:
        raise ValueError("Flexible signal artifact rulebook identity is inconsistent")
    reference = payload.get("evaluation_reference")
    if not isinstance(reference, Mapping) or set(reference) != {
        "evaluation_id", "source_fingerprint", "calendar_fingerprint", "snapshot_fingerprint"
    }:
        raise ValueError("Flexible signal artifact evaluation reference is invalid")
    evaluation_id = reference.get("evaluation_id")
    if not isinstance(evaluation_id, str) or not _EVALUATION_ID.fullmatch(evaluation_id):
        raise ValueError("Flexible signal artifact evaluation_id is invalid")
    for field in ("source_fingerprint", "calendar_fingerprint", "snapshot_fingerprint"):
        _require_digest(reference.get(field), field)
    evaluation = payload.get("evaluation")
    if not isinstance(evaluation, Mapping) or set(evaluation) != {
        "source", "split", "metrics", "trades", "warnings", "terminal_state"
    }:
        raise ValueError("Flexible signal artifact evaluation is invalid")
    if evaluation.get("terminal_state") != "completed" or not isinstance(evaluation.get("source"), Mapping):
        raise ValueError("Flexible signal artifact requires completed evaluation evidence")
    source = evaluation["source"]
    for field in ("source_fingerprint", "calendar_fingerprint", "snapshot_fingerprint"):
        if source.get(field) != reference[field]:
            raise ValueError("Flexible signal artifact source fingerprint is inconsistent")
    definition = payload.get("rulebook_definition")
    if not isinstance(definition, Mapping) or definition.get("horizon") != horizon:
        raise ValueError("Flexible signal artifact definition is invalid")
    if rulebook_semantic_digest(definition) != semantic_digest_value:
        raise ValueError("Flexible signal artifact definition identity is inconsistent")
    events = payload.get("current_signal_events")
    if not isinstance(events, list):
        raise ValueError("Flexible signal artifact current_signal_events must be a list")
    _normalized_events(events)
    if terminal_state == "empty" and events:
        raise ValueError("Flexible empty artifact cannot retain current signal events")
    if not isinstance(payload.get("evaluated_at"), str):
        raise ValueError("Flexible signal artifact evaluated_at is invalid")
    try:
        datetime.fromisoformat(payload["evaluated_at"])
    except ValueError as error:
        raise ValueError("Flexible signal artifact evaluated_at is invalid") from error
    return dict(payload)


def _write_json_atomically(path: Path, payload: Mapping[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    return path


def validate_flexible_signal_artifact(artifact: Mapping[str, object]) -> dict[str, object]:
    """Validate an in-memory Flexible artifact without changing the filesystem."""

    return _validate_artifact(artifact)


def write_flexible_signal_artifact(artifact: Mapping[str, object], signal_dir: str | Path) -> Path:
    """Atomically replace one current Flexible artifact in its isolated namespace."""

    payload = validate_flexible_signal_artifact(artifact)
    path = flexible_signal_artifact_path(
        str(payload["ticker"]),
        str(payload["horizon"]),
        str(payload["rulebook_id"]),
        signal_dir,
    )
    return _write_json_atomically(path, payload)


def replace_flexible_signal_artifact(
    artifact: Mapping[str, object], signal_dir: str | Path
) -> Path:
    """Atomically replace one validated Flexible artifact after a local edit."""

    return write_flexible_signal_artifact(artifact, signal_dir)


def load_flexible_signal_artifact(path: str | Path) -> dict[str, object]:
    """Read exactly one validated Flexible signal artifact."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Flexible signal artifact is unreadable") from error
    return _validate_artifact(payload)


def _artifact_date(value: object, field: str) -> date | None:
    if value is None:
        return None
    if type(value) is date:
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"Flexible artifact {field} is invalid") from error
    raise ValueError(f"Flexible artifact {field} is invalid")


def replay_flexible_signal_artifact(
    artifact: Mapping[str, object],
    *,
    engine: object,
) -> dict[str, object]:
    """Recompute current Flexible support facts only when frozen source matches.

    Validation is read-only: it never writes an evaluation, cache component, or
    artifact.  A changed source must be recollected before current advice can
    be trusted.
    """

    payload = validate_flexible_signal_artifact(artifact)
    if payload["terminal_state"] != "success":
        raise ValueError("No current Flexible exploratory rulebook exists.")
    definition = definition_from_document(payload["rulebook_definition"])
    source = payload["evaluation"]["source"]
    assert isinstance(source, Mapping)
    inspection = inspect_current_definition(
        definition,
        str(payload["ticker"]),
        start_date=_artifact_date(source.get("requested_start"), "requested_start"),
        end_date=_artifact_date(source.get("requested_end"), "requested_end"),
        engine=engine,
    )
    reference = payload["evaluation_reference"]
    assert isinstance(reference, Mapping)
    for field in ("source_fingerprint", "calendar_fingerprint", "snapshot_fingerprint"):
        if inspection.source.get(field) != reference.get(field):
            raise ValueError("source_history_changed")
    return {
        "artifact": payload,
        "definition": definition,
        "inspection": inspection,
    }


def collect_published_flexible_signals(
    published_rulebooks: Sequence[PublishedRulebook],
    *,
    tickers: Sequence[str],
    signal_dir: str | Path,
    v2_root: Path | None = None,
    training_ratio: float = 0.65,
    start_date: date | None = None,
    end_date: date | None = None,
    use_cache: bool = True,
    engine: object | None = None,
    collection_fn: Callable = evaluate_published_collection,
) -> tuple[FlexibleCollectionOutcome, ...]:
    """Evaluate active published rules and persist only their distinct artifacts.

    The v2 service loads each ticker source once per request.  This adapter
    deliberately writes no Standard result or job document.
    """

    root = resolve_v2_root() if v2_root is None else Path(v2_root)
    if not root.is_absolute():
        raise ValueError("v2_root must be an absolute Path")
    items = collection_fn(
        published_rulebooks,
        tickers=tickers,
        root=root,
        training_ratio=training_ratio,
        start_date=start_date,
        end_date=end_date,
        use_cache=use_cache,
        engine=engine,
    )
    outcomes: list[FlexibleCollectionOutcome] = []
    for item in items:
        if not isinstance(item, PublishedCollectionItem):
            raise ValueError("Flexible collection returned an invalid item")
        if item.terminal_state != "completed":
            outcomes.append(FlexibleCollectionOutcome(
                rulebook_id=item.rulebook_id,
                ticker=item.ticker,
                terminal_state=item.terminal_state,
                message=item.message,
            ))
            continue
        assert item.evaluation is not None
        matching = next((rulebook for rulebook in published_rulebooks if rulebook.rulebook_id == item.rulebook_id), None)
        if matching is None:
            raise ValueError("Flexible collection returned an unrequested rulebook")
        artifact = build_flexible_signal_artifact(
            matching,
            item.evaluation,
            evaluation_id=evaluation_id_for(matching.rulebook_id, item.evaluation),
            current_signal_events=item.current_signal_events,
        )
        path = write_flexible_signal_artifact(artifact, signal_dir)
        outcomes.append(FlexibleCollectionOutcome(
            rulebook_id=item.rulebook_id,
            ticker=item.ticker,
            terminal_state="completed",
            artifact_path=path,
        ))
    return tuple(outcomes)


__all__ = [
    "build_flexible_signal_artifact",
    "collect_published_flexible_signals",
    "FlexibleCollectionOutcome",
    "flexible_signal_artifact_root",
    "flexible_signal_artifact_path",
    "load_flexible_signal_artifact",
    "replay_flexible_signal_artifact",
    "replace_flexible_signal_artifact",
    "validate_flexible_signal_artifact",
    "write_flexible_signal_artifact",
]
