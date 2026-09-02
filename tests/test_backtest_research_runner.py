"""Controlled research runner ordering, isolation, and immutable output tests."""

from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

from backtest_engine.exploratory import EvaluationSplit
from backtest_engine.research_runner import (
    BASELINE_VERIFICATION_SHA256,
    ResearchPrerequisiteError,
    ResearchRequest,
    run_controlled_experiment,
)


def _raw() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2020-01-01", periods=40),
            "open": [100] * 40,
            "high": [102] * 40,
            "low": [98] * 40,
            "close": [100] * 40,
            "volume": [1000] * 40,
        }
    )


def _frame() -> pd.DataFrame:
    frame = _raw()
    frame["ATR_14"] = 2.0
    return frame


def _split() -> EvaluationSplit:
    return EvaluationSplit(
        "chronological_65_35",
        date(2020, 1, 1),
        date(2020, 1, 31),
        date(2020, 2, 3),
        date(2020, 2, 25),
    )


def _evidence():
    return SimpleNamespace(
        eligible=True,
        to_dict=lambda: {
            "status": "eligible",
            "eligible": True,
            "reasons": [],
            "common_as_of": "2020-02-25",
            "ticker_fingerprint": "a" * 64,
            "vnindex_fingerprint": "b" * 64,
        },
    )


class ResearchRunnerTests(unittest.TestCase):
    def _request(self, directory: str, **changes) -> ResearchRequest:
        values = {
            "ticker": "vcb",
            "horizon": "swing",
            "start_date": date(2011, 1, 1),
            "end_date": date(2026, 1, 1),
            "permutation_count": 1000,
            "permutation_seed": 42,
            "permutation_block_size": 20,
            "output_dir": directory,
            "persist": False,
        }
        values.update(changes)
        return ResearchRequest(**values)

    def _patch_run(self, call_order: list[str]):
        raw = _raw()
        frame = _frame()

        def execute(_frame_value, _execution, _entries, *, start, end):
            partition = "training" if end == _split().train_end else "test"
            call_order.append(partition)
            return ()

        return (
            patch("backtest_engine.research_runner._load_validated_history", return_value=raw),
            patch("backtest_engine.research_runner.latest_common_completed_bar", return_value=date(2020, 2, 25)),
            patch(
                "backtest_engine.research_runner._prepare_ticker",
                return_value=(frame, SimpleNamespace(status="clean"), raw),
            ),
            patch("backtest_engine.research_runner.assess_evidence", return_value=_evidence()),
            patch("backtest_engine.research_runner._build_confirmation_frame", return_value=frame),
            patch(
                "backtest_engine.research_runner._theme_signal",
                return_value=pd.Series(True, index=frame.index, dtype=bool),
            ),
            patch("backtest_engine.research_runner.split_native_frame", return_value=_split()),
            patch(
                "backtest_engine.research_runner.definition_entry_signal",
                return_value=pd.Series(False, index=frame.index, dtype=bool),
            ),
            patch("backtest_engine.research_runner._execute_events", side_effect=execute),
        )

    def test_runner_freezes_sources_and_finishes_all_training_before_test(self):
        with TemporaryDirectory() as directory:
            order: list[str] = []
            patches = self._patch_run(order)
            with patches[0] as load, patches[1] as common, patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
                result = run_controlled_experiment(self._request(directory), engine=object())

            self.assertEqual(["training"] * 4 + ["test"] * 4, order)
            self.assertEqual(2, load.call_count)
            self.assertEqual(("VCB", "VNINDEX"), tuple(call.args[0] for call in load.call_args_list))
            self.assertEqual(1, common.call_count)
            self.assertEqual("research_only", result.candidate_role)
            self.assertEqual([], list(Path(directory).iterdir()))

    def test_persisted_output_is_research_only_and_outside_canonical_paths(self):
        with TemporaryDirectory() as directory:
            order: list[str] = []
            patches = self._patch_run(order)
            request = self._request(directory, persist=True)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
                run_controlled_experiment(request, engine=object())
            files = list(Path(directory).glob("*.json"))
            self.assertEqual(1, len(files))
            self.assertEqual("btre_" + sha256(files[0].read_bytes()).hexdigest(), files[0].stem)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual("research_only", payload["promotion_status"])
            self.assertEqual("complete", payload["terminal_state"])
            self.assertNotIn("product_rulebook_id", payload)
            self.assertNotIn("rulebook_id", files[0].read_text(encoding="utf-8"))

            second_order: list[str] = []
            second_patches = self._patch_run(second_order)
            with second_patches[0], second_patches[1], second_patches[2], second_patches[3], second_patches[4], second_patches[5], second_patches[6], second_patches[7], second_patches[8]:
                run_controlled_experiment(request, engine=object())
            self.assertEqual(1, len(list(Path(directory).glob("*.json"))))

    def test_canonical_output_directory_is_rejected_before_source_access(self):
        request = self._request("backtest-result/ticker-signals", persist=True)
        with patch("backtest_engine.research_runner._load_validated_history") as load:
            with self.assertRaisesRegex(ValueError, "canonical Backtest result tree"):
                run_controlled_experiment(request, engine=object())
        load.assert_not_called()

    def test_midterm_requires_exact_baseline_hash_and_writes_not_run(self):
        with TemporaryDirectory() as directory:
            request = self._request(
                directory,
                horizon="midterm",
                persist=True,
                baseline_verification_sha256="0" * 64,
            )
            with patch("backtest_engine.research_runner._load_validated_history") as load:
                with self.assertRaisesRegex(ResearchPrerequisiteError, "baseline verification hash"):
                    run_controlled_experiment(request, engine=object())
            load.assert_not_called()
            payload = json.loads(next(Path(directory).glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual("not_run", payload["terminal_state"])
            self.assertEqual("research_only", payload["promotion_status"])

    def test_midterm_valid_hash_still_requires_current_baseline_and_date_identity(self):
        with TemporaryDirectory() as directory:
            order: list[str] = []
            patches = self._patch_run(order)
            request = self._request(
                directory,
                horizon="midterm",
                baseline_verification_sha256=BASELINE_VERIFICATION_SHA256,
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patch(
                "backtest_engine.research_runner._validate_midterm_prerequisite",
                side_effect=ResearchPrerequisiteError("ticker/theme date identity failed"),
            ):
                with self.assertRaisesRegex(ResearchPrerequisiteError, "date identity"):
                    run_controlled_experiment(request, engine=object())

    def test_request_normalizes_ticker_and_rejects_invalid_bounds(self):
        request = self._request("research-output")
        self.assertEqual("VCB", request.ticker)
        with self.assertRaisesRegex(ValueError, "start_date"):
            self._request(
                "research-output",
                start_date=date(2026, 1, 2),
                end_date=date(2026, 1, 1),
            )


if __name__ == "__main__":
    unittest.main()
