import importlib.util
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import backtest_engine.job_runner as job_runner
from backtest_engine.config import BacktestBatchConfig, BacktestConfig
from backtest_engine.job_runner import (
    read_job_status,
    run_backtest_job,
    submit_backtest,
)
from backtest_engine.worker import run_worker_request
from backtest_engine.models import BatchTickerStatus


def _slow_engine(config, report_progress):
    report_progress(0.25)
    time.sleep(0.2)
    report_progress(0.75)
    return [f"{config.tickers[0]}.json"]


def _instant_engine(config, report_progress):
    return []


def _progress_engine(config, report_progress):
    report_progress(0.4)
    report_progress(0.1)
    report_progress(0.8)
    return []


def _failing_engine(config, report_progress):
    report_progress(0.2)
    raise RuntimeError("synthetic engine failure")


def _batch_status_engine(config, report_progress):
    ticker_results = (
        BatchTickerStatus(
            "FPT",
            attempts=1,
            state="done",
            output_paths=("FPT.json",),
        ),
        BatchTickerStatus(
            "VCB",
            attempts=2,
            state="failed",
            error_texts=("ValueError: first failure", "ValueError: retry failure"),
        ),
    )
    report_progress(0.5, ticker_results)
    report_progress(0.8)
    return {
        "output_paths": ["FPT.json"],
        "ticker_results": [result.to_dict() for result in ticker_results],
    }


class BacktestJobRunnerTests(unittest.TestCase):
    def test_batch_config_normalizes_and_rejects_duplicate_or_invalid_tickers(self):
        config = BacktestBatchConfig(tickers=("fpt", "vcb"), horizon="swing")

        self.assertEqual(config.tickers, ("FPT", "VCB"))
        self.assertEqual(config.to_dict()["request_type"], "backtest_batch_v4")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            BacktestBatchConfig(tickers=("FPT", "fpt"))
        with self.assertRaisesRegex(ValueError, "between 1 and 15"):
            BacktestBatchConfig(tickers=())
        with self.assertRaisesRegex(ValueError, "between 1 and 15"):
            BacktestBatchConfig(
                tickers=tuple(f"T{index:02d}" for index in range(1, 17))
            )

    def test_worker_module_is_available_for_isolated_jobs(self):
        self.assertIsNotNone(
            importlib.util.find_spec("backtest_engine.worker")
        )

    def test_submit_persists_serialized_worker_request(self):
        config = BacktestConfig.for_ticker("FPT")
        with self._temporary_status_dir() as directory:
            job_id = submit_backtest(config, _instant_engine, directory)
            request_path = Path(directory) / f"{job_id}.request.json"

            self.assertTrue(request_path.exists())
            request = json.loads(request_path.read_text(encoding="utf-8"))

        self.assertEqual(request["config"], config.to_dict())
        self.assertEqual(
            request["factory_ref"],
            f"{_instant_engine.__module__}:_instant_engine",
        )

    def test_submit_rejects_non_importable_factory(self):
        with self._temporary_status_dir() as directory:
            with patch.object(
                job_runner, "ProcessPoolExecutor", create=True
            ) as executor:
                with self.assertRaisesRegex(ValueError, "importable"):
                    submit_backtest(
                        BacktestConfig.for_ticker("FPT"),
                        lambda *_: [],
                        directory,
                    )
            executor.assert_not_called()

    def test_worker_persists_factory_resolution_failure(self):
        config = BacktestConfig.for_ticker("FPT")
        with self._temporary_status_dir() as directory:
            request_path = Path(directory) / "bad.request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "job_id": "bad",
                        "config": config.to_dict(),
                        "factory_ref": "not_a_module:missing",
                        "status_dir": directory,
                    }
                ),
                encoding="utf-8",
            )

            final = run_worker_request(str(request_path))

            self.assertEqual(read_job_status("bad", directory), final)

        self.assertEqual(final.state, "failed")
        self.assertIn("ModuleNotFoundError", final.error_text)

    def test_submit_returns_before_background_work_finishes_and_reaches_done(self):
        config = BacktestConfig.for_ticker("FPT")
        with self.subTest("background lifecycle"), self._temporary_status_dir() as directory:
            started = time.monotonic()
            job_id = submit_backtest(config, _slow_engine, directory)
            elapsed = time.monotonic() - started
            queued_or_running = read_job_status(job_id, directory)

            self.assertLess(elapsed, 0.2)
            self.assertIn(queued_or_running.state, ("queued", "running"))

            final = self._wait_for_state(job_id, directory, "done")

        self.assertEqual(final.progress, 1.0)
        self.assertEqual(final.output_paths, ("FPT.json",))
        self.assertIsNone(final.error_text)

    def test_progress_is_monotonic_and_failure_is_persisted(self):
        config = BacktestConfig.for_ticker("FPT")
        with self._temporary_status_dir() as directory:
            with patch(
                "backtest_engine.job_runner._write_status",
                wraps=__import__("backtest_engine.job_runner", fromlist=["_write_status"])._write_status,
            ) as write_status:
                successful = run_backtest_job(config, _progress_engine, directory)

            progress_values = [
                call.args[0].progress
                for call in write_status.call_args_list
                if call.args
            ]
            self.assertEqual(progress_values, sorted(progress_values))
            self.assertEqual(successful.state, "done")

            failed = run_backtest_job(config, _failing_engine, directory)

        self.assertEqual(failed.state, "failed")
        self.assertIn("synthetic engine failure", failed.error_text)
        self.assertEqual(failed.progress, 0.2)

    def test_batch_status_round_trips_through_progress_and_terminal_sidecars(self):
        config = BacktestBatchConfig(tickers=("FPT", "VCB"))
        with self._temporary_status_dir() as directory:
            final = run_backtest_job(config, _batch_status_engine, directory)
            loaded = read_job_status(final.job_id, directory)

        self.assertEqual(final.state, "done")
        self.assertEqual(final.output_paths, ("FPT.json",))
        self.assertEqual(loaded.ticker_results, final.ticker_results)
        self.assertEqual([result.ticker for result in loaded.ticker_results], ["FPT", "VCB"])
        self.assertEqual(loaded.ticker_results[1].attempts, 2)
        self.assertEqual(
            loaded.ticker_results[1].error_texts,
            ("ValueError: first failure", "ValueError: retry failure"),
        )

    def test_failure_records_an_exception_trace_in_worker_logs(self):
        with self._temporary_status_dir() as directory:
            with self.assertLogs("backtest_engine.job_runner", "ERROR") as logs:
                final = run_backtest_job(
                    BacktestConfig.for_ticker("FPT"),
                    _failing_engine,
                    directory,
                )

        self.assertEqual(final.state, "failed")
        self.assertEqual(len(logs.records), 1)
        self.assertIn(final.job_id, logs.records[0].getMessage())
        self.assertIsNotNone(logs.records[0].exc_info)

    def test_default_worker_configuration_is_six_and_runner_has_no_streamlit_import(self):
        config = BacktestConfig.for_ticker("FPT")
        source = (Path(__file__).parents[1] / "backtest_engine" / "job_runner.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(config.worker_count, 6)
        self.assertNotIn("streamlit", source.casefold())

    def _temporary_status_dir(self):
        import tempfile

        return tempfile.TemporaryDirectory()

    def _wait_for_state(self, job_id, directory, expected):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = read_job_status(job_id, directory)
            if status.state == expected:
                return status
            if status.state == "failed":
                self.fail(status.error_text)
            time.sleep(0.05)
        self.fail(f"job did not reach {expected}")


if __name__ == "__main__":
    unittest.main()
