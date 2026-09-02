"""Immutable schema-5 source identity and evidence-density assessment."""

from dataclasses import dataclass
from datetime import date
import hashlib

import numpy as np
import pandas as pd


_RAW_COLUMNS = ("open", "high", "low", "close", "volume")
_REQUIRED_COLUMNS = ("date", *_RAW_COLUMNS)


@dataclass(frozen=True)
class EvidenceEligibility:
    """One common-as-of source identity and BUY-safety assessment."""

    status: str
    eligible: bool
    reasons: tuple[str, ...]
    common_as_of: date
    first_available_bar: date
    last_available_bar: date
    ticker_fingerprint: str
    vnindex_fingerprint: str
    observed_sessions: int
    expected_sessions: int
    coverage_ratio: float
    max_gap_sessions: int

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "common_as_of": self.common_as_of.isoformat(),
            "first_available_bar": self.first_available_bar.isoformat(),
            "last_available_bar": self.last_available_bar.isoformat(),
            "ticker_fingerprint": self.ticker_fingerprint,
            "vnindex_fingerprint": self.vnindex_fingerprint,
            "observed_sessions": self.observed_sessions,
            "expected_sessions": self.expected_sessions,
            "coverage_ratio": self.coverage_ratio,
            "max_gap_sessions": self.max_gap_sessions,
        }


def _canonical_rows(frame: pd.DataFrame, common_as_of: date) -> pd.DataFrame:
    """Return sorted effective raw rows with exact integer numeric values."""

    if not isinstance(frame, pd.DataFrame):
        raise ValueError("source history must be a pandas DataFrame")
    missing = [column for column in _REQUIRED_COLUMNS if column not in frame]
    if missing:
        raise ValueError("source history missing columns: " + ", ".join(missing))
    working = frame.loc[:, _REQUIRED_COLUMNS].copy(deep=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if working["date"].isna().any():
        raise ValueError("source history contains an invalid date")
    working = working.loc[
        working["date"].le(pd.Timestamp(common_as_of))
    ].copy()
    if working.empty:
        raise ValueError("source history has no row through common_as_of")
    if working["date"].duplicated().any():
        raise ValueError("source history contains duplicate effective dates")
    for column in _RAW_COLUMNS:
        numeric = pd.to_numeric(working[column], errors="coerce")
        values = numeric.to_numpy(dtype=float)
        if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
            raise ValueError(f"{column} must contain raw integer values")
        working[column] = numeric.map(int)
    return working.sort_values("date").reset_index(drop=True)


def source_fingerprint(
    ticker: str,
    frame: pd.DataFrame,
    common_as_of: date,
) -> str:
    """Hash ticker plus canonical ordered raw integer tuples through cutoff."""

    normalized = str(ticker).strip().upper()
    if not normalized:
        raise ValueError("ticker must be non-empty")
    rows = _canonical_rows(frame, common_as_of)
    digest = hashlib.sha256()
    for row in rows.itertuples(index=False):
        fields = (
            normalized,
            pd.Timestamp(row.date).date().isoformat(),
            *(str(getattr(row, column)) for column in _RAW_COLUMNS),
        )
        digest.update(("|".join(fields) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _maximum_missing_run(expected: pd.Series, observed: set[pd.Timestamp]) -> int:
    maximum = 0
    current = 0
    for session in expected:
        if pd.Timestamp(session) in observed:
            current = 0
        else:
            current += 1
            maximum = max(maximum, current)
    return maximum


def assess_evidence(
    ticker_frame: pd.DataFrame,
    vnindex_frame: pd.DataFrame,
    common_as_of: date,
    *,
    ticker: str = "TICKER",
    audit_eligible: bool = True,
) -> EvidenceEligibility:
    """Assess effective ticker density against VN-Index session evidence."""

    ticker_rows = _canonical_rows(ticker_frame, common_as_of)
    vnindex_rows = _canonical_rows(vnindex_frame, common_as_of)
    common = pd.Timestamp(common_as_of).date()
    first = pd.Timestamp(ticker_rows["date"].iloc[0]).date()
    last = pd.Timestamp(ticker_rows["date"].iloc[-1]).date()
    expected_dates = vnindex_rows.loc[
        vnindex_rows["date"].ge(pd.Timestamp(first))
        & vnindex_rows["date"].le(pd.Timestamp(common)),
        "date",
    ].reset_index(drop=True)
    if expected_dates.empty:
        raise ValueError("VN-Index has no effective sessions for ticker interval")
    observed_dates = {
        pd.Timestamp(value) for value in ticker_rows["date"].tolist()
    }
    observed_sessions = sum(
        pd.Timestamp(session) in observed_dates for session in expected_dates
    )
    expected_sessions = len(expected_dates)
    coverage_ratio = observed_sessions / expected_sessions
    max_gap_sessions = _maximum_missing_run(expected_dates, observed_dates)
    reasons = []
    if last != common:
        reasons.append("latest_bar_mismatch")
    if coverage_ratio < 0.95:
        reasons.append("coverage_ratio_below_0.95")
    if max_gap_sessions > 20:
        reasons.append("max_gap_sessions_exceeds_20")
    if not audit_eligible:
        reasons.append("raw_audit_not_clean")
    eligible = not reasons
    return EvidenceEligibility(
        status="eligible" if eligible else "ineligible",
        eligible=eligible,
        reasons=tuple(reasons),
        common_as_of=common,
        first_available_bar=first,
        last_available_bar=last,
        ticker_fingerprint=source_fingerprint(ticker, ticker_rows, common),
        vnindex_fingerprint=source_fingerprint("VNINDEX", vnindex_rows, common),
        observed_sessions=observed_sessions,
        expected_sessions=expected_sessions,
        coverage_ratio=coverage_ratio,
        max_gap_sessions=max_gap_sessions,
    )


def unavailable_evidence(reason: str) -> dict[str, object]:
    """Return strict schema-5 evidence metadata when sources are unavailable."""

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("unavailable evidence reason must be non-empty")
    return {
        "status": "unavailable",
        "eligible": False,
        "reasons": [reason],
        "common_as_of": None,
        "first_available_bar": None,
        "last_available_bar": None,
        "ticker_fingerprint": None,
        "vnindex_fingerprint": None,
        "observed_sessions": 0,
        "expected_sessions": 0,
        "coverage_ratio": 0.0,
        "max_gap_sessions": 0,
    }


__all__ = [
    "EvidenceEligibility",
    "assess_evidence",
    "source_fingerprint",
    "unavailable_evidence",
]
