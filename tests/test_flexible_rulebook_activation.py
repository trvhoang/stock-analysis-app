"""Immutable direct-cap activation policy tests."""

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import flexible_rulebook.activation as activation
from flexible_rulebook.activation import (
    activate_cap_report,
    load_active_policy,
    load_policy_by_digest,
)
from flexible_rulebook.cap_benchmark import (
    DiscoveryCapBenchmarkReport,
    DiscoveryCapSample,
    write_cap_benchmark_report,
)
from flexible_rulebook.cap_benchmark_runner import (
    discovery_runtime_contract_identity,
    production_cap_runtime,
)
from flexible_rulebook.contracts import canonical_json


_AS_OF = date(2026, 8, 28)
_SEED = "frb-default-seed-v1"
_CAP = 8
_RUNTIME = discovery_runtime_contract_identity(production_cap_runtime())


def _sample(index: int, *, ticker: str = "VCB", fingerprint: str = "a" * 64) -> DiscoveryCapSample:
    start_slot = index * _CAP
    return DiscoveryCapSample(
        ticker=ticker,
        seed=_SEED,
        mode="cold",
        sample_index=index,
        benchmark_as_of=_AS_OF,
        cap_attempts=_CAP,
        start_slot=start_slot,
        assignment_hash=f"{index:064x}",
        source_identity=canonical_json(
            {
                "ticker": ticker,
                "raw_history_fingerprint": fingerprint,
                "requested_start": "2011-08-28",
                "requested_as_of": "2026-08-28",
                "first_date": "2011-08-29",
                "as_of_date": "2026-08-28",
                "quality_state": "eligible",
                "quality_revision": "flexible-history-v1",
            }
        ),
        split_identity=canonical_json({"method": "calendar_10y_5y"}),
        attempted_count=_CAP,
        committed_count=_CAP,
        next_slot=start_slot + _CAP,
        uncommitted_slot=None,
        preflight_seconds=1.0,
        cap_window_seconds=2.0,
        total_seconds=3.0,
        slot_timings=(),
        selection_seconds=0.1,
        write_seconds=0.1,
        terminal_state="completed",
        safe_error_code=None,
        peak_rss_bytes=1024,
        peak_pool_checkouts=1,
        cache_bytes=512,
        artifact_bytes=256,
    )


def _report(*, ticker: str = "VCB", fingerprint: str = "a" * 64, runtime_identity: str = _RUNTIME):
    return DiscoveryCapBenchmarkReport(
        benchmark_as_of=_AS_OF,
        tickers=(ticker,),
        seeds=(_SEED,),
        cap_attempts=_CAP,
        runtime_contract_identity=runtime_identity,
        samples=tuple(_sample(index, ticker=ticker, fingerprint=fingerprint) for index in range(100)),
        ticker_elapsed_seconds_by_ticker=((ticker, 300.0),),
    )


class FlexibleRulebookActivationTests(unittest.TestCase):
    def test_activation_cli_imports_without_module_reexecution_warning(self):
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::RuntimeWarning",
                "-m",
                "flexible_rulebook.activation",
                "--help",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_policy_pointer_replacement_does_not_change_old_campaign_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            report_a = root / "input-a.json"
            report_b = root / "input-b.json"
            write_cap_benchmark_report(report_a, _report(ticker="VCB"))
            write_cap_benchmark_report(report_b, _report(ticker="FPT", fingerprint="b" * 64))

            first = activate_cap_report(
                report_a,
                root / "benchmark",
                allowed_tickers=("VCB",),
                allowed_seeds=(_SEED,),
                approved_by="operator-a",
                approval_note="approved after independent review",
            )
            second = activate_cap_report(
                report_b,
                root / "benchmark",
                allowed_tickers=("FPT",),
                allowed_seeds=(_SEED,),
                approved_by="operator-b",
                approval_note="approved after independent review",
            )
            active, reason = load_active_policy(root / "benchmark" / "active-policy.json")

            self.assertNotEqual(first.policy_digest, second.policy_digest)
            self.assertEqual(load_policy_by_digest(root / "benchmark", first.policy_digest), first)
            self.assertEqual((active, reason), (second, "active"))

    def test_activation_copies_canonical_report_and_immutable_write_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "input.json"
            write_cap_benchmark_report(source, _report())

            policy = activate_cap_report(
                source,
                root / "benchmark",
                allowed_tickers=("VCB",),
                allowed_seeds=(_SEED,),
                approved_by="operator",
                approval_note="independent review complete",
            )
            copied = root / "benchmark" / policy.report_relpath
            self.assertEqual(copied.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))

            policy_path = root / "benchmark" / "policies" / f"{policy.policy_digest}.json"
            material = policy_path.read_text(encoding="utf-8")
            self.assertEqual(activation._write_immutable(policy_path, material), policy_path)
            with self.assertRaisesRegex(ValueError, "already differs"):
                activation._write_immutable(policy_path, "{}")

    def test_pointer_traversal_and_tampered_derived_record_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "input.json"
            write_cap_benchmark_report(source, _report())
            policy = activate_cap_report(
                source,
                root / "benchmark",
                allowed_tickers=("VCB",),
                allowed_seeds=(_SEED,),
                approved_by="operator",
                approval_note="independent review complete",
            )
            pointer = root / "benchmark" / "active-policy.json"

            pointer.write_text(
                canonical_json(
                    {
                        "kind": "flexible_rulebook_active_discovery_policy",
                        "policy_relpath": "../outside.json",
                        "policy_digest": policy.policy_digest,
                    }
                ),
                encoding="utf-8",
            )
            active, reason = load_active_policy(pointer)
            self.assertIsNone(active)
            self.assertIn("relative path", reason)

            payload = policy.to_payload()
            payload["benchmark_record_digest"] = "0" * 64
            digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            (root / "benchmark" / "policies" / f"{digest}.json").write_text(
                canonical_json(
                    {
                        "kind": "flexible_rulebook_activated_discovery_policy",
                        "digest": digest,
                        "payload": payload,
                    }
                ),
                encoding="utf-8",
            )
            pointer.write_text(
                canonical_json(
                    {
                        "kind": "flexible_rulebook_active_discovery_policy",
                        "policy_relpath": f"policies/{digest}.json",
                        "policy_digest": digest,
                    }
                ),
                encoding="utf-8",
            )
            active, reason = load_active_policy(pointer)
            self.assertIsNone(active)
            self.assertIn("benchmark record digest", reason)

    def test_activation_rejects_runtime_worker_and_unmeasured_cap_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            runtime_mismatch = root / "runtime-mismatch.json"
            write_cap_benchmark_report(
                runtime_mismatch,
                _report(runtime_identity=canonical_json({"contract": "wrong"})),
            )
            with self.assertRaisesRegex(ValueError, "runtime contract"):
                activate_cap_report(
                    runtime_mismatch,
                    root / "benchmark-runtime",
                    allowed_tickers=("VCB",),
                    allowed_seeds=(_SEED,),
                    approved_by="operator",
                    approval_note="independent review complete",
                )

            incomplete_samples = list(_report().samples)
            incomplete_samples[-1] = replace(
                incomplete_samples[-1],
                committed_count=_CAP - 1,
                next_slot=100 * _CAP - 1,
                uncommitted_slot=100 * _CAP - 1,
            )
            incomplete = DiscoveryCapBenchmarkReport(
                benchmark_as_of=_AS_OF,
                tickers=("VCB",),
                seeds=(_SEED,),
                cap_attempts=_CAP,
                runtime_contract_identity=_RUNTIME,
                samples=tuple(incomplete_samples),
                ticker_elapsed_seconds_by_ticker=(("VCB", 300.0),),
            )
            incomplete_path = root / "incomplete.json"
            write_cap_benchmark_report(incomplete_path, incomplete)
            with self.assertRaisesRegex(ValueError, "requires 100"):
                activate_cap_report(
                    incomplete_path,
                    root / "benchmark-incomplete",
                    allowed_tickers=("VCB",),
                    allowed_seeds=(_SEED,),
                    approved_by="operator",
                    approval_note="independent review complete",
                )

            anchor_drift_samples = list(_report().samples)
            anchor_drift_samples[-1] = replace(
                anchor_drift_samples[-1],
                source_identity=_sample(99, fingerprint="b" * 64).source_identity,
            )
            anchor_drift = DiscoveryCapBenchmarkReport(
                benchmark_as_of=_AS_OF,
                tickers=("VCB",),
                seeds=(_SEED,),
                cap_attempts=_CAP,
                runtime_contract_identity=_RUNTIME,
                samples=tuple(anchor_drift_samples),
                ticker_elapsed_seconds_by_ticker=(("VCB", 300.0),),
            )
            anchor_drift_path = root / "anchor-drift.json"
            write_cap_benchmark_report(anchor_drift_path, anchor_drift)
            with self.assertRaisesRegex(ValueError, "source identity changed"):
                activate_cap_report(
                    anchor_drift_path,
                    root / "benchmark-anchor-drift",
                    allowed_tickers=("VCB",),
                    allowed_seeds=(_SEED,),
                    approved_by="operator",
                    approval_note="independent review complete",
                )

            valid_path = root / "valid.json"
            write_cap_benchmark_report(valid_path, _report())
            valid = activate_cap_report(
                valid_path,
                root / "benchmark-worker",
                allowed_tickers=("VCB",),
                allowed_seeds=(_SEED,),
                approved_by="operator",
                approval_note="independent review complete",
            )
            with self.assertRaisesRegex(ValueError, "exactly one worker"):
                replace(valid, worker_count=2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
