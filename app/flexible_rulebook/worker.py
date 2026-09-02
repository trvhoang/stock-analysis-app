"""Isolated Flexible Rulebook campaign worker entry point.

Only a small JSON request crosses the process boundary.  Callables are named
top-level imports, never pickled objects, and the worker delegates all mutable
manifest writes to :func:`runner.run_campaign`.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import re
from typing import Callable

from .campaigns import CampaignManifest
from .runner import run_campaign
from .worker_contract import WorkerRequest

_REF = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")


def read_worker_request(path: Path) -> WorkerRequest:
    """Read and validate one immutable worker request document."""

    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("worker request path must be absolute")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("worker request is unreadable") from error
    return WorkerRequest.from_dict(payload)


def resolve_callable(reference: str) -> Callable[..., object]:
    """Resolve only a named top-level callable; reject unsafe references."""

    if not isinstance(reference, str) or not _REF.fullmatch(reference):
        raise ValueError("callable reference is invalid")
    module_name, attribute_path = reference.split(":", 1)
    if module_name in {"__main__", "app.main"} or module_name.startswith("streamlit"):
        raise ValueError("worker callable module is not allowed")
    try:
        value: object = importlib.import_module(module_name)
        for name in attribute_path.split("."):
            value = getattr(value, name)
    except (ImportError, AttributeError) as error:
        raise ValueError("worker callable cannot be resolved") from error
    if not callable(value):
        raise ValueError("worker reference is not callable")
    return value


def run_worker_request(path: Path) -> CampaignManifest:
    """Run a trusted service factory against one persisted campaign."""

    request = read_worker_request(path)
    service_factory = resolve_callable(request.service_ref)
    source_loader = resolve_callable(request.source_loader_ref)
    service = service_factory(request)
    return run_campaign(
        request.campaign_id,
        request.root,
        service,
        source_loader=source_loader,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point used by the parent runner's isolated subprocess."""

    import sys

    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        raise SystemExit("usage: python -m flexible_rulebook.worker REQUEST_PATH")
    run_worker_request(Path(arguments[0]).resolve())
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess smoke tests
    raise SystemExit(main())


__all__ = ["WorkerRequest", "main", "read_worker_request", "resolve_callable", "run_worker_request"]
