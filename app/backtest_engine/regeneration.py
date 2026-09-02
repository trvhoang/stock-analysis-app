"""Filename-only invalidation of superseded artifacts and job sidecars."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import HORIZONS, _normalize_ticker
from .job_runner import write_requires_regeneration_marker
from .persistence import save_regeneration_marker, write_regeneration_marker


_LEGACY_ARTIFACT = re.compile(
    r"^(?P<ticker>[A-Z0-9._-]+)_signals_(?P<horizon>swing|midterm)_"
    r"(?P<variant>no-background-theme|background-theme)\.json$"
)
_CANONICAL_ARTIFACT = re.compile(
    r"^(?P<ticker>[A-Z0-9._-]+)_signals_"
    r"(?P<horizon>swing|midterm)\.json$"
)


@dataclass(frozen=True)
class RegenerationReport:
    """Paths overwritten by one intentionally content-blind invalidation run."""

    canonical_paths: tuple[Path, ...]
    legacy_artifact_paths: tuple[Path, ...]
    job_ids: tuple[str, ...]


def _legacy_artifacts(signal_root: Path):
    if not signal_root.exists():
        return ()
    records = []
    for path in signal_root.rglob("*.json"):
        match = _LEGACY_ARTIFACT.fullmatch(path.name)
        if match is None:
            continue
        ticker = _normalize_ticker(match["ticker"])
        if path.parent.name != ticker or match["horizon"] not in HORIZONS:
            continue
        records.append((path, ticker, match["horizon"]))
    return tuple(sorted(records, key=lambda item: str(item[0])))


def _canonical_artifacts(signal_root: Path):
    if not signal_root.exists():
        return ()
    records = []
    for path in signal_root.rglob("*.json"):
        match = _CANONICAL_ARTIFACT.fullmatch(path.name)
        if match is None:
            continue
        ticker = _normalize_ticker(match["ticker"])
        if path.parent.name != ticker or match["horizon"] not in HORIZONS:
            continue
        records.append((path, ticker, match["horizon"]))
    return tuple(sorted(records, key=lambda item: str(item[0])))


def _legacy_job_ids(status_root: Path) -> tuple[str, ...]:
    if not status_root.exists():
        return ()
    job_ids = set()
    for path in status_root.glob("*.request.json"):
        job_id = path.name.removesuffix(".request.json")
        if job_id:
            job_ids.add(job_id)
    for path in status_root.glob("*.json"):
        if path.name.endswith(".request.json"):
            continue
        job_id = path.stem
        if job_id:
            job_ids.add(job_id)
    return tuple(sorted(job_ids))


def invalidate_superseded_outputs(signal_dir: str, status_dir: str) -> RegenerationReport:
    """Overwrite exact superseded filenames without opening prior contents."""

    signal_root = Path(signal_dir)
    status_root = Path(status_dir)
    canonical_paths: set[Path] = set()
    legacy_paths = []
    for canonical_path, ticker, horizon in _canonical_artifacts(signal_root):
        write_regeneration_marker(canonical_path, ticker, horizon)
        canonical_paths.add(canonical_path)
    for legacy_path, ticker, horizon in _legacy_artifacts(signal_root):
        canonical_path = signal_root / ticker / f"{ticker}_signals_{horizon}.json"
        if canonical_path not in canonical_paths:
            canonical_paths.add(
                Path(save_regeneration_marker(ticker, horizon, str(signal_root)))
            )
        write_regeneration_marker(legacy_path, ticker, horizon)
        legacy_paths.append(legacy_path)
    job_ids = _legacy_job_ids(status_root)
    for job_id in job_ids:
        write_requires_regeneration_marker(status_root / f"{job_id}.request.json", job_id)
        write_requires_regeneration_marker(status_root / f"{job_id}.json", job_id)
    return RegenerationReport(
        tuple(sorted(canonical_paths, key=str)),
        tuple(legacy_paths),
        job_ids,
    )


__all__ = ["RegenerationReport", "invalidate_superseded_outputs"]
