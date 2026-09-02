"""Profile one schema-5 Backtest evaluation without persisting product artifacts."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import pytz
from dotenv import load_dotenv


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPOSITORY_ROOT / "app"
if not (APP_ROOT / "backtest_engine").is_dir():
    APP_ROOT = REPOSITORY_ROOT
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

load_dotenv(REPOSITORY_ROOT / ".env")

import backtest_engine.exploratory as exploratory
import backtest_engine.indicators as indicators
from backtest_engine.config import BacktestConfig, rulebook_for
from backtest_engine.data_quality import audit_history
from backtest_engine.evidence import assess_evidence
from backtest_engine.pipeline import (
    _build_confirmation_frame,
    _database_url,
    _evaluate_ticker,
    _load_validated_history,
)
from backtest_engine.rolling_window import run_rulebook_trade_sequence_reference
from backtest_engine.timeframes import latest_common_completed_bar
from backtest_engine.validation import moving_block_permutation_test_reference
from pages.data_preparation import get_engine_with_retry


def _stable_digest(payload: object) -> str:
    """Hash one canonical JSON value for semantic parity comparisons."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _timing_summary(samples: tuple[float, ...]) -> dict[str, float]:
    """Return deterministic p50/p95 wall-clock summaries."""

    if not samples:
        raise ValueError("at least one timing sample is required")
    values = np.asarray(samples, dtype=float)
    if not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("timing samples must be finite and non-negative")
    return {
        "p50_seconds": float(np.percentile(values, 50)),
        "p95_seconds": float(np.percentile(values, 95)),
    }


def _peak_rss_mb() -> float | None:
    """Return process peak resident memory on the Linux benchmark runtime."""

    try:
        import resource
    except ImportError:
        return None
    # Linux reports ru_maxrss in KiB. The approved benchmark runs in Docker/Linux.
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


@contextmanager
def _runtime_mode(mode: str):
    """Temporarily select reference callables without changing public APIs."""

    if mode not in {"reference", "optimized"}:
        raise ValueError("mode must be reference or optimized")
    if mode == "optimized":
        yield
        return

    originals = (
        exploratory.run_rulebook_trade_sequence,
        exploratory.moving_block_permutation_test,
        indicators._smma,
        indicators._wilder_average,
    )
    exploratory.run_rulebook_trade_sequence = run_rulebook_trade_sequence_reference
    exploratory.moving_block_permutation_test = moving_block_permutation_test_reference
    indicators._smma = indicators._smma_reference
    indicators._wilder_average = indicators._wilder_average_reference
    try:
        yield
    finally:
        (
            exploratory.run_rulebook_trade_sequence,
            exploratory.moving_block_permutation_test,
            indicators._smma,
            indicators._wilder_average,
        ) = originals


def _evaluation_payload(evaluation) -> dict[str, object]:
    """Project all values whose equality is required for optimization acceptance."""

    return {
        "split": evaluation.split.to_dict(),
        "candidates": [candidate.to_dict() for candidate in evaluation.candidates],
        "top_rulebook_ids": list(evaluation.top_rulebook_ids),
    }


def _top_trade_count(evaluation) -> int:
    """Count completed train/test trades for the first preferred Top-3 rulebook."""

    if not evaluation.top_rulebook_ids:
        return 0
    top_id = evaluation.top_rulebook_ids[0]
    candidate = next(item for item in evaluation.candidates if item.rule_id == top_id)
    return candidate.preferred.training.n + candidate.preferred.test.n


def profile(args) -> dict[str, object]:
    """Load sources once and time repeated non-persisting schema-5 evaluations."""

    end_date = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).date()
    start_date = (pd.Timestamp(end_date) - pd.DateOffset(years=15)).date()
    config = BacktestConfig(
        ticker=args.ticker,
        start_date=start_date,
        end_date=end_date,
        horizon=args.horizon,
        permutation_count=args.permutations,
        permutation_seed=args.seed,
        permutation_block_size=args.block_size,
        worker_count=1,
    )
    engine = get_engine_with_retry(_database_url())
    try:
        load_started = time.perf_counter()
        ticker_history = _load_validated_history(config.ticker, config, engine)
        vnindex_history = _load_validated_history("VNINDEX", config, engine)
        common_as_of = latest_common_completed_bar(
            {config.ticker: ticker_history, "VNINDEX": vnindex_history},
            end_date,
        )
        database_seconds = time.perf_counter() - load_started
        audit = audit_history(config.ticker, ticker_history)
        evidence = assess_evidence(
            ticker_history,
            vnindex_history,
            common_as_of,
            ticker=config.ticker,
            audit_eligible=audit.status == "clean",
        )
        confirmation = _build_confirmation_frame(
            vnindex_history,
            config.horizon,
            common_as_of=common_as_of,
        )

        samples: list[float] = []
        payload = None
        with _runtime_mode(args.mode):
            for _ in range(args.repeats):
                started = time.perf_counter()
                frame = indicators.build_rulebook_frame(
                    ticker_history,
                    rulebook_for(config.horizon),
                    common_as_of=common_as_of,
                )
                evaluation = _evaluate_ticker(frame, config, confirmation)
                samples.append(time.perf_counter() - started)
                current_payload = _evaluation_payload(evaluation)
                if payload is not None and current_payload != payload:
                    raise RuntimeError("repeated profile evaluation changed semantic output")
                payload = current_payload
        if payload is None:
            raise RuntimeError("profile produced no evaluation")

        result = {
            "schema_version": 1,
            "kind": "backtest_schema5_runtime_profile",
            "mode": args.mode,
            "ticker": config.ticker,
            "horizon": config.horizon,
            "permutations": config.permutation_count,
            "repeats": args.repeats,
            "common_as_of": common_as_of.isoformat(),
            "database_seconds": database_seconds,
            **_timing_summary(tuple(samples)),
            "samples_seconds": samples,
            "peak_rss_mb": _peak_rss_mb(),
            "trade_count": _top_trade_count(evaluation),
            "candidate_count": len(evaluation.candidates),
            "top_rulebook_ids": list(evaluation.top_rulebook_ids),
            "artifact_digest": _stable_digest(payload),
            "ticker_fingerprint": evidence.ticker_fingerprint,
            "vnindex_fingerprint": evidence.vnindex_fingerprint,
            "evidence_status": evidence.status,
            "evidence_reasons": list(evidence.reasons),
        }
        return result
    finally:
        engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--horizon", choices=("swing", "midterm"), required=True)
    parser.add_argument("--permutations", type=int, default=1000)
    parser.add_argument("--mode", choices=("reference", "optimized"), required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--block-size", type=int, default=20)
    return parser


def main(argv=None) -> None:
    args = _parser().parse_args(argv)
    if args.permutations < 1 or args.repeats < 1 or args.block_size < 1:
        raise SystemExit("permutations, repeats, and block-size must be positive")
    print(json.dumps(profile(args), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
