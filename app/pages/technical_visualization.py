import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from commons.technical_analysis import (
    MA_PAIRS_BY_TIMEFRAME,
    build_technical_snapshot,
    fetch_data,
)


TECHNICAL_INDICATOR_TABS = (
    "Overview",
    "MA",
    "MA Cross",
    "RSI",
    "Stochastic",
    "ADX",
    "OBV",
    "ATR",
    "Bollinger Bands",
)
TECHNICAL_CHART_OPTIONS = TECHNICAL_INDICATOR_TABS[1:]

_INDICATOR_REPORT_NAMES = {
    "MA Cross": "MA cross",
    "Bollinger Bands": "Bollinger",
}

_INDICATOR_RULES = {
    "MA": "Sideways when the MA spread is below 2% of price.",
    "MA Cross": "Golden and Death cross events are evaluated separately from MA spread.",
    "RSI": "RSI 70 is overbought and RSI 30 is oversold.",
    "Stochastic": "80/20 lines identify overbought and oversold zones.",
    "ADX": "ADX is a gate only; it is never a voting indicator.",
    "OBV": "OBV trend requires volume direction to agree with price direction.",
    "ATR": "ATR trend compares normalized volatility with its trailing baseline.",
    "Bollinger Bands": "Band position, bandwidth, and %B determine the trend classification.",
}


def get_indicator_chart_spec(indicator, short_ma, long_ma):
    """Return the single chart layer specification for one indicator."""
    specs = {
        "MA": {
            "kind": "overlay",
            "columns": [f"SMA_{short_ma}", f"SMA_{long_ma}"],
        },
        "MA Cross": {
            "kind": "overlay",
            "columns": [
                f"SMA_{short_ma}",
                f"SMA_{long_ma}",
                f"cross_{short_ma}_{long_ma}",
            ],
        },
        "RSI": {"kind": "panel", "columns": ["RSI_14"]},
        "Stochastic": {"kind": "panel", "columns": ["%K", "%D"]},
        "ADX": {"kind": "panel", "columns": ["ADX_14", "DMP_14", "DMN_14"]},
        "OBV": {"kind": "panel", "columns": ["OBV"]},
        "ATR": {"kind": "panel", "columns": ["ATR_14"]},
        "Bollinger Bands": {
            "kind": "panel",
            "columns": [
                "BBM_20_2",
                "BBU_20_2",
                "BBL_20_2",
                "BBB_20_2",
                "BBP_20_2",
            ],
        },
    }
    return specs.get(indicator)


def get_ma_pair_options(timeframe):
    """Return stable string values for the MA-pair selectbox widget."""
    return tuple(
        f"{short_ma}-{long_ma} Cross"
        for short_ma, long_ma in MA_PAIRS_BY_TIMEFRAME.get(timeframe, ())
    )


def parse_ma_pair(option):
    """Convert a widget label back to the tuple used by indicator logic."""
    if not option:
        return None

    try:
        pair = str(option).split(" ", 1)[0]
        short_ma, long_ma = pair.split("-", 1)
        return int(short_ma), int(long_ma)
    except (AttributeError, TypeError, ValueError):
        return None


def _report_name(indicator):
    return _INDICATOR_REPORT_NAMES.get(indicator, indicator)


def build_price_candlestick(df):
    """Build a version-compatible candlestick trace with k VND hover text."""
    def format_prices(column):
        values = pd.to_numeric(df[column], errors="coerce")
        return values.map(lambda value: f"{value:.2f}k" if pd.notna(value) else "N/A")

    dates = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    hover_text = (
        "Date: " + dates
        + "<br>Open: " + format_prices("open")
        + "<br>High: " + format_prices("high")
        + "<br>Low: " + format_prices("low")
        + "<br>Close: " + format_prices("close")
    ).tolist()

    return go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="OHLC",
        text=hover_text,
        hoverinfo="text",
    )


def _add_selected_indicator(fig, df, indicator, spec, row, short_ma, long_ma):
    """Add exactly one selected indicator layer to the existing base chart."""
    if spec is None:
        return

    columns = spec["columns"]
    if not all(column in df.columns for column in columns):
        return

    x_values = df["date"]
    if indicator in ("MA", "MA Cross"):
        short_col = f"SMA_{short_ma}"
        long_col = f"SMA_{long_ma}"
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=df[short_col],
                mode="lines",
                name=f"SMA {short_ma}",
                line=dict(color="orange", width=1),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=df[long_col],
                mode="lines",
                name=f"SMA {long_ma}",
                line=dict(color="blue", width=1),
            ),
            row=1,
            col=1,
        )

        if indicator == "MA Cross":
            signal_col = f"cross_{short_ma}_{long_ma}"
            golden_crosses = df[df[signal_col] == 1]
            death_crosses = df[df[signal_col] == -1]
            if not golden_crosses.empty:
                fig.add_trace(
                    go.Scatter(
                        x=golden_crosses["date"],
                        y=golden_crosses["low"] * 0.98,
                        mode="markers",
                        marker=dict(symbol="triangle-up", size=10, color="green"),
                        name="Golden Cross",
                    ),
                    row=1,
                    col=1,
                )
            if not death_crosses.empty:
                fig.add_trace(
                    go.Scatter(
                        x=death_crosses["date"],
                        y=death_crosses["high"] * 1.02,
                        mode="markers",
                        marker=dict(symbol="triangle-down", size=10, color="red"),
                        name="Death Cross",
                    ),
                    row=1,
                    col=1,
                )
        return

    line_styles = {
        "RSI_14": ("RSI 14", "purple"),
        "%K": ("%K", "purple"),
        "%D": ("%D", "red"),
        "ADX_14": ("ADX 14", "black"),
        "DMP_14": ("+DI", "green"),
        "DMN_14": ("-DI", "red"),
        "OBV": ("OBV", "blue"),
        "ATR_14": ("ATR 14", "orange"),
        "BBM_20_2": ("BB Middle", "blue"),
        "BBU_20_2": ("BB Upper", "red"),
        "BBL_20_2": ("BB Lower", "green"),
        "BBB_20_2": ("BB Bandwidth", "purple"),
        "BBP_20_2": ("BB %B", "orange"),
    }
    for column in columns:
        name, color = line_styles[column]
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=df[column],
                mode="lines",
                name=name,
                line=dict(color=color, width=1),
            ),
            row=row,
            col=1,
        )

    if indicator == "RSI":
        fig.add_hline(y=70, line_dash="dash", line_color="red", line_width=1, row=row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", line_width=1, row=row, col=1)
    elif indicator == "Stochastic":
        fig.add_hline(y=80, line_dash="dash", line_color="gray", line_width=1, row=row, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="gray", line_width=1, row=row, col=1)
    elif indicator == "ADX":
        fig.add_hline(y=20, line_dash="dash", line_color="orange", line_width=1, row=row, col=1)

    fig.update_yaxes(title_text=indicator, row=row, col=1)


def technical_analysis_page(engine):
    st.header("Technical Analysis")

    tech_df_key = "tech_df"
    tech_ticker_key = "tech_ticker"
    tech_snapshot_key = "tech_snapshot"
    tech_snapshot_params_key = "tech_snapshot_params"

    if tech_df_key not in st.session_state:
        st.session_state[tech_df_key] = None
    if tech_ticker_key not in st.session_state:
        st.session_state[tech_ticker_key] = ""
    if tech_snapshot_key not in st.session_state:
        st.session_state[tech_snapshot_key] = None
    if tech_snapshot_params_key not in st.session_state:
        st.session_state[tech_snapshot_params_key] = None

    def clear_cache():
        st.session_state[tech_df_key] = None
        st.session_state[tech_ticker_key] = ""
        st.session_state[tech_snapshot_key] = None
        st.session_state[tech_snapshot_params_key] = None

    if st.sidebar.button("Clear Cache", key="clear_cache_sidebar"):
        clear_cache()

    with st.sidebar:
        st.header("Input Options")
        ticker = st.text_input("Ticker Code", value="FPT").upper()
        timeframe = st.selectbox("Timeframe", ["Day", "Week", "Month"], index=0)
        limit = st.number_input("Max Time (Lookback)", min_value=10, value=100, step=10)

        st.subheader("Chart Indicator")
        chart_indicator = st.selectbox(
            "Show one indicator",
            options=TECHNICAL_CHART_OPTIONS,
            index=0,
        )

        pair_options = get_ma_pair_options(timeframe)
        selected_pair_label = st.selectbox(
            "MA Cross Pair",
            options=pair_options,
            index=0,
            disabled=not pair_options,
        )
        if st.button("Clear Cache", key="clear_cache_input"):
            clear_cache()

    selected_pair = parse_ma_pair(selected_pair_label)
    short_ma, long_ma = selected_pair if selected_pair else (0, 0)
    current_params = (ticker, timeframe, int(limit), short_ma, long_ma)

    if st.button("Analyze"):
        data_key = f"{ticker}_{timeframe}_{limit}"
        if st.session_state.get(data_key) is None:
            with st.spinner("Fetching data..."):
                raw_df = fetch_data(ticker, timeframe, limit, engine)
                st.session_state[data_key] = raw_df
        else:
            raw_df = st.session_state[data_key]

        st.session_state[tech_ticker_key] = ticker
        if raw_df.empty:
            st.session_state[tech_df_key] = None
            st.session_state[tech_snapshot_key] = None
            st.warning(f"No data found for {ticker} with timeframe {timeframe}.")
            return

        snapshot = build_technical_snapshot(raw_df, short_ma, long_ma)
        st.session_state[tech_snapshot_key] = snapshot
        st.session_state[tech_snapshot_params_key] = current_params
        st.session_state[tech_df_key] = snapshot["data"]

    snapshot = st.session_state[tech_snapshot_key]
    if snapshot is None or st.session_state[tech_snapshot_params_key] != current_params:
        return

    df = snapshot["data"]
    report_by_name = {record["indicator"]: record for record in snapshot["report"]}
    st.subheader(f"Data for {ticker} ({timeframe})")

    with st.expander("View Raw Data"):
        st.caption("Price values shown in k VND; volume remains raw shares.")
        st.dataframe(df, use_container_width=True)

    spec = get_indicator_chart_spec(chart_indicator, short_ma, long_ma)
    panel_selected = spec is not None and spec["kind"] == "panel"
    rows = 3 if panel_selected else 2
    row_heights = [0.55, 0.2, 0.25] if panel_selected else [0.7, 0.3]
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
    )

    fig.add_trace(build_price_candlestick(df), row=1, col=1)
    volume_colors = [
        "green" if close >= open_ else "red"
        for close, open_ in zip(df["close"], df["open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["volume"],
            name="Volume",
            marker_color=volume_colors,
        ),
        row=2,
        col=1,
    )
    _add_selected_indicator(
        fig,
        df,
        chart_indicator,
        spec,
        3,
        short_ma,
        long_ma,
    )

    if timeframe == "Day" and not df.empty:
        all_dates = pd.date_range(start=df["date"].iloc[0], end=df["date"].iloc[-1])
        observed_dates = {date.strftime("%Y-%m-%d") for date in df["date"]}
        missing_dates = [
            date.strftime("%Y-%m-%d")
            for date in all_dates
            if date.strftime("%Y-%m-%d") not in observed_dates
        ]
        fig.update_xaxes(rangebreaks=[dict(values=missing_dates)])

    chart_height = 600 + (150 if panel_selected else 0)
    fig.update_layout(xaxis_rangeslider_visible=False, height=chart_height, showlegend=True)
    fig.update_yaxes(title_text="Price (k VND)", row=1, col=1)
    st.subheader(f"Price, Volume & {chart_indicator}")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Technical Indicators Details")
    tabs = st.tabs(TECHNICAL_INDICATOR_TABS)

    with tabs[0]:
        overview_rows = [
            {
                "Indicator": record["indicator"],
                "Dimension": record["dimension"],
                "Role": record["role"],
                "Value": record["value"],
                "Final Trend": record["trend"],
            }
            for record in snapshot["report"]
        ]
        st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)
        adx_value = snapshot["adx_value"]
        if adx_value is None:
            st.info("ADX gate not applied because ADX is unavailable.")
        elif adx_value < 20:
            st.info(f"ADX is {adx_value:.2f}: trend-direction contribution is multiplied by 0.5.")
        else:
            st.info(f"ADX is {adx_value:.2f}: trend-direction contribution keeps full weight.")

    for tab, indicator in zip(tabs[1:], TECHNICAL_CHART_OPTIONS):
        with tab:
            record = report_by_name[_report_name(indicator)]
            st.metric("Final Trend", record["trend"])
            st.markdown(
                f"**Dimension:** {record['dimension']}  \n"
                f"**Role:** {record['role']}  \n"
                f"**Latest values:** {record['value']}"
            )
            st.caption(_INDICATOR_RULES[indicator])

            if indicator == "ADX":
                adx_value = snapshot["adx_value"]
                if adx_value is None:
                    st.info("Gate not applied: ADX is unavailable.")
                elif adx_value < 20:
                    st.info("Gate applied: trend-direction contribution × 0.5.")
                else:
                    st.info("Gate not reducing trend-direction contribution.")

            detail_spec = get_indicator_chart_spec(indicator, short_ma, long_ma)
            display_columns = ["date"] + [
                column for column in detail_spec["columns"] if column in df.columns
            ]
            if len(display_columns) == 1:
                st.info("Not enough data to display this indicator.")
            else:
                st.dataframe(
                    df[display_columns].tail(20).sort_values("date", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )
