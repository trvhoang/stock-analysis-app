"""Read-only adapter for existing named ticker-group JSON documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import uuid


@dataclass(frozen=True)
class FrozenGroup:
    """Immutable membership snapshot captured at campaign submission."""

    group_name: str
    group_id: str
    members: tuple[str, ...]
    source_updated_at: str


def resolve_named_group_dir() -> Path:
    """Resolve the app's existing group directory without consulting CWD."""

    return (Path(__file__).resolve().parents[1] / "backtest-result" / "ticker-group").resolve()


def _normalize_group_name(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("group_name must be text")
    name = value.strip().upper()
    if not name or name in {"-", "N/A"}:
        raise ValueError("group_name must identify a named group")
    # Existing Group JSON permits Unicode display names (for example, the
    # Vietnamese names used by the app).  Keep the adapter read-only and
    # path-safe without reducing valid names to ASCII.
    if any(ord(character) < 32 or character in {"/", "\\"} for character in name):
        raise ValueError("group_name contains unsupported characters")
    return name


def _read_group(path: Path, expected_name: str) -> FrozenGroup | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("group document is unreadable") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("group document schema is invalid")
    name = _normalize_group_name(payload.get("group_name"))
    if name != expected_name:
        return None
    group_id = payload.get("group_id")
    try:
        if not isinstance(group_id, str) or str(uuid.UUID(group_id)) != group_id:
            raise ValueError
    except (ValueError, AttributeError) as error:
        raise ValueError("group_id is invalid") from error
    tickers = payload.get("tickers")
    if not isinstance(tickers, list):
        raise ValueError("group tickers must be a list")
    members: list[str] = []
    for ticker in tickers:
        if not isinstance(ticker, str):
            raise ValueError("group ticker must be text")
        normalized = ticker.strip().upper()
        if not normalized or not re.fullmatch(r"[A-Z0-9._-]+", normalized):
            raise ValueError("group ticker is invalid")
        if normalized in members:
            raise ValueError("group tickers must be unique")
        members.append(normalized)
    updated_at = payload.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        raise ValueError("updated_at is required")
    try:
        parsed = datetime.fromisoformat(updated_at)
    except ValueError as error:
        raise ValueError("updated_at must be ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("updated_at must include timezone")
    return FrozenGroup(name, group_id, tuple(members), updated_at)


def snapshot_named_group(group_name: str, *, group_dir: Path | None = None) -> FrozenGroup:
    """Read one named group; never resolve the V3 N/A pseudo-group."""

    expected_name = _normalize_group_name(group_name)
    directory = resolve_named_group_dir() if group_dir is None else group_dir
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError("group_dir must be an absolute path")
    if not directory.is_dir():
        raise ValueError("named group directory is unavailable")
    matches: list[FrozenGroup] = []
    for path in sorted(directory.glob("*.json")):
        group = _read_group(path, expected_name)
        if group is not None:
            matches.append(group)
    if not matches:
        raise ValueError("named group is unavailable")
    if len({(item.group_id, item.members, item.source_updated_at) for item in matches}) != 1:
        raise ValueError("named group has conflicting documents")
    return matches[0]


def available_named_group_names(*, group_dir: Path | None = None) -> tuple[str, ...]:
    """Return sorted names backed by valid, non-conflicting group documents.

    This is a read-only discovery helper for selectors.  It never creates or
    mutates group files, and it omits pseudo-groups, malformed documents, and
    names whose valid documents disagree about their frozen snapshot.
    """

    directory = resolve_named_group_dir() if group_dir is None else group_dir
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError("group_dir must be an absolute path")
    if not directory.is_dir():
        return ()

    matches_by_name: dict[str, list[FrozenGroup]] = {}
    invalid_names: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            expected_name = _normalize_group_name(payload.get("group_name"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        try:
            group = _read_group(path, expected_name)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            invalid_names.add(expected_name)
            continue
        if group is not None:
            matches_by_name.setdefault(group.group_name, []).append(group)

    names: list[str] = []
    for name, matches in matches_by_name.items():
        signatures = {(item.group_id, item.members, item.source_updated_at) for item in matches}
        if name not in invalid_names and len(signatures) == 1:
            names.append(name)
    return tuple(sorted(names))


__all__ = [
    "FrozenGroup",
    "available_named_group_names",
    "resolve_named_group_dir",
    "snapshot_named_group",
]
