"""Horizon-native Technical Analysis inputs owned by the Backtest rulebooks."""

import pandas as pd

from backtest_engine.config import RulebookSpec, rulebook_for
from backtest_engine.indicators import build_indicator_frame, series_upcross
from commons.price_utils import PRICE_OUTPUT_UI, prepare_price_for_output
from commons.technical_analysis import (
    _format_indicator_value,
    _format_price_value,
    _latest_numeric_value,
    calculate_adx_trend,
    calculate_atr_trend,
    calculate_bollinger,
    calculate_bollinger_trend,
    calculate_ma_cross_trend,
    calculate_ma_trend,
    calculate_obv,
    calculate_obv_trend,
    calculate_rsi_trend,
    calculate_stochastic,
    fetch_calendar_technical_history,
)


TECHNICAL_NATIVE_BAR_LIMIT = 100
TECHNICAL_SOURCE_ROW_LIMIT = {
    "swing": TECHNICAL_NATIVE_BAR_LIMIT,
    # Daily rows cover 100 completed W-FRI bars plus indicator warm-up.
    "midterm": 800,
}

_HORIZON_LABELS = {
    "swing": "swing",
    "mid-term": "midterm",
}


def normalize_technical_horizon(value: object) -> str:
    """Map the two UI labels to the immutable Backtest horizon names."""
    normalized = str(value or "").strip().casefold()
    try:
        return _HORIZON_LABELS[normalized]
    except KeyError as error:
        raise ValueError("horizon must be Swing or Mid-term") from error


def fetch_horizon_source(ticker: str, horizon: object, engine) -> pd.DataFrame:
    """Load enough unscaled daily history for one native horizon snapshot."""
    normalized_horizon = normalize_technical_horizon(horizon)
    return fetch_calendar_technical_history(
        ticker,
        TECHNICAL_SOURCE_ROW_LIMIT[normalized_horizon],
        engine,
    )


def build_horizon_native_frame(
    source: pd.DataFrame,
    horizon: object,
) -> tuple[pd.DataFrame, RulebookSpec]:
    """Build the exact Backtest frame, then retain up to 100 native bars."""
    normalized_horizon = normalize_technical_horizon(horizon)
    if not isinstance(source, pd.DataFrame) or source.empty:
        raise ValueError("technical history is empty")
    if "date" not in source.columns:
        raise ValueError("technical history requires a date column")

    # DB reads are descending; Backtest validation deliberately requires
    # ascending input so indicator recurrences remain causal and auditable.
    working = source.copy(deep=True)
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    if working["date"].isna().any():
        raise ValueError("technical history contains invalid dates")
    working = working.sort_values("date").reset_index(drop=True)
    rulebook = rulebook_for(normalized_horizon)
    frame = build_indicator_frame(
        working,
        normalized_horizon,
        common_as_of=pd.Timestamp(working["date"].iloc[-1]).date(),
    )
    return frame.tail(TECHNICAL_NATIVE_BAR_LIMIT).reset_index(drop=True), rulebook


def _alligator_trend(frame: pd.DataFrame) -> str:
    """Translate the Backtest-owned Alligator point to a display trend."""
    point = _latest_numeric_value(frame, "rulebook_alligator_point")
    return {1.0: "Down", 2.0: "Sideways", 3.0: "Up"}.get(point, "Unknown")


def _recent_cross_value(frame: pd.DataFrame, column: str) -> str:
    """Format recent exact-MA crossing events without exposing raw flags."""
    if column not in frame.columns:
        return "None"
    labels = {1: "Golden", -1: "Death"}
    events = frame.loc[frame[column] != 0, column].tail(3).tolist()
    return " - ".join(labels.get(event, "Unknown") for event in events) or "None"


def _scaled_price_value(value: float | None, digits: int = 2) -> str:
    """Format one raw BIGINT-derived value at the only UI scaling boundary."""
    if value is None:
        return "N/A"
    return _format_price_value(value / 1000, digits)


def _build_report(
    working: pd.DataFrame,
    rulebook: RulebookSpec,
    stochastic_trend: str,
) -> tuple[list[dict[str, object]], float | None]:
    """Return the nine existing/new display records from one raw native frame."""
    fast_period, slow_period = rulebook.ma_pair
    short_column = f"{rulebook.ma_kind}_{fast_period}"
    long_column = f"{rulebook.ma_kind}_{slow_period}"
    rsi_column = f"RSI_{rulebook.rsi_period}"
    cross_column = f"cross_{fast_period}_{slow_period}"

    values = {
        "ma_short": _latest_numeric_value(working, short_column),
        "ma_long": _latest_numeric_value(working, long_column),
        "alligator_lips": _latest_numeric_value(working, "ALLIGATOR_LIPS"),
        "alligator_teeth": _latest_numeric_value(working, "ALLIGATOR_TEETH"),
        "alligator_jaw": _latest_numeric_value(working, "ALLIGATOR_JAW"),
        "rsi": _latest_numeric_value(working, rsi_column),
        "stoch_k": _latest_numeric_value(working, "%K"),
        "stoch_d": _latest_numeric_value(working, "%D"),
        "adx": _latest_numeric_value(working, "ADX_14"),
        "dmp": _latest_numeric_value(working, "DMP_14"),
        "dmn": _latest_numeric_value(working, "DMN_14"),
        "obv": _latest_numeric_value(working, "OBV"),
        "atr": _latest_numeric_value(working, "ATR_14"),
        "bbm": _latest_numeric_value(working, "BBM_20_2"),
        "bbu": _latest_numeric_value(working, "BBU_20_2"),
        "bbl": _latest_numeric_value(working, "BBL_20_2"),
        "bbb": _latest_numeric_value(working, "BBB_20_2"),
        "bbp": _latest_numeric_value(working, "BBP_20_2"),
    }
    report = [
        {
            "indicator": "MA",
            "dimension": "trend_direction",
            "role": "vote",
            "value": (
                f"{short_column}: {_scaled_price_value(values['ma_short'], 1)} - "
                f"{long_column}: {_scaled_price_value(values['ma_long'], 1)}"
            ),
            "trend": calculate_ma_trend(working, short_column, long_column),
        },
        {
            "indicator": "MA cross",
            "dimension": "trend_direction",
            "role": "vote",
            "value": _recent_cross_value(working, cross_column),
            "trend": calculate_ma_cross_trend(working, cross_column),
        },
        {
            "indicator": "Alligator",
            "dimension": "trend_direction",
            "role": "gate",
            "value": (
                f"Lips: {_scaled_price_value(values['alligator_lips'])} - "
                f"Teeth: {_scaled_price_value(values['alligator_teeth'])} - "
                f"Jaw: {_scaled_price_value(values['alligator_jaw'])}"
            ),
            "trend": _alligator_trend(working),
        },
        {
            "indicator": "RSI",
            "dimension": "momentum",
            "role": "vote",
            "value": _format_indicator_value(values["rsi"], 1),
            "trend": calculate_rsi_trend(working, rsi_column),
        },
        {
            "indicator": "Stochastic",
            "dimension": "momentum",
            "role": "vote",
            "value": (
                f"%K: {_format_indicator_value(values['stoch_k'], 1)} - "
                f"%D: {_format_indicator_value(values['stoch_d'], 1)}"
            ),
            "trend": stochastic_trend,
        },
        {
            "indicator": "ADX",
            "dimension": "trend_strength",
            "role": "gate",
            "value": (
                f"ADX: {_format_indicator_value(values['adx'], 1)} - "
                f"+DI: {_format_indicator_value(values['dmp'], 1)} - "
                f"-DI: {_format_indicator_value(values['dmn'], 1)}"
            ),
            "trend": calculate_adx_trend(working),
        },
        {
            "indicator": "OBV",
            "dimension": "volume",
            "role": "vote",
            "value": _format_indicator_value(values["obv"], 0),
            "trend": calculate_obv_trend(working),
        },
        {
            "indicator": "ATR",
            "dimension": "volatility",
            "role": "vote",
            "value": _scaled_price_value(values["atr"]),
            "trend": calculate_atr_trend(working),
        },
        {
            "indicator": "Bollinger",
            "dimension": "volatility",
            "role": "vote",
            "value": (
                f"Middle: {_scaled_price_value(values['bbm'])} - "
                f"Upper: {_scaled_price_value(values['bbu'])} - "
                f"Lower: {_scaled_price_value(values['bbl'])} - "
                f"Bandwidth: {_format_indicator_value(values['bbb'], 2)}% - "
                f"%B: {_format_indicator_value(values['bbp'], 2)}"
            ),
            "trend": calculate_bollinger_trend(working),
        },
    ]
    return report, values["adx"]


def build_horizon_technical_snapshot(
    source: pd.DataFrame,
    horizon: object,
) -> dict[str, object]:
    """Build a UI-ready nine-indicator snapshot from raw daily history.

    Backtest owns the causal MA, Alligator, RSI, ADX, and ATR calculations.
    Technical Analysis adds only its established Stochastic, OBV, and
    Bollinger values, then converts price columns to k VND exactly once.
    """
    working, rulebook = build_horizon_native_frame(source, horizon)
    fast_period, slow_period = rulebook.ma_pair
    short_column = f"{rulebook.ma_kind}_{fast_period}"
    long_column = f"{rulebook.ma_kind}_{slow_period}"
    rsi_column = f"RSI_{rulebook.rsi_period}"
    cross_column = f"cross_{fast_period}_{slow_period}"

    working[short_column] = working["rulebook_ma_fast"]
    working[long_column] = working["rulebook_ma_slow"]
    working[rsi_column] = working["rulebook_rsi"]
    working["ADX_14"] = working["rulebook_adx_14"]
    working["DMP_14"] = working["rulebook_plus_di_14"]
    working["DMN_14"] = working["rulebook_minus_di_14"]
    working["ALLIGATOR_JAW"] = working["rulebook_alligator_jaw"]
    working["ALLIGATOR_TEETH"] = working["rulebook_alligator_teeth"]
    working["ALLIGATOR_LIPS"] = working["rulebook_alligator_lips"]
    working[cross_column] = 0
    working.loc[series_upcross(working[short_column], working[long_column]), cross_column] = 1
    working.loc[series_upcross(working[long_column], working[short_column]), cross_column] = -1
    working, stochastic_trend = calculate_stochastic(working)
    working["OBV"] = calculate_obv(working)
    working = working.join(calculate_bollinger(working, period=20, std_mult=2))

    report, adx_value = _build_report(working, rulebook, stochastic_trend)
    signals = [
        [index, record["indicator"], record["value"], record["trend"]]
        for index, record in enumerate(report)
    ]

    display_columns = [
        "open", "high", "low", "close", short_column, long_column,
        "ALLIGATOR_JAW", "ALLIGATOR_TEETH", "ALLIGATOR_LIPS", "ATR_14",
        "BBM_20_2", "BBU_20_2", "BBL_20_2",
    ]
    for column in display_columns:
        if column in working.columns:
            working[column] = prepare_price_for_output(
                working[column], PRICE_OUTPUT_UI
            )
    working = working.drop(
        columns=[column for column in working.columns if column.startswith("rulebook_")]
    )
    normalized_horizon = normalize_technical_horizon(horizon)
    return {
        "data": working,
        "signals": signals,
        "report": report,
        "adx_value": adx_value,
        "profile": {
            "horizon": normalized_horizon,
            "label": "Swing" if normalized_horizon == "swing" else "Mid-term",
            "ma_kind": rulebook.ma_kind,
            "short_ma": fast_period,
            "long_ma": slow_period,
            "rsi_period": rulebook.rsi_period,
            "native_timeframe": rulebook.native_timeframe,
        },
        "common_as_of": pd.Timestamp(working["date"].max()).date(),
    }


__all__ = [
    "TECHNICAL_NATIVE_BAR_LIMIT",
    "TECHNICAL_SOURCE_ROW_LIMIT",
    "build_horizon_technical_snapshot",
    "build_horizon_native_frame",
    "fetch_horizon_source",
    "normalize_technical_horizon",
]
