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


def _history_ending(end: str) -> pd.DataFrame:
    dates = pd.bdate_range(end=end, periods=40)
    close = pd.Series(range(100, 100 + len(dates)), dtype="int64")
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": [1000] * len(dates),
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
    def test_single_run_passes_internal_evidence_to_persistence(self):
        raw = _frame()
        audit = audit_history("FPT", raw)
        confirmation = pd.DataFrame(
            {"date": raw["date"], "vnindex_confirmation": [True] * len(raw)}
        )
        evidence = object()
        with TemporaryDirectory() as directory:
            config = BacktestConfig(ticker="FPT", output_dir=directory)
            with patch.object(
                pipeline, "_load_validated_history", return_value=raw
            ), patch.object(
                pipeline, "_prepare_ticker", return_value=(_frame(), audit, raw)
            ), patch.object(
                pipeline,
                "_load_confirmation_for_single",
                return_value=(confirmation, raw["date"].iloc[-1].date(), raw),
            ), patch.object(
                pipeline, "assess_evidence", return_value=evidence
            ) as assess, patch.object(
                pipeline, "_evaluate_ticker", return_value=_empty_evaluation()
            ), patch.object(
                pipeline, "_persist_evaluation", return_value=["result.json"]
            ) as persist:
                paths = pipeline.run_backtest_pipeline(config, None, object())

        self.assertEqual(["result.json"], paths)
        self.assertIs(evidence, persist.call_args.args[-1])
        self.assertTrue(assess.call_args.kwargs["audit_eligible"])
        self.assertEqual("FPT", assess.call_args.kwargs["ticker"])

    def test_evaluation_failure_passes_available_evidence_to_failure_persistence(self):
        raw = _frame()
        audit = audit_history("FPT", raw)
        confirmation = pd.DataFrame(
            {"date": raw["date"], "vnindex_confirmation": [True] * len(raw)}
        )
        evidence = object()
        config = BacktestConfig(ticker="FPT")
        with patch.object(
            pipeline, "_load_validated_history", return_value=raw
        ), patch.object(
            pipeline, "_prepare_ticker", return_value=(_frame(), audit, raw)
        ), patch.object(
            pipeline,
            "_load_confirmation_for_single",
            return_value=(confirmation, raw["date"].iloc[-1].date(), raw),
        ), patch.object(
            pipeline, "assess_evidence", return_value=evidence
        ), patch.object(
            pipeline, "_evaluate_ticker", side_effect=RuntimeError("evaluation failed")
        ), patch.object(
            pipeline, "_persist_failure", return_value=["failed.json"]
        ) as persist_failure:
            paths = pipeline.run_backtest_pipeline(config, None, object())

        self.assertEqual(["failed.json"], paths)
        self.assertIs(evidence, persist_failure.call_args.kwargs["evidence"])

    def test_single_run_slices_ticker_and_theme_to_one_common_completed_bar(self):
        sources = {
            "FPT": _history_ending("2024-01-12"),
            "VNINDEX": _history_ending("2024-01-15"),
        }
        with TemporaryDirectory() as directory:
            config = BacktestConfig(
                ticker="FPT",
                start_date=date(2023, 1, 1),
                end_date=date(2024, 1, 15),
                output_dir=directory,
            )
            with patch.object(
                pipeline,
                "load_ticker_history",
                side_effect=lambda ticker, *_args: sources[ticker].copy(deep=True),
            ), patch.object(
                pipeline, "_evaluate_ticker", return_value=_empty_evaluation()
            ) as evaluate:
                pipeline.run_backtest_pipeline(config, None, object())
            result = load_rulebook_result(
                signal_artifact_path("FPT", "swing", directory)
            )

        ticker_frame, _, confirmation = evaluate.call_args.args
        self.assertEqual(date(2024, 1, 12), ticker_frame["date"].max().date())
        self.assertEqual(date(2024, 1, 12), confirmation["date"].max().date())
        self.assertEqual("2024-01-12", result["effective_data_range"]["end"])

    def test_batch_uses_one_common_bar_across_every_successful_source(self):
        sources = {
            "FPT": _history_ending("2024-01-12"),
            "VCB": _history_ending("2024-01-10"),
            "VNINDEX": _history_ending("2024-01-15"),
        }
        with TemporaryDirectory() as directory:
            config = BacktestBatchConfig(
                tickers=("FPT", "VCB"),
                start_date=date(2023, 1, 1),
                end_date=date(2024, 1, 15),
                output_dir=directory,
            )
            with patch.object(
                pipeline,
                "load_ticker_history",
                side_effect=lambda ticker, *_args: sources[ticker].copy(deep=True),
            ), patch.object(
                pipeline, "assign_tickers_group"
            ), patch.object(
                pipeline, "_evaluate_ticker", return_value=_empty_evaluation()
            ) as evaluate:
                pipeline.run_backtest_batch_pipeline(config, None, object())
            effective_ends = {
                ticker: load_rulebook_result(
                    signal_artifact_path(ticker, "swing", directory)
                )["effective_data_range"]["end"]
                for ticker in config.tickers
            }

        self.assertEqual(2, evaluate.call_count)
        for call in evaluate.call_args_list:
            ticker_frame, _, confirmation = call.args
            self.assertEqual(date(2024, 1, 10), ticker_frame["date"].max().date())
            self.assertEqual(date(2024, 1, 10), confirmation["date"].max().date())
        self.assertEqual({"FPT": "2024-01-10", "VCB": "2024-01-10"}, effective_ends)

    def test_single_run_always_loads_theme_and_writes_one_aggregate(self):
        raw = _frame()
        audit = audit_history("FPT", raw)
        confirmation = pd.DataFrame(
            {"date": raw["date"], "vnindex_confirmation": [True] * len(raw)}
        )
        with TemporaryDirectory() as directory:
            config = BacktestConfig(ticker="FPT", output_dir=directory)
            with patch.object(
                pipeline, "_load_validated_history", return_value=raw
            ), patch.object(
                pipeline, "_prepare_ticker", return_value=(_frame(), audit, raw)
            ), patch.object(
                pipeline,
                "_load_confirmation_for_single",
                return_value=(confirmation, raw["date"].iloc[-1].date(), raw),
            ) as load_confirmation, patch.object(
                pipeline, "_evaluate_ticker", return_value=_empty_evaluation()
            ) as evaluate:
                paths = pipeline.run_backtest_pipeline(config, None, object())

            result = load_rulebook_result(paths[0])

        self.assertEqual(paths, [str(signal_artifact_path("FPT", "swing", directory))])
        self.assertEqual(result["schema_version"], 5)
        self.assertEqual(result["terminal_state"], "empty")
        self.assertEqual(result["evaluation_label"], "Exploratory — gross")
        load_confirmation.assert_called_once_with(
            config,
            unittest.mock.ANY,
            ticker_history=raw,
        )
        self.assertIs(evaluate.call_args.args[2], confirmation)

    def test_theme_source_failure_replaces_the_aggregate_with_failed_document(self):
        raw = _frame()
        audit = audit_history("FPT", raw)
        with TemporaryDirectory() as directory:
            config = BacktestConfig(ticker="FPT", output_dir=directory)
            with patch.object(
                pipeline, "_load_validated_history", return_value=raw
            ), patch.object(
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
                pipeline, "_load_validated_history", return_value=_frame()
            ), patch.object(
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
