"""Non-blocking isolated-worker entry point and JSON status helpers."""

import importlib
import inspect
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Callable

from .models import BatchTickerStatus, JobStatus


LOGGER = logging.getLogger(__name__)
_ACTIVE_PROCESSES: dict[str, subprocess.Popen] = {}
REGENERATION_REASON = "Regenerate under Backtest schema 5."


def _status_path(job_id: str, status_dir: str) -> Path:
    return Path(status_dir) / f"{job_id}.json"


def _request_path(job_id: str, status_dir: str) -> Path:
    return Path(status_dir) / f"{job_id}.request.json"


def _write_json_atomically(payload: dict[str, object], target: Path) -> None:
    directory = target.parent
    directory.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            json.dump(payload, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _write_status(status: JobStatus, status_dir: str) -> None:
    _write_json_atomically(status.to_dict(), _status_path(status.job_id, status_dir))


def write_requires_regeneration_marker(path: str | Path, job_id: str) -> None:
    """Overwrite one legacy sidecar without decoding its historical payload."""

    _write_json_atomically(
        JobStatus(
            job_id,
            "requires_regeneration",
            progress=1.0,
            error_text=REGENERATION_REASON,
        ).to_dict(),
        Path(path),
    )


def _write_request(
    job_id: str,
    config,
    factory_ref: str,
    status_dir: str,
) -> Path:
    target = _request_path(job_id, status_dir)
    _write_json_atomically(
        {
            "schema_version": 5,
            "job_id": job_id,
            "config": config.to_dict(),
            "factory_ref": factory_ref,
            "status_dir": str(status_dir),
        },
        target,
    )
    return target


def read_job_status(job_id: str, status_dir: str) -> JobStatus:
    """Read one complete status snapshot from the atomic JSON sidecar."""

    payload = json.loads(
        _status_path(job_id, status_dir).read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict) or payload.get("schema_version") != 5:
        raise ValueError("unsupported job status schema")
    return JobStatus(
        job_id=payload["job_id"],
        state=payload["state"],
        progress=payload.get("progress", 0.0),
        output_paths=tuple(payload.get("output_paths", ())),
        error_text=payload.get("error_text"),
        ticker_results=_ticker_results(payload.get("ticker_results", ())),
    )


def _ticker_results(value) -> tuple[BatchTickerStatus, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raise ValueError("ticker_results must be a sequence")
    try:
        values = tuple(value)
    except TypeError as error:
        raise ValueError("ticker_results must be a sequence") from error
    normalized = []
    for item in values:
        if isinstance(item, BatchTickerStatus):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(BatchTickerStatus(**item))
        else:
            raise ValueError("ticker_results must contain status objects")
    return tuple(normalized)


def _factory_result_details(
    result,
) -> tuple[tuple[str, ...], tuple[BatchTickerStatus, ...] | None]:
    if result is None:
        return (), None
    if isinstance(result, JobStatus):
        return tuple(result.output_paths), tuple(result.ticker_results)
    if isinstance(result, dict):
        return (
            tuple(str(path) for path in result.get("output_paths", ())),
            _ticker_results(result.get("ticker_results"))
            if "ticker_results" in result
            else None,
        )
    if isinstance(result, (str, Path)):
        return (str(result),), None
    return tuple(str(path) for path in result), None


def _invoke_factory(factory: Callable, config, report_progress):
    parameter_count = len(inspect.signature(factory).parameters)
    if parameter_count >= 2:
        return factory(config, report_progress)
    return factory(config)


def _run_job_with_id(
    job_id: str,
    config,
    engine_factory: Callable,
    status_dir: str,
) -> JobStatus:
    progress = 0.0
    ticker_results: tuple[BatchTickerStatus, ...] = ()
    _write_status(
        JobStatus(job_id, "running", progress=progress, ticker_results=ticker_results),
        status_dir,
    )

    def report_progress(value: float, reported_ticker_results=None) -> None:
        nonlocal progress, ticker_results
        try:
            numeric = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("progress must be numeric") from error
        progress = max(progress, min(1.0, numeric))
        if reported_ticker_results is not None:
            ticker_results = _ticker_results(reported_ticker_results)
        _write_status(
            JobStatus(
                job_id,
                "running",
                progress=progress,
                ticker_results=ticker_results,
            ),
            status_dir,
        )

    try:
        result = _invoke_factory(engine_factory, config, report_progress)
        output_paths, final_ticker_results = _factory_result_details(result)
        final = JobStatus(
            job_id,
            "done",
            progress=1.0,
            output_paths=output_paths,
            ticker_results=(
                ticker_results
                if final_ticker_results is None
                else final_ticker_results
            ),
        )
    except Exception as error:  # persist failures for polling callers
        # Keep the status safe for UI display while preserving the traceback in
        # the worker's inherited stderr for Docker-log diagnosis.
        LOGGER.exception("Backtest job %s failed", job_id)
        final = JobStatus(
            job_id,
            "failed",
            progress=progress,
            error_text=f"{type(error).__name__}: {error}",
            ticker_results=ticker_results,
        )
    _write_status(final, status_dir)
    return final


def _factory_reference(factory: Callable) -> str:
    """Return a stable import path only for a module-level callable."""

    module_name = getattr(factory, "__module__", "")
    qualname = getattr(factory, "__qualname__", "")
    if not module_name or not qualname or "<" in qualname:
        raise ValueError("engine_factory must be importable")
    try:
        resolved = importlib.import_module(module_name)
        for attribute in qualname.split("."):
            resolved = getattr(resolved, attribute)
    except Exception as error:
        raise ValueError("engine_factory must be importable") from error
    if resolved is not factory:
        raise ValueError("engine_factory must be importable")
    return f"{module_name}:{qualname}"


def _factory_environment(factory: Callable) -> dict[str, str] | None:
    """Expose a module-level factory's source directory to its worker process."""

    source_path = inspect.getsourcefile(factory)
    if source_path is None:
        return None
    source_directory = str(Path(source_path).resolve().parent)
    inherited = os.environ.get("PYTHONPATH", "")
    paths = [path for path in inherited.split(os.pathsep) if path]
    if source_directory in paths:
        return None
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join([source_directory, *paths])
    return environment


def _reap_worker(job_id: str, status_dir: str, process: subprocess.Popen) -> None:
    """Reap one child and ensure it leaves a terminal status behind."""

    try:
        exit_code = process.wait()
        try:
            final = read_job_status(job_id, status_dir)
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            final = None
        if final is None or final.state not in ("done", "failed", "requires_regeneration"):
            detail = (
                f"worker exited with code {exit_code} before writing "
                "a terminal status"
            )
            progress = final.progress if final is not None else 0.0
            _write_status(
                JobStatus(
                    job_id,
                    "failed",
                    progress=progress,
                    error_text=f"RuntimeError: {detail}",
                ),
                status_dir,
            )
    finally:
        _ACTIVE_PROCESSES.pop(job_id, None)


def submit_backtest(config, engine_factory: Callable, status_dir: str) -> str:
    """Queue a job through an isolated module worker and return immediately."""

    factory_ref = _factory_reference(engine_factory)
    job_id = uuid.uuid4().hex
    _write_status(JobStatus(job_id, "queued", progress=0.0), status_dir)
    try:
        request_path = _write_request(job_id, config, factory_ref, status_dir)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "backtest_engine.worker",
                str(request_path),
            ],
            close_fds=True,
            env=_factory_environment(engine_factory),
        )
    except Exception as error:
        _write_status(
            JobStatus(
                job_id,
                "failed",
                error_text=f"{type(error).__name__}: {error}",
            ),
            status_dir,
        )
        return job_id
    _ACTIVE_PROCESSES[job_id] = process
    threading.Thread(
        target=_reap_worker,
        args=(job_id, status_dir, process),
        daemon=True,
    ).start()
    return job_id


def run_backtest_job(config, engine_factory: Callable, status_dir: str) -> JobStatus:
    """Run one job synchronously for workers and deterministic unit tests."""

    return _run_job_with_id(uuid.uuid4().hex, config, engine_factory, status_dir)


__all__ = [
    "REGENERATION_REASON",
    "read_job_status",
    "run_backtest_job",
    "submit_backtest",
    "write_requires_regeneration_marker",
]
