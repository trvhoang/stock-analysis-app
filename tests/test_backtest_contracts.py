import json
import unittest
from datetime import date
from dataclasses import fields

from backtest_engine.config import (
    HORIZONS,
    THEME_VARIANTS,
    BacktestBatchConfig,
    BacktestConfig,
    rulebook_for,
)
from backtest_engine.models import JobStatus, RulebookExecution, TradeEvent


class BacktestContractTests(unittest.TestCase):
    def test_default_config_is_long_only_and_uses_the_swing_rulebook(self):
        config = BacktestConfig.for_ticker("FPT")
        rule = rulebook_for(config.horizon)

        self.assertEqual(config.ticker, "FPT")
        self.assertEqual(config.horizon, "swing")
        self.assertEqual(rule.rule_id, "swing_rulebook_v5")
        self.assertEqual(rule.max_hold_bars, 22)
        self.assertEqual(rule.min_n, 5)
        self.assertEqual(rule.atr_period, 14)
        self.assertEqual(rule.atr_sl_multiplier, 1.5)
        self.assertEqual(rule.atr_tp_multiplier, 2.5)
        self.assertEqual(config.permutation_count, 1000)
        self.assertEqual(config.permutation_seed, 42)
        self.assertEqual(config.permutation_block_size, 20)
        self.assertNotIn("deflated_sharpe_cutoff", {field.name for field in fields(config)})
        self.assertEqual(config.worker_count, 6)

    def test_midterm_config_uses_weekly_timeout(self):
        config = BacktestConfig.for_ticker("FPT", horizon="midterm")
        rule = rulebook_for(config.horizon)

        self.assertEqual(config.horizon, "midterm")
        self.assertEqual(rule.native_timeframe, "weekly")
        self.assertEqual(rule.max_hold_bars, 16)
        self.assertEqual(rule.min_n, 5)

    def test_weekly_ohlcv_aggregates_complete_daily_weeks_without_mutation(self):
        import pandas as pd

        from backtest_engine.timeframes import to_weekly_ohlcv

        daily = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=10, freq="B"),
                "open": list(range(100, 110)),
                "high": list(range(102, 112)),
                "low": list(range(99, 109)),
                "close": list(range(100, 110)),
                "volume": [1000] * 10,
            }
        )
        original = daily.copy(deep=True)

        weekly = to_weekly_ohlcv(daily, common_as_of=date(2024, 1, 12))

        self.assertEqual(weekly["date"].tolist(), list(pd.to_datetime(["2024-01-05", "2024-01-12"])))
        self.assertEqual(weekly["open"].tolist(), [100, 105])
        self.assertEqual(weekly["high"].tolist(), [106, 111])
        self.assertEqual(weekly["low"].tolist(), [99, 104])
        self.assertEqual(weekly["close"].tolist(), [104, 109])
        self.assertEqual(weekly["volume"].tolist(), [5000, 5000])
        pd.testing.assert_frame_equal(daily, original)

    def test_weekly_ohlcv_never_emits_a_friday_after_the_common_cutoff(self):
        import pandas as pd

        from backtest_engine.timeframes import to_weekly_ohlcv

        daily = pd.DataFrame(
            {
                "date": pd.bdate_range("2024-05-06", "2024-05-20"),
                "open": [100] * 11,
                "high": [101] * 11,
                "low": [99] * 11,
                "close": [100] * 11,
                "volume": [1000] * 11,
            }
        )

        historical = to_weekly_ohlcv(
            daily.loc[daily["date"].le(pd.Timestamp("2024-05-15"))],
            common_as_of=date(2024, 5, 15),
        )
        with_future_rows = to_weekly_ohlcv(
            daily,
            common_as_of=date(2024, 5, 15),
        )

        self.assertEqual(date(2024, 5, 10), historical["date"].max().date())
        pd.testing.assert_frame_equal(historical, with_future_rows)

    def test_latest_common_completed_bar_uses_every_named_source(self):
        import pandas as pd

        from backtest_engine.timeframes import latest_common_completed_bar

        sources = {
            "FPT": pd.DataFrame({"date": pd.to_datetime(["2024-01-10", "2024-01-12"])}),
            "VCB": pd.DataFrame({"date": pd.to_datetime(["2024-01-09", "2024-01-11"])}),
            "VNINDEX": pd.DataFrame({"date": pd.to_datetime(["2024-01-10", "2024-01-15"])}),
        }

        self.assertEqual(
            date(2024, 1, 11),
            latest_common_completed_bar(sources, date(2024, 1, 15)),
        )
        with self.assertRaisesRegex(ValueError, "MISSING"):
            latest_common_completed_bar(
                {"MISSING": pd.DataFrame({"date": pd.to_datetime(["2024-01-16"])})},
                date(2024, 1, 15),
            )

    def test_config_rejects_invalid_values_and_normalizes_ticker(self):
        self.assertEqual(BacktestConfig.for_ticker(" fpt ").ticker, "FPT")

        with self.assertRaises(ValueError):
            BacktestConfig.for_ticker("FPT", horizon="longterm")
        with self.assertRaises(TypeError):
            BacktestConfig.for_ticker("FPT", theme_variant="old-theme")
        with self.assertRaises(TypeError):
            BacktestConfig.for_ticker("FPT", threshold_score_buy=55)

    def test_batch_config_accepts_fifteen_tickers_and_rejects_sixteen(self):
        tickers = tuple(f"T{index:02d}" for index in range(1, 16))

        try:
            config = BacktestBatchConfig(tickers=tickers)
        except ValueError as error:
            self.fail(f"15-ticker batch was rejected: {error}")
        self.assertEqual(config.tickers, tickers)
        with self.assertRaisesRegex(ValueError, "between 1 and 15"):
            BacktestBatchConfig(tickers=(*tickers, "T16"))

    def test_contract_constants_are_closed_sets(self):
        self.assertEqual(
            THEME_VARIANTS,
            ("no-background-theme", "background-theme"),
        )
        self.assertEqual(HORIZONS, ("swing", "midterm"))

    def test_rulebook_execution_is_the_only_new_run_identity(self):
        execution = RulebookExecution(
            rulebook_for("swing"), ("rulebook_adx_gate",)
        )

        self.assertEqual(execution.rule_id, "swing_rulebook_v5__adx")
        self.assertEqual(execution.theme_variant, "no-background-theme")
        self.assertNotIn("strategy_id", {field.name for field in fields(execution)})

    def test_trade_event_and_job_status_serialize_to_json(self):
        trade = TradeEvent(
            signal_date=date(2025, 1, 2),
            entry_date=date(2025, 1, 3),
            entry_price=50300,
            atr=1200,
            stop_loss=48500,
            take_profit=53300,
            exit_date=date(2025, 1, 8),
            exit_price=53300,
            exit_reason="take_profit",
            return_pct=6.0,
            source_window=(date(2024, 7, 1), date(2025, 1, 1)),
        )
        status = JobStatus(
            job_id="job-1",
            state="done",
            progress=1.0,
            output_paths=("ticker-signals/FPT/FPT_signals_no-background-theme.json",),
        )

        self.assertEqual(json.loads(json.dumps(trade.to_dict()))["entry_price"], 50300)
        self.assertEqual(json.loads(json.dumps(status.to_dict()))["state"], "done")

    def test_job_status_rejects_invalid_state_or_progress(self):
        with self.assertRaises(ValueError):
            JobStatus(job_id="job-1", state="finished")
        with self.assertRaises(ValueError):
            JobStatus(job_id="job-1", state="queued", progress=1.1)


if __name__ == "__main__":
    unittest.main()
