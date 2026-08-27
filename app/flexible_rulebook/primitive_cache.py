"""Atomic, computed-component-only cache primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Literal
import zipfile

import numpy as np

from .contracts import canonical_json


@dataclass(frozen=True)
class CachedComponent:
    digest: str
    arrays: dict[str, np.ndarray]
    state: dict[str, object]
    completed_at: datetime


@dataclass(frozen=True)
class CacheWriteResult:
    """Non-fatal persistence outcome; caller still owns in-memory component."""

    state: Literal["stored", "already_present", "nondeterministic_build", "uncached_locked", "uncached_low_disk", "uncached_io_error"]


@dataclass
class BuildLease:
    """Exclusive short-lived build claim for one primitive cache key."""

    path: Path
    _released: bool = False

    def release(self) -> None:
        if not self._released:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self._released = True

    def __enter__(self) -> "BuildLease":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def component_digest(key: str, arrays: dict[str, np.ndarray], state: dict[str, object]) -> str:
    digest = hashlib.sha256(canonical_json({"key": key, "state": state}).encode("utf-8"))
    for name in sorted(arrays):
        array = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("utf-8")); digest.update(str(array.dtype).encode("ascii"))
        digest.update(canonical_json(array.shape).encode("ascii")); digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _paths(root: Path, key: str) -> tuple[Path, Path]:
    raw_hash = len(key) == 64 and all(char in "0123456789abcdef" for char in key)
    primitive_key = len(key) == 69 and key.startswith("frpk_") and all(char in "0123456789abcdef" for char in key[5:])
    if not raw_hash and not primitive_key:
        raise ValueError("cache key must be a SHA-256 digest or frpk_ SHA-256 key")
    directory = root / "cache" / key[:2]
    return directory / f"{key}.npz", directory / f"{key}.json"


def acquire_build_lease(root: Path, key: str, *, wait_seconds: float = 0.0) -> BuildLease | None:
    """Acquire bounded exclusive cache-build lease; contention means safe miss."""

    npz_path, _ = _paths(root, key)
    lease_path = npz_path.with_suffix(".lock")
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        try:
            descriptor = os.open(lease_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                return None
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            continue
        try:
            os.write(descriptor, b"flexible-primitive-build-v1\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return BuildLease(lease_path)


def write_component(root: Path, key: str, arrays: dict[str, np.ndarray], state: dict[str, object], completed_at: datetime) -> None:
    if completed_at.tzinfo is None or completed_at.utcoffset() is None:
        raise ValueError("cache completion time must be timezone-aware")
    npz_path, manifest_path = _paths(root, key); npz_path.parent.mkdir(parents=True, exist_ok=True)
    digest = component_digest(key, arrays, state)
    existing = safe_read_component(root, key)
    if existing is not None:
        if existing.digest != digest:
            raise ValueError("FEATURE.NONDETERMINISTIC_BUILD")
        return
    with tempfile.NamedTemporaryFile(dir=npz_path.parent, suffix=".npz", delete=False) as stream:
        temp_npz = Path(stream.name); np.savez(stream, **{name: np.ascontiguousarray(value) for name, value in arrays.items()}); stream.flush(); os.fsync(stream.fileno())
    manifest = {"key": key, "digest": digest, "arrays": {name: {"dtype": str(value.dtype), "shape": list(value.shape)} for name, value in arrays.items()}, "state": state, "completed_at": completed_at.isoformat()}
    with tempfile.NamedTemporaryFile(dir=manifest_path.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temp_manifest = Path(stream.name); json.dump(manifest, stream, sort_keys=True, separators=(",", ":")); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp_npz, npz_path); os.replace(temp_manifest, manifest_path)


def read_component(root: Path, key: str) -> CachedComponent:
    npz_path, manifest_path = _paths(root, key)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("key") != key: raise ValueError("cache manifest key mismatch")
    with np.load(npz_path, allow_pickle=False) as source:
        arrays = {name: source[name].copy() for name in source.files}
    expected = manifest.get("arrays")
    if set(arrays) != set(expected) or any(str(arrays[name].dtype) != expected[name]["dtype"] or list(arrays[name].shape) != expected[name]["shape"] for name in arrays): raise ValueError("cache manifest array mismatch")
    state = manifest.get("state")
    digest = component_digest(key, arrays, state)
    if digest != manifest.get("digest"): raise ValueError("cache digest mismatch")
    completed_at = datetime.fromisoformat(manifest["completed_at"])
    if completed_at.tzinfo is None or completed_at.utcoffset() is None:
        raise ValueError("cache completion time must be timezone-aware")
    return CachedComponent(digest, arrays, state, completed_at)


def safe_read_component(root: Path, key: str) -> CachedComponent | None:
    """Treat every unreadable or invalid on-disk item as a rebuildable miss."""

    try:
        return read_component(root, key)
    except (
        FileNotFoundError, IsADirectoryError, OSError, ValueError, TypeError,
        KeyError, json.JSONDecodeError, EOFError, zipfile.BadZipFile,
    ):
        return None


def try_write_component(
    root: Path,
    key: str,
    arrays: dict[str, np.ndarray],
    state: dict[str, object],
    completed_at: datetime,
    *,
    minimum_free_bytes: int = 512 * 1024 * 1024,
) -> CacheWriteResult:
    """Persist opportunistically; cache failure never invalidates built arrays."""

    try:
        # Require spare room beyond component bytes so a full disk cannot turn a
        # reusable optimization into a ticker-level failure.
        cache_root = Path(root)
        cache_root.mkdir(parents=True, exist_ok=True)
        required = minimum_free_bytes + sum(np.asarray(value).nbytes for value in arrays.values()) * 2
        if shutil.disk_usage(cache_root).free < required:
            return CacheWriteResult("uncached_low_disk")
        lease = acquire_build_lease(cache_root, key, wait_seconds=0.1)
        if lease is None:
            return CacheWriteResult("uncached_locked")
        with lease:
            existing = safe_read_component(cache_root, key)
            digest = component_digest(key, arrays, state)
            if existing is not None:
                return CacheWriteResult("already_present" if existing.digest == digest else "nondeterministic_build")
            write_component(cache_root, key, arrays, state, completed_at)
            return CacheWriteResult("stored")
    except (OSError, ValueError, TypeError):
        return CacheWriteResult("uncached_io_error")


__all__ = [
    "BuildLease",
    "CachedComponent",
    "CacheWriteResult",
    "acquire_build_lease",
    "component_digest",
    "read_component",
    "safe_read_component",
    "try_write_component",
    "write_component",
]
