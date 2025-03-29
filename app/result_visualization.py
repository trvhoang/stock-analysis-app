import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, timedelta

# Result page logic
def result_page(engine):
    st.header("Result Page")
    months = st.number_input("Number of months back", min_value=1, value=3)
    current_date = datetime.today().date()
    start_date = current_date - timedelta(days=months * 30)
    
    query_volume = text("""
        SELECT ticker, SUM(volume) as total_volume
        FROM trading_data
        WHERE date >= :start_date AND date <= :current_date AND ticker <> 'VNINDEX'
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
        WHERE date >= :start_date AND date <= :current_date AND ticker <> 'VNINDEX'
        GROUP BY ticker
        ORDER BY total_value DESC
        LIMIT 10
    """)
    df_value = pd.read_sql(query_value, engine, params={"start_date": start_date, "current_date": current_date})

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Top 10 Trading Volume")
        st.dataframe(df_volume, use_container_width=True)
    with col2:
        st.subheader("Top 10 Trading Value")
        st.dataframe(df_value, use_container_width=True)