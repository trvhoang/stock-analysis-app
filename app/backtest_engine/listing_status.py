"""Live ticker listing status derived from the latest VN-Index session."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd
from sqlalchemy import text

from .config import _normalize_ticker


class VNIndexListingStatusUnavailable(RuntimeError):
    """Raised when a live Listed/Delisted comparison has no VN-Index anchor."""


def _date_only(value: object) -> date | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed).date()


@dataclass(frozen=True)
class ListingStatus:
    """One non-persistent live comparison against VN-Index's latest session."""

    ticker: str
    state: str
    ticker_latest: date | None
    vnindex_latest: date

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        if self.state not in {"listed", "delisted"}:
            raise ValueError("listing state must be listed or delisted")
        if self.ticker_latest is not None and not isinstance(self.ticker_latest, date):
            raise ValueError("ticker_latest must be a date or None")
        if not isinstance(self.vnindex_latest, date):
            raise ValueError("vnindex_latest must be a date")
        expected = "listed" if self.ticker_latest == self.vnindex_latest else "delisted"
        if self.state != expected:
            raise ValueError("listing state must match the latest-session comparison")

    @property
    def is_listed(self) -> bool:
        return self.state == "listed"

    @property
    def reason(self) -> str:
        if self.is_listed:
            return f"Listed: ticker and VN-Index latest session {self.vnindex_latest.isoformat()}."
        ticker_latest = (
            "ticker has no latest session"
            if self.ticker_latest is None
            else f"ticker latest {self.ticker_latest.isoformat()}"
        )
        return f"Delisted: {ticker_latest}; VN-Index latest {self.vnindex_latest.isoformat()}."

    def to_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "state": self.state,
            "ticker_latest": None if self.ticker_latest is None else self.ticker_latest.isoformat(),
            "vnindex_latest": self.vnindex_latest.isoformat(),
            "reason": self.reason,
        }


def load_listing_statuses(
    tickers: Sequence[str],
    engine,
) -> dict[str, ListingStatus]:
    """Return each requested ticker's live status from one parameterized query."""

    if isinstance(tickers, (str, bytes)) or not isinstance(tickers, Sequence):
        raise ValueError("tickers must be a sequence")
    normalized = tuple(dict.fromkeys(_normalize_ticker(ticker) for ticker in tickers))
    if not normalized:
        raise ValueError("tickers must contain at least one ticker")
    query = text(
        """
        SELECT ticker, MAX(date) AS latest_session
        FROM trading_data
        WHERE ticker = 'VNINDEX'
           OR ticker = ANY(%(tickers)s)
        GROUP BY ticker
        """
    )
    connection = engine.raw_connection()
    try:
        rows = pd.read_sql(query.text, connection, params={"tickers": list(normalized)})
    finally:
        connection.close()
    latest_by_ticker = {
        str(row.ticker).strip().upper(): _date_only(row.latest_session)
        for row in rows.itertuples(index=False)
    }
    vnindex_latest = latest_by_ticker.get("VNINDEX")
    if vnindex_latest is None:
        raise VNIndexListingStatusUnavailable(
            "VN-Index latest trading session is unavailable; Listed/Delisted status cannot be determined."
        )
    return {
        ticker: ListingStatus(
            ticker=ticker,
            state="listed" if latest_by_ticker.get(ticker) == vnindex_latest else "delisted",
            ticker_latest=latest_by_ticker.get(ticker),
            vnindex_latest=vnindex_latest,
        )
        for ticker in normalized
    }


__all__ = ["ListingStatus", "VNIndexListingStatusUnavailable", "load_listing_statuses"]
