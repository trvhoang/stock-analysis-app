"""Shared price-output rules for UI and export consumers."""

from decimal import Decimal, InvalidOperation

import pandas as pd


PRICE_OUTPUT_UI = "ui"
PRICE_OUTPUT_EXPORT = "export"


def price_from_ui_k_vnd(value: object) -> int:
    """Convert a positive UI ``k VND`` value to the raw BIGINT representation."""

    try:
        price_k_vnd = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("price must be a valid k VND number") from error
    if not price_k_vnd.is_finite() or price_k_vnd <= 0:
        raise ValueError("price must be positive")
    if price_k_vnd.as_tuple().exponent < -3:
        raise ValueError("price must have at most three decimal places")

    raw_price = price_k_vnd * Decimal(1000)
    if raw_price != raw_price.to_integral_value():
        raise ValueError("price does not convert to an integral raw value")
    return int(raw_price)


def prepare_price_for_output(values, output):
    """Return prices in the explicitly requested output representation."""
    if output == PRICE_OUTPUT_EXPORT:
        # Export must preserve the database's original BIGINT value exactly.
        return values
    if output != PRICE_OUTPUT_UI:
        raise ValueError(f"Unsupported price output: {output}")

    # UI/Plotly prices use k VND while the database remains BIGINT x 1000.
    return pd.to_numeric(values, errors="coerce") / 1000
