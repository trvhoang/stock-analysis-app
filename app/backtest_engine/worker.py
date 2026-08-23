"""Dedicated, Streamlit-free process entry point for one Backtest job."""

import importlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Callable

from .config import BacktestBatchConfig, BacktestConfig
from .job_runner import _run_job_with_id, _write_status
from .models import JobStatus


def _request_identity(request_path: str) -> tuple[str, str]:
    path = Path(request_path)
    suffix = ".request.json"
    job_id = path.name.removesuffix(suffix)
    return job_id, str(path.parent)


def _config_from_payload(payload: dict[str, object]) -> BacktestBatchConfig:
    values = dict(payload)
    request_type = values.pop("request_type", None)
    for field in ("start_date", "end_date"):
        value = values.get(field)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError(f"{field} must be an ISO date string")
            values[field] = date.fromisoformat(value)
    if request_type == "backtest_single_v4":
        return BacktestConfig(**values).as_batch()
    if request_type == "backtest_batch_v4":
        return BacktestBatchConfig(**values)
    raise ValueError("request_type is not supported")


def _resolve_factory(factory_ref: object) -> Callable:
    if not isinstance(factory_ref, str):
        raise ValueError("factory_ref must be a module-qualified string")
    module_name, separator, qualname = factory_ref.partition(":")
    if not separator or not module_name or not qualname or "<" in qualname:
        raise ValueError("factory_ref must be module:qualname")
    factory = importlib.import_module(module_name)
    for attribute in qualname.split("."):
        factory = getattr(factory, attribute)
    if not callable(factory):
        raise ValueError("factory_ref must resolve to a callable")
    return factory


def run_worker_request(request_path: str) -> JobStatus:
    """Run one persisted request, retaining a terminal failure on bad input."""

    job_id, status_dir = _request_identity(request_path)
    try:
        payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("worker request must be a JSON object")
        marker_fields = {
            "schema_version", "job_id", "state", "progress", "output_paths",
            "error_text", "ticker_results",
        }
        if payload.get("schema_version") == 4 and payload.get("state") == "requires_regeneration":
            if set(payload) != marker_fields:
                raise ValueError("requires_regeneration marker has an invalid schema")
            marker = JobStatus(
                job_id=str(payload["job_id"]),
                state="requires_regeneration",
                progress=1.0,
                output_paths=tuple(payload.get("output_paths", ())),
                error_text=payload.get("error_text"),
                ticker_results=(),
            )
            if not isinstance(marker.error_text, str) or not marker.error_text.strip():
                raise ValueError("requires_regeneration marker requires a reason")
            _write_status(marker, status_dir)
            return marker
        job_id = str(payload["job_id"])
        status_dir = str(payload["status_dir"])
        config_payload = payload["config"]
        if not isinstance(config_payload, dict):
            raise ValueError("config must be a JSON object")
        config = _config_from_payload(config_payload)
        engine_factory = _resolve_factory(payload["factory_ref"])
    except Exception as error:
        failed = JobStatus(
            job_id,
            "failed",
            error_text=f"{type(error).__name__}: {error}",
        )
        _write_status(failed, status_dir)
        return failed
    return _run_job_with_id(job_id, config, engine_factory, status_dir)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m backtest_engine.worker <request-path>")
    run_worker_request(sys.argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
