"""Flat-to-flat V3 rulebook trade-execution contracts."""

import unittest

import pandas as pd

from backtest_engine.config import rulebook_for
from backtest_engine.models import RulebookExecution
from backtest_engine.rolling_window import run_rulebook_trade_sequence


def make_frame(rows=30, weekly=False, high_overrides=None, low_overrides=None):
    high_overrides = high_overrides or {}
    low_overrides = low_overrides or {}
    dates = pd.date_range(
        "2025-01-03",
        periods=rows,
        freq="W-FRI" if weekly else "B",
    )
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [100] * rows,
            "high": [105] * rows,
            "low": [95] * rows,
            "close": [100] * rows,
            "ATR_14": [10] * rows,
        }
    )
    for position, value in high_overrides.items():
        frame.loc[position, "high"] = value
    for position, value in low_overrides.items():
        frame.loc[position, "low"] = value
    return frame


class TradeExecutionTests(unittest.TestCase):
    def test_second_entry_is_ignored_until_first_rulebook_trade_is_closed(self):
        frame = make_frame(rows=30)
        entries = pd.Series(False, index=frame.index)
        entries.loc[1] = True
        entries.loc[2] = True

        events = run_rulebook_trade_sequence(
            frame,
            RulebookExecution(rulebook_for("swing"), ("rulebook_adx_gate",)),
            entries,
        )

        self.assertEqual(
            [(event.entry_date, event.exit_date) for event in events],
            [(frame.loc[2, "date"], frame.loc[23, "date"])],
        )

    def test_entry_is_next_open_and_same_bar_stop_target_is_stop_first(self):
        frame = make_frame(high_overrides={5: 130}, low_overrides={5: 80})
        entries = pd.Series(False, index=frame.index)
        entries.loc[1] = True

        events = run_rulebook_trade_sequence(
            frame,
            RulebookExecution(rulebook_for("swing"), ("rulebook_adx_gate",)),
            entries,
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.signal_date, frame.loc[1, "date"])
        self.assertEqual(event.entry_date, frame.loc[2, "date"])
        self.assertEqual(event.entry_price, 100)
        self.assertEqual(event.atr, 10)
        self.assertEqual(event.stop_loss, 85)
        self.assertEqual(event.take_profit, 125)
        self.assertEqual(event.exit_date, frame.loc[5, "date"])
        self.assertEqual(event.exit_reason, "stop_loss")

    def test_swing_timeout_is_inclusive_at_bar_twenty_two(self):
        frame = make_frame(rows=30)
        entries = pd.Series(False, index=frame.index)
        entries.loc[1] = True

        events = run_rulebook_trade_sequence(
            frame,
            RulebookExecution(rulebook_for("swing"), ("rulebook_adx_gate",)),
            entries,
        )

        self.assertEqual(events[0].exit_date, frame.loc[23, "date"])
        self.assertEqual(events[0].exit_reason, "timeout")

    def test_midterm_exit_can_first_fire_on_next_weekly_bar(self):
        frame = make_frame(rows=20, weekly=True, low_overrides={2: 80, 3: 80})
        entries = pd.Series(False, index=frame.index)
        entries.loc[1] = True

        events = run_rulebook_trade_sequence(
            frame,
            RulebookExecution(rulebook_for("midterm"), ("rulebook_adx_gate",)),
            entries,
        )

        self.assertEqual(events[0].entry_date, frame.loc[2, "date"])
        self.assertEqual(events[0].exit_date, frame.loc[3, "date"])
        self.assertEqual(events[0].exit_reason, "stop_loss")

    def test_signal_without_next_bar_or_complete_timeout_never_creates_a_trade(self):
        frame = make_frame(rows=4)
        entries = pd.Series(False, index=frame.index)
        entries.loc[3] = True

        self.assertEqual(
            run_rulebook_trade_sequence(
                frame,
                RulebookExecution(rulebook_for("swing"), ("rulebook_adx_gate",)),
                entries,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
