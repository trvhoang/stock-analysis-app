"""Read-only empirical comparison of legacy and current trend labels."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import text


WINDOWS = ((5, 5), (10, 5), (20, 10))
MINIMUM_TICKER_ROWS = 260
DEFAULT_TICKER_LIMIT = 64
EXCLUDED_TICKER = "VNINDEX"
RECORD_COLUMNS = (
    "ticker",
    "validation_days",
    "result_days",
    "signal_date",
    "start_date",
    "end_date",
    "current_delta",
    "total_signals",
    "possibility_up",
    "possibility_down",
)

TICKER_QUERY = text(
    """
    SELECT ticker
    FROM trading_data
    WHERE ticker <> :excluded_ticker
    GROUP BY ticker
    HAVING COUNT(*) >= :minimum_rows
    ORDER BY ticker
    LIMIT :ticker_limit
    """
)


def _raw_connection_query(statement, params):
    """Adapt SQLAlchemy bind markers for the existing raw-connection convention."""
    query = statement.text
    for name in params:
        query = query.replace(f":{name}", f"%({name})s")
    return query


def select_tickers(
    engine,
    limit=DEFAULT_TICKER_LIMIT,
    minimum_rows=MINIMUM_TICKER_ROWS,
    excluded_ticker=EXCLUDED_TICKER,
):
    """Select a stable, bounded ticker sample without changing database state."""
    bounded_limit = max(0, min(int(limit), DEFAULT_TICKER_LIMIT))
    params = {
        "excluded_ticker": excluded_ticker,
        "minimum_rows": minimum_rows,
        "ticker_limit": bounded_limit,
    }
    conn = engine.raw_connection()
    try:
        frame = pd.read_sql(_raw_connection_query(TICKER_QUERY, params), conn, params=params)
    finally:
        conn.close()
    return sorted(frame["ticker"].dropna().astype(str).tolist())


def _has_valid_signals(result):
    if not result or "total_signals" not in result:
        return False
    try:
        return not pd.isna(result["total_signals"]) and result["total_signals"] > 0
    except (TypeError, ValueError):
        return False


def collect_probability_records(tickers, windows, engine, analyzer=None):
    """Collect analyzer observations, retaining exclusions for transparent reporting."""
    if analyzer is None:
        from commons.common_functions import analyze_ticker

        analyzer = analyze_ticker

    records = []
    excluded = []
    ordered_tickers = sorted(dict.fromkeys(tickers))
    ordered_windows = sorted(dict.fromkeys(windows))

    for ticker in ordered_tickers:
        for validation_days, result_days in ordered_windows:
            context = {
                "ticker": ticker,
                "validation_days": validation_days,
                "result_days": result_days,
            }
            try:
                result = analyzer(ticker, validation_days, result_days, engine)
            except Exception as error:
                excluded.append({**context, "reason": str(error)})
                continue

            if not _has_valid_signals(result):
                excluded.append({**context, "reason": "no valid signals"})
                continue

            records.append(
                {
                    **context,
                    "signal_date": result["end_date"],
                    "start_date": result.get("start_date"),
                    "end_date": result["end_date"],
                    "current_delta": result["current_delta"],
                    "total_signals": result["total_signals"],
                    "possibility_up": result["possibility_up"],
                    "possibility_down": result["possibility_down"],
                }
            )

    return pd.DataFrame(records, columns=RECORD_COLUMNS), excluded


def _database_url():
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        return configured_url
    return (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=DEFAULT_TICKER_LIMIT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/superpowers/reports/2026-08-02-trend-classification-validation-data.csv"),
    )
    args = parser.parse_args(argv)

    from commons.common_functions import analyze_ticker
    from pages.data_preparation import get_engine_with_retry

    engine = get_engine_with_retry(_database_url())
    tickers = select_tickers(engine, limit=args.limit)
    records, excluded = collect_probability_records(tickers, WINDOWS, engine, analyzer=analyze_ticker)

    from commons.validation import compare_trend_classifications

    output = compare_trend_classifications(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(
        {
            "ticker_count": len(tickers),
            "windows": WINDOWS,
            "valid_rows": len(output),
            "excluded_rows": len(excluded),
            "output": str(args.output),
        }
    )


if __name__ == "__main__":
    main()
