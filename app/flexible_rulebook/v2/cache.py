"""Atomic cache for reusable v2 computed indicator components only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Literal, Mapping
import zipfile

import numpy as np
import pytz

from .contracts import canonical_json, semantic_digest


_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_HCM = pytz.timezone("Asia/Ho_Chi_Minh")


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


@dataclass(frozen=True)
class ComponentIdentity:
    """Every persisted array is bound to its exact source, calendar, and formula build."""

    source_fingerprint: str
    calendar_fingerprint: str
    build_revision: str
    family: str
    formula_revision: str
    settings: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_fingerprint", _require_digest(self.source_fingerprint, "source_fingerprint"))
        object.__setattr__(self, "calendar_fingerprint", _require_digest(self.calendar_fingerprint, "calendar_fingerprint"))
        object.__setattr__(self, "build_revision", _require_text(self.build_revision, "build_revision"))
        if not isinstance(self.family, str) or not _TOKEN_PATTERN.fullmatch(self.family):
            raise ValueError("family must be a lowercase token")
        object.__setattr__(self, "formula_revision", _require_text(self.formula_revision, "formula_revision"))
        if not isinstance(self.settings, Mapping):
            raise ValueError("settings must be a mapping")
        object.__setattr__(self, "settings", json.loads(canonical_json(dict(self.settings))))

    def to_dict(self) -> dict[str, object]:
        return {
            "source_fingerprint": self.source_fingerprint,
            "calendar_fingerprint": self.calendar_fingerprint,
            "build_revision": self.build_revision,
            "family": self.family,
            "formula_revision": self.formula_revision,
            "settings": self.settings,
        }

    @property
    def key(self) -> str:
        return semantic_digest({"cache_revision": "flexible-rulebook-v2-component-cache-v1", **self.to_dict()})


@dataclass(frozen=True)
class CachedComponent:
    digest: str
    identity: ComponentIdentity
    arrays: dict[str, np.ndarray]
    state: dict[str, object]
    completed_at: datetime


@dataclass(frozen=True)
class CacheWriteResult:
    state: Literal["stored", "already_present", "nondeterministic_build", "uncached_locked", "uncached_low_disk", "uncached_io_error"]


@dataclass
class BuildLease:
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


def component_digest(identity: ComponentIdentity, arrays: Mapping[str, np.ndarray], state: Mapping[str, object]) -> str:
    """Digest semantic source/build identity, stored state, and deterministic array bytes."""

    if not isinstance(identity, ComponentIdentity):
        raise ValueError("identity must be ComponentIdentity")
    digest = hashlib.sha256(canonical_json({"identity": identity.to_dict(), "state": dict(state)}).encode("utf-8"))
    for name in sorted(arrays):
        if not isinstance(name, str) or not name:
            raise ValueError("component array names must be non-empty text")
        array = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("utf-8"))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(canonical_json(array.shape).encode("ascii"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _paths(root: Path, identity: ComponentIdentity) -> tuple[Path, Path]:
    if not isinstance(root, Path):
        root = Path(root)
    key = identity.key
    cache_root = (root / "v2" / "cache" / "primitives").resolve()
    directory = (cache_root / key[:2]).resolve()
    try:
        directory.relative_to(cache_root)
    except ValueError as error:
        raise ValueError("cache path escapes the v2 primitive root") from error
    return directory / f"{key}.npz", directory / f"{key}.json"


def acquire_build_lease(root: Path, identity: ComponentIdentity, *, wait_seconds: float = 0.0) -> BuildLease | None:
    """A bounded cache-build lease; contention deliberately remains an in-memory miss."""

    npz_path, _ = _paths(root, identity)
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
            os.write(descriptor, b"flexible-rulebook-v2-component-build\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return BuildLease(lease_path)


def write_component(
    root: Path,
    identity: ComponentIdentity,
    arrays: Mapping[str, np.ndarray],
    state: Mapping[str, object],
    completed_at: datetime,
) -> None:
    """Atomically replace both files; a interrupted pair is always a safe reader miss."""

    if completed_at.tzinfo is None or completed_at.utcoffset() is None:
        raise ValueError("cache completion time must be timezone-aware")
    completed_at = completed_at.astimezone(_HCM)
    npz_path, manifest_path = _paths(root, identity)
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_arrays = {name: np.ascontiguousarray(value) for name, value in arrays.items()}
    normalized_state = json.loads(canonical_json(dict(state)))
    digest = component_digest(identity, normalized_arrays, normalized_state)
    existing = safe_read_component(root, identity)
    if existing is not None:
        if existing.digest != digest:
            raise ValueError("FEATURE.NONDETERMINISTIC_BUILD")
        return
    temp_npz: Path | None = None
    temp_manifest: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=npz_path.parent, suffix=".npz", delete=False) as stream:
            temp_npz = Path(stream.name)
            np.savez(stream, **normalized_arrays)
            stream.flush()
            os.fsync(stream.fileno())
        manifest = {
            "schema": "flexible-rulebook-v2-component-cache-v1",
            "identity": identity.to_dict(),
            "digest": digest,
            "arrays": {
                name: {"dtype": str(value.dtype), "shape": list(value.shape)}
                for name, value in normalized_arrays.items()
            },
            "state": normalized_state,
            "completed_at": completed_at.isoformat(),
        }
        with tempfile.NamedTemporaryFile(dir=manifest_path.parent, mode="w", encoding="utf-8", delete=False) as stream:
            temp_manifest = Path(stream.name)
            json.dump(manifest, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_npz, npz_path)
        temp_npz = None
        os.replace(temp_manifest, manifest_path)
        temp_manifest = None
    finally:
        for path in (temp_npz, temp_manifest):
            if path is not None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass


def read_component(root: Path, identity: ComponentIdentity) -> CachedComponent:
    """Read only a fully matching cached component; any mismatch is untrusted."""

    npz_path, manifest_path = _paths(root, identity)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "flexible-rulebook-v2-component-cache-v1":
        raise ValueError("cache schema mismatch")
    if manifest.get("identity") != identity.to_dict():
        raise ValueError("cache identity mismatch")
    with np.load(npz_path, allow_pickle=False) as source:
        arrays = {name: source[name].copy() for name in source.files}
    expected = manifest.get("arrays")
    if not isinstance(expected, dict) or set(arrays) != set(expected):
        raise ValueError("cache manifest array mismatch")
    for name, array in arrays.items():
        expected_array = expected[name]
        if (
            not isinstance(expected_array, dict)
            or str(array.dtype) != expected_array.get("dtype")
            or list(array.shape) != expected_array.get("shape")
        ):
            raise ValueError("cache manifest array mismatch")
    state = manifest.get("state")
    if not isinstance(state, dict):
        raise ValueError("cache state mismatch")
    digest = component_digest(identity, arrays, state)
    if digest != manifest.get("digest"):
        raise ValueError("cache digest mismatch")
    completed_at = datetime.fromisoformat(manifest["completed_at"])
    if completed_at.tzinfo is None or completed_at.utcoffset() is None:
        raise ValueError("cache completion time must be timezone-aware")
    completed_at = completed_at.astimezone(_HCM)
    return CachedComponent(digest, identity, arrays, state, completed_at)


def safe_read_component(root: Path, identity: ComponentIdentity) -> CachedComponent | None:
    """Corruption, version drift, and incomplete atomic pairs become an ordinary cache miss."""

    try:
        return read_component(root, identity)
    except (
        FileNotFoundError,
        IsADirectoryError,
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        json.JSONDecodeError,
        EOFError,
        zipfile.BadZipFile,
    ):
        return None


def try_write_component(
    root: Path,
    identity: ComponentIdentity,
    arrays: Mapping[str, np.ndarray],
    state: Mapping[str, object],
    completed_at: datetime,
    *,
    minimum_free_bytes: int = 512 * 1024 * 1024,
) -> CacheWriteResult:
    """Persist opportunistically; cache failures never invalidate a completed in-memory feature."""

    try:
        storage_root = Path(root)
        storage_root.mkdir(parents=True, exist_ok=True)
        required = minimum_free_bytes + sum(np.asarray(value).nbytes for value in arrays.values()) * 2
        if shutil.disk_usage(storage_root).free < required:
            return CacheWriteResult("uncached_low_disk")
        lease = acquire_build_lease(storage_root, identity, wait_seconds=0.1)
        if lease is None:
            return CacheWriteResult("uncached_locked")
        with lease:
            existing = safe_read_component(storage_root, identity)
            digest = component_digest(identity, arrays, state)
            if existing is not None:
                return CacheWriteResult(
                    "already_present" if existing.digest == digest else "nondeterministic_build"
                )
            write_component(storage_root, identity, arrays, state, completed_at)
            return CacheWriteResult("stored")
    except (OSError, ValueError, TypeError):
        return CacheWriteResult("uncached_io_error")


__all__ = [
    "BuildLease",
    "CachedComponent",
    "CacheWriteResult",
    "ComponentIdentity",
    "acquire_build_lease",
    "component_digest",
    "read_component",
    "safe_read_component",
    "try_write_component",
    "write_component",
]
