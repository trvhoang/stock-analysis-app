"""V3 rulebook sequence boundary contracts."""

import unittest

import pandas as pd

from backtest_engine.config import ENTRY_GATE_NAMES, rulebook_for
from backtest_engine.models import RulebookExecution
from backtest_engine.rolling_window import Window, partition_completed_events, run_rulebook_trade_sequence


def make_frame(rows=30):
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=rows, freq="B"),
            "open": [100] * rows,
            "high": [105] * rows,
            "low": [95] * rows,
            "close": [100] * rows,
            "ATR_14": [10] * rows,
        }
    )


class RollingWindowTests(unittest.TestCase):
    def test_invalid_first_signal_does_not_block_a_later_valid_trade(self):
        frame = make_frame()
        frame.loc[1, "ATR_14"] = float("nan")
        entries = pd.Series(False, index=frame.index)
        entries.loc[1] = True
        entries.loc[3] = True

        events = run_rulebook_trade_sequence(
            frame,
            RulebookExecution(rulebook_for("swing"), ENTRY_GATE_NAMES),
            entries,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].signal_date, frame.loc[3, "date"])

    def test_partition_excludes_event_when_exit_crosses_report_boundary(self):
        event = type(
            "Event",
            (),
            {
                "signal_date": pd.Timestamp("2024-01-31"),
                "entry_date": pd.Timestamp("2024-01-31"),
                "exit_date": pd.Timestamp("2024-02-01"),
            },
        )()
        window = Window(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31"))

        self.assertEqual(partition_completed_events([event], window), [])


if __name__ == "__main__":
    unittest.main()
