"""Policy-bound Discover preflight and worker-context tests."""

from datetime import date, datetime
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
import pytz

from flexible_rulebook.activation import ActivatedDiscoveryPolicy
from flexible_rulebook.cap_benchmark_runner import (
    discovery_runtime_contract_identity,
    production_cap_runtime,
)
from flexible_rulebook.campaigns import create_manifest, write_campaign_manifest
from flexible_rulebook.contracts import canonical_json
from flexible_rulebook.features import CacheOffer, FeatureResolution, feature_snapshot_for_history
from flexible_rulebook.history import HistorySnapshot, make_evaluation_split
from flexible_rulebook.worker import WorkerRequest


_HCM = pytz.timezone("Asia/Ho_Chi_Minh")
_NOW = _HCM.localize(datetime(2026, 8, 30, 10, 0, 0))
_SEED = "frb-default-seed-v1"
_RUNTIME = discovery_runtime_contract_identity(production_cap_runtime())


def _history(*, as_of: date, fingerprint: str = "a" * 64) -> HistorySnapshot:
    first = date(2011, 8, 29)
    latest = min(as_of, date(2026, 8, 29))
    frame = pd.DataFrame(
        {
            "date": [first, latest],
            "open": [100, 110],
            "high": [101, 111],
            "low": [99, 109],
            "close": [100, 110],
            "volume": [1000, 1000],
        }
    )
    return HistorySnapshot(
        "VCB",
        frame,
        fingerprint,
        "eligible",
        date(2011, 8, 28),
        as_of,
        first,
        latest,
        fingerprint,
    )


def _anchor_identity(snapshot: HistorySnapshot) -> str:
    source = feature_snapshot_for_history(snapshot)
    return canonical_json(
        {
            "ticker": source.ticker,
            "raw_history_fingerprint": source.raw_history_fingerprint,
            "requested_start": source.requested_start.isoformat(),
            "requested_as_of": source.requested_as_of.isoformat(),
            "first_date": source.first_date.isoformat(),
            "as_of_date": source.as_of_date.isoformat(),
            "quality_state": source.quality_state,
            "quality_revision": source.quality_revision,
        }
    )


def _policy(anchor: HistorySnapshot) -> ActivatedDiscoveryPolicy:
    return ActivatedDiscoveryPolicy(
        report_digest="a" * 64,
        benchmark_record_digest="b" * 64,
        report_relpath="reports/" + "a" * 64 + ".json",
        allowed_tickers=("VCB",),
        allowed_seeds=(_SEED,),
        runtime_contract_identity=_RUNTIME,
        source_anchors=(("VCB", _anchor_identity(anchor)),),
        benchmark_splits=(("VCB", canonical_json(make_evaluation_split(anchor).to_identity_dict())),),
        cap_attempts=3,
        worker_count=1,
        approved_by="operator",
        approval_note="independent cap report review",
        activated_at=_NOW.isoformat(),
    )


class FlexibleRulebookDiscoveryActivationTests(unittest.TestCase):
    def test_preflight_requires_the_current_active_policy_before_history_access(self):
        from flexible_rulebook.discovery_activation import preflight_activated_discovery

        historical = _history(as_of=date(2026, 8, 28))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(None, "pointer missing")),
                patch("flexible_rulebook.discovery_activation.load_flexible_history") as load_history,
            ):
                with self.assertRaisesRegex(ValueError, "policy is unavailable"):
                    preflight_activated_discovery(
                        object(), "VCB", _SEED, _policy(historical), root=root, now=_NOW
                    )

        load_history.assert_not_called()

    def test_preflight_checks_historical_anchor_before_loading_and_freezing_current_source(self):
        from flexible_rulebook.discovery_activation import preflight_activated_discovery

        historical = _history(as_of=date(2026, 8, 28))
        current = _history(as_of=_NOW.date())
        policy = _policy(historical)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(policy, "active")),
                patch(
                    "flexible_rulebook.discovery_activation.load_flexible_history",
                    side_effect=(historical, current),
                ) as load_history,
                patch(
                    "flexible_rulebook.discovery_activation.inspect_primitive_cache",
                    return_value=CacheOffer(("component",), (), ()),
                ),
            ):
                preflight = preflight_activated_discovery(
                    object(), "vcb", _SEED, policy, root=root, now=_NOW
                )

        self.assertEqual(preflight.snapshot, current)
        self.assertEqual(preflight.policy_digest, policy.policy_digest)
        self.assertEqual(
            [call.args[1:] for call in load_history.call_args_list],
            [("VCB",), ("VCB",)],
        )
        self.assertEqual(load_history.call_args_list[0].kwargs["as_of"], date(2026, 8, 28))
        self.assertEqual(load_history.call_args_list[1].kwargs["as_of"], _NOW.date())

    def test_changed_historical_anchor_blocks_before_current_source_load(self):
        from flexible_rulebook.discovery_activation import preflight_activated_discovery

        historical = _history(as_of=date(2026, 8, 28))
        changed = _history(as_of=date(2026, 8, 28), fingerprint="c" * 64)
        policy = _policy(historical)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(policy, "active")),
                patch(
                    "flexible_rulebook.discovery_activation.load_flexible_history",
                    return_value=changed,
                ) as load_history,
            ):
                with self.assertRaisesRegex(ValueError, "benchmark source anchor changed"):
                    preflight_activated_discovery(
                        object(), "VCB", _SEED, policy, root=root, now=_NOW
                    )

        self.assertEqual(load_history.call_count, 1)

    def test_submit_persists_policy_bound_campaign_then_claims_and_spawns_worker(self):
        from flexible_rulebook.discovery_activation import (
            preflight_activated_discovery,
            submit_activated_discovery,
        )

        historical = _history(as_of=date(2026, 8, 28))
        current = _history(as_of=_NOW.date())
        policy = _policy(historical)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(policy, "active")),
                patch(
                    "flexible_rulebook.discovery_activation.load_flexible_history",
                    side_effect=(historical, current),
                ),
                patch(
                    "flexible_rulebook.discovery_activation.inspect_primitive_cache",
                    return_value=CacheOffer(("component",), (), ()),
                ),
                patch(
                    "flexible_rulebook.discovery_activation.submit_campaign",
                    return_value="fcmp_" + "d" * 64,
                ) as submit,
                patch(
                    "flexible_rulebook.discovery_activation.read_campaign",
                    return_value=MagicMock(state="queued"),
                ),
                patch("flexible_rulebook.discovery_activation.claim_campaign") as claim,
                patch("flexible_rulebook.discovery_activation.start_campaign_worker") as start,
            ):
                preflight = preflight_activated_discovery(
                    object(), "VCB", _SEED, policy, root=root, now=_NOW
                )
                campaign_id = submit_activated_discovery(preflight, cache_choice="reuse", root=root)

        request = submit.call_args.args[0]
        self.assertEqual(campaign_id, "fcmp_" + "d" * 64)
        self.assertEqual(request.activation_policy_digest, preflight.policy_digest)
        self.assertEqual(request.cache_choice, "reuse")
        self.assertEqual((request.per_ticker_budget, request.frontier_assignment.attempt_count), (3, 3))
        claim.assert_called_once_with(campaign_id, root)
        self.assertEqual(start.call_args.args, (campaign_id, root))

    def test_submit_rejects_a_cache_offer_that_changed_after_preflight(self):
        """A delayed UI Start must not reuse cache treatment verified only earlier."""

        from flexible_rulebook.discovery_activation import (
            preflight_activated_discovery,
            submit_activated_discovery,
        )

        historical = _history(as_of=date(2026, 8, 28))
        current = _history(as_of=_NOW.date())
        policy = _policy(historical)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(policy, "active")),
                patch(
                    "flexible_rulebook.discovery_activation.load_flexible_history",
                    side_effect=(historical, current),
                ),
                patch(
                    "flexible_rulebook.discovery_activation.inspect_primitive_cache",
                    side_effect=(
                        CacheOffer(("component",), (), ()),
                        CacheOffer((), ("component",), ()),
                    ),
                ),
                patch("flexible_rulebook.discovery_activation.submit_campaign") as submit,
            ):
                preflight = preflight_activated_discovery(
                    object(), "VCB", _SEED, policy, root=root, now=_NOW
                )
                with self.assertRaisesRegex(ValueError, "cache preflight changed"):
                    submit_activated_discovery(preflight, cache_choice="reuse", root=root)

        submit.assert_not_called()

    def test_worker_factory_reloads_named_policy_and_honors_persisted_cache_choice(self):
        import flexible_rulebook.discovery_activation as activated

        historical = _history(as_of=date(2026, 8, 28))
        current = _history(as_of=_NOW.date())
        policy = _policy(historical)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(policy, "active")),
                patch(
                    "flexible_rulebook.discovery_activation.load_flexible_history",
                    side_effect=(historical, current),
                ),
                patch(
                    "flexible_rulebook.discovery_activation.inspect_primitive_cache",
                    return_value=CacheOffer(("component",), (), ()),
                ),
            ):
                preflight = activated.preflight_activated_discovery(
                    object(), "VCB", _SEED, policy, root=root, now=_NOW
                )
            request = activated._request_from_preflight(preflight, "reuse")
            manifest = create_manifest(request)
            write_campaign_manifest(root, manifest)
            expected_plan = preflight.feature_plan
            resolution = FeatureResolution(MagicMock(), expected_plan, MagicMock())
            worker = WorkerRequest(
                manifest.campaign_id,
                root,
                "flexible_rulebook.discovery_activation:activated_discovery_service",
                "flexible_rulebook.discovery_activation:activated_discovery_source_loader",
            )
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.active_policy_directory", return_value=root / "benchmark"),
                patch("flexible_rulebook.discovery_activation.load_policy_by_digest", return_value=policy),
                patch(
                    "flexible_rulebook.discovery_activation.resolve_frozen_feature_bundle",
                    return_value=resolution,
                ) as resolve_features,
            ):
                service = activated.activated_discovery_service(worker)
                resolved = service._feature_resolver(current)

        self.assertIs(resolved, resolution)
        self.assertEqual(resolve_features.call_args.kwargs["cache_choice"], "reuse")
        self.assertEqual(resolve_features.call_args.args[3], root)

    def test_worker_rejects_a_campaign_with_a_mismatched_policy_digest(self):
        import flexible_rulebook.discovery_activation as activated

        historical = _history(as_of=date(2026, 8, 28))
        current = _history(as_of=_NOW.date())
        policy = _policy(historical)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(policy, "active")),
                patch(
                    "flexible_rulebook.discovery_activation.load_flexible_history",
                    side_effect=(historical, current),
                ),
                patch(
                    "flexible_rulebook.discovery_activation.inspect_primitive_cache",
                    return_value=CacheOffer(("component",), (), ()),
                ),
            ):
                preflight = activated.preflight_activated_discovery(
                    object(), "VCB", _SEED, policy, root=root, now=_NOW
                )
            request = replace(
                activated._request_from_preflight(preflight, "reuse"),
                activation_policy_digest="d" * 64,
            )
            manifest = create_manifest(request)
            write_campaign_manifest(root, manifest)
            worker = WorkerRequest(
                manifest.campaign_id,
                root,
                "flexible_rulebook.discovery_activation:activated_discovery_service",
                "flexible_rulebook.discovery_activation:activated_discovery_source_loader",
            )
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.active_policy_directory", return_value=root / "benchmark"),
                patch("flexible_rulebook.discovery_activation.load_policy_by_digest", return_value=policy),
            ):
                with self.assertRaisesRegex(ValueError, "does not match its activated policy"):
                    activated.activated_discovery_service(worker)

    def test_activated_lifecycle_rejects_a_legacy_manifest_without_source_access(self):
        import flexible_rulebook.discovery_activation as activated

        historical = _history(as_of=date(2026, 8, 28))
        current = _history(as_of=_NOW.date())
        policy = _policy(historical)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root),
                patch("flexible_rulebook.discovery_activation.load_active_policy", return_value=(policy, "active")),
                patch(
                    "flexible_rulebook.discovery_activation.load_flexible_history",
                    side_effect=(historical, current),
                ),
                patch(
                    "flexible_rulebook.discovery_activation.inspect_primitive_cache",
                    return_value=CacheOffer(("component",), (), ()),
                ),
            ):
                preflight = activated.preflight_activated_discovery(
                    object(), "VCB", _SEED, policy, root=root, now=_NOW
                )
            legacy = create_manifest(
                replace(activated._request_from_preflight(preflight, "reuse"), activation_policy_digest=None)
            )
            write_campaign_manifest(root, legacy)
            with patch("flexible_rulebook.discovery_activation.resolve_flexible_root", return_value=root):
                for action in (
                    lambda: activated.resume_activated_discovery(legacy.campaign_id, root=root),
                    lambda: activated.continue_activated_discovery(legacy.campaign_id, root=root),
                ):
                    with self.assertRaisesRegex(ValueError, "legacy campaign"):
                        action()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
