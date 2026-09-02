"""Data-quality gate and raw BIGINT history loading for backtest runs."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pandas as pd
import pytz
from sqlalchemy import text

REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")
MAX_UNEXPLAINED_MOVE = 0.07
GAP_WARNING_DAYS = 7
PRICE_AUDIT_CLOSE_MOVE_THRESHOLD = 0.15
MAX_MINOR_OHLC_MISMATCH = 0.01
PRE_2021_END = date(2020, 12, 31)


@dataclass(frozen=True)
class PriceAuditFinding:
    """One DB-visible discontinuity; it cannot prove adjustment status."""

    date: date
    close_return_pct: float
    close_ratio: float
    volume_ratio: Optional[float]
    intraday_range_pct: float


@dataclass(frozen=True)
class TickerAudit:
    """Read-only continuity and coverage result for one ticker history."""

    ticker: str
    status: str
    source_row_count: int
    first_date: Optional[date]
    last_date: Optional[date]
    pre_2021_return_pct: Optional[float]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    findings: tuple[PriceAuditFinding, ...] = ()


@dataclass(frozen=True)
class DataQualityReport:
    """Validation result; warnings preserve a usable frame for review."""

    valid_frame: Optional[pd.DataFrame]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_ohlcv(frame: pd.DataFrame) -> DataQualityReport:
    """Validate OHLCV structure without mutating the caller-owned frame."""

    if not isinstance(frame, pd.DataFrame):
        return DataQualityReport(None, ("OHLCV input must be a pandas DataFrame",))

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        return DataQualityReport(
            None,
            (f"missing required columns: {', '.join(missing)}",),
        )

    working = frame.copy(deep=True)
    errors: list[str] = []
    warnings: list[str] = []

    parsed_dates = pd.to_datetime(working["date"], errors="coerce")
    if parsed_dates.isna().any():
        errors.append("date contains missing or invalid values")
    elif parsed_dates.duplicated().any():
        errors.append("date contains duplicate values")
    elif not parsed_dates.is_monotonic_increasing:
        errors.append("date values must be in ascending order")
    else:
        working["date"] = parsed_dates

        # ponytail: without an exchange calendar, flag only long calendar gaps;
        # weekends and ordinary holidays remain explicit data, not false errors.
        gaps = parsed_dates.diff().dt.days.dropna()
        for position, gap_days in gaps.items():
            if gap_days > GAP_WARNING_DAYS:
                warnings.append(
                    f"date gap of {int(gap_days)} calendar days before "
                    f"{parsed_dates.loc[position].date().isoformat()}"
                )

    numeric_columns = (*PRICE_COLUMNS, "volume")
    numeric = {}
    for column in numeric_columns:
        numeric[column] = pd.to_numeric(working[column], errors="coerce")

    for column in PRICE_COLUMNS:
        if numeric[column].isna().any():
            errors.append(f"{column} contains missing or non-numeric prices")
        elif (numeric[column] <= 0).any():
            errors.append(f"{column} contains non-positive prices")

    if numeric["volume"].isna().any():
        errors.append("volume contains missing or non-numeric values")
    elif (numeric["volume"] < 0).any():
        errors.append("volume contains negative values")
    elif (numeric["volume"] == 0).any():
        warnings.append("zero volume rows present")

    if not errors:
        previous_close = numeric["close"].shift(1)
        move = ((numeric["close"] - previous_close) / previous_close).abs()
        for position, magnitude in move[move > MAX_UNEXPLAINED_MOVE].items():
            warnings.append(
                f"close move exceeds 7% on "
                f"{parsed_dates.loc[position].date().isoformat()}: "
                f"{magnitude:.2%}"
            )

    if errors:
        return DataQualityReport(None, tuple(errors), tuple(warnings))
    return DataQualityReport(working, (), tuple(warnings))


def _ohlc_ordering_relative_mismatch(frame: pd.DataFrame) -> pd.Series:
    """Return each raw OHLC ordering gap as a fraction of that bar's price."""

    numeric = {
        column: pd.to_numeric(frame[column], errors="coerce")
        for column in PRICE_COLUMNS
    }
    body_high = pd.concat([numeric["open"], numeric["close"]], axis=1).max(axis=1)
    body_low = pd.concat([numeric["open"], numeric["close"]], axis=1).min(axis=1)
    mismatch = pd.concat(
        [
            body_high - numeric["high"],
            numeric["low"] - body_low,
            numeric["low"] - numeric["high"],
        ],
        axis=1,
    ).clip(lower=0).max(axis=1)
    scale = pd.concat(list(numeric.values()), axis=1).max(axis=1)
    return mismatch.div(scale)


def normalize_ohlc_for_backtest(frame: pd.DataFrame) -> pd.DataFrame:
    """Create a derived valid OHLC envelope; raw database values stay unchanged."""

    working = frame.copy(deep=True)
    numeric = {
        column: pd.to_numeric(working[column], errors="coerce")
        for column in PRICE_COLUMNS
    }
    working["high"] = pd.concat(
        [numeric["high"], numeric["open"], numeric["close"]], axis=1
    ).max(axis=1)
    working["low"] = pd.concat(
        [numeric["low"], numeric["open"], numeric["close"]], axis=1
    ).min(axis=1)
    return working


def history_coverage_years(
    frame: pd.DataFrame,
    *,
    today: Optional[date] = None,
) -> dict[str, float]:
    """Measure daily and completed W-FRI history spans without changing raw rows."""

    quality = validate_ohlcv(frame)
    if not quality.is_valid or quality.valid_frame is None:
        return {"swing_history_years": 0.0, "midterm_history_years": 0.0}

    dates = pd.DatetimeIndex(pd.to_datetime(quality.valid_frame["date"]))
    if dates.empty:
        return {"swing_history_years": 0.0, "midterm_history_years": 0.0}

    as_of_date = today or datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).date()
    weekly_labels = pd.Series(1, index=dates).resample("W-FRI").size().index
    # A Friday label is complete only after its local calendar day has passed.
    closed_weekly_labels = weekly_labels[weekly_labels < pd.Timestamp(as_of_date)]

    def elapsed_years(labels: pd.DatetimeIndex) -> float:
        if len(labels) < 2:
            return 0.0
        start = pd.Timestamp(labels[0])
        end = pd.Timestamp(labels[-1])
        full_years = end.year - start.year
        anniversary = start + pd.DateOffset(years=full_years)
        if anniversary > end:
            full_years -= 1
            anniversary = start + pd.DateOffset(years=full_years)
        next_anniversary = anniversary + pd.DateOffset(years=1)
        return full_years + (end - anniversary).days / (
            next_anniversary - anniversary
        ).days

    return {
        "swing_history_years": elapsed_years(dates),
        "midterm_history_years": elapsed_years(closed_weekly_labels),
    }


def audit_history(
    ticker: str,
    frame: pd.DataFrame,
    *,
    required_start_date: Optional[date] = None,
    required_end_date: Optional[date] = None,
    expected_terminal_date: Optional[date] = None,
) -> TickerAudit:
    """Audit raw OHLCV continuity without claiming corporate-action knowledge."""

    normalized_ticker = str(ticker).strip().upper()
    quality = validate_ohlcv(frame)
    row_count = len(frame) if isinstance(frame, pd.DataFrame) else 0
    if not quality.is_valid or quality.valid_frame is None:
        return TickerAudit(
            ticker=normalized_ticker,
            status="invalid",
            source_row_count=row_count,
            first_date=None,
            last_date=None,
            pre_2021_return_pct=None,
            errors=quality.errors,
            warnings=quality.warnings,
        )

    valid = quality.valid_frame.reset_index(drop=True)
    dates = pd.to_datetime(valid["date"])
    first_date = dates.iloc[0].date()
    last_date = dates.iloc[-1].date()
    errors = list(quality.errors)
    warnings = list(quality.warnings)
    maximum_mismatch = _ohlc_ordering_relative_mismatch(valid).max()
    if maximum_mismatch > 0:
        mismatch_message = (
            "OHLC ordering mismatch "
            f"{float(maximum_mismatch):.2%}"
        )
        if maximum_mismatch > MAX_MINOR_OHLC_MISMATCH:
            errors.append(
                f"{mismatch_message} exceeds "
                f"{MAX_MINOR_OHLC_MISMATCH:.2%}"
            )
        else:
            warnings.append(
                f"{mismatch_message} is within "
                f"{MAX_MINOR_OHLC_MISMATCH:.2%} derived-envelope tolerance"
            )
    if required_start_date is not None and first_date > required_start_date:
        errors.append(
            "coverage starts after required date "
            f"{required_start_date.isoformat()}"
        )
    terminal_date = expected_terminal_date or required_end_date
    if terminal_date is not None and last_date < terminal_date:
        errors.append(
            "coverage ends before required terminal date "
            f"{terminal_date.isoformat()}"
        )

    close = pd.to_numeric(valid["close"], errors="coerce")
    volume = pd.to_numeric(valid["volume"], errors="coerce")
    high = pd.to_numeric(valid["high"], errors="coerce")
    low = pd.to_numeric(valid["low"], errors="coerce")
    previous_close = close.shift(1)
    close_return = close.div(previous_close).sub(1.0)
    findings = []
    threshold_hits = close_return.abs().ge(
        PRICE_AUDIT_CLOSE_MOVE_THRESHOLD - 1e-12
    )
    for position in close_return[threshold_hits].index:
        previous_volume = volume.iloc[position - 1] if position else None
        current_volume = volume.iloc[position]
        volume_ratio = (
            float(current_volume / previous_volume)
            if previous_volume is not None and previous_volume > 0
            else None
        )
        findings.append(
            PriceAuditFinding(
                date=dates.iloc[position].date(),
                close_return_pct=round(float(close_return.iloc[position] * 100.0), 2),
                close_ratio=float(close.iloc[position] / previous_close.iloc[position]),
                volume_ratio=volume_ratio,
                intraday_range_pct=float(
                    (high.iloc[position] - low.iloc[position]) / close.iloc[position] * 100.0
                ),
            )
        )

    pre_2021 = valid.loc[dates <= pd.Timestamp(PRE_2021_END)]
    pre_2021_return_pct = None
    if not pre_2021.empty:
        pre_close = pd.to_numeric(pre_2021["close"], errors="coerce")
        pre_2021_return_pct = round(
            float(pre_close.iloc[-1] / pre_close.iloc[0] - 1.0) * 100.0,
            2,
        )

    return TickerAudit(
        ticker=normalized_ticker,
        status="invalid" if errors else "indeterminate" if findings else "clean",
        source_row_count=row_count,
        first_date=first_date,
        last_date=last_date,
        pre_2021_return_pct=pre_2021_return_pct,
        errors=tuple(errors),
        warnings=tuple(warnings),
        findings=tuple(findings),
    )


def fresh_schema5_audit_eligibility(
    raw_history: pd.DataFrame,
    audit: TickerAudit,
    effective_bounds: dict[str, object],
) -> dict[str, object]:
    """Serialize only the current run's raw-history audit for schema 5."""

    if not isinstance(raw_history, pd.DataFrame):
        raise ValueError("raw_history must be a pandas DataFrame")
    if not isinstance(audit, TickerAudit):
        raise ValueError("audit must be a TickerAudit")
    if not isinstance(effective_bounds, dict):
        raise ValueError("effective_bounds must be a date-range object")
    start = effective_bounds.get("start")
    end = effective_bounds.get("end")
    if (start is None) != (end is None):
        raise ValueError("effective_bounds start and end must be paired")
    if start is None:
        raise ValueError("fresh raw history requires effective date bounds")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("effective_bounds dates must be ISO strings")
    try:
        date.fromisoformat(start)
        date.fromisoformat(end)
    except ValueError as error:
        raise ValueError("effective_bounds dates must be ISO strings") from error
    # Recalculate from the supplied raw rows so callers cannot carry an audit
    # decision forward from any earlier result document.
    fresh_audit = audit_history(audit.ticker, raw_history)
    return {
        "source": "fresh_schema5_raw_history",
        "eligible": fresh_audit.status == "clean",
        "status": fresh_audit.status,
        "reasons": [*fresh_audit.errors],
        "warnings": [*fresh_audit.warnings],
        "effective_date_range": [start, end],
    }


def unavailable_schema5_audit_eligibility(reason: str) -> dict[str, object]:
    """Describe a terminal failure before any raw ticker history was available."""

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be non-empty")
    return {
        "source": "unavailable",
        "eligible": False,
        "status": "unavailable",
        "reasons": [reason],
        "warnings": [],
        "effective_date_range": [None, None],
    }


def load_ticker_history(
    ticker: str,
    start_date: object,
    end_date: object,
    engine,
) -> pd.DataFrame:
    """Load raw BIGINT OHLCV rows through a bounded, parameterized query."""

    query = text(
        """
        SELECT date, open, high, low, close, volume
        FROM trading_data
        WHERE ticker = %(ticker)s
          AND date >= %(start_date)s
          AND date <= %(end_date)s
        ORDER BY date ASC
        """
    )
    connection = engine.raw_connection()
    try:
        return pd.read_sql(
            query.text,
            connection,
            params={
                "ticker": str(ticker).strip().upper(),
                "start_date": start_date,
                "end_date": end_date,
            },
        )
    finally:
        connection.close()
