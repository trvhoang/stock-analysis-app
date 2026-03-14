import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from technical_analysis import fetch_data, calculate_ma_cross, calculate_rsi, calculate_stochastic, calculate_ma_trend, calculate_ma_cross_trend

def technical_analysis_page(engine):
    st.header("Technical Analysis")

    # Session state keys
    TECH_DF_KEY = 'tech_df'
    TECH_TICKER_KEY = 'tech_ticker'
    MA_SPREAD_TREND_KEY = 'ma_spread_trend'
    MA_CROSS_TREND_KEY = 'ma_cross_trend'
    RSI_TREND_KEY = 'rsi_trend'
    STOCHASTIC_TREND_KEY = 'stochastic_trend'
    SHOW_STOCHASTIC_KEY = 'show_stochastic'
    TECH_TICKER_KEY = 'tech_ticker'

    # Initialize session state variables if they don't exist
    if TECH_DF_KEY not in st.session_state:
        st.session_state[TECH_DF_KEY] = None
    if TECH_TICKER_KEY not in st.session_state:
        st.session_state[TECH_TICKER_KEY] = ""
    if MA_SPREAD_TREND_KEY not in st.session_state:
        st.session_state[MA_SPREAD_TREND_KEY] = "Unknown"
    if MA_CROSS_TREND_KEY not in st.session_state:
        st.session_state[MA_CROSS_TREND_KEY] = "Unknown"
    if RSI_TREND_KEY not in st.session_state:
        st.session_state[RSI_TREND_KEY] = "Unknown"
    if STOCHASTIC_TREND_KEY not in st.session_state:
        st.session_state[STOCHASTIC_TREND_KEY] = "Unknown"
    if SHOW_STOCHASTIC_KEY not in st.session_state:

        st.session_state[SHOW_STOCHASTIC_KEY] = False

    # Helper function to clear cache
    def clear_cache():
        st.session_state[TECH_DF_KEY] = None
        st.session_state[TECH_TICKER_KEY] = ""
        st.session_state[MA_SPREAD_TREND_KEY] = "Unknown"
        st.session_state[MA_CROSS_TREND_KEY] = "Unknown"
        st.session_state[RSI_TREND_KEY] = "Unknown"
        st.session_state[STOCHASTIC_TREND_KEY] = "Unknown"

    # Button to clear cache
    if st.sidebar.button("Clear Cache", key="clear_cache_sidebar"):
        clear_cache()



    # 1. Input Section
    with st.sidebar:
        st.header("Input Options")

        ticker = st.text_input("Ticker Code", value="FPT").upper()
        timeframe = st.selectbox("Timeframe", ["Day", "Week", "Month"], index=0)
        # Default 100 periods as requested
        limit = st.number_input("Max Time (Lookback)", min_value=10, value=100, step=10)

        # Chart Overlays Section
        st.subheader("Chart Overlays")
        

        show_ma = True
        show_rsi = True
        # Define standard MA pairs for each timeframe
        MA_PAIRS_BY_TIMEFRAME = {
            "Day": [(5, 10), (10, 20), (20, 60)],
            "Week": [(4, 12), (12, 26), (26,52)],
            "Month": [(3, 6), (6, 12), (12,36)]
        }
        # Get the list of available pairs for the selected timeframe
        available_pairs = MA_PAIRS_BY_TIMEFRAME.get(timeframe, [])

        selected_pair = st.selectbox(
            "MA Cross Pair",
            options=available_pairs,
            format_func=lambda pair: f"{pair[0]}-{pair[1]} Cross",
            index=0,
            disabled=not available_pairs
            )
        if st.button("Clear Cache", key="clear_cache_input"):
            clear_cache()

    short_ma, long_ma = selected_pair if selected_pair else (0, 0)



    # Initialize session state for data persistence

    if st.button("Analyze"):
        # 2. Fetch Data
        data_key = f"{ticker}_{timeframe}_{limit}"
        if st.session_state.get(data_key) is None:
            with st.spinner("Fetching data..."):
                df = fetch_data(ticker, timeframe, limit, engine)                
                st.session_state[data_key] = df # Cache the fetched data
                st.session_state[TECH_TICKER_KEY] = ticker
        else:            
            df = st.session_state[data_key] # Retrieve data from cache
            st.session_state[TECH_TICKER_KEY] = ticker

        if df.empty:
            st.warning(f"No data found for {ticker} with timeframe {timeframe}.")
            return
        df, stochastic_trend = calculate_stochastic(df)
        st.session_state.stochastic_trend = stochastic_trend
        
        # Calculate MA and Cross data
        df = calculate_ma_cross(df, [(short_ma, long_ma)])
        
        # Calculate separate trends
        short_col = f'SMA_{short_ma}'
        long_col = f'SMA_{long_ma}'
        signal_col = f'cross_{short_ma}_{long_ma}'
        st.session_state.ma_spread_trend = calculate_ma_trend(df, short_col, long_col)
        st.session_state.ma_cross_trend = calculate_ma_cross_trend(df, signal_col)

        if show_rsi:
            # Calculate RSI with a length of 14
            df, rsi_trend = calculate_rsi(df, length=14)
            st.session_state.rsi_trend = rsi_trend
        else:
            st.session_state.rsi_trend = "Unknown"
            
        st.session_state.tech_df = df

         # Update Session State
        st.session_state.tech_df = df

    # 3. Display Data & Charts (Read from Session State)
    # Only display if we have data and it matches the current ticker (basic sync check)
    if st.session_state.tech_df is not None and st.session_state.tech_ticker == ticker:
        df = st.session_state.tech_df
        
        # 3. Display Data & Charts
        st.subheader(f"Data for {ticker} ({timeframe})")
        
        # Display raw data table (collapsed by default)
        with st.expander("View Raw Data"):
            st.dataframe(df, use_container_width=True)

        # Charts using Plotly
        # We only render the chart if the user wants to see it, OR if we want to support toggle without re-calc.
        # Logic: If data exists in DF (columns present), and checkbox is True, show it.
        
        # Determine if we have the specific columns needed for the requested overlays
        has_ma_data = f'SMA_{short_ma}' in df.columns and f'SMA_{long_ma}' in df.columns
        has_rsi_data = 'RSI_14' in df.columns
        

        render_ma = show_ma and has_ma_data
        render_rsi = show_rsi and has_rsi_data



        st.subheader("Price & Volume Chart")
        
        # Determine number of rows and heights based on selected indicators
        has_stochastic_data = '%K' in df.columns and '%D' in df.columns
        render_stochastic = has_stochastic_data

        rows = 2
        indicator_rows = 0
        if render_rsi: indicator_rows += 1
        if render_stochastic: indicator_rows += 1
        
        rows += indicator_rows
        
        if rows == 2:
            row_heights = [0.7, 0.3]
        elif rows == 3:
            row_heights = [0.6, 0.2, 0.2] # Price, Volume, RSI
        else:
            row_heights = [0.5, 0.2, 0.15, 0.15] # Price, Volume, RSI, Stochastic

        # Create subplots
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, row_heights=row_heights)

        # Add Candlestick trace
        fig.add_trace(go.Candlestick(x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'], name="OHLC"), row=1, col=1)
        
        # Add Volume trace
        # Color volume bars based on price movement (Green if Close >= Open, else Red)
        colors = ['green' if c >= o else 'red' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df['date'], y=df['volume'], name="Volume", marker_color=colors), row=2, col=1)
        
        # Add MA Traces and Cross Markers
        if render_ma:
            short_col = f'SMA_{short_ma}'
            long_col = f'SMA_{long_ma}'
            signal_col = f'cross_{short_ma}_{long_ma}'

            # Check if columns exist (calculation might fail if not enough data)
            if short_col in df.columns and long_col in df.columns:
                # Add Short MA Line
                fig.add_trace(go.Scatter(x=df['date'], y=df[short_col], 
                                         mode='lines', name=f'SMA {short_ma}', 
                                         line=dict(color='orange', width=1)), row=1, col=1)
                
                # Add Long MA Line
                fig.add_trace(go.Scatter(x=df['date'], y=df[long_col], 
                                         mode='lines', name=f'SMA {long_ma}', 
                                         line=dict(color='blue', width=1)), row=1, col=1)

                # Only plot cross markers if the signal column was successfully calculated
                if signal_col in df.columns:
                    # Filter for Golden Cross (Signal = 1)
                    golden_crosses = df[df[signal_col] == 1]
                    if not golden_crosses.empty:
                        fig.add_trace(go.Scatter(
                            x=golden_crosses['date'], 
                            y=golden_crosses['low'] * 0.98, # Position slightly below low
                            mode='markers', 
                            marker=dict(symbol='triangle-up', size=10, color='green'),
                            name='Golden Cross'
                        ), row=1, col=1)

                    # Filter for Death Cross (Signal = -1)
                    death_crosses = df[df[signal_col] == -1]
                    if not death_crosses.empty:
                        fig.add_trace(go.Scatter(
                            x=death_crosses['date'], 
                            y=death_crosses['high'] * 1.02, # Position slightly above high
                            mode='markers', 
                            marker=dict(symbol='triangle-down', size=10, color='red'),
                            name='Death Cross'
                        ), row=1, col=1)
        
        current_indicator_row = 3

        # Add RSI trace if enabled
        if render_rsi:
            # Add RSI line
            fig.add_trace(go.Scatter(x=df['date'], y=df['RSI_14'],
                                     mode='lines', name='RSI 14',
                                     line=dict(color='purple', width=1)), row=current_indicator_row, col=1)
            # Add overbought/oversold lines
            fig.add_hline(y=70, line_dash="dash", line_color="red", line_width=1, row=current_indicator_row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", line_width=1, row=current_indicator_row, col=1)
            # Update the y-axis title for the RSI subplot
            fig.update_yaxes(title_text="RSI", row=current_indicator_row, col=1)
            current_indicator_row += 1

        # Update x-axis to remove gaps for non-trading days (Weekends, Holidays)
        # This applies specifically to the 'Day' timeframe where gaps are visible.
        if timeframe == 'Day' and not df.empty:
            # Calculate the time difference between consecutive dates
            dt_all = pd.date_range(start=df['date'].iloc[0], end=df['date'].iloc[-1])
            # Find dates that are NOT in our dataframe (these are the gaps)
            dt_obs = [d.strftime("%Y-%m-%d") for d in df['date']]
            dt_breaks = [d.strftime("%Y-%m-%d") for d in dt_all if d.strftime("%Y-%m-%d") not in dt_obs]
            
            fig.update_xaxes(
                rangebreaks=[dict(values=dt_breaks)]
            )

        if render_stochastic:
             # Add Stochastic trace if enabled
            fig.add_trace(go.Scatter(x=df['date'], y=df['%K'], mode='lines', name='%K', line=dict(color='purple', width=1)), row=current_indicator_row, col=1)
            fig.add_trace(go.Scatter(x=df['date'], y=df['%D'], mode='lines', name='%D', line=dict(color='red', width=1)), row=current_indicator_row, col=1)

            fig.add_hline(y=80, line_dash="dash", line_color="gray", line_width=1, row=current_indicator_row, col=1)
            fig.add_hline(y=20, line_dash="dash", line_color="gray", line_width=1, row=current_indicator_row, col=1)
            # Update the y-axis title for the Stochastic subplot
            fig.update_yaxes(title_text="Stochastic", row=current_indicator_row, col=1)
            current_indicator_row += 1



        # Final layout updates
        chart_height = 600 + (indicator_rows * 150)
        fig.update_layout(xaxis_rangeslider_visible=False, height=chart_height, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        # 4. Indicator Placeholders
        st.subheader("Technical Indicators Details")
        tabs = st.tabs(["Stochastic", "RSI", "MA", "MA Cross", "Ichimoku", "Bollinger"])
        

        with tabs[0]: # Stochastic
            st.metric("Trend", st.session_state.stochastic_trend)
            if '%K' in df.columns and '%D' in df.columns:
                st.write("**Stochastic Oscillator (10, 3, 3)**")
                st.dataframe(df[['date', '%K', '%D']].tail(20).sort_values('date', ascending=False), use_container_width=True)
            else:

                st.info("Stochastic data not calculated. Click Analyze to generate.")
        with tabs[1]: # RSI
            if 'RSI_14' in df.columns:

                st.metric("Current Trend", st.session_state.rsi_trend)
                st.write("**Relative Strength Index (14)**")
                # Show tail of data with RSI column
                cols_to_show = ['date', 'close', 'RSI_14']
                st.dataframe(df[cols_to_show].tail(20).sort_values('date', ascending=False), use_container_width=True)
            else:
                st.info("RSI data not calculated. Enable 'Show RSI (14)' and click Analyze.")
        
        with tabs[2]: # MA
            if has_ma_data:
                # Display the spread-based trend
                if st.session_state.ma_spread_trend == "Unknown":
                    st.info("MA data is still loading or could not be determined.")
                else:
                    st.metric(f"Current Trend ({short_ma}-{long_ma})", st.session_state.ma_spread_trend)

                    st.write(f"**Moving Averages ({short_ma}, {long_ma})**")
                    # Show tail of data with MA columns
                    cols_to_show = ['date', 'close', f'SMA_{short_ma}', f'SMA_{long_ma}']
                    # Filter columns that actually exist
                    cols_to_show = [c for c in cols_to_show if c in df.columns]
                    st.dataframe(df[cols_to_show].tail(20).sort_values('date', ascending=False), use_container_width=True)
            else:
                st.info("MA data not calculated. Enable 'Show MA / MA Cross' and click Analyze.")

        with tabs[3]: # MA Cross
            if has_ma_data:
                # Display the cross-event-based trend
                if st.session_state.ma_cross_trend == "Unknown":
                    st.info("MA data is still loading or could not be determined.")
                else:
                    st.metric(f"Current Trend ({short_ma}-{long_ma})", st.session_state.ma_cross_trend)

                signal_col = f'cross_{short_ma}_{long_ma}'
                if signal_col in df.columns:
                    cross_events = df[df[signal_col] != 0].copy()
                    if not cross_events.empty:
                        # Map 1/-1 to readable text
                        cross_events['Type'] = cross_events[signal_col].map({1: 'Golden Cross', -1: 'Death Cross'})
                        st.write(f"**Cross Events Found: {len(cross_events)}**")
                        
                        # Select relevant columns for display
                        display_cols = ['date', 'Type', 'close', f'SMA_{short_ma}', f'SMA_{long_ma}']
                        st.dataframe(cross_events[display_cols].sort_values('date', ascending=False), use_container_width=True)
                    else:                        
                        st.info("No cross events found in the selected timeframe.")
                else:
                    st.warning("Not enough data to calculate MA Cross.")
            else:
                st.info("MA data not calculated. Enable 'Show MA / MA Cross' and click Analyze.")

        with tabs[4]: # Ichimoku

             st.info("Indicator logic coming soon.")
        with tabs[5]: # Bollinger
             st.info("Indicator logic coming soon.")