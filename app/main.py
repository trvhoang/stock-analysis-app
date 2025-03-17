import streamlit as st
import requests
import zipfile
import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Database connection with retry logic
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

def get_engine_with_retry(retries=5, delay=5):
    attempt = 0
    while attempt < retries:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:  # Test the connection
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            attempt += 1
            st.warning(f"Failed to connect to database (attempt {attempt}/{retries}): {str(e)}")
            if attempt == retries:
                st.error("Could not connect to database after multiple attempts.")
                raise
            time.sleep(delay)

engine = get_engine_with_retry()

# Create trading_data table if it doesn't exist
def init_db():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS trading_data (
                ticker TEXT,
                date DATE,
                open INTEGER,
                high INTEGER,
                low INTEGER,
                close INTEGER,
                volume INTEGER,
                PRIMARY KEY (ticker, date)
            );
        """))
        conn.commit()

# Function to get the last trading day (Monday to Friday)
def get_last_trading_day(current_date):
    if current_date.weekday() == 5:  # Saturday
        return current_date - timedelta(days=1)
    elif current_date.weekday() == 6:  # Sunday
        return current_date - timedelta(days=2)
    return current_date

# Function to process CSV file
def process_csv_file(file_path, cutoff_date):
    df = pd.read_csv(file_path)
    st.write(f"Raw data rows in {os.path.basename(file_path)}: {len(df)}")
    
    df.columns = ["Ticker", "DTYYYYMMDD", "Open", "High", "Low", "Close", "Volume"]
    df["DTYYYYMMDD"] = pd.to_datetime(df["DTYYYYMMDD"], format="%Y%m%d").dt.date
    df = df[df["DTYYYYMMDD"] >= cutoff_date]
    df = df[df["Ticker"].str.len() <= 3]
    st.write(f"Rows after filtering: {len(df)}")
    
    df = df.drop_duplicates(subset=["Ticker", "DTYYYYMMDD"], keep="last")
    st.write(f"Rows after deduplication: {len(df)}")
    
    if not df.empty:
        df["Open"] = (df["Open"] * 1000).astype(int)
        df["High"] = (df["High"] * 1000).astype(int)
        df["Low"] = (df["Low"] * 1000).astype(int)
        df["Close"] = (df["Close"] * 1000).astype(int)
        df["Volume"] = df["Volume"].astype(int)
        df.columns = ["ticker", "date", "open", "high", "low", "close", "volume"]
    
    return df

# Function to download and process data
def download_and_process_data():
    try:
        st.write("Cleaning up existing data...")
        with engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE trading_data;"))
            conn.commit()

        current_date = datetime.today()
        last_trading_day = get_last_trading_day(current_date).date()
        
        ymd_to_date = last_trading_day.strftime("%Y%m%d")
        dmy_to_date = last_trading_day.strftime("%d%m%Y")
        url = f"https://cafef1.mediacdn.vn/data/ami_data/{ymd_to_date}/CafeF.SolieuGD.Upto{dmy_to_date}.zip"
        
        st.write(f"Downloading data from {url}...")
        response = requests.get(url)
        response.raise_for_status()
        zip_path = "/data/stock_data.zip"
        with open(zip_path, "wb") as f:
            f.write(response.content)

        st.write("Extracting data...")
        extract_path = "/data/extracted"
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        st.write("Processing data...")
        cutoff_date = last_trading_day - timedelta(days=365 * 10)
        
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TEMPORARY TABLE temp_trading_data (
                    ticker TEXT,
                    date DATE,
                    open INTEGER,
                    high INTEGER,
                    low INTEGER,
                    close INTEGER,
                    volume INTEGER
                );
            """))
            conn.commit()
            
            for csv_file in os.listdir(extract_path):
                if csv_file.endswith(".csv"):
                    file_path = os.path.join(extract_path, csv_file)
                    st.write(f"Processing {csv_file}...")
                    
                    df = process_csv_file(file_path, cutoff_date)
                    
                    if not df.empty:
                        df.to_sql("temp_trading_data", conn, if_exists="append", index=False)
                        conn.commit()
                        temp_count = conn.execute(text("SELECT COUNT(*) FROM temp_trading_data")).fetchone()[0]
                        st.write(f"Inserted {len(df)} rows from {csv_file} into temp_trading_data, total now: {temp_count}")
            
            temp_count = conn.execute(text("SELECT COUNT(*) FROM temp_trading_data")).fetchone()[0]
            st.write(f"Total rows in temp_trading_data before transfer: {temp_count}")
            
            if temp_count > 0:
                conn.execute(text("""
                    INSERT INTO trading_data (ticker, date, open, high, low, close, volume)
                    SELECT DISTINCT ticker, date, open, high, low, close, volume
                    FROM temp_trading_data;
                """))
                conn.commit()
            
            conn.execute(text("DROP TABLE temp_trading_data;"))
            conn.commit()
            
            conn.execute(text("DROP INDEX IF EXISTS idx_ticker_date;"))
            conn.execute(text("""
                CREATE INDEX idx_ticker_date ON trading_data (ticker, date DESC);
            """))
            conn.commit()
            
            result = conn.execute(text("SELECT COUNT(*) FROM trading_data")).fetchone()
            st.write(f"Total rows in trading_data after insert: {result[0]}")

        st.write("Data saved to database.")
    except Exception as e:
        st.error(f"Error downloading or processing data: {str(e)}")

# Function to analyze price movements
def analyze_price_movement(ticker, validation_days, result_days, delta_target):
    query = text("""
        WITH ordered_data AS (
            SELECT date, close,
                   LAG(close, :validation_days) OVER (ORDER BY date) AS prev_close,
                   LEAD(close, :result_days) OVER (ORDER BY date) AS next_close
            FROM trading_data
            WHERE ticker = :ticker
            ORDER BY date
        ),
        delta_calc AS (
            SELECT date,
                   close,
                   prev_close,
                   next_close,
                   CASE 
                       WHEN prev_close IS NOT NULL 
                       THEN ROUND(((close - prev_close)::FLOAT / prev_close * 100)::NUMERIC, 2)
                       ELSE NULL 
                   END AS exact_delta,
                   CASE 
                       WHEN next_close IS NOT NULL 
                       THEN ROUND(((next_close - close)::FLOAT / close * 100)::NUMERIC, 2)
                       ELSE NULL 
                   END AS result_delta
            FROM ordered_data
        )
        SELECT 
            date AS event_date,
            exact_delta,
            CASE 
                WHEN result_delta > 0 THEN 'Up'
                WHEN result_delta < 0 THEN 'Down'
                ELSE 'No Change'
            END AS result,
            result_delta
        FROM delta_calc
        WHERE exact_delta IS NOT NULL 
          AND exact_delta >= :delta_min 
          AND exact_delta <= :delta_max
          AND result_delta IS NOT NULL
        ORDER BY date;
    """)
    
    delta_min = delta_target - 0.99  # e.g., -3.99 for -3 target
    delta_max = delta_target        # e.g., -3.00 for -3 target
    
    params = {
        "ticker": ticker,
        "validation_days": validation_days,
        "result_days": result_days,
        "delta_min": delta_min,
        "delta_max": delta_max
    }
    
    df = pd.read_sql(query, engine, params=params)
    
    if not df.empty:
        df["no. events"] = range(1, len(df) + 1)
        df = df[["no. events", "exact_delta", "result", "result_delta"]]
    else:
        df = pd.DataFrame(columns=["no. events", "exact_delta", "result", "result_delta"])
    
    return df

# Function to create analyzed statistical report with No Change
def create_analyzed_statistical_report(df_block):
    if df_block.empty:
        return pd.DataFrame(columns=["result", "possibility of result", "result range", "median"])
    
    result_counts = df_block["result"].value_counts()
    total_events = len(df_block)
    
    up_results = df_block[df_block["result"] == "Up"]["result_delta"]
    down_results = df_block[df_block["result"] == "Down"]["result_delta"]
    no_change_results = df_block[df_block["result"] == "No Change"]["result_delta"]
    
    stats = []
    if "Up" in result_counts:
        up_count = result_counts["Up"]
        up_percentage = round((up_count / total_events) * 100, 2)
        up_range = f"{up_results.min()}% to {up_results.max()}%" if not up_results.empty else "N/A"
        up_median = round(up_results.median(), 2) if not up_results.empty else "N/A"
        stats.append({"result": "Up", "possibility of result": f"{up_percentage}%", "result range": up_range, "median": f"{up_median}%"})
    
    if "Down" in result_counts:
        down_count = result_counts["Down"]
        down_percentage = round((down_count / total_events) * 100, 2)
        down_range = f"{down_results.min()}% to {down_results.max()}%" if not down_results.empty else "N/A"
        down_median = round(down_results.median(), 2) if not down_results.empty else "N/A"
        stats.append({"result": "Down", "possibility of result": f"{down_percentage}%", "result range": down_range, "median": f"{down_median}%"})
    
    if "No Change" in result_counts:
        no_change_count = result_counts["No Change"]
        no_change_percentage = round((no_change_count / total_events) * 100, 2)
        no_change_range = f"{no_change_results.min()}% to {no_change_results.max()}%" if not no_change_results.empty else "N/A"
        no_change_median = round(no_change_results.median(), 2) if not no_change_results.empty else "N/A"
        stats.append({"result": "No Change", "possibility of result": f"{no_change_percentage}%", "result range": no_change_range, "median": f"{no_change_median}%"})
    
    return pd.DataFrame(stats)

# Function to provide advice with three options
def provide_advice(ticker, validation_days, result_days, delta_target, df_stats):
    query_latest = text("""
        SELECT date, close,
               LAG(close, :validation_days) OVER (ORDER BY date) AS prev_close
        FROM trading_data
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT :validation_days
    """)
    params = {"ticker": ticker, "validation_days": validation_days}
    df_latest = pd.read_sql(query_latest, engine, params=params)
    
    if len(df_latest) < validation_days or df_latest["prev_close"].iloc[0] is None:
        return "Not enough data to calculate the latest block day delta."
    
    latest_close = df_latest["close"].iloc[0]
    prev_close = df_latest["prev_close"].iloc[0]
    latest_delta = round(((latest_close - prev_close) / prev_close * 100), 2)
    delta_min = delta_target - 0.99
    delta_max = delta_target
    
    if delta_min <= latest_delta <= delta_max:
        if df_stats.empty:
            return f"Latest {validation_days}-day delta is {latest_delta}%, but no historical data matches the criteria for prediction."
        
        up_row = df_stats[df_stats["result"] == "Up"]
        down_row = df_stats[df_stats["result"] == "Down"]
        no_change_row = df_stats[df_stats["result"] == "No Change"]
        
        up_prob = float(up_row["possibility of result"].iloc[0].replace("%", "")) if not up_row.empty else 0
        down_prob = float(down_row["possibility of result"].iloc[0].replace("%", "")) if not down_row.empty else 0
        no_change_prob = float(no_change_row["possibility of result"].iloc[0].replace("%", "")) if not no_change_row.empty else 0
        
        probs = {"Up": up_prob, "Down": down_prob, "No Change": no_change_prob}
        max_prob = max(probs.values())
        predictions = [k for k, v in probs.items() if v == max_prob]
        
        if len(predictions) == 1:
            prediction = predictions[0]
        else:
            prediction = "Uncertain (multiple equal probabilities)"
        
        return f"Based on historical data, after a {validation_days}-day delta of {latest_delta}%, the stock is more likely to go **{prediction}** in the next {result_days} days."
    else:
        return f"Latest {validation_days}-day delta is {latest_delta}%, which is outside the target range ({delta_min}% to {delta_max}%). No prediction can be made."

# Streamlit app
def main():
    init_db()
    st.title("Stock Analysis App")
    page = st.sidebar.selectbox("Select Page", ["Data", "Result", "Analyze"], index=0)  # Data as default

    if page == "Data":
        st.header("Data Page")
        if st.button("Get Data"):
            download_and_process_data()

    elif page == "Result":
        st.header("Result Page")
        months = st.number_input("Number of months back", min_value=1, value=3)
        current_date = datetime.today().date()
        start_date = current_date - timedelta(days=months * 30)
        
        query_volume = text("""
            SELECT ticker, SUM(volume) as total_volume
            FROM trading_data
            WHERE date >= :start_date AND date <= :current_date
            GROUP BY ticker
            ORDER BY total_volume DESC
            LIMIT 10
        """)
        df_volume = pd.read_sql(query_volume, engine, params={"start_date": start_date, "current_date": current_date})

        query_value = text("""
            SELECT ticker, 
                   SUM(CAST(close AS BIGINT) * CAST(volume AS BIGINT)) as total_value,
                   SUM(volume) as total_volume,
                   ROUND((SUM(CAST(close AS BIGINT) * CAST(volume AS BIGINT))::FLOAT / SUM(volume))::NUMERIC, 2) as avg_price
            FROM trading_data
            WHERE date >= :start_date AND date <= :current_date
            GROUP BY ticker
            ORDER BY total_value DESC
            LIMIT 10
        """)
        df_value = pd.read_sql(query_value, engine, params={"start_date": start_date, "current_date": current_date})

        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("Top 10 Trading Volume")
            st.dataframe(df_volume)
        with col2:
            st.subheader("Top 10 Trading Value")
            st.dataframe(df_value)

    elif page == "Analyze":
        st.header("Analyze Page")
        
        col1, col2 = st.columns(2)
        with col1:
            ticker = st.text_input("Ticker Code", value="FPT")
        with col2:
            validation_days = st.number_input("Validation Day Range", min_value=1, value=3, step=1)
        
        col3, col4 = st.columns(2)
        with col3:
            result_days = st.number_input("Result Day Range", min_value=1, value=7, step=1)
        with col4:
            delta_target = st.number_input("Delta Range (%)", value=-3.0, step=0.1)
        
        if st.button("Analyze"):
            ticker = ticker.upper()
            
            df_block = analyze_price_movement(ticker, validation_days, result_days, delta_target)
            df_stats = create_analyzed_statistical_report(df_block)
            
            # Display tables on separate lines with full width
            st.subheader("Block Day and Delta Statistical Report")
            if not df_block.empty:
                st.dataframe(df_block, use_container_width=True)  # Use full container width
            else:
                st.write("No events found matching the criteria.")
            
            st.subheader("Analyzed Statistical Report")
            if not df_stats.empty:
                st.dataframe(df_stats, use_container_width=True)  # Use full container width
            else:
                st.write("No statistical data available.")
            
            advice = provide_advice(ticker, validation_days, result_days, delta_target, df_stats)
            st.subheader("Advice")
            st.write(advice)

if __name__ == "__main__":
    main()