import streamlit as st
import requests
import zipfile
import os
import pandas as pd
from sqlalchemy import create_engine, text, event
from sqlalchemy.types import BigInteger
from datetime import datetime, timedelta
import pytz
import shutil
import tempfile
import time

# Import the high-performance `execute_values` helper from psycopg2
from psycopg2.extras import execute_values

# Database connection
def get_engine_with_retry(database_url, retries=5, delay=5):
    attempt = 0
    while attempt < retries:
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            attempt += 1
            st.warning(f"Failed to connect to database (attempt {attempt}/{retries}): {str(e)}")
            if attempt == retries:
                st.error("Could not connect to database after multiple attempts.")
                raise
            time.sleep(delay)

# Create trading_data table with BIGINT for numerical columns
def init_db(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS trading_data (
                ticker TEXT,
                date DATE,
                open BIGINT,
                high BIGINT,
                low BIGINT,
                close BIGINT,
                volume BIGINT,
                PRIMARY KEY (ticker, date)
            );
        """))
        # Verify schema
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'trading_data' 
            AND column_name IN ('open', 'high', 'low', 'close', 'volume');
        """)).fetchall()
        for col, dtype in result:
            if dtype.lower() != 'bigint':
                st.error(f"Column {col} is {dtype}, expected BIGINT")
                raise ValueError(f"Invalid schema for trading_data: {col} is {dtype}")
        conn.commit()

# Function to get the last trading day (Monday to Friday)
def get_last_trading_day(current_date):
    if current_date.weekday() == 5:  # Saturday
        return current_date - timedelta(days=1)
    elif current_date.weekday() == 6:  # Sunday
        return current_date - timedelta(days=2)
    return current_date

# Function to determine default report date based on GMT+7 time
def get_default_report_date():
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.now(tz)
    current_time = now.time()
    eight_pm = datetime.strptime("20:00", "%H:%M").time()

    if current_time >= eight_pm:
        report_date = now.date()
    else:
        report_date = now.date() - timedelta(days=1)
        if now.weekday() == 0:
            report_date -= timedelta(days=2)

    return get_last_trading_day(report_date)

# Function to clean up files
def cleanup_files(zip_path, extract_path):
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            st.write(f"Deleted ZIP file: {zip_path}")
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
            st.write(f"Deleted extracted folder: {extract_path}")
    except Exception as e:
        st.warning(f"Error during cleanup: {str(e)}")

# Function to process CSV file with chunking and ticker filtering
def process_csv_file(file_path, cutoff_date, ticker_filter=None, chunk_size=10000, engine=None):
    chunks = pd.read_csv(file_path, chunksize=chunk_size, dtype={"Open": "float64", "High": "float64", "Low": "float64", "Close": "float64", "Volume": "float64"})
    total_rows = 0
    filtered_rows = 0
    last_chunk_dtypes = None
    
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TEMPORARY TABLE temp_chunk (
                ticker TEXT,
                date DATE,
                open BIGINT,
                high BIGINT,
                low BIGINT,
                close BIGINT,
                volume BIGINT
            );
        """))

        for chunk in chunks:
            total_rows += len(chunk)
            chunk.columns = ["Ticker", "DTYYYYMMDD", "Open", "High", "Low", "Close", "Volume"]
            chunk["DTYYYYMMDD"] = pd.to_datetime(chunk["DTYYYYMMDD"], format="%Y%m%d").dt.date
            chunk = chunk[chunk["DTYYYYMMDD"] >= cutoff_date]
            if ticker_filter is not None:
                chunk = chunk[chunk["Ticker"] == ticker_filter]
            else:
                chunk = chunk[chunk["Ticker"].str.len() <= 7]
            filtered_rows += len(chunk)
            
            if not chunk.empty:
                try:
                    chunk["Open"] = (chunk["Open"] * 1000).round().astype('int64')
                    chunk["High"] = (chunk["High"] * 1000).round().astype('int64')
                    chunk["Low"] = (chunk["Low"] * 1000).round().astype('int64')
                    chunk["Close"] = (chunk["Close"] * 1000).round().astype('int64')
                    chunk["Volume"] = chunk["Volume"].round().astype('int64')
                    chunk.columns = ["ticker", "date", "open", "high", "low", "close", "volume"]
                    # Deduplicate in Pandas
                    chunk = chunk.drop_duplicates(subset=["ticker", "date"], keep="first")
                    # The `dtype` argument is removed as it causes a ValueError in this pandas/SQLAlchemy version.
                    # The temp_chunk table already has the correct BIGINT types, and the DataFrame dtypes are int64,
                    # so the database driver can handle the mapping correctly.
                    # DIRECT INSERTION USING PSYCOPG2
                    # Bypass pandas.to_sql entirely to avoid SQLAlchemy/Pandas version conflicts
                    with conn.connection.cursor() as cursor:
                        execute_values(cursor, 
                            "INSERT INTO temp_chunk (ticker, date, open, high, low, close, volume) VALUES %s", 
                            chunk.values.tolist())
                    last_chunk_dtypes = chunk.dtypes
                except Exception as e:
                    st.error(f"Error processing chunk in {os.path.basename(file_path)}: {str(e)}")
                    raise

        st.write(f"Raw data rows in {os.path.basename(file_path)}: {total_rows}")
        st.write(f"Rows after filtering: {filtered_rows}")
        if last_chunk_dtypes is not None:
            st.write(f"Processed chunk dtypes: {last_chunk_dtypes}")
        
        # Log temp_chunk contents
        temp_count = conn.execute(text("SELECT COUNT(*) FROM temp_chunk")).fetchone()[0]
        st.write(f"Rows in temp_chunk before insert: {temp_count}")
        
        # Check for duplicates in temp_chunk
        duplicates = conn.execute(text("""
            SELECT ticker, date, COUNT(*) 
            FROM temp_chunk 
            GROUP BY ticker, date 
            HAVING COUNT(*) > 1;
        """)).fetchall()
        if duplicates:
            st.warning(f"Duplicates found in temp_chunk: {duplicates}")
        
        # Insert into trading_data
        try:
            result = conn.execute(text("""
                INSERT INTO trading_data (ticker, date, open, high, low, close, volume)
                SELECT ticker, date, open, high, low, close, volume
                FROM temp_chunk
                ON CONFLICT (ticker, date) DO NOTHING
                RETURNING ticker;
            """))
            inserted_rows = result.rowcount
            st.write(f"Inserted {inserted_rows} rows into trading_data from {os.path.basename(file_path)}")
        except Exception as e:
            st.error(f"Error inserting into trading_data: {str(e)}")
            raise
        
        # Verify trading_data contents
        trading_count = conn.execute(text("SELECT COUNT(*) FROM trading_data")).fetchone()[0]
        st.write(f"Rows in trading_data after insert: {trading_count}")
        
        conn.execute(text("DROP TABLE temp_chunk;"))

# Function to download and process data
def download_and_process_data(report_date, gaps_of_data, data_type="stock", engine=None):
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "stock_data.zip")
        extract_path = os.path.join(temp_dir, "extracted")
        
        try:
            last_trading_day = get_last_trading_day(report_date)
            ymd_to_date = last_trading_day.strftime("%Y%m%d")
            dmy_to_date = last_trading_day.strftime("%d%m%Y")
            if data_type == "stock":
                url = f"https://cafef1.mediacdn.vn/data/ami_data/{ymd_to_date}/CafeF.SolieuGD.Upto{dmy_to_date}.zip"
                ticker_filter = None
            elif data_type == "index":
                url = f"https://cafef1.mediacdn.vn/data/ami_data/{ymd_to_date}/CafeF.Index.Upto{dmy_to_date}.zip"
                ticker_filter = "VNINDEX"
            else:
                raise ValueError(f"Unknown data_type: {data_type}")
            
            st.write(f"Downloading {data_type} data from {url}...")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            st.write(f"Extracting {data_type} data...")
            os.makedirs(extract_path, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_path)

            st.write(f"Processing {data_type} data...")
            cutoff_date = last_trading_day - timedelta(days=365 * gaps_of_data)
            
            for csv_file in os.listdir(extract_path):
                if csv_file.endswith(".csv"):
                    file_path = os.path.join(extract_path, csv_file)
                    st.write(f"Processing {csv_file}...")
                    process_csv_file(file_path, cutoff_date, ticker_filter, engine=engine)

            with engine.connect() as conn:
                conn.execute(text("DROP INDEX IF EXISTS idx_ticker_date;"))
                conn.execute(text("CREATE INDEX idx_ticker_date ON trading_data (ticker, date DESC);"))
                conn.commit()
                result = conn.execute(text("SELECT COUNT(*) FROM trading_data")).fetchone()
                st.write(f"Total rows in trading_data after {data_type} insert: {result[0]}")

            st.write(f"{data_type.capitalize()} data saved to database.")
        except Exception as e:
            st.error(f"Error downloading or processing {data_type} data: {str(e)}")
            raise
        finally:
            cleanup_files(zip_path, extract_path)

# Data page logic
def data_page(engine):
    st.header("Data Page")
    default_date = get_default_report_date()
    report_date = st.date_input("Select Report Date", value=default_date)
    gaps_of_data = st.number_input("Gaps of Data (Years)", min_value=1, value=10, step=1)
    if st.button("Get Data"):
        st.write("Starting data retrieval...")
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE trading_data;"))
            conn.commit()
        download_and_process_data(report_date, gaps_of_data, "stock", engine=engine)
        download_and_process_data(report_date, gaps_of_data, "index", engine=engine)
        st.write("Data retrieval complete.")