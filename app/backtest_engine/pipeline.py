"""Offline schema-5 exploratory rulebook evaluation for ticker runs and batches."""

import os
import time
from datetime import datetime

import pandas as pd
import pytz
from sqlalchemy.engine import make_url

from .config import BacktestBatchConfig, BacktestConfig, rulebook_for
from .data_quality import (
    audit_history,
    fresh_schema5_audit_eligibility,
    load_ticker_history,
    unavailable_schema5_audit_eligibility,
    validate_ohlcv,
)
from .evidence import EvidenceEligibility, assess_evidence, unavailable_evidence
from .exploratory import ExploratoryEvaluation, evaluate_exploratory_candidates
from .indicators import build_rulebook_frame
from .models import BatchTickerStatus
from .persistence import save_rulebook_result
from .result_store import assign_tickers_group
from .timeframes import latest_common_completed_bar
from .vnindex_theme import align_vnindex_asof, build_vnindex_confirmation


_CONTRACT_VERSION = "backtest_schema5_v1"
_PARTITION_LABELS = {
    "training": "in-sample",
    "test": "historical test — previously observed",
}


def _report(report_progress, value: float, ticker_results=None) -> None:
    if report_progress is not None:
        if ticker_results is None:
            report_progress(value)
        else:
            report_progress(value, ticker_results)


def _requested_dates(config: BacktestConfig | BacktestBatchConfig) -> tuple[object, object]:
    end_date = config.end_date or datetime.now(
        pytz.timezone("Asia/Ho_Chi_Minh")
    ).date()
    start_date = config.start_date or (
        pd.Timestamp(end_date) - pd.DateOffset(years=15)
    ).date()
    return start_date, end_date


def _build_confirmation_frame(
    vnindex_frame: pd.DataFrame,
    horizon: str,
    *,
    common_as_of,
) -> pd.DataFrame:
    confirmation = build_vnindex_confirmation(
        vnindex_frame,
        horizon,
        common_as_of=common_as_of,
    )
    return pd.DataFrame(
        {
            "date": pd.DatetimeIndex(confirmation.index),
            "vnindex_confirmation": confirmation.to_numpy(),
        }
    ).sort_values("date")


def _theme_signal(ticker_frame: pd.DataFrame, confirmation_frame: pd.DataFrame) -> pd.Series:
    aligned = align_vnindex_asof(
        ticker_frame[["date"]],
        confirmation_frame.rename(columns={"vnindex_confirmation": "close"}),
    )
    return aligned["vnindex_close"].fillna(False).astype(bool)


def _prepare_ticker(
    ticker: str,
    config: BacktestConfig,
    engine,
    *,
    common_as_of,
    raw_history: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, object, pd.DataFrame]:
    """Load, validate, audit, and build one canonical native rulebook frame."""

    if raw_history is None:
        start_date, end_date = _requested_dates(config)
        raw = load_ticker_history(ticker, start_date, end_date, engine)
    else:
        raw = raw_history.copy(deep=True)
    quality = validate_ohlcv(raw)
    if not quality.is_valid or quality.valid_frame is None:
        raise ValueError("invalid backtest data: " + "; ".join(quality.errors))
    raw = quality.valid_frame
    evidence_history = raw.loc[
        pd.to_datetime(raw["date"]).le(pd.Timestamp(common_as_of))
    ].reset_index(drop=True)
    if evidence_history.empty:
        raise ValueError("backtest data has no row at or before common_as_of")
    audit = audit_history(ticker, evidence_history)
    return (
        build_rulebook_frame(
            evidence_history,
            rulebook_for(config.horizon),
            common_as_of=common_as_of,
        ),
        audit,
        evidence_history,
    )


def _load_validated_history(
    ticker: str,
    config: BacktestConfig | BacktestBatchConfig,
    engine,
) -> pd.DataFrame:
    """Load one requested raw source and return its validated, date-parsed copy."""

    start_date, end_date = _requested_dates(config)
    raw = load_ticker_history(ticker, start_date, end_date, engine)
    quality = validate_ohlcv(raw)
    if not quality.is_valid or quality.valid_frame is None:
        source = "VN-Index" if ticker == "VNINDEX" else "backtest"
        raise ValueError(f"invalid {source} data: " + "; ".join(quality.errors))
    return quality.valid_frame


def _date_range(start, end, reason: str | None = None) -> dict[str, str | None]:
    """Serialize paired bounds for a schema-5 terminal document."""

    if start is None or end is None:
        return {"start": None, "end": None, "reason": reason}
    return {
        "start": pd.Timestamp(start).date().isoformat(),
        "end": pd.Timestamp(end).date().isoformat(),
        "reason": None,
    }


def _requested_date_range(config: BacktestConfig) -> dict[str, str | None]:
    return _date_range(*_requested_dates(config))


def _effective_data_range(raw_history: pd.DataFrame) -> dict[str, str | None]:
    dates = pd.to_datetime(raw_history["date"], errors="coerce")
    if dates.empty or dates.isna().any():
        raise ValueError("fresh raw history has no usable effective date range")
    return _date_range(dates.min(), dates.max())


def _evaluation_document(
    config: BacktestConfig,
    evaluation: ExploratoryEvaluation,
    audit_eligibility: dict[str, object],
    evidence_eligibility: dict[str, object],
    effective_data_range: dict[str, str | None],
) -> dict[str, object]:
    """Build the one ticker/horizon aggregate from every qualifying subset."""

    candidates = [candidate.to_dict() for candidate in evaluation.candidates]
    state = "success" if candidates else "empty"
    return {
        "contract_version": _CONTRACT_VERSION,
        "partition_labels": dict(_PARTITION_LABELS),
        "horizon": config.horizon,
        "terminal_state": state,
        "empty": state != "success",
        "failure_reason": None,
        "rejection_reason": (
            None
            if candidates
            else f"No rulebook has no-theme training n >= {rulebook_for(config.horizon).min_n}."
        ),
        "evaluation_label": "Exploratory — gross",
        "rulebook": rulebook_for(config.horizon).to_dict(),
        "audit_eligibility": audit_eligibility,
        "evidence_eligibility": evidence_eligibility,
        "requested_date_range": _requested_date_range(config),
        "effective_data_range": effective_data_range,
        "split": evaluation.split.to_dict(),
        "candidates": candidates,
        "top_rulebook_ids": list(evaluation.top_rulebook_ids),
    }


def _failed_document(
    config: BacktestConfig,
    reason: str,
    audit_eligibility: dict[str, object],
    evidence_eligibility: dict[str, object],
    effective_data_range: dict[str, str | None],
) -> dict[str, object]:
    """Build a truthful failed aggregate when inputs or evaluation are unavailable."""

    return {
        "contract_version": _CONTRACT_VERSION,
        "partition_labels": dict(_PARTITION_LABELS),
        "horizon": config.horizon,
        "terminal_state": "failed",
        "empty": True,
        "failure_reason": reason,
        "rejection_reason": None,
        "evaluation_label": "Exploratory — gross",
        "rulebook": rulebook_for(config.horizon).to_dict(),
        "audit_eligibility": audit_eligibility,
        "evidence_eligibility": evidence_eligibility,
        "requested_date_range": _requested_date_range(config),
        "effective_data_range": effective_data_range,
        "split": None,
        "candidates": [],
        "top_rulebook_ids": [],
    }


def _persist_evaluation(
    ticker: str,
    config: BacktestConfig,
    evaluation: ExploratoryEvaluation,
    raw_history: pd.DataFrame,
    audit,
    evidence: EvidenceEligibility,
) -> list[str]:
    effective = _effective_data_range(raw_history)
    eligibility = fresh_schema5_audit_eligibility(raw_history, audit, effective)
    return [
        save_rulebook_result(
            ticker,
            _evaluation_document(
                config,
                evaluation,
                eligibility,
                evidence.to_dict(),
                effective,
            ),
            config.output_dir,
        )
    ]


def _persist_failure(
    ticker: str,
    config: BacktestConfig,
    reason: str,
    *,
    raw_history: pd.DataFrame | None = None,
    audit=None,
    evidence: EvidenceEligibility | None = None,
) -> list[str]:
    if raw_history is None or audit is None:
        effective = _date_range(None, None, reason)
        eligibility = unavailable_schema5_audit_eligibility(reason)
    else:
        effective = _effective_data_range(raw_history)
        eligibility = fresh_schema5_audit_eligibility(raw_history, audit, effective)
    evidence_eligibility = (
        unavailable_evidence(reason) if evidence is None else evidence.to_dict()
    )
    return [
        save_rulebook_result(
            ticker,
            _failed_document(
                config,
                reason,
                eligibility,
                evidence_eligibility,
                effective,
            ),
            config.output_dir,
        )
    ]


def _evaluate_ticker(
    frame: pd.DataFrame,
    config: BacktestConfig,
    confirmation_frame: pd.DataFrame,
) -> ExploratoryEvaluation:
    """Evaluate every gate subset under compulsory no-theme and VN-Index treatments."""

    requested_start, requested_end = _requested_dates(config)
    return evaluate_exploratory_candidates(
        frame,
        horizon=config.horizon,
        requested_start=requested_start,
        requested_end=requested_end,
        theme_eligible=_theme_signal(frame, confirmation_frame),
        permutation_count=config.permutation_count,
        permutation_seed=config.permutation_seed,
        permutation_block_size=config.permutation_block_size,
    )


def _load_confirmation_for_single(
    config: BacktestConfig,
    engine,
    *,
    ticker_history: pd.DataFrame,
) -> tuple[pd.DataFrame, object, pd.DataFrame]:
    vnindex = _load_validated_history("VNINDEX", config, engine)
    _, requested_end = _requested_dates(config)
    common_as_of = latest_common_completed_bar(
        {config.ticker: ticker_history, "VNINDEX": vnindex},
        requested_end,
    )
    return (
        _build_confirmation_frame(
            vnindex,
            config.horizon,
            common_as_of=common_as_of,
        ),
        common_as_of,
        vnindex,
    )


def _error_text(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def run_backtest_pipeline(config: BacktestConfig, report_progress, engine) -> list[str]:
    """Evaluate and atomically persist one schema-5 ticker/horizon aggregate."""

    try:
        raw_history = _load_validated_history(config.ticker, config, engine)
        audit = audit_history(config.ticker, raw_history)
    except Exception as error:
        paths = _persist_failure(config.ticker, config, _error_text(error))
        _report(report_progress, 1.0)
        return paths
    _report(report_progress, 0.1)
    evidence = None
    try:
        confirmation, common_as_of, vnindex_history = _load_confirmation_for_single(
            config,
            engine,
            ticker_history=raw_history,
        )
        frame, audit, raw_history = _prepare_ticker(
            config.ticker,
            config,
            engine,
            common_as_of=common_as_of,
            raw_history=raw_history,
        )
        evidence = assess_evidence(
            raw_history,
            vnindex_history,
            common_as_of,
            ticker=config.ticker,
            audit_eligible=audit.status == "clean",
        )
        evaluation = _evaluate_ticker(frame, config, confirmation)
        paths = _persist_evaluation(
            config.ticker,
            config,
            evaluation,
            raw_history,
            audit,
            evidence,
        )
    except Exception as error:
        paths = _persist_failure(
            config.ticker,
            config,
            _error_text(error),
            raw_history=raw_history,
            audit=audit,
            evidence=evidence,
        )
    _report(report_progress, 1.0)
    return paths


def _shared_confirmation(
    config: BacktestBatchConfig,
    engine,
    *,
    ticker_sources: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, object, pd.DataFrame]:
    """Build one shared VN-Index confirmation, retrying its preflight once."""

    _, requested_end = _requested_dates(config)
    for attempt in range(2):
        try:
            vnindex = _load_validated_history("VNINDEX", config, engine)
            common_as_of = latest_common_completed_bar(
                {**ticker_sources, "VNINDEX": vnindex},
                requested_end,
            )
            return (
                _build_confirmation_frame(
                    vnindex,
                    config.horizon,
                    common_as_of=common_as_of,
                ),
                common_as_of,
                vnindex,
            )
        except Exception as error:
            if attempt == 0:
                time.sleep(5)
                continue
            raise RuntimeError(f"VN-Index preflight failed after retry: {error}") from error
    raise AssertionError("shared confirmation retry loop must return or raise")


def run_backtest_batch_pipeline(
    config: BacktestBatchConfig,
    report_progress,
    engine,
) -> dict[str, object]:
    """Evaluate each ticker against the compulsory shared-treatment rulebook family."""

    statuses = [
        BatchTickerStatus(ticker, attempts=0, state="queued")
        for ticker in config.tickers
    ]
    assign_tickers_group(config.tickers, config.group_name, config.output_dir)

    def report(value: float) -> None:
        _report(report_progress, value, tuple(statuses))

    report(0.0)
    ticker_sources: dict[str, pd.DataFrame] = {}
    for index, ticker in enumerate(config.tickers):
        errors: list[str] = []
        for attempt in range(1, 3):
            try:
                ticker_sources[ticker] = _load_validated_history(ticker, config, engine)
            except Exception as error:
                errors.append(_error_text(error))
            else:
                break
        if ticker not in ticker_sources:
            ticker_config = config.for_ticker(ticker)
            reason = errors[-1]
            paths = _persist_failure(ticker, ticker_config, reason)
            statuses[index] = BatchTickerStatus(
                ticker,
                attempts=2,
                state="failed",
                output_paths=tuple(paths),
                error_texts=tuple(errors),
            )

    if not ticker_sources:
        report(1.0)
        return {
            "output_paths": [path for status in statuses for path in status.output_paths],
            "ticker_results": [status.to_dict() for status in statuses],
        }

    try:
        confirmation, common_as_of, vnindex_history = _shared_confirmation(
            config,
            engine,
            ticker_sources=ticker_sources,
        )
    except Exception as error:
        reason = _error_text(error)
        for index, ticker in enumerate(config.tickers):
            if ticker not in ticker_sources:
                continue
            paths = _persist_failure(ticker, config.for_ticker(ticker), reason)
            statuses[index] = BatchTickerStatus(
                ticker, attempts=1, state="failed", output_paths=tuple(paths), error_texts=(reason,)
            )
        report(1.0)
        return {
            "output_paths": [path for status in statuses for path in status.output_paths],
            "ticker_results": [status.to_dict() for status in statuses],
        }

    report(0.05)

    def run_ticker(index: int, attempts: int) -> None:
        ticker = config.tickers[index]
        ticker_config = config.for_ticker(ticker)
        prior = statuses[index]
        statuses[index] = BatchTickerStatus(
            ticker, attempts=attempts, state="running", output_paths=prior.output_paths,
            error_texts=prior.error_texts,
        )
        raw_history = None
        audit = None
        evidence = None
        try:
            frame, audit, raw_history = _prepare_ticker(
                ticker,
                ticker_config,
                engine,
                common_as_of=common_as_of,
                raw_history=ticker_sources[ticker],
            )
            evidence = assess_evidence(
                raw_history,
                vnindex_history,
                common_as_of,
                ticker=ticker,
                audit_eligible=audit.status == "clean",
            )
            evaluation = _evaluate_ticker(frame, ticker_config, confirmation)
            paths = _persist_evaluation(
                ticker,
                ticker_config,
                evaluation,
                raw_history,
                audit,
                evidence,
            )
        except Exception as error:
            reason = _error_text(error)
            paths = _persist_failure(
                ticker,
                ticker_config,
                reason,
                raw_history=raw_history,
                audit=audit,
                evidence=evidence,
            )
            statuses[index] = BatchTickerStatus(
                ticker,
                attempts=attempts,
                state="failed",
                output_paths=tuple(paths),
                error_texts=(*prior.error_texts, reason),
            )
        else:
            statuses[index] = BatchTickerStatus(
                ticker, attempts=attempts, state="done", output_paths=tuple(paths)
            )

    run_indexes = [
        index for index, ticker in enumerate(config.tickers)
        if ticker in ticker_sources
    ]
    for position, index in enumerate(run_indexes, start=1):
        run_ticker(index, 1)
        report(0.05 + 0.65 * position / len(run_indexes))

    retry_indexes = [
        index for index, status in enumerate(statuses)
        if status.state == "failed" and config.tickers[index] in ticker_sources
    ]
    for retry_number, index in enumerate(retry_indexes, start=1):
        run_ticker(index, 2)
        report(0.70 + 0.30 * retry_number / len(retry_indexes))

    report(1.0)
    return {
        "output_paths": [path for status in statuses for path in status.output_paths],
        "ticker_results": [status.to_dict() for status in statuses],
    }


def _validate_database_url(database_url: str) -> str:
    """Reject URL ports that SQLAlchemy would otherwise parse during connect."""

    try:
        make_url(database_url).port
    except (TypeError, ValueError) as error:
        raise RuntimeError("DATABASE_URL has an invalid port") from error
    return database_url


def _database_url() -> str:
    existing = os.getenv("DATABASE_URL")
    if existing:
        return _validate_database_url(existing)
    values = {
        key: os.getenv(key)
        for key in (
            "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB"
        )
    }
    if not all(values.values()):
        raise RuntimeError("database connection environment is incomplete")
    database_url = (
        f"postgresql://{values['POSTGRES_USER']}:{values['POSTGRES_PASSWORD']}"
        f"@{values['POSTGRES_HOST']}:{values['POSTGRES_PORT']}/{values['POSTGRES_DB']}"
    )
    return _validate_database_url(database_url)


def run_backtest_from_env(config, report_progress):
    """Spawn-safe factory used by the standalone page and scheduled jobs."""

    from pages.data_preparation import get_engine_with_retry

    engine = get_engine_with_retry(_database_url())
    try:
        return run_backtest_pipeline(config, report_progress, engine)
    finally:
        engine.dispose()


def run_backtest_batch_from_env(config, report_progress):
    """Spawn-safe factory for one sequential batch worker request."""

    from pages.data_preparation import get_engine_with_retry

    engine = get_engine_with_retry(_database_url())
    try:
        return run_backtest_batch_pipeline(config, report_progress, engine)
    finally:
        engine.dispose()


__all__ = [
    "run_backtest_batch_from_env",
    "run_backtest_batch_pipeline",
    "run_backtest_from_env",
    "run_backtest_pipeline",
]
