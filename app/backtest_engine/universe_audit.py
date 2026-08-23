"""Read-only audit and deterministic selection of compact-strategy tickers."""

from datetime import date, datetime
from statistics import median
from typing import Iterable

import pandas as pd
import pytz
from sqlalchemy import text

from .data_quality import (
    TickerAudit,
    audit_history,
    history_coverage_years,
    load_ticker_history,
)

CANARY_TICKER = "VCB"
_ROSTER_HISTORY_START = date(1900, 1, 1)
_OHLCV_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def load_audit_candidates(
    engine,
    start_date: date,
    end_date: date,
) -> dict[str, pd.DataFrame]:
    """Load all candidate OHLCV in one bounded raw-connection query."""

    query = text(
        """
        SELECT ticker, date, open, high, low, close, volume
        FROM trading_data
        WHERE ticker <> %(index_ticker)s
          AND date >= %(start_date)s
          AND date <= %(end_date)s
        ORDER BY ticker ASC, date ASC
        """
    )
    connection = engine.raw_connection()
    try:
        rows = pd.read_sql(
            query.text,
            connection,
            params={
                "index_ticker": "VNINDEX",
                "start_date": start_date,
                "end_date": end_date,
            },
        )
    finally:
        connection.close()

    if rows.empty:
        return {}
    return {
        str(ticker).strip().upper(): group.drop(columns="ticker").reset_index(drop=True)
        for ticker, group in rows.groupby("ticker", sort=True)
    }


def load_frozen_roster_histories(
    tickers: Iterable[str],
    start_date: date,
    end_date: date,
    engine,
) -> dict[str, pd.DataFrame]:
    """Load the fixed audit roster in one bounded, parameterized DB read."""

    roster = tuple(str(ticker).strip().upper() for ticker in tickers)
    if not roster or any(not ticker for ticker in roster):
        raise ValueError("frozen roster must contain non-empty tickers")
    if len(set(roster)) != len(roster):
        raise ValueError("frozen roster must not contain duplicate tickers")

    query = text(
        """
        SELECT ticker, date, open, high, low, close, volume
        FROM trading_data
        WHERE ticker = ANY(%(tickers)s)
          AND date >= %(start_date)s
          AND date <= %(end_date)s
        ORDER BY ticker ASC, date ASC
        """
    )
    connection = engine.raw_connection()
    try:
        rows = pd.read_sql(
            query.text,
            connection,
            params={
                "tickers": list(roster),
                "start_date": start_date,
                "end_date": end_date,
            },
        )
    finally:
        connection.close()

    histories = {
        ticker: pd.DataFrame(columns=_OHLCV_COLUMNS)
        for ticker in roster
    }
    if rows.empty:
        return histories
    histories.update(
        {
            str(ticker).strip().upper(): group.drop(columns="ticker").reset_index(
                drop=True
            )
            for ticker, group in rows.groupby("ticker", sort=False)
        }
    )
    return histories


def audit_candidates(
    candidates: dict[str, pd.DataFrame],
) -> tuple[TickerAudit, ...]:
    """Audit every candidate against the shared available database history."""

    start_dates = [
        pd.to_datetime(frame["date"]).min().date()
        for frame in candidates.values()
        if not frame.empty
    ]
    terminal_dates = [
        pd.to_datetime(frame["date"]).max().date()
        for frame in candidates.values()
        if not frame.empty
    ]
    if not start_dates or not terminal_dates:
        return ()
    expected_start_date = min(start_dates)
    expected_terminal_date = max(terminal_dates)
    return tuple(
        audit_history(
            ticker,
            frame,
            required_start_date=expected_start_date,
            expected_terminal_date=expected_terminal_date,
        )
        for ticker, frame in sorted(candidates.items())
    )


def audit_frozen_roster(
    tickers: Iterable[str],
    engine,
    *,
    today: date | None = None,
) -> tuple[dict[str, object], ...]:
    """Audit the literal research roster without selecting or writing anything."""

    roster = tuple(str(ticker).strip().upper() for ticker in tickers)
    if not roster or any(not ticker for ticker in roster):
        raise ValueError("frozen roster must contain non-empty tickers")
    if len(set(roster)) != len(roster):
        raise ValueError("frozen roster must not contain duplicate tickers")

    as_of_date = today or datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).date()
    histories = load_frozen_roster_histories(
        roster,
        _ROSTER_HISTORY_START,
        as_of_date,
        engine,
    )
    reports = []
    for ticker in roster:
        raw_history = histories[ticker]
        audit = (
            audit_history(ticker, raw_history)
            if not raw_history.empty
            else TickerAudit(
                ticker=ticker,
                status="invalid",
                source_row_count=0,
                first_date=None,
                last_date=None,
                pre_2021_return_pct=None,
                errors=("no raw history returned for frozen roster ticker",),
            )
        )
        coverage = history_coverage_years(raw_history, today=as_of_date)
        reports.append(
            {
                "ticker": ticker,
                "price_audit_clean": audit.status == "clean",
                "study_history_sufficient": (
                    coverage["swing_history_years"] >= 5
                    and coverage["midterm_history_years"] >= 8
                ),
                "swing_history_years": coverage["swing_history_years"],
                "midterm_history_years": coverage["midterm_history_years"],
                "audit_status": audit.status,
                "source_row_count": audit.source_row_count,
                "first_date": audit.first_date.isoformat() if audit.first_date else None,
                "last_date": audit.last_date.isoformat() if audit.last_date else None,
                "errors": list(audit.errors),
                "warnings": list(audit.warnings),
            }
        )
    return tuple(reports)


def select_frozen_universe(audits: Iterable[TickerAudit]) -> tuple[str, ...]:
    """Return VCB plus fixed high, low, and median-return clean candidates."""

    clean = sorted(
        (
            audit
            for audit in audits
            if audit.status == "clean" and audit.pre_2021_return_pct is not None
        ),
        key=lambda audit: audit.ticker,
    )
    by_ticker = {audit.ticker: audit for audit in clean}
    if CANARY_TICKER not in by_ticker:
        raise ValueError("VCB must be a clean audit canary")
    if len(clean) < 8:
        raise ValueError("at least eight clean tickers are required")

    candidates = [audit for audit in clean if audit.ticker != CANARY_TICKER]
    highest = sorted(
        candidates,
        key=lambda audit: (-float(audit.pre_2021_return_pct), audit.ticker),
    )[:2]
    lowest = sorted(
        (audit for audit in candidates if audit not in highest),
        key=lambda audit: (float(audit.pre_2021_return_pct), audit.ticker),
    )[:2]
    occupied = {audit.ticker for audit in (*highest, *lowest)}
    return_median = float(median(audit.pre_2021_return_pct for audit in clean))
    middle = sorted(
        (audit for audit in candidates if audit.ticker not in occupied),
        key=lambda audit: (
            abs(float(audit.pre_2021_return_pct) - return_median),
            audit.ticker,
        ),
    )[:3]
    if len(highest) != 2 or len(lowest) != 2 or len(middle) != 3:
        raise ValueError("at least seven non-VCB clean tickers are required")
    return (
        CANARY_TICKER,
        *(audit.ticker for audit in highest),
        *(audit.ticker for audit in lowest),
        *(audit.ticker for audit in middle),
    )


__all__ = [
    "CANARY_TICKER",
    "audit_frozen_roster",
    "audit_candidates",
    "load_audit_candidates",
    "load_frozen_roster_histories",
    "select_frozen_universe",
]
