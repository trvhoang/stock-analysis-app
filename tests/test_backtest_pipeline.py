"""Pipeline contracts for one schema-4 aggregate with compulsory treatments."""

from datetime import date
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

import backtest_engine.pipeline as pipeline
from backtest_engine.config import BacktestBatchConfig, BacktestConfig
from backtest_engine.data_quality import audit_history
from backtest_engine.exploratory import EvaluationSplit, ExploratoryEvaluation
from backtest_engine.persistence import load_rulebook_result, signal_artifact_path


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=25, freq="B"),
            "open": [100] * 25,
            "high": [101] * 25,
            "low": [99] * 25,
            "close": [100] * 25,
            "volume": [1000] * 25,
            "ATR_14": [2] * 25,
        }
    )


def _empty_evaluation() -> ExploratoryEvaluation:
    return ExploratoryEvaluation(
        EvaluationSplit(
            "chronological_65_35",
            date(2024, 1, 1),
            date(2024, 1, 31),
            date(2024, 2, 1),
            date(2024, 2, 2),
        ),
        (),
        (),
    )


class BacktestPipelineTests(unittest.TestCase):
    def test_single_run_always_loads_theme_and_writes_one_aggregate(self):
        raw = _frame()
        audit = audit_history("FPT", raw)
        confirmation = pd.DataFrame(
            {"date": raw["date"], "vnindex_confirmation": [True] * len(raw)}
        )
        with TemporaryDirectory() as directory:
            config = BacktestConfig(ticker="FPT", output_dir=directory)
            with patch.object(
                pipeline, "_prepare_ticker", return_value=(_frame(), audit, raw)
            ), patch.object(
                pipeline, "_load_confirmation_for_single", return_value=confirmation
            ) as load_confirmation, patch.object(
                pipeline, "_evaluate_ticker", return_value=_empty_evaluation()
            ) as evaluate:
                paths = pipeline.run_backtest_pipeline(config, None, object())

            result = load_rulebook_result(paths[0])

        self.assertEqual(paths, [str(signal_artifact_path("FPT", "swing", directory))])
        self.assertEqual(result["schema_version"], 4)
        self.assertEqual(result["terminal_state"], "empty")
        self.assertEqual(result["evaluation_label"], "Exploratory — gross")
        load_confirmation.assert_called_once_with(config, unittest.mock.ANY)
        self.assertIs(evaluate.call_args.args[2], confirmation)

    def test_theme_source_failure_replaces_the_aggregate_with_failed_document(self):
        raw = _frame()
        audit = audit_history("FPT", raw)
        with TemporaryDirectory() as directory:
            config = BacktestConfig(ticker="FPT", output_dir=directory)
            with patch.object(
                pipeline, "_prepare_ticker", return_value=(_frame(), audit, raw)
            ), patch.object(
                pipeline, "_load_confirmation_for_single", side_effect=RuntimeError("VN unavailable")
            ):
                paths = pipeline.run_backtest_pipeline(config, None, object())
            result = load_rulebook_result(paths[0])

        self.assertEqual(result["terminal_state"], "failed")
        self.assertIn("VN unavailable", result["failure_reason"])
        self.assertEqual(result["candidates"], [])

    def test_batch_preflight_failure_writes_one_failed_aggregate_per_ticker(self):
        with TemporaryDirectory() as directory:
            config = BacktestBatchConfig(tickers=("FPT", "VCB"), output_dir=directory)
            with patch.object(pipeline, "assign_tickers_group"), patch.object(
                pipeline, "_shared_confirmation", side_effect=RuntimeError("VN unavailable")
            ):
                outcome = pipeline.run_backtest_batch_pipeline(config, None, object())

            fpt = load_rulebook_result(signal_artifact_path("FPT", "swing", directory))
            vcb = load_rulebook_result(signal_artifact_path("VCB", "swing", directory))

        self.assertEqual(len(outcome["output_paths"]), 2)
        self.assertEqual(fpt["terminal_state"], "failed")
        self.assertEqual(vcb["terminal_state"], "failed")


if __name__ == "__main__":
    unittest.main()
