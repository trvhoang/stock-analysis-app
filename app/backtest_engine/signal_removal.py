"""Crash-safe removal of selected schema-5 exploratory candidates."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_SIGNAL_DIR, HORIZONS, _normalize_ticker
from .persistence import (
    _candidate_rank,
    _write_json_atomically,
    load_rulebook_result,
    replace_validated_rulebook_result,
    signal_artifact_path,
    validate_rulebook_document,
)
from .position_overview import load_all_positions


_JOURNAL_FILENAME = ".backtest-signal-removal-transaction.json"
_JOURNAL_SCHEMA_VERSION = 1
_JOURNAL_OPERATION = "backtest_signal_removal"
_FINAL_REMOVAL_REASON = "All saved candidates were removed by user."


@dataclass(frozen=True, order=True)
class SignalCandidateKey:
    """One immutable schema-5 candidate identity."""

    ticker: str
    horizon: str
    rulebook_id: str


@dataclass(frozen=True)
class SignalRemovalResult:
    """Immutable report of the candidates removed by one completed request."""

    removed: tuple[SignalCandidateKey, ...]


class SignalRemovalBlockedError(ValueError):
    """Raised before writes when historical positions reference a selection."""

    def __init__(self, protected: Iterable[SignalCandidateKey]):
        self.protected = tuple(sorted(set(protected)))
        formatted = ", ".join(
            f"{item.ticker} / {item.horizon} / {item.rulebook_id}"
            for item in self.protected
        )
        super().__init__(f"saved positions reference selected signal candidates: {formatted}")


def _candidate_key(value: SignalCandidateKey | Mapping[str, object]) -> SignalCandidateKey:
    if isinstance(value, SignalCandidateKey):
        value = {
            "ticker": value.ticker,
            "horizon": value.horizon,
            "rulebook_id": value.rulebook_id,
        }
    if not isinstance(value, Mapping) or set(value) != {"ticker", "horizon", "rulebook_id"}:
        raise ValueError("signal candidate selection is invalid")
    ticker = _normalize_ticker(value["ticker"])
    horizon = value["horizon"]
    rulebook_id = value["rulebook_id"]
    if horizon not in HORIZONS or not isinstance(rulebook_id, str) or not rulebook_id:
        raise ValueError("signal candidate selection is invalid")
    return SignalCandidateKey(ticker, horizon, rulebook_id)


def _normalized_selections(
    selections: Iterable[SignalCandidateKey | Mapping[str, object]],
) -> tuple[SignalCandidateKey, ...]:
    if isinstance(selections, (str, bytes)):
        raise ValueError("signal candidate selections must be an iterable")
    try:
        normalized = tuple(sorted({_candidate_key(value) for value in selections}))
    except TypeError as error:
        raise ValueError("signal candidate selections must be an iterable") from error
    if not normalized:
        raise ValueError("select at least one signal candidate")
    return normalized


def _journal_path(signal_dir: str) -> Path:
    return Path(signal_dir) / _JOURNAL_FILENAME


def _replacement_documents(
    selections: tuple[SignalCandidateKey, ...],
    signal_dir: str,
) -> tuple[dict[str, object], ...]:
    selected_ids: dict[tuple[str, str], set[str]] = {}
    for selection in selections:
        selected_ids.setdefault((selection.ticker, selection.horizon), set()).add(selection.rulebook_id)

    entries: list[dict[str, object]] = []
    for (ticker, horizon), requested_ids in sorted(selected_ids.items()):
        before = load_rulebook_result(signal_artifact_path(ticker, horizon, signal_dir))
        if before["terminal_state"] != "success":
            raise ValueError(f"{ticker} / {horizon} does not contain removable candidates")
        candidates = before["candidates"]
        present_ids = {candidate["rulebook_id"] for candidate in candidates}
        missing_ids = sorted(requested_ids.difference(present_ids))
        if missing_ids:
            raise ValueError(
                f"selected rulebook_id {missing_ids[0]} is not present in {ticker} / {horizon}"
            )
        after = copy.deepcopy(before)
        remaining = [
            candidate for candidate in after["candidates"]
            if candidate["rulebook_id"] not in requested_ids
        ]
        after["candidates"] = remaining
        if remaining:
            after["top_rulebook_ids"] = [
                candidate["rulebook_id"]
                for candidate in sorted(remaining, key=_candidate_rank)[:3]
            ]
        else:
            after.update(
                {
                    "terminal_state": "empty",
                    "empty": True,
                    "failure_reason": None,
                    "rejection_reason": _FINAL_REMOVAL_REASON,
                    "top_rulebook_ids": [],
                }
            )
        validate_rulebook_document(before)
        validate_rulebook_document(after)
        entries.append({
            "ticker": ticker,
            "horizon": horizon,
            "before": before,
            "after": after,
        })
    return tuple(entries)


def _protected_selections(
    selections: tuple[SignalCandidateKey, ...],
    positions_dir: str,
) -> tuple[SignalCandidateKey, ...]:
    records, errors = load_all_positions(positions_dir)
    if errors:
        raise ValueError(f"saved positions cannot be checked: {errors[0]}")
    requested = set(selections)
    protected = set()
    for position in records:
        reference = position.get("signal_reference")
        if not isinstance(reference, Mapping) or reference.get("schema_version") != 5:
            continue
        key = SignalCandidateKey(
            str(reference.get("ticker", "")),
            str(reference.get("horizon", "")),
            str(reference.get("rulebook_id", "")),
        )
        if key in requested:
            protected.add(key)
    return tuple(sorted(protected))


def _validated_journal_entries(payload: object, signal_dir: str) -> tuple[dict[str, object], ...]:
    if not isinstance(payload, Mapping) or set(payload) != {"schema_version", "operation", "entries"}:
        raise ValueError("signal removal transaction journal is invalid")
    if payload.get("schema_version") != _JOURNAL_SCHEMA_VERSION or payload.get("operation") != _JOURNAL_OPERATION:
        raise ValueError("signal removal transaction journal is invalid")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("signal removal transaction journal is invalid")
    entries: list[dict[str, object]] = []
    seen = set()
    for raw in raw_entries:
        if not isinstance(raw, Mapping) or set(raw) != {"ticker", "horizon", "before", "after"}:
            raise ValueError("signal removal transaction journal is invalid")
        ticker = _normalize_ticker(raw["ticker"])
        horizon = raw["horizon"]
        if horizon not in HORIZONS or (ticker, horizon) in seen:
            raise ValueError("signal removal transaction journal is invalid")
        before, after = raw["before"], raw["after"]
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            raise ValueError("signal removal transaction journal is invalid")
        before_copy, after_copy = copy.deepcopy(dict(before)), copy.deepcopy(dict(after))
        if (
            before_copy.get("ticker") != ticker or before_copy.get("horizon") != horizon
            or after_copy.get("ticker") != ticker or after_copy.get("horizon") != horizon
        ):
            raise ValueError("signal removal transaction journal is invalid")
        validate_rulebook_document(before_copy)
        validate_rulebook_document(after_copy)
        expected_path = signal_artifact_path(ticker, horizon, signal_dir)
        if expected_path.parent != Path(signal_dir) / ticker:
            raise ValueError("signal removal transaction journal is invalid")
        entries.append({"ticker": ticker, "horizon": horizon, "before": before_copy, "after": after_copy})
        seen.add((ticker, horizon))
    return tuple(sorted(entries, key=lambda item: (item["ticker"], item["horizon"])))


def _read_journal(signal_dir: str) -> tuple[dict[str, object], ...] | None:
    path = _journal_path(signal_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("signal removal transaction journal is invalid") from error
    return _validated_journal_entries(payload, signal_dir)


def _remove_journal(signal_dir: str) -> None:
    try:
        _journal_path(signal_dir).unlink()
    except FileNotFoundError:
        pass


def recover_pending_signal_removal(signal_dir: str = DEFAULT_SIGNAL_DIR) -> None:
    """Restore a coherent before/after state after an interrupted batch rewrite."""

    entries = _read_journal(signal_dir)
    if entries is None:
        return
    current_states = []
    for entry in entries:
        try:
            current = load_rulebook_result(
                signal_artifact_path(entry["ticker"], entry["horizon"], signal_dir)
            )
        except (OSError, TypeError, ValueError) as error:
            raise ValueError("signal removal transaction journal cannot be recovered") from error
        if current == entry["before"]:
            current_states.append("before")
        elif current == entry["after"]:
            current_states.append("after")
        else:
            raise ValueError("signal removal transaction journal cannot be recovered")
    if all(state == "after" for state in current_states) or all(state == "before" for state in current_states):
        _remove_journal(signal_dir)
        return
    for entry in entries:
        replace_validated_rulebook_result(
            entry["ticker"], entry["horizon"], entry["before"], signal_dir,
        )
    _remove_journal(signal_dir)


def remove_saved_signal_candidates(
    selections: Iterable[SignalCandidateKey | Mapping[str, object]],
    *,
    signal_dir: str = DEFAULT_SIGNAL_DIR,
    positions_dir: str = "backtest-positions",
) -> SignalRemovalResult:
    """Remove complete schema-5 candidates after position and artifact preflight."""

    recover_pending_signal_removal(signal_dir)
    normalized = _normalized_selections(selections)
    entries = _replacement_documents(normalized, signal_dir)
    protected = _protected_selections(normalized, positions_dir)
    if protected:
        raise SignalRemovalBlockedError(protected)
    journal = {
        "schema_version": _JOURNAL_SCHEMA_VERSION,
        "operation": _JOURNAL_OPERATION,
        "entries": list(entries),
    }
    _write_json_atomically(_journal_path(signal_dir), journal)
    for entry in entries:
        replace_validated_rulebook_result(
            entry["ticker"], entry["horizon"], entry["after"], signal_dir,
        )
    _remove_journal(signal_dir)
    return SignalRemovalResult(removed=normalized)


__all__ = [
    "SignalCandidateKey",
    "SignalRemovalBlockedError",
    "SignalRemovalResult",
    "recover_pending_signal_removal",
    "remove_saved_signal_candidates",
]
