"""Native-horizon monitoring tests for open manual Backtest positions."""

from __future__ import annotations

import copy
import unittest

import pandas as pd

from backtest_engine.position_monitor import monitor_position


def _daily_history(rows: int, close: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2026-01-05", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "open": [close] * rows,
            "high": [close + 2] * rows,
            "low": [close - 2] * rows,
            "close": [close] * rows,
            "volume": [1000] * rows,
        }
    )


def _position(horizon: str = "swing", max_hold_bars: int | None = None) -> dict[str, object]:
    return {
        "id": "position-1",
        "status": "open",
        "actual_buy_price": 100,
        "buy_date": "2026-01-05",
        "certified_signal": {"combo": {"horizon": horizon, "direction": "long"}},
        "risk_snapshot": {
            "atr": 5,
            "stop_loss": 80,
            "take_profit": 120,
            "max_hold_bars": max_hold_bars or (15 if horizon == "swing" else 16),
        },
    }


class PositionMonitorTests(unittest.TestCase):
    def test_v3_frozen_rulebook_snapshot_uses_its_horizon_without_combo_replay(self):
        history = _daily_history(4)
        position = _position()
        position["certified_signal"] = {
            "rule_id": "swing_rulebook_v3",
            "horizon": "swing",
            "metrics": ["win_rate", "profit", "sharpe"],
        }

        monitor = monitor_position(position, history, history.loc[3, "date"])

        self.assertEqual(monitor["horizon"], "swing")
    def test_swing_holding_first_exceeds_sixty_percent_at_tenth_daily_bar(self):
        history = _daily_history(15)
        position = _position()

        bar_nine = monitor_position(position, history, history.loc[8, "date"])
        bar_ten = monitor_position(position, history, history.loc[9, "date"])

        self.assertEqual(bar_nine["holding_bars"], 9)
        self.assertFalse(bar_nine["sell_allowed"])
        self.assertEqual(bar_ten["holding_bars"], 10)
        self.assertTrue(bar_ten["sell_allowed"])
        self.assertTrue(bar_ten["holding_period_exceeded"])

    def test_midterm_counts_weekly_periods_and_blocks_same_week_exit(self):
        history = _daily_history(16 * 5)
        position = _position("midterm")

        week_one = monitor_position(position, history, history.loc[4, "date"])
        week_nine = monitor_position(position, history, history.loc[44, "date"])
        week_ten = monitor_position(position, history, history.loc[49, "date"])

        self.assertEqual(week_one["holding_bars"], 1)
        self.assertFalse(week_one["exit_eligible"])
        self.assertEqual(week_nine["holding_bars"], 9)
        self.assertFalse(week_nine["sell_allowed"])
        self.assertEqual(week_ten["holding_bars"], 10)
        self.assertTrue(week_ten["sell_allowed"])
        self.assertEqual(week_ten["latest_close"], 100)

    def test_stop_and_take_profit_proximity_allow_manual_sell_after_minimum_hold(self):
        history = _daily_history(6)
        position = _position()

        history.loc[5, "close"] = 84
        stop_loss = monitor_position(position, history, history.loc[5, "date"])
        history.loc[5, "close"] = 114
        take_profit = monitor_position(position, history, history.loc[5, "date"])

        self.assertTrue(stop_loss["stop_loss_near"])
        self.assertTrue(stop_loss["sell_allowed"])
        self.assertTrue(take_profit["take_profit_near"])
        self.assertTrue(take_profit["sell_allowed"])

    def test_midterm_proximity_cannot_create_same_week_exit(self):
        history = _daily_history(5)
        history.loc[4, "close"] = 84

        result = monitor_position(_position("midterm"), history, history.loc[4, "date"])

        self.assertTrue(result["stop_loss_near"])
        self.assertFalse(result["exit_eligible"])
        self.assertFalse(result["sell_allowed"])

    def test_manual_weekend_buy_starts_from_first_database_session_after_buy(self):
        history = _daily_history(5)
        position = _position()
        position["buy_date"] = "2026-01-03"

        result = monitor_position(position, history, history.loc[4, "date"])

        self.assertEqual(result["holding_bars"], 5)

    def test_timeout_is_informational_and_future_rows_do_not_change_as_of_result(self):
        history = _daily_history(16)
        position = _position()
        as_of_date = history.loc[14, "date"]
        original = monitor_position(position, history, as_of_date)
        future_mutated = history.copy(deep=True)
        future_mutated.loc[15, ["open", "high", "low", "close"]] = 999
        unchanged = monitor_position(position, future_mutated, as_of_date)

        self.assertTrue(original["timeout_reached"])
        self.assertEqual(original, unchanged)
        self.assertEqual(position["status"], "open")


if __name__ == "__main__":
    unittest.main()
