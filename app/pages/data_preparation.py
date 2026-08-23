import streamlit as st
import requests
import zipfile
import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import pytz
import tempfile
import time
import threading
from typing import Callable

# Import the high-performance `execute_values` helper from psycopg2
from psycopg2.extras import execute_values

# Global lock to prevent multiple data preparation tasks from running concurrently
# Shared by both the Streamlit UI and the FastAPI background thread
data_prep_lock = threading.Lock()

# --- Headless Support Helpers ---
def log_progress(msg, level="info"):
    """Logs messages to Streamlit UI if available, otherwise to console."""
    # Check for script context to determine if we are in a Streamlit thread
    # We use a defensive check to avoid "missing ScriptRunContext" warnings in background threads
    ctx = None
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
    except (ImportError, RuntimeError):
        pass

    if ctx is not None:
        if level == "error": st.error(msg)
        elif level == "warning": st.warning(msg)
        elif level == "success": st.success(msg)
        else: st.write(msg)
        return

    # Fallback to standard console output for API or background tasks
    print(f"[DATA PREP] {level.upper()}: {msg}")

# Database connection
def get_engine_with_retry(database_url, retries=5, delay=5):
    attempt = 0
    while attempt < retries:
        try:
            engine = create_engine(database_url)
            connection = engine.raw_connection()
            cursor = connection.cursor()
            try:
                cursor.execute(text("SELECT 1").text)
            finally:
                cursor.close()
                connection.close()
            return engine
        except Exception as e:
            attempt += 1
            log_progress(f"Failed to connect to database (attempt {attempt}/{retries}): {str(e)}", "warning")
            if attempt == retries:
                log_progress("Could not connect to database after multiple attempts.", "error")
                raise
            time.sleep(delay)

_CREATE_TRADING_DATA_SQL = text("""
    CREATE TABLE IF NOT EXISTS trading_data (
        ticker TEXT,
        exchange TEXT,
        date DATE,
        open BIGINT,
        high BIGINT,
        low BIGINT,
        close BIGINT,
        volume BIGINT,
        PRIMARY KEY (ticker, date)
    )
""")
_ALTER_EXCHANGE_SQL = text(
    "ALTER TABLE trading_data ADD COLUMN IF NOT EXISTS exchange TEXT"
)
_SCHEMA_COLUMNS_SQL = text("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'trading_data'
      AND column_name IN ('exchange', 'open', 'high', 'low', 'close', 'volume')
""")
_LATEST_DATES_SQL = text(
    "SELECT ticker, MAX(date) FROM trading_data GROUP BY ticker"
)
_CREATE_STAGING_SQL = text("""
    CREATE TEMPORARY TABLE ingestion_stage (
        ticker TEXT NOT NULL,
        exchange TEXT NOT NULL,
        date DATE NOT NULL,
        open BIGINT NOT NULL,
        high BIGINT NOT NULL,
        low BIGINT NOT NULL,
        close BIGINT NOT NULL,
        volume BIGINT NOT NULL,
        PRIMARY KEY (ticker, date)
    ) ON COMMIT DROP
""")
_INSERT_STAGE_SQL = text("""
    INSERT INTO ingestion_stage (ticker, exchange, date, open, high, low, close, volume)
    VALUES %s
    ON CONFLICT (ticker, date) DO NOTHING
""")
_INSERT_TRADING_DATA_SQL = text("""
    INSERT INTO trading_data (ticker, exchange, date, open, high, low, close, volume)
    SELECT ticker, exchange, date, open, high, low, close, volume
    FROM ingestion_stage
    ON CONFLICT (ticker, date) DO NOTHING
""")
_CREATE_TICKER_DATE_INDEX_SQL = text(
    "CREATE INDEX IF NOT EXISTS idx_ticker_date ON trading_data (ticker, date DESC)"
)
_CSV_COLUMNS = ("Ticker", "DTYYYYMMDD", "Open", "High", "Low", "Close", "Volume")


@dataclass(frozen=True)
class ExtractedSource:
    """One downloaded source ready for staging; it has made no DB mutation."""

    data_type: str
    extract_path: Path
    ticker_filter: str | None


def _execute(cursor, statement, params=None) -> None:
    """Execute one fixed sqlalchemy.text statement through a raw connection."""

    cursor.execute(statement.text, params)


def _ensure_schema(cursor) -> None:
    """Create/verify the append-only table without touching existing rows."""

    _execute(cursor, _CREATE_TRADING_DATA_SQL)
    _execute(cursor, _ALTER_EXCHANGE_SQL)
    _execute(cursor, _SCHEMA_COLUMNS_SQL)
    columns = cursor.fetchall()
    if len(columns) < 6:
        raise ValueError("Incomplete database schema. Missing required columns.")
    for column, data_type in columns:
        expected = "text" if column == "exchange" else "bigint"
        if str(data_type).lower() != expected:
            raise ValueError(f"Invalid schema for trading_data: {column} is {data_type}")


def init_db(engine):
    """Retain startup compatibility while using the project raw-connection standard."""

    connection = engine.raw_connection()
    cursor = connection.cursor()
    try:
        _ensure_schema(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def get_last_trading_day(current_date):
    if current_date.weekday() == 5:
        return current_date - timedelta(days=1)
    if current_date.weekday() == 6:
        return current_date - timedelta(days=2)
    return current_date


def get_default_report_date():
    tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now = datetime.now(tz)
    if now.time() >= datetime.strptime("20:00", "%H:%M").time():
        report_date = now.date()
    else:
        report_date = now.date() - timedelta(days=1)
        if now.weekday() == 0:
            report_date -= timedelta(days=2)
    return get_last_trading_day(report_date)


def _source_url(report_date, data_type: str) -> tuple[str, str | None]:
    last_trading_day = get_last_trading_day(report_date)
    ymd = last_trading_day.strftime("%Y%m%d")
    dmy = last_trading_day.strftime("%d%m%Y")
    if data_type == "stock":
        return (
            f"https://cafef1.mediacdn.vn/data/ami_data/{ymd}/CafeF.SolieuGD.Upto{dmy}.zip",
            None,
        )
    if data_type == "index":
        return (
            f"https://cafef1.mediacdn.vn/data/ami_data/{ymd}/CafeF.Index.Upto{dmy}.zip",
            "VNINDEX",
        )
    raise ValueError(f"Unknown data_type: {data_type}")


def _download_and_extract_source(
    report_date,
    data_type: str,
    root: Path,
) -> ExtractedSource:
    """Download/extract one source before the transaction starts."""

    url, ticker_filter = _source_url(report_date, data_type)
    zip_path = root / f"{data_type}.zip"
    extract_path = root / data_type
    log_progress(f"Downloading {data_type} data from {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with zip_path.open("wb") as target:
        for response_chunk in response.iter_content(chunk_size=8192):
            target.write(response_chunk)
    extract_path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_path)
    return ExtractedSource(data_type, extract_path, ticker_filter)


def _latest_dates(cursor) -> dict[str, object]:
    _execute(cursor, _LATEST_DATES_SQL)
    return {str(ticker).upper(): latest_date for ticker, latest_date in cursor.fetchall()}


def _exchange_for_file(path: Path) -> str:
    filename = path.name.upper()
    if "HSX" in filename:
        return "HSX"
    if "HNX" in filename:
        return "HNX"
    if "UPCOM" in filename:
        return "UPCOM"
    return "Unknown"


def _eligible_chunk(
    chunk: pd.DataFrame,
    latest_dates: dict[str, object],
    cutoff_date,
    *,
    ticker_filter: str | None,
    exchange: str,
) -> pd.DataFrame:
    """Keep only append-eligible source rows; existing dates never change."""

    prepared = chunk.copy()
    prepared["Ticker"] = prepared["Ticker"].astype(str).str.strip().str.upper()
    prepared["DTYYYYMMDD"] = pd.to_datetime(
        prepared["DTYYYYMMDD"], format="%Y%m%d", errors="raise"
    ).dt.date
    if ticker_filter is not None:
        prepared = prepared.loc[prepared["Ticker"] == ticker_filter]
    else:
        prepared = prepared.loc[prepared["Ticker"].str.len() <= 7]
    latest = prepared["Ticker"].map(latest_dates)
    eligible = (latest.notna() & (prepared["DTYYYYMMDD"] > latest)) | (
        latest.isna() & (prepared["DTYYYYMMDD"] >= cutoff_date)
    )
    prepared = prepared.loc[eligible].copy()
    prepared["ticker"] = prepared["Ticker"]
    prepared["date"] = prepared["DTYYYYMMDD"]
    prepared["exchange"] = exchange
    return prepared


def _stage_chunk(cursor, chunk: pd.DataFrame) -> int:
    if chunk.empty:
        return 0
    staged = chunk.copy()
    # Database prices are immutable BIGINT values; UI scaling happens elsewhere.
    staged["open"] = (staged["Open"] * 1000).round().astype("int64")
    staged["high"] = (staged["High"] * 1000).round().astype("int64")
    staged["low"] = (staged["Low"] * 1000).round().astype("int64")
    staged["close"] = (staged["Close"] * 1000).round().astype("int64")
    staged["volume"] = staged["Volume"].round().astype("int64")
    staged = staged.drop_duplicates(subset=["ticker", "date"], keep="first")
    columns = ["ticker", "exchange", "date", "open", "high", "low", "close", "volume"]
    execute_values(cursor, _INSERT_STAGE_SQL.text, staged[columns].values.tolist())
    return len(staged)


def _stage_source(
    cursor,
    source: ExtractedSource,
    latest_dates: dict[str, object],
    cutoff_date,
    chunk_size: int = 10_000,
) -> int:
    """Stage every eligible source row in the caller-owned transaction."""

    staged_rows = 0
    for csv_path in sorted(source.extract_path.glob("*.csv")):
        exchange = _exchange_for_file(csv_path)
        chunks = pd.read_csv(
            csv_path,
            chunksize=chunk_size,
            dtype={"Open": "float64", "High": "float64", "Low": "float64", "Close": "float64", "Volume": "float64"},
        )
        for chunk in chunks:
            if len(chunk.columns) != len(_CSV_COLUMNS):
                raise ValueError(f"Unexpected CSV structure: {csv_path.name}")
            chunk.columns = _CSV_COLUMNS
            eligible = _eligible_chunk(
                chunk,
                latest_dates,
                cutoff_date,
                ticker_filter=source.ticker_filter,
                exchange=exchange,
            )
            staged_rows += _stage_chunk(cursor, eligible)
    log_progress(f"Staged {staged_rows} append-eligible rows from {source.data_type}.")
    return staged_rows


def _finalize_staged_rows(cursor) -> None:
    _execute(cursor, _INSERT_TRADING_DATA_SQL)
    _execute(cursor, _CREATE_TICKER_DATE_INDEX_SQL)


def _report_phase(progress_callback: Callable[[int, str], None] | None, value, label):
    if progress_callback is not None:
        progress_callback(value, label)


def run_full_ingestion(report_date, gaps_of_data, engine, progress_callback=None):
    """Append Stock and VN-Index data atomically, preserving all old rows."""

    if not data_prep_lock.acquire(blocking=False):
        log_progress("Data preparation is already in progress.", level="warning")
        return False

    connection = None
    cursor = None
    try:
        _report_phase(progress_callback, 0, "Starting data ingestion...")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stock_source = _download_and_extract_source(report_date, "stock", root)
            _report_phase(progress_callback, 20, "Stock source downloaded.")
            index_source = _download_and_extract_source(report_date, "index", root)
            _report_phase(progress_callback, 35, "VN-Index source downloaded.")

            connection = engine.raw_connection()
            cursor = connection.cursor()
            _ensure_schema(cursor)
            latest_dates = _latest_dates(cursor)
            _execute(cursor, _CREATE_STAGING_SQL)
            _report_phase(progress_callback, 50, "Schema and existing data preserved.")
            cutoff_date = report_date - timedelta(days=365 * int(gaps_of_data))
            _stage_source(cursor, stock_source, latest_dates, cutoff_date)
            _report_phase(progress_callback, 70, "Stock data staged.")
            _stage_source(cursor, index_source, latest_dates, cutoff_date)
            _report_phase(progress_callback, 90, "VN-Index data staged.")
            _finalize_staged_rows(cursor)
            connection.commit()
        log_progress("Full data ingestion complete.", level="success")
        _report_phase(progress_callback, 100, "Data ingestion complete.")
        return True
    except Exception as error:
        if connection is not None:
            connection.rollback()
        log_progress(f"Data ingestion failed: {error}", level="error")
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
        data_prep_lock.release()

# Data page logic
def data_page(engine):
    st.header("Data Page")
    default_date = get_default_report_date()
    up_to_date_column, year_gaps_column, action_column = st.columns(3)
    with up_to_date_column:
        report_date = st.date_input("Up-to date", value=default_date)
    with year_gaps_column:
        gaps_of_data = st.number_input("Year gaps", min_value=1, value=15, step=1)
    with action_column:
        st.caption("Action")
        get_data = st.button("Get data", use_container_width=True)

    if get_data:
        if data_prep_lock.locked():
            st.warning("Data preparation is already in progress (triggered via API or UI).")
        else:
            progress_bar = st.progress(0, text="Starting data ingestion...")
            with st.expander("Progress details", expanded=True):
                completed = run_full_ingestion(
                    report_date,
                    gaps_of_data,
                    engine,
                    progress_callback=lambda value, label: progress_bar.progress(
                        value, text=label
                    ),
                )
            if not completed:
                st.error("No new data was saved. Please rerun Get data manually.")
