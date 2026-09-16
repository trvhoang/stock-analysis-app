"""Read-only inventory of the retired Flexible Rulebook v1 surface.

The cutover uses this report to prove what legacy runtime, tests, references,
and opaque artifact trees existed before selective replacement. Artifact JSON
is deliberately not parsed or migrated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


_REFERENCE_PATTERNS = {
    "flexible_imports": re.compile(
        r"(?:(?:from|import)\s+flexible_rulebook(?:\.|\b)|"
        r"__import__\(\s*[\"']flexible_rulebook(?:\.|[\"'])|"
        r"import_module\(\s*[\"']flexible_rulebook(?:\.|[\"']))"
    ),
    "page_routes": re.compile(r"render_flexible_rulebook_page|pages\.flexible_rulebook"),
    "subprocess_entry_points": re.compile(
        r"(?:-m\s+flexible_rulebook\.|"
        r"[\"']-m[\"']\s*,\s*[\"']flexible_rulebook\.|"
        r"flexible_rulebook\.[\w.]+:[A-Za-z_]\w*)"
    ),
    "benchmark_policy": re.compile(r"(?:/data|data)[/\\]flexible-benchmark"),
}


def _application_root(project_root: Path) -> Path:
    nested = project_root / "app"
    if (nested / "pages").is_dir() or (nested / "flexible_rulebook").is_dir():
        return nested
    return project_root


def _display_path(
    path: Path,
    *,
    project_root: Path,
    application_root: Path,
) -> str:
    if application_root == project_root:
        for top_level in ("tests", "scripts"):
            scoped_root = project_root / top_level
            try:
                return f"{top_level}/{path.relative_to(scoped_root).as_posix()}"
            except ValueError:
                continue
        try:
            return f"app/{path.relative_to(application_root).as_posix()}"
        except ValueError:
            return path.as_posix()

    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        pass

    try:
        return f"app/{path.relative_to(application_root).as_posix()}"
    except ValueError:
        return path.as_posix()


def _iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _tree_digest(root: Path, files: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative_path = path.relative_to(root).as_posix()
        file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _inventory_artifact_root(label: str, root: Path) -> dict[str, object]:
    files = _iter_files(root)
    kinds: Counter[str] = Counter()
    file_records: list[dict[str, object]] = []

    for path in files:
        relative_path = path.relative_to(root)
        kind = relative_path.parts[0] if len(relative_path.parts) > 1 else "root"
        kinds[kind] += 1
        file_records.append(
            {
                "path": relative_path.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    return {
        "label": label,
        "path": str(root),
        "exists": root.is_dir(),
        "file_count": len(files),
        "byte_count": sum(int(record["size_bytes"]) for record in file_records),
        "kinds": dict(sorted(kinds.items())),
        "tree_digest": _tree_digest(root, files),
        "files": file_records,
    }


def _reference_files(
    *,
    project_root: Path,
    application_root: Path,
) -> list[Path]:
    roots = [application_root, project_root / "tests", project_root / "scripts"]
    excluded_roots = {
        (application_root / "Flexible-Rulebook").resolve(),
    }
    files: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            resolved = path.resolve()
            if resolved in seen or "__pycache__" in path.parts:
                continue
            if path.name in {
                "audit_flexible_rulebook_legacy.py",
                "test_flexible_rulebook_v2_cutover.py",
            }:
                continue
            if any(excluded == resolved or excluded in resolved.parents for excluded in excluded_roots):
                continue
            seen.add(resolved)
            files.append(path)

    return sorted(
        files,
        key=lambda path: _display_path(
            path,
            project_root=project_root,
            application_root=application_root,
        ),
    )


def collect_inventory(project_root: Path) -> dict[str, object]:
    """Return a deterministic, JSON-compatible inventory without writing files."""

    project_root = project_root.resolve()
    application_root = _application_root(project_root).resolve()
    runtime_root = application_root / "flexible_rulebook"
    tests_root = project_root / "tests"

    runtime_modules = (
        sorted(path for path in runtime_root.glob("*.py") if path.name != "__init__.py")
        if runtime_root.is_dir()
        else []
    )
    legacy_tests = (
        sorted(
            path
            for path in tests_root.glob("test_flexible_rulebook_*.py")
            if not path.name.startswith("test_flexible_rulebook_v2_")
        )
        if tests_root.is_dir()
        else []
    )

    references: dict[str, list[str]] = {
        category: [] for category in (*_REFERENCE_PATTERNS, "backtest_position")
    }
    for path in _reference_files(
        project_root=project_root,
        application_root=application_root,
    ):
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        display_path = _display_path(
            path,
            project_root=project_root,
            application_root=application_root,
        )
        for category, pattern in _REFERENCE_PATTERNS.items():
            if pattern.search(source):
                references[category].append(display_path)
        if (
            ("backtest" in display_path.lower() or "position" in display_path.lower())
            and re.search(r"flexible_rulebook|Flexible-Rulebook|frb_", source)
        ):
            references["backtest_position"].append(display_path)

    package_artifacts = application_root / "Flexible-Rulebook"
    repository_benchmark = project_root / "data" / "flexible-benchmark"
    runtime_benchmark = Path("/data/flexible-benchmark")
    benchmark_artifacts = (
        repository_benchmark
        if repository_benchmark.exists() or application_root != project_root
        else runtime_benchmark
    )

    return {
        "schema_version": 1,
        "artifact_kind": "flexible_rulebook_legacy_inventory",
        "project_root": str(project_root),
        "legacy_runtime": {
            "module_count": len(runtime_modules),
            "modules": [
                _display_path(
                    path,
                    project_root=project_root,
                    application_root=application_root,
                )
                for path in runtime_modules
            ],
        },
        "legacy_tests": {
            "file_count": len(legacy_tests),
            "files": [
                _display_path(
                    path,
                    project_root=project_root,
                    application_root=application_root,
                )
                for path in legacy_tests
            ],
        },
        "references": references,
        "artifact_roots": [
            _inventory_artifact_root("package_v1", package_artifacts),
            _inventory_artifact_root("benchmark_v1", benchmark_artifacts),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a read-only inventory of Flexible Rulebook v1.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    print(json.dumps(collect_inventory(args.project_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
