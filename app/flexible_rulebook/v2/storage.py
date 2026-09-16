"""Contained durable storage for the user-authored Flexible Rulebook v2."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping
from uuid import UUID

from .contracts import (
    AtrExitV2,
    EvaluationResult,
    PredicateV2,
    PublishedRulebook,
    RulebookDefinitionV2,
    RulebookDraft,
    canonical_json,
    collision_safe_short_ids,
)


_SCHEMA_VERSION = 2
_DRAFT_KIND = "flexible_rulebook_v2_draft"
_DEFINITION_KIND = "flexible_rulebook_v2_definition"
_EVALUATION_KIND = "flexible_rulebook_v2_evaluation"
_RETIREMENT_KIND = "flexible_rulebook_v2_retirement"
_UNRETIREMENT_KIND = "flexible_rulebook_v2_unretirement"
_RULEBOOK_PATTERN = re.compile(r"^frb2_[0-9a-f]{64}$")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
_EVALUATION_PATTERN = re.compile(r"^frev2_[0-9a-f]{64}$")


def resolve_v2_root() -> Path:
    """Return the separate v2 namespace beneath the existing Flexible root."""

    return (Path(__file__).resolve().parents[2] / "Flexible-Rulebook").resolve()


def _base(root: Path, *, create: bool) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible v2 storage root must be an absolute Path")
    base = root.resolve()
    if create:
        (base / "v2").mkdir(parents=True, exist_ok=True)
    return base


def _contained(base: Path, *parts: str) -> Path:
    path = (base.joinpath(*parts)).resolve()
    try:
        path.relative_to(base)
    except ValueError as error:
        raise ValueError("Flexible v2 path escapes storage root") from error
    return path


def _draft_id(value: object) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError("draft_id must be a UUID") from error


def _rulebook_id(value: object) -> str:
    if not isinstance(value, str) or not _RULEBOOK_PATTERN.fullmatch(value):
        raise ValueError("rulebook_id must be a full frb2_ SHA-256 identifier")
    return value


def _ticker(value: object) -> str:
    normalized = value.strip().upper() if isinstance(value, str) else ""
    if not _TICKER_PATTERN.fullmatch(normalized):
        raise ValueError("ticker must be a persistence-safe ticker")
    return normalized


def _load_document(path: Path, kind: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Flexible v2 document is unreadable") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != _SCHEMA_VERSION
        or payload.get("artifact_kind") != kind
    ):
        raise ValueError("Flexible v2 document has unsupported schema or kind")
    return payload


def _atomic_replace(path: Path, payload: Mapping[str, object]) -> Path:
    material = canonical_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _write_immutable(path: Path, payload: Mapping[str, object]) -> Path:
    material = canonical_json(payload)
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError("immutable Flexible v2 document is unreadable") from error
        if existing != material:
            raise ValueError("immutable Flexible v2 document already differs")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != material:
                raise ValueError("immutable Flexible v2 document already differs")
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _decode(value: object) -> object:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"$decimal"}:
        try:
            return Decimal(str(value["$decimal"]))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("Flexible v2 decimal is invalid") from error
    if set(value) == {"$datetime"}:
        try:
            return datetime.fromisoformat(str(value["$datetime"]))
        except ValueError as error:
            raise ValueError("Flexible v2 datetime is invalid") from error
    if set(value) == {"$date"}:
        try:
            return date.fromisoformat(str(value["$date"]))
        except ValueError as error:
            raise ValueError("Flexible v2 date is invalid") from error
    if set(value) == {"$uuid"}:
        return str(value["$uuid"])
    return {str(key): _decode(item) for key, item in value.items()}


def _mapping(value: object, name: str) -> dict[str, object]:
    decoded = _decode(value)
    if not isinstance(decoded, dict):
        raise ValueError(f"{name} must be a mapping")
    return decoded


def _predicate_from_document(value: object) -> PredicateV2:
    payload = _mapping(value, "predicate")
    return PredicateV2(
        role=payload.get("role"),
        family=payload.get("family"),
        family_revision=payload.get("family_revision"),
        settings=_mapping(payload.get("settings"), "predicate settings"),
        operator=payload.get("operator"),
        condition=_mapping(payload.get("condition"), "predicate condition"),
        direction_lookback=payload.get("direction_lookback"),
    )


def _definition_from_document(value: object) -> RulebookDefinitionV2:
    payload = _mapping(value, "definition")
    atr_raw = payload.get("atr_exit")
    atr_exit = None
    if atr_raw is not None:
        atr = _mapping(atr_raw, "ATR exit")
        atr_exit = AtrExitV2(
            period=atr.get("period"),
            formula_revision=atr.get("formula_revision"),
            stop_multiplier=atr.get("stop_multiplier"),
            target_multiplier=atr.get("target_multiplier"),
            trailing_multiplier=atr.get("trailing_multiplier"),
        )

    def predicates(key: str) -> tuple[PredicateV2, ...]:
        values = payload.get(key)
        if not isinstance(values, list):
            raise ValueError(f"definition {key} must be a list")
        return tuple(_predicate_from_document(item) for item in values)

    return RulebookDefinitionV2(
        horizon=payload.get("horizon"),
        entry_operator=payload.get("entry_operator"),
        buy_predicates=predicates("buy_predicates"),
        gates=predicates("gates"),
        technical_exits=predicates("technical_exits"),
        atr_exit=atr_exit,
        min_hold_bars=payload.get("min_hold_bars"),
        max_hold_bars=payload.get("max_hold_bars"),
        semantic_revision=payload.get("semantic_revision"),
    )


def definition_from_document(value: object) -> RulebookDefinitionV2:
    """Rehydrate one canonical Flexible definition without touching storage."""

    return _definition_from_document(value)


def _draft_payload(draft: RulebookDraft) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "artifact_kind": _DRAFT_KIND,
        "draft": {
            "draft_id": draft.draft_id,
            "revision": draft.revision,
            "name": draft.name,
            "description": draft.description,
            "definition": draft.definition.to_semantic_dict(),
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
            "state": draft.state,
        },
    }


def _evaluation_payload(rulebook_id: str, evaluation: EvaluationResult) -> dict[str, object]:
    if evaluation.semantic_digest != rulebook_id.removeprefix("frb2_"):
        raise ValueError("evaluation semantic digest must match the full rulebook ID")
    evidence = {
        "semantic_digest": evaluation.semantic_digest,
        "ticker": evaluation.ticker,
        "source": evaluation.source,
        "split": evaluation.split,
        "metrics": evaluation.metrics,
        "trades": list(evaluation.trades),
        "warnings": list(evaluation.warnings),
        "terminal_state": evaluation.terminal_state,
    }
    evaluation_id = "frev2_" + hashlib.sha256(
        canonical_json({"rulebook_id": rulebook_id, "evaluation": evidence}).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": _SCHEMA_VERSION,
        "artifact_kind": _EVALUATION_KIND,
        "evaluation_id": evaluation_id,
        "rulebook_id": rulebook_id,
        "evaluation": evidence,
    }


def evaluation_id_for(rulebook_id: str, evaluation: EvaluationResult) -> str:
    """Return the immutable v2 evidence identity without writing an artifact."""

    identifier = _rulebook_id(rulebook_id)
    if not isinstance(evaluation, EvaluationResult):
        raise ValueError("evaluation must be EvaluationResult")
    evaluation_id = _evaluation_payload(identifier, evaluation)["evaluation_id"]
    assert isinstance(evaluation_id, str)
    return evaluation_id


def write_draft(root: Path, draft: RulebookDraft, *, expected_revision: int) -> Path:
    """Atomically write a draft only when the caller still owns its revision."""

    if not isinstance(draft, RulebookDraft):
        raise ValueError("draft must be RulebookDraft")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise ValueError("expected_revision must be a non-negative integer")
    base = _base(root, create=True)
    path = _contained(base, "v2", "drafts", f"{draft.draft_id}.json")
    if path.exists():
        existing = read_draft(base, draft.draft_id)
        if existing.revision != expected_revision:
            raise ValueError("stale draft revision")
    elif expected_revision != 0:
        raise ValueError("stale draft revision")
    if draft.revision != expected_revision + 1:
        raise ValueError("draft revision must advance expected_revision by one")
    return _atomic_replace(path, _draft_payload(draft))


def read_draft(root: Path, draft_id: str) -> RulebookDraft:
    """Load one valid v2 draft without inspecting any legacy artifact."""

    identifier = _draft_id(draft_id)
    base = _base(root, create=False)
    path = _contained(base, "v2", "drafts", f"{identifier}.json")
    payload = _load_document(path, _DRAFT_KIND)
    draft = _mapping(payload.get("draft"), "draft")
    result = RulebookDraft(
        draft_id=draft.get("draft_id"),
        revision=draft.get("revision"),
        name=draft.get("name"),
        description=draft.get("description"),
        definition=_definition_from_document(draft.get("definition")),
        created_at=_decode(draft.get("created_at")),
        updated_at=_decode(draft.get("updated_at")),
        state=draft.get("state", "draft"),
    )
    if result.draft_id != identifier:
        raise ValueError("draft document identity is invalid")
    return result


def discard_draft(root: Path, draft_id: str, *, confirmed: bool) -> bool:
    """Delete only the mutable v2 draft after an explicit UI confirmation."""

    if confirmed is not True:
        raise ValueError("draft discard requires explicit confirmation")
    identifier = _draft_id(draft_id)
    base = _base(root, create=False)
    path = _contained(base, "v2", "drafts", f"{identifier}.json")
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def list_drafts(root: Path) -> tuple[RulebookDraft, ...]:
    """List trusted mutable v2 drafts without opening any legacy directory."""

    base = _base(root, create=False)
    directory = _contained(base, "v2", "drafts")
    if not directory.is_dir():
        return ()
    drafts: list[RulebookDraft] = []
    for path in directory.glob("*.json"):
        try:
            draft = read_draft(base, path.stem)
        except ValueError:
            continue
        drafts.append(draft)
    return tuple(sorted(drafts, key=lambda item: (item.name.casefold(), item.draft_id)))


def write_published_rulebook(root: Path, published: PublishedRulebook) -> Path:
    """Create-or-verify an immutable published definition document."""

    if not isinstance(published, PublishedRulebook):
        raise ValueError("published must be PublishedRulebook")
    base = _base(root, create=True)
    path = _contained(base, "v2", "definitions", f"{published.rulebook_id}.json")
    return _write_immutable(
        path,
        {
            "schema_version": _SCHEMA_VERSION,
            "artifact_kind": _DEFINITION_KIND,
            "rulebook_id": published.rulebook_id,
            "definition": published.definition.to_semantic_dict(),
            "published_at": published.published_at,
        },
    )


def _read_published(root: Path, rulebook_id: str) -> PublishedRulebook:
    identifier = _rulebook_id(rulebook_id)
    base = _base(root, create=False)
    path = _contained(base, "v2", "definitions", f"{identifier}.json")
    payload = _load_document(path, _DEFINITION_KIND)
    if payload.get("rulebook_id") != identifier:
        raise ValueError("published definition identity is invalid")
    return PublishedRulebook(
        rulebook_id=identifier,
        definition=_definition_from_document(payload.get("definition")),
        published_at=_decode(payload.get("published_at")),
    )


def retire_rulebook(root: Path, rulebook_id: str, *, retired_at: datetime) -> Path:
    """Record immutable retirement without changing the published definition."""

    identifier = _rulebook_id(rulebook_id)
    _read_published(root, identifier)
    base = _base(root, create=True)
    path = _contained(base, "v2", "retirements", f"{identifier}.json")
    return _write_immutable(
        path,
        {
            "schema_version": _SCHEMA_VERSION,
            "artifact_kind": _RETIREMENT_KIND,
            "rulebook_id": identifier,
            "retired_at": retired_at,
        },
    )


def unretire_rulebook(root: Path, rulebook_id: str, *, unretired_at: datetime) -> Path:
    """Record an immutable restoration event without rewriting prior evidence."""

    identifier = _rulebook_id(rulebook_id)
    base = _base(root, create=False)
    retired_at = _retirement_timestamp(base, identifier)
    if retired_at is None:
        raise ValueError("rulebook must be retired before it can be unretired")
    if not isinstance(unretired_at, datetime) or unretired_at.tzinfo is None or unretired_at.utcoffset() is None:
        raise ValueError("unretired_at must be timezone-aware")
    normalized = unretired_at.astimezone(retired_at.tzinfo)
    if normalized <= retired_at:
        raise ValueError("unretired_at must follow retired_at")
    path = _contained(base, "v2", "unretirements", f"{identifier}.json")
    return _write_immutable(
        path,
        {
            "schema_version": _SCHEMA_VERSION,
            "artifact_kind": _UNRETIREMENT_KIND,
            "rulebook_id": identifier,
            "unretired_at": normalized,
        },
    )


def _retirement_timestamp(root: Path, rulebook_id: str) -> datetime | None:
    base = _base(root, create=False)
    path = _contained(base, "v2", "retirements", f"{rulebook_id}.json")
    if not path.is_file():
        return None
    payload = _load_document(path, _RETIREMENT_KIND)
    if payload.get("rulebook_id") != rulebook_id:
        raise ValueError("retirement identity is invalid")
    retired_at = _decode(payload.get("retired_at"))
    if not isinstance(retired_at, datetime):
        raise ValueError("retirement timestamp is invalid")
    return retired_at


def _retired_at(root: Path, rulebook_id: str) -> datetime | None:
    base = _base(root, create=False)
    retired_at = _retirement_timestamp(base, rulebook_id)
    if retired_at is None:
        return None
    path = _contained(base, "v2", "unretirements", f"{rulebook_id}.json")
    if not path.is_file():
        return retired_at
    payload = _load_document(path, _UNRETIREMENT_KIND)
    if payload.get("rulebook_id") != rulebook_id:
        raise ValueError("unretirement identity is invalid")
    unretired_at = _decode(payload.get("unretired_at"))
    if not isinstance(unretired_at, datetime) or unretired_at <= retired_at:
        raise ValueError("unretirement timestamp is invalid")
    return None


def list_published_rulebooks(root: Path, *, include_retired: bool = True) -> tuple[PublishedRulebook, ...]:
    """Return valid immutable v2 definitions; corrupt records are not trusted."""

    if not isinstance(include_retired, bool):
        raise ValueError("include_retired must be boolean")
    base = _base(root, create=False)
    definitions = _contained(base, "v2", "definitions")
    if not definitions.is_dir():
        return ()
    result: list[PublishedRulebook] = []
    for path in sorted(definitions.glob("frb2_*.json")):
        try:
            published = _read_published(base, path.stem)
            retired_at = _retired_at(base, published.rulebook_id)
            if retired_at is not None:
                published = published.retire(retired_at=retired_at)
        except ValueError:
            continue
        if include_retired or not published.is_retired:
            result.append(published)
    return tuple(result)


def published_short_ids(root: Path, *, include_retired: bool = True) -> dict[str, str]:
    """Resolve display prefixes only from the durable published v2 library."""

    return collision_safe_short_ids(
        (item.rulebook_id for item in list_published_rulebooks(root, include_retired=include_retired))
    )


def write_evaluation(root: Path, rulebook_id: str, evaluation: EvaluationResult) -> Path:
    """Create-or-verify immutable per-ticker evidence beneath a full rulebook ID."""

    identifier = _rulebook_id(rulebook_id)
    if not isinstance(evaluation, EvaluationResult):
        raise ValueError("evaluation must be EvaluationResult")
    payload = _evaluation_payload(identifier, evaluation)
    evaluation_id = payload["evaluation_id"]
    assert isinstance(evaluation_id, str)
    base = _base(root, create=True)
    path = _contained(base, "v2", "evaluations", identifier, evaluation.ticker, f"{evaluation_id}.json")
    return _write_immutable(path, payload)


def read_evaluation(root: Path, path: Path) -> tuple[str, EvaluationResult]:
    """Read one valid immutable evaluation only from the v2 evaluation tree."""

    base = _base(root, create=False)
    resolved = path.resolve()
    evaluation_root = _contained(base, "v2", "evaluations")
    try:
        resolved.relative_to(evaluation_root)
    except ValueError as error:
        raise ValueError("evaluation path escapes v2 evaluation storage") from error
    payload = _load_document(resolved, _EVALUATION_KIND)
    identifier = _rulebook_id(payload.get("rulebook_id"))
    evaluation_id = payload.get("evaluation_id")
    if not isinstance(evaluation_id, str) or not _EVALUATION_PATTERN.fullmatch(evaluation_id):
        raise ValueError("evaluation identity is invalid")
    if resolved.stem != evaluation_id:
        raise ValueError("evaluation filename identity is invalid")
    evidence = _mapping(payload.get("evaluation"), "evaluation")
    result = EvaluationResult(
        semantic_digest=evidence.get("semantic_digest"),
        ticker=evidence.get("ticker"),
        source=_mapping(evidence.get("source"), "evaluation source"),
        split=_mapping(evidence.get("split"), "evaluation split"),
        metrics=_mapping(evidence.get("metrics"), "evaluation metrics"),
        trades=_decode(evidence.get("trades", [])),
        warnings=_decode(evidence.get("warnings", [])),
        terminal_state=evidence.get("terminal_state", "completed"),
    )
    if result.semantic_digest != identifier.removeprefix("frb2_"):
        raise ValueError("evaluation semantic digest is invalid")
    expected = _evaluation_payload(identifier, result)
    if (
        expected["evaluation_id"] != evaluation_id
        or canonical_json(payload) != canonical_json(expected)
    ):
        raise ValueError("evaluation document identity is invalid")
    return identifier, result


def list_evaluations(root: Path, rulebook_id: str) -> tuple[EvaluationResult, ...]:
    """Return trusted evidence for one definition, skipping corrupt documents."""

    identifier = _rulebook_id(rulebook_id)
    base = _base(root, create=False)
    evaluation_root = _contained(base, "v2", "evaluations", identifier)
    if not evaluation_root.is_dir():
        return ()
    results: list[EvaluationResult] = []
    for path in sorted(evaluation_root.glob("*/*.json")):
        try:
            stored_identifier, result = read_evaluation(base, path)
        except ValueError:
            continue
        if stored_identifier == identifier:
            results.append(result)
    return tuple(results)


__all__ = [
    "discard_draft",
    "evaluation_id_for",
    "definition_from_document",
    "list_drafts",
    "list_evaluations",
    "list_published_rulebooks",
    "published_short_ids",
    "read_draft",
    "read_evaluation",
    "resolve_v2_root",
    "retire_rulebook",
    "unretire_rulebook",
    "write_draft",
    "write_evaluation",
    "write_published_rulebook",
]
