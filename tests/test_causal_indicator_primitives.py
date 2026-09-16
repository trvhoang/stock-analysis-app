"""Golden causal contracts for the shared indicator implementation."""

import unittest

import numpy as np
import pandas as pd

from commons.causal_indicators import (
    SUPERTREND_FORMULA_ID,
    adx_dmi,
    alligator_hl2,
    atr,
    bollinger,
    ema,
    obv,
    prior_extrema,
    relative_volume,
    rsi,
    sma,
    stochastic,
    supertrend,
)


def ohlcv(high, low, close, volume=None):
    """Return a small numeric OHLCV fixture with a stable integer index."""

    return pd.DataFrame(
        {
            "high": high,
            "low": low,
            "close": close,
            "volume": volume if volume is not None else [100] * len(close),
        }
    )


class CausalIndicatorGoldenTests(unittest.TestCase):
    def test_sma_and_ema_have_literal_completed_bar_warmup_values(self):
        close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

        np.testing.assert_allclose(
            sma(close, 3).to_numpy(),
            np.array([np.nan, np.nan, 2.0, 3.0, 4.0]),
            equal_nan=True,
        )
        np.testing.assert_allclose(
            ema(close, 3).to_numpy(),
            np.array([np.nan, np.nan, 2.25, 3.125, 4.0625]),
            equal_nan=True,
        )

    def test_rsi_atr_and_adx_use_exact_sma_seeded_wilder_values(self):
        close = pd.Series([10.0, 11.0, 14.0, 13.0, 15.0, 14.0, 18.0])
        np.testing.assert_allclose(
            rsi(close, 3).to_numpy(),
            np.array([np.nan, np.nan, np.nan, 80.0, 87.5, 68.29268292682927, 86.3157894736842]),
            rtol=1e-12,
            equal_nan=True,
        )

        atr_frame = ohlcv(
            [10.0, 13.0, 13.0, 15.0, 14.0],
            [8.0, 9.0, 10.0, 11.0, 10.0],
            [9.0, 12.0, 11.0, 14.0, 12.0],
        )
        np.testing.assert_allclose(
            atr(atr_frame, 3).to_numpy(),
            np.array([np.nan, np.nan, 3.0, 10.0 / 3.0, 32.0 / 9.0]),
            rtol=1e-12,
            equal_nan=True,
        )

        adx_frame = ohlcv(
            [10.0, 11.0, 12.0, 11.0, 10.0, 11.0],
            [8.0, 9.0, 10.0, 8.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 9.0, 8.0, 10.0],
        )
        values = adx_dmi(adx_frame, 3)
        np.testing.assert_allclose(
            values["adx"].to_numpy(),
            np.array([np.nan, np.nan, np.nan, np.nan, 54.94252873563219, 37.02050935316655]),
            rtol=1e-12,
            equal_nan=True,
        )
        self.assertGreater(values.loc[2, "plus_di"], 0.0)
        self.assertGreater(values.loc[3, "minus_di"], 0.0)

    def test_hl2_alligator_stochastic_volume_obv_and_prior_extrema_are_causal(self):
        frame = ohlcv(
            [3.0, 4.0, 5.0, 6.0, 7.0],
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [2.0, 3.0, 4.0, 5.0, 6.0],
            [10.0, 20.0, 30.0, 60.0, 60.0],
        )
        alligator = alligator_hl2(
            frame,
            jaw_period=3,
            teeth_period=3,
            lips_period=3,
            jaw_offset=1,
            teeth_offset=0,
            lips_offset=0,
        )
        np.testing.assert_allclose(
            alligator["jaw"].to_numpy(),
            np.array([np.nan, np.nan, np.nan, 3.0, 11.0 / 3.0]),
            equal_nan=True,
        )
        np.testing.assert_allclose(
            alligator["teeth"].to_numpy(),
            np.array([np.nan, np.nan, 3.0, 11.0 / 3.0, 40.0 / 9.0]),
            equal_nan=True,
        )

        stoch = stochastic(frame, k_period=3, k_smoothing=2, d_period=2)
        np.testing.assert_allclose(
            stoch["raw_k"].to_numpy(),
            np.array([np.nan, np.nan, 75.0, 75.0, 75.0]),
            equal_nan=True,
        )
        np.testing.assert_allclose(
            stoch["k"].to_numpy(),
            np.array([np.nan, np.nan, np.nan, 75.0, 75.0]),
            equal_nan=True,
        )
        np.testing.assert_allclose(
            stoch["d"].to_numpy(),
            np.array([np.nan, np.nan, np.nan, np.nan, 75.0]),
            equal_nan=True,
        )

        volume = relative_volume(frame["volume"], 2)
        np.testing.assert_allclose(
            volume["baseline"].to_numpy(),
            np.array([np.nan, np.nan, 15.0, 25.0, 45.0]),
            equal_nan=True,
        )
        np.testing.assert_allclose(
            volume["relative_volume"].to_numpy(),
            np.array([np.nan, np.nan, 2.0, 2.4, 60.0 / 45.0]),
            equal_nan=True,
        )
        np.testing.assert_allclose(obv(frame["close"], frame["volume"]).to_numpy(), [0.0, 20.0, 50.0, 110.0, 170.0])

        extrema = prior_extrema(frame, 2)
        np.testing.assert_allclose(extrema["prior_high"].to_numpy(), [np.nan, np.nan, 4.0, 5.0, 6.0], equal_nan=True)
        np.testing.assert_allclose(extrema["prior_low"].to_numpy(), [np.nan, np.nan, 1.0, 2.0, 3.0], equal_nan=True)

    def test_bollinger_uses_sample_std_and_flat_bands_never_emit_percent_b(self):
        bands = bollinger(pd.Series([1.0, 2.0, 3.0]), 3, 2.0)
        np.testing.assert_allclose(bands["middle"].to_numpy(), [np.nan, np.nan, 2.0], equal_nan=True)
        np.testing.assert_allclose(bands["upper"].to_numpy(), [np.nan, np.nan, 4.0], equal_nan=True)
        np.testing.assert_allclose(bands["lower"].to_numpy(), [np.nan, np.nan, 0.0], equal_nan=True)
        np.testing.assert_allclose(bands["bandwidth"].to_numpy(), [np.nan, np.nan, 200.0], equal_nan=True)
        np.testing.assert_allclose(bands["percent_b"].to_numpy(), [np.nan, np.nan, 0.75], equal_nan=True)

        flat = bollinger(pd.Series([5.0, 5.0, 5.0]), 3, 2.0)
        self.assertEqual(0.0, flat.loc[2, "bandwidth"])
        self.assertTrue(pd.isna(flat.loc[2, "percent_b"]))

    def test_supertrend_has_a_versioned_recursive_completed_bar_contract(self):
        self.assertEqual("supertrend-hl2-wilder-v1", SUPERTREND_FORMULA_ID)
        frame = ohlcv(
            [10.0, 11.0, 12.0, 15.0, 13.0, 10.0, 8.0, 16.0],
            [8.0, 9.0, 10.0, 13.0, 11.0, 8.0, 6.0, 14.0],
            [9.0, 10.0, 11.0, 14.0, 11.0, 9.0, 7.0, 15.0],
        )
        values = supertrend(frame, period=2, multiplier=2.0)
        np.testing.assert_allclose(
            values["final_upper"].to_numpy(),
            [np.nan, 14.0, 14.0, 14.0, 14.0, 14.0, 13.0, 13.0],
            equal_nan=True,
        )
        np.testing.assert_allclose(
            values["final_lower"].to_numpy(),
            [np.nan, 6.0, 7.0, 8.0, 8.0, 8.0, 8.0, 3.0],
            equal_nan=True,
        )
        np.testing.assert_allclose(
            values["direction"].to_numpy(),
            [np.nan, 1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0],
            equal_nan=True,
        )
        # Equal to the prior upper band at row 3: strict break only, no flip.
        self.assertEqual(1.0, values.loc[3, "direction"])
        self.assertEqual(13.0, values.loc[6, "supertrend"])
        self.assertEqual(3.0, values.loc[7, "supertrend"])

    def test_appending_future_rows_cannot_rewrite_prior_values(self):
        original = ohlcv(
            [10, 11, 12, 15, 13, 10, 8, 16],
            [8, 9, 10, 13, 11, 8, 6, 14],
            [9, 10, 11, 14, 11, 9, 7, 15],
            [100, 120, 140, 160, 180, 200, 220, 240],
        )
        future = pd.concat(
            [original, ohlcv([1000, 1100], [900, 1000], [950, 1050], [10000, 11000])],
            ignore_index=True,
        )
        before = supertrend(original, period=2, multiplier=2.0)
        after = supertrend(future, period=2, multiplier=2.0)
        pd.testing.assert_frame_equal(before, after.iloc[: len(before)].reset_index(drop=True))


if __name__ == "__main__":
    unittest.main()
