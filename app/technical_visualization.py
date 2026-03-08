import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from technical_analysis import fetch_data, calculate_ma_cross

def technical_analysis_page(engine):
    st.header("Technical Analysis")

    # 1. Input Section
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker = st.text_input("Ticker Code", value="FPT").upper()
    with col2:
        timeframe = st.selectbox("Timeframe", ["Day", "Week", "Month"], index=0)
    with col3:
        # Default 100 periods as requested
        limit = st.number_input("Max Time (Lookback)", min_value=10, value=100, step=10)

    # Define standard MA pairs for each timeframe
    MA_PAIRS_BY_TIMEFRAME = {
        "Day": [(5, 10), (10, 20), (20, 60)],
        "Week": [(4, 12), (12, 26), (26,52)],
        "Month": [(3, 6), (6, 12), (12,36)]
    }

    # Chart Overlays Section
    st.subheader("Chart Overlays")
    col_ma1, col_ma2 = st.columns([1, 2])
    with col_ma1:
        show_ma = st.checkbox("Show MA / MA Cross", value=True)

    # Get the list of available pairs for the selected timeframe
    available_pairs = MA_PAIRS_BY_TIMEFRAME.get(timeframe, [])

    with col_ma2:
        selected_pair = st.selectbox(
            "MA Cross Pair",
            options=available_pairs,
            format_func=lambda pair: f"{pair[0]}-{pair[1]} Cross",
            index=0,
            disabled=not show_ma or not available_pairs
        )
    short_ma, long_ma = selected_pair if selected_pair else (0, 0)

    if st.button("Analyze"):
        # 2. Fetch Data
        with st.spinner("Fetching data..."):
            df = fetch_data(ticker, timeframe, limit, engine)

        if df.empty:
            st.warning(f"No data found for {ticker} with timeframe {timeframe}.")
            return

        # Calculate Indicators if enabled
        if show_ma and selected_pair:
            # Pass a list of tuples for pairs: [(short, long)]
            df = calculate_ma_cross(df, [(short_ma, long_ma)])

        # 3. Display Data & Charts
        st.subheader(f"Data for {ticker} ({timeframe})")
        
        # Display raw data table (collapsed by default)
        with st.expander("View Raw Data"):
            st.dataframe(df, use_container_width=True)

        # Charts using Plotly
        st.subheader("Price & Volume Chart")
        
        # Create subplots: 2 rows (Price, Volume), shared x-axis
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, row_heights=[0.7, 0.3])

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
        if show_ma and selected_pair:
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

        fig.update_layout(xaxis_rangeslider_visible=False, height=600, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        # 4. Indicator Placeholders
        st.subheader("Technical Indicators Details")
        tabs = st.tabs(["Stochastic", "RSI", "MA", "MA Cross", "Ichimoku", "Bollinger"])
        
        with tabs[0]: # Stochastic
             st.info("Indicator logic coming soon.")
        with tabs[1]: # RSI
             st.info("Indicator logic coming soon.")
        
        with tabs[2]: # MA
            if show_ma and selected_pair:
                st.write(f"**Moving Averages ({short_ma}, {long_ma})**")
                # Show tail of data with MA columns
                cols_to_show = ['date', 'close', f'SMA_{short_ma}', f'SMA_{long_ma}']
                # Filter columns that actually exist
                cols_to_show = [c for c in cols_to_show if c in df.columns]
                st.dataframe(df[cols_to_show].tail(20), use_container_width=True)
            else:
                st.info("Enable 'Show MA / MA Cross' to view data.")

        with tabs[3]: # MA Cross
            if show_ma and selected_pair:
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
                st.info("Enable 'Show MA / MA Cross' to view data.")

        with tabs[4]: # Ichimoku
             st.info("Indicator logic coming soon.")
        with tabs[5]: # Bollinger
             st.info("Indicator logic coming soon.")