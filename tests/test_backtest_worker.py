"""Worker request decoding tests for Backtest V4 jobs."""

import unittest
from datetime import date

from backtest_engine.config import BacktestBatchConfig, BacktestConfig
from backtest_engine.worker import _config_from_payload


class BacktestWorkerTests(unittest.TestCase):
    def test_decodes_v4_batch_request_with_date_round_trip(self):
        config = BacktestBatchConfig(
            tickers=("FPT", "VCB"),
            start_date=date(2020, 1, 1),
            end_date=date(2026, 8, 14),
            horizon="midterm",
        )

        restored = _config_from_payload(config.to_dict())

        self.assertEqual(restored, config)

    def test_batch_group_round_trips_without_leaking_to_ticker_config(self):
        config = BacktestBatchConfig(tickers=("FPT",), group_name="bank")

        restored = _config_from_payload(config.to_dict())

        self.assertEqual(config.group_name, "BANK")
        self.assertEqual(restored.group_name, "BANK")
        self.assertNotIn("group_name", config.for_ticker("FPT").to_dict())

    def test_single_v4_request_decodes_to_the_batch_of_one_execution_service(self):
        config = BacktestConfig(
            ticker="FPT",
            horizon="midterm",
        )

        restored = _config_from_payload(config.to_dict())

        self.assertEqual(restored.tickers, ("FPT",))
        self.assertEqual(restored.horizon, "midterm")
        self.assertEqual(restored.group_name, "N/A")

    def test_rejects_unknown_explicit_worker_request_type(self):
        with self.assertRaisesRegex(ValueError, "request_type"):
            _config_from_payload({"request_type": "unknown"})

    def test_rejects_missing_and_v2_worker_request_types(self):
        with self.assertRaisesRegex(ValueError, "request_type"):
            _config_from_payload({"ticker": "FPT"})
        with self.assertRaisesRegex(ValueError, "not supported"):
            _config_from_payload({"request_type": "backtest_batch_v2"})


if __name__ == "__main__":
    unittest.main()
