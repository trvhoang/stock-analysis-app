"""Schema-5 result-root and recoverable Group management without migration."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytz

from .config import DEFAULT_GROUP_DIR, DEFAULT_SIGNAL_DIR, HORIZONS, _normalize_ticker
from .persistence import load_rulebook_result, signal_artifact_path


_GROUP_JOURNAL_NAME = ".group-move-journal.json"
_SAFE_SLUG_PATTERN = re.compile(r"[^A-Z0-9]+")
_MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class SignalGroup:
    """One validated user-management Group; UUID stays outside the UI."""

    group_id: str
    group_name: str
    tickers: tuple[str, ...]
    metadata: dict[str, object]
    path: Path


def _group_dir(signal_dir: Path) -> Path:
    return Path(DEFAULT_GROUP_DIR) if signal_dir == Path(DEFAULT_SIGNAL_DIR) else signal_dir.parent / "ticker-group"


def _normalize_group_name(value: object) -> str | None:
    if not isinstance(value, str):
        raise ValueError("Group must be text")
    normalized = value.strip().upper()
    return None if not normalized or normalized == "N/A" else normalized


def _group_slug(group_name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", group_name).encode("ascii", "ignore").decode("ascii")
    return _SAFE_SLUG_PATTERN.sub("-", ascii_name.upper()).strip("-") or "GROUP"


def _group_payload(group: SignalGroup) -> dict[str, object]:
    return {
        "schema_version": 1,
        "group_id": group.group_id,
        "group_name": group.group_name,
        "tickers": list(group.tickers),
        "metadata": dict(group.metadata),
        "updated_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
    }


def _group_from_payload(path: Path, payload: object) -> SignalGroup:
    required = {"schema_version", "group_id", "group_name", "tickers", "metadata", "updated_at"}
    if not isinstance(payload, Mapping) or set(payload) != required or payload["schema_version"] != 1:
        raise ValueError(f"Group JSON is invalid: {path}")
    group_id, group_name, tickers = payload["group_id"], payload["group_name"], payload["tickers"]
    if not isinstance(group_id, str) or str(uuid.UUID(group_id)) != group_id:
        raise ValueError(f"Group JSON UUID is invalid: {path}")
    if not isinstance(group_name, str) or _normalize_group_name(group_name) != group_name:
        raise ValueError(f"Group JSON name is invalid: {path}")
    if not isinstance(tickers, list) or not all(isinstance(ticker, str) for ticker in tickers):
        raise ValueError(f"Group JSON tickers are invalid: {path}")
    normalized = tuple(_normalize_ticker(ticker) for ticker in tickers)
    if len(set(normalized)) != len(normalized) or tuple(tickers) != normalized:
        raise ValueError(f"Group JSON tickers are invalid: {path}")
    if not isinstance(payload["metadata"], dict) or not isinstance(payload["updated_at"], str):
        raise ValueError(f"Group JSON metadata is invalid: {path}")
    if path.name != f"{_group_slug(group_name)}-{group_id}.json":
        raise ValueError(f"Group JSON filename is invalid: {path}")
    return SignalGroup(group_id, group_name, tuple(sorted(normalized)), dict(payload["metadata"]), path)


def _write_json_atomically(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
            temporary_path = temporary.name
            json.dump(payload, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _load_groups(group_dir: Path) -> tuple[SignalGroup, ...]:
    groups = tuple(
        _group_from_payload(path, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(group_dir.glob("*.json"), key=lambda item: item.name)
    )
    if len({group.group_id for group in groups}) != len(groups) or len({group.group_name for group in groups}) != len(groups):
        raise ValueError("Group JSON has duplicate identity")
    return tuple(sorted(groups, key=lambda group: (group.group_name, group.group_id)))


def _journal_entries(value: object, group_dir: Path) -> list[tuple[Path, dict[str, object]]]:
    if not isinstance(value, list):
        raise ValueError("Group move journal is invalid")
    entries = []
    for entry in value:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "payload"}:
            raise ValueError("Group move journal is invalid")
        path, payload = Path(entry["path"]), entry["payload"]
        if path.resolve().parent != group_dir.resolve() or not isinstance(payload, dict):
            raise ValueError("Group move journal is invalid")
        _group_from_payload(path, payload)
        entries.append((path, dict(payload)))
    return entries


def _recover_group_move(group_dir: Path) -> None:
    journal = group_dir / _GROUP_JOURNAL_NAME
    if not journal.exists():
        return
    payload = json.loads(journal.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
        raise ValueError("Group move journal is invalid")
    _journal_entries(payload.get("before"), group_dir)
    for path, group_payload in _journal_entries(payload.get("after"), group_dir):
        _write_json_atomically(path, group_payload)
    journal.unlink()


def ensure_result_root(signal_dir: str = DEFAULT_SIGNAL_DIR) -> Path:
    """Create only current schema-5 and Group roots; never inspect frozen files."""

    signal_root = Path(signal_dir)
    signal_root.mkdir(parents=True, exist_ok=True)
    _group_dir(signal_root).mkdir(parents=True, exist_ok=True)
    return signal_root


def list_groups(signal_dir: str = DEFAULT_SIGNAL_DIR) -> tuple[SignalGroup, ...]:
    root = ensure_result_root(signal_dir)
    group_dir = _group_dir(root)
    _recover_group_move(group_dir)
    return _load_groups(group_dir)


def groups_for_ticker(ticker: str, signal_dir: str = DEFAULT_SIGNAL_DIR) -> tuple[str, ...]:
    normalized = _normalize_ticker(ticker)
    return tuple(group.group_name for group in list_groups(signal_dir) if normalized in group.tickers)


def list_validation_group_choices(signal_dir: str = DEFAULT_SIGNAL_DIR) -> tuple[str, ...]:
    return ("-", "N/A", *(group.group_name for group in list_groups(signal_dir)))


def _artifact_tickers(signal_root: Path) -> tuple[str, ...]:
    """Find only readable nonempty schema-5 results across every horizon."""

    tickers: list[str] = []
    for candidate in signal_root.iterdir():
        if not candidate.is_dir():
            continue
        try:
            ticker = _normalize_ticker(candidate.name)
        except ValueError:
            continue
        found = False
        for horizon in HORIZONS:
            path = signal_artifact_path(ticker, horizon, str(signal_root))
            if not path.is_file():
                continue
            try:
                result = load_rulebook_result(path)
            except (OSError, ValueError, TypeError):
                continue
            if result["terminal_state"] == "success" and not result["empty"]:
                found = True
                break
            if found:
                break
        if found:
            tickers.append(ticker)
    return tuple(sorted(tickers))


def resolve_group_tickers(selection: str, signal_dir: str = DEFAULT_SIGNAL_DIR) -> tuple[str, ...]:
    if not isinstance(selection, str):
        raise ValueError("Group selection must be text")
    normalized = selection.strip().upper()
    if not normalized or normalized == "-":
        raise ValueError("Group selection must be a named Group or N/A")
    root = ensure_result_root(signal_dir)
    groups = list_groups(str(root))
    if normalized == "N/A":
        members = {ticker for group in groups for ticker in group.tickers}
        return tuple(ticker for ticker in _artifact_tickers(root) if ticker not in members)
    selected = next((group for group in groups if group.group_name == normalized), None)
    if selected is None:
        raise ValueError(f"Group does not exist: {normalized}")
    return selected.tickers


def assign_ticker_group(ticker: str, group_name: str, signal_dir: str = DEFAULT_SIGNAL_DIR) -> None:
    assign_tickers_group((ticker,), group_name, signal_dir)


def assign_tickers_group(tickers: Sequence[str], group_name: str, signal_dir: str = DEFAULT_SIGNAL_DIR) -> None:
    if isinstance(tickers, (str, bytes)) or not isinstance(tickers, Sequence):
        raise ValueError("Group tickers must be a sequence")
    normalized_tickers = tuple(sorted({_normalize_ticker(ticker) for ticker in tickers}))
    normalized_name = _normalize_group_name(group_name)
    if normalized_name is None or not normalized_tickers:
        return
    root = ensure_result_root(signal_dir)
    group_dir = _group_dir(root)
    _recover_group_move(group_dir)
    groups = list(_load_groups(group_dir))
    current = next((group for group in groups if group.group_name == normalized_name), None)
    if current is not None and set(normalized_tickers).issubset(current.tickers):
        return
    if current is None:
        group_id = str(uuid.uuid4())
        current = SignalGroup(
            group_id,
            normalized_name,
            (),
            {},
            group_dir / f"{_group_slug(normalized_name)}-{group_id}.json",
        )
        before = []
    else:
        before = [{"path": str(current.path.resolve()), "payload": _group_payload(current)}]
    updated = SignalGroup(current.group_id, current.group_name, tuple(sorted({*current.tickers, *normalized_tickers})), current.metadata, current.path)
    after = [{"path": str(updated.path.resolve()), "payload": _group_payload(updated)}]
    _write_json_atomically(group_dir / _GROUP_JOURNAL_NAME, {"schema_version": 1, "before": before, "after": after})
    _recover_group_move(group_dir)


def replace_group_tickers(
    group_name: str,
    tickers: Sequence[str],
    signal_dir: str = DEFAULT_SIGNAL_DIR,
) -> None:
    """Atomically replace one existing named Group's members, including empty."""

    if isinstance(tickers, (str, bytes)) or not isinstance(tickers, Sequence):
        raise ValueError("Group tickers must be a sequence")
    normalized_name = _normalize_group_name(group_name)
    if normalized_name is None:
        raise ValueError("Group must be a named Group")
    normalized_tickers = tuple(sorted({_normalize_ticker(ticker) for ticker in tickers}))
    root = ensure_result_root(signal_dir)
    group_dir = _group_dir(root)
    _recover_group_move(group_dir)
    groups = list(_load_groups(group_dir))
    current = next((group for group in groups if group.group_name == normalized_name), None)
    if current is None:
        raise ValueError("Group does not exist")
    updated = SignalGroup(
        current.group_id, current.group_name, normalized_tickers,
        current.metadata, current.path,
    )
    before = [{"path": str(current.path.resolve()), "payload": _group_payload(current)}]
    after = [{"path": str(updated.path.resolve()), "payload": _group_payload(updated)}]
    _write_json_atomically(group_dir / _GROUP_JOURNAL_NAME, {"schema_version": 1, "before": before, "after": after})
    _recover_group_move(group_dir)


__all__ = [
    "SignalGroup", "assign_ticker_group", "assign_tickers_group", "ensure_result_root",
    "groups_for_ticker", "list_groups", "list_validation_group_choices", "replace_group_tickers", "resolve_group_tickers",
]
