"""Progressive, candidate-specific current signal state contracts."""

import unittest

import pandas as pd

from backtest_engine.signal_state import assess_signal_state


def _joint_frame(
    closes: list[int],
    *,
    entry_index: int = 1,
    joint_last: bool = True,
    atr: float = 10.0,
    contracting: bool = False,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build a causal Swing fixture with only the selected joint-trend source."""

    count = len(closes)
    dates = pd.bdate_range("2026-08-03", periods=count)
    spread = list(range(10, 10 + count))
    if contracting:
        spread = list(range(10 + count, 10, -1))
    frame = pd.DataFrame(
        {
            "date": dates,
            "close": closes,
            "ATR_14": [atr] * count,
            "rulebook_missing_required_input": [False] * count,
            "rulebook_joint_trend_pass": [False] + [True] * (count - 1),
            "rulebook_ma_fast": [100 + value for value in spread],
            "rulebook_ma_slow": [100] * count,
            "rulebook_alligator_lips": [130 + value for value in spread],
            "rulebook_alligator_teeth": [120] * count,
            "rulebook_alligator_jaw": [110 - value for value in spread],
        }
    )
    if not joint_last:
        frame.loc[frame.index[-1], "rulebook_joint_trend_pass"] = False
    entries = pd.Series([False] * count)
    entries.iloc[entry_index:] = True
    return frame, entries


class SignalStateTests(unittest.TestCase):
    def test_fresh_entry_is_fresh(self):
        frame, entries = _joint_frame([100, 102], entry_index=1)

        result = assess_signal_state(
            frame, entries, ("rulebook_joint_trend_pass",), "no-background-theme", "swing"
        )

        self.assertEqual(result["state"], "fresh")
        self.assertEqual(result["age_native_bars"], 0)

    def test_one_to_three_bars_with_holding_joint_trend_is_ongoing(self):
        frame, entries = _joint_frame([100, 102, 104, 106], entry_index=1)

        result = assess_signal_state(
            frame, entries, ("rulebook_joint_trend_pass",), "no-background-theme", "swing"
        )

        self.assertEqual(result["state"], "ongoing")
        self.assertEqual(result["age_native_bars"], 2)

    def test_more_than_six_bars_with_price_and_selected_support_stays_ongoing(self):
        frame, entries = _joint_frame([100, 102, 104, 106, 108, 110, 112, 114, 116], entry_index=1)

        result = assess_signal_state(
            frame, entries, ("rulebook_joint_trend_pass",), "no-background-theme", "swing"
        )

        self.assertEqual(result["state"], "ongoing")
        self.assertEqual(result["age_native_bars"], 7)

    def test_early_adverse_price_and_selected_source_contraction_is_weakening(self):
        frame, entries = _joint_frame(
            [100, 104, 102, 97], entry_index=1, atr=10.0, contracting=True
        )

        result = assess_signal_state(
            frame, entries, ("rulebook_joint_trend_pass",), "no-background-theme", "swing"
        )

        self.assertEqual(result["state"], "weakening")
        self.assertIn("adverse_price", result["reasons"])
        self.assertIn("joint_trend_deteriorating", result["reasons"])

    def test_selected_joint_gate_failure_is_invalidated_at_any_age(self):
        frame, entries = _joint_frame([100, 102, 104], entry_index=1, joint_last=False)

        result = assess_signal_state(
            frame, entries, ("rulebook_joint_trend_pass",), "no-background-theme", "swing"
        )

        self.assertEqual(result["state"], "invalidated")
        self.assertIn("joint_trend_failed", result["reasons"])


if __name__ == "__main__":
    unittest.main()
