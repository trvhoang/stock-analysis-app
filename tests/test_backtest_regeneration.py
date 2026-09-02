"""Filename-only invalidation contracts for superseded V3 outputs."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backtest_engine.job_runner import read_job_status
from backtest_engine.regeneration import invalidate_superseded_outputs
from backtest_engine.worker import run_worker_request


class RegenerationTests(unittest.TestCase):
    def test_legacy_artifact_is_overwritten_without_reading_invalid_json(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            signal_root, status_root = root / "signals", root / "jobs"
            legacy = signal_root / "VCB" / "VCB_signals_swing_no-background-theme.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("{deliberately invalid JSON", encoding="utf-8")

            report = invalidate_superseded_outputs(str(signal_root), str(status_root))

            legacy_marker = json.loads(legacy.read_text(encoding="utf-8"))
            canonical_marker = json.loads(
                (signal_root / "VCB" / "VCB_signals_swing.json").read_text(encoding="utf-8")
            )

        self.assertEqual(legacy_marker["terminal_state"], "requires_regeneration")
        self.assertEqual(legacy_marker["schema_version"], 5)
        self.assertEqual(
            legacy_marker["rejection_reason"],
            "Regenerate under Backtest schema 5.",
        )
        self.assertEqual(canonical_marker["terminal_state"], "requires_regeneration")
        self.assertEqual([path.name for path in report.canonical_paths], ["VCB_signals_swing.json"])

    def test_existing_canonical_artifact_is_overwritten_without_payload_decode(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            signal_root, status_root = root / "signals", root / "jobs"
            canonical = signal_root / "FPT" / "FPT_signals_midterm.json"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("not json", encoding="utf-8")

            report = invalidate_superseded_outputs(str(signal_root), str(status_root))
            marker = json.loads(canonical.read_text(encoding="utf-8"))

        self.assertEqual(5, marker["schema_version"])
        self.assertEqual("requires_regeneration", marker["terminal_state"])
        self.assertEqual((canonical,), report.canonical_paths)

    def test_legacy_request_and_status_are_marked_without_config_decode(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            signal_root, status_root = root / "signals", root / "jobs"
            status_root.mkdir()
            request = status_root / "abc.request.json"
            status = status_root / "abc.json"
            request.write_text("not json", encoding="utf-8")
            status.write_text("not json", encoding="utf-8")

            report = invalidate_superseded_outputs(str(signal_root), str(status_root))
            final = run_worker_request(str(request))

            request_marker = json.loads(request.read_text(encoding="utf-8"))
            status_marker = read_job_status("abc", str(status_root))

        self.assertEqual(request_marker["state"], "requires_regeneration")
        self.assertEqual(request_marker["schema_version"], 5)
        self.assertEqual(
            request_marker["error_text"],
            "Regenerate under Backtest schema 5.",
        )
        self.assertEqual(status_marker.state, "requires_regeneration")
        self.assertEqual(final.state, "requires_regeneration")
        self.assertEqual(report.job_ids, ("abc",))


if __name__ == "__main__":
    unittest.main()
