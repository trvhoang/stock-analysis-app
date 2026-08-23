"""Write a read-only FPT Backtest funnel report to an explicit JSON path."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import pandas as pd
import pytz
from dotenv import load_dotenv


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPOSITORY_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

load_dotenv(REPOSITORY_ROOT / ".env")

from backtest_engine.config import BacktestConfig
from backtest_engine.diagnostics import collect_backtest_diagnostics
from backtest_engine.pipeline import _database_url
from pages.data_preparation import get_engine_with_retry


def _config_from_args(args) -> BacktestConfig:
    end_date = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).date()
    start_date = (pd.Timestamp(end_date) - pd.DateOffset(years=args.years)).date()
    theme_variant = "background-theme" if args.theme_mode else "no-background-theme"
    return BacktestConfig(
        ticker=args.ticker,
        start_date=start_date,
        end_date=end_date,
        horizon=args.horizon,
        theme_variant=theme_variant,
        theme_mode=args.theme_mode,
    )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--horizon", choices=("swing", "midterm"), required=True)
    parser.add_argument("--years", choices=(5, 15), type=int, required=True)
    parser.add_argument("--theme-mode", choices=("AND", "OR"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = _config_from_args(args)
    engine = get_engine_with_retry(_database_url())
    try:
        report = collect_backtest_diagnostics(config, engine)
    finally:
        engine.dispose()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        {
            "ticker": report["ticker"],
            "theme_mode": report["theme_mode"],
            "combo_count": report["combo_count"],
            "window_count": report["window_count"],
            "elapsed_seconds": report["elapsed_seconds"],
            "output": str(args.output),
        }
    )


if __name__ == "__main__":
    main()
