from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import pytz

from flexible_rulebook.contracts import (
    EvaluationPartition,
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
    RuntimeBudget,
    SelectionPolicy,
    rulebook_id,
)
from flexible_rulebook.campaigns import CampaignRequest
from flexible_rulebook.features import FeaturePreflight
from flexible_rulebook.group_adapter import FrozenGroup
from flexible_rulebook.history import HistorySnapshot
from flexible_rulebook.catalog import catalog_revision_1
from flexible_rulebook.service import (
    preflight_group_feature_components,
    qualify_rulebook_for_ticker,
    qualify_rulebooks_for_group,
)


class FlexibleRulebookServiceTests(unittest.TestCase):
    @staticmethod
    def _snapshot(ticker: str, fingerprint: str) -> HistorySnapshot:
        start = date(2011, 1, 3)
        dates = [start + timedelta(days=index) for index in range(40)]
        frame = pd.DataFrame(
            {
                "date": [item.isoformat() for item in dates],
                "open": [10_000 + index for index in range(40)],
                "high": [10_100 + index for index in range(40)],
                "low": [9_900 + index for index in range(40)],
                "close": [10_050 + index for index in range(40)],
                "volume": [100 + index for index in range(40)],
            }
        )
        return HistorySnapshot(
            ticker=ticker,
            frame=frame,
            fingerprint=fingerprint,
            quality_state="eligible",
            requested_start=start,
            requested_as_of=dates[-1],
            first_date=start,
            as_of_date=dates[-1],
            evidence_prefix_fingerprint=fingerprint,
        )

    @staticmethod
    def _definition(period: int) -> RulebookDefinition:
        return RulebookDefinition(
            buy_predicates=(
                PredicateSpec(
                    "buy",
                    PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", period),)),
                    (("cross", "up"), ("level", Decimal("52"))),
                ),
            ),
        )

    def test_group_preflight_fresh_loads_every_member_and_unions_profiles(self):
        group = FrozenGroup(
            "BANK",
            "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0",
            ("FPT", "VCB"),
            "2026-08-23T12:56:27.040393+07:00",
        )
        definitions = (self._definition(9), self._definition(14))
        seen: list[str] = []
        snapshots = {
            ticker: self._snapshot(ticker, ("a" if ticker == "FPT" else "b") * 64)
            for ticker in group.members
        }
        now = pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9))
        with patch("flexible_rulebook.service.load_flexible_history", side_effect=lambda _engine, ticker: seen.append(ticker) or snapshots[ticker]):
            with tempfile.TemporaryDirectory() as directory:
                result = preflight_group_feature_components(
                    object(), group, definitions, Path(directory), now
                )

        self.assertEqual(seen, ["FPT", "VCB"])
        self.assertEqual(
            set(result),
            {
                ("FPT", FeatureBuildContract().feature_build_contract_hash),
                ("VCB", FeatureBuildContract().feature_build_contract_hash),
            },
        )
        for preflight in result.values():
            self.assertIsInstance(preflight, FeaturePreflight)
            periods = {
                dict(spec.settings).get("period")
                for spec in preflight.feature_plan.profile.primitive_specs
                if spec.family == "rsi"
            }
            self.assertEqual(periods, {9, 14})

    def test_group_preflight_inspects_cache_once_per_target_contract(self):
        group = FrozenGroup(
            "BANK",
            "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0",
            ("FPT", "VCB"),
            "2026-08-23T12:56:27.040393+07:00",
        )
        snapshots = {
            ticker: self._snapshot(ticker, ("a" if ticker == "FPT" else "b") * 64)
            for ticker in group.members
        }
        calls: list[tuple[str, str]] = []
        now = pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9))
        with patch("flexible_rulebook.service.load_flexible_history", side_effect=lambda _engine, ticker: snapshots[ticker]):
            with patch(
                "flexible_rulebook.service.inspect_primitive_cache",
                side_effect=lambda snapshot, contract, profile, root, now: calls.append(
                    (snapshot.ticker, contract.feature_build_contract_hash)
                ) or __import__("flexible_rulebook.features", fromlist=["CacheOffer"]).CacheOffer((), (), ()),
            ):
                with tempfile.TemporaryDirectory() as directory:
                    result = preflight_group_feature_components(
                        object(), group, (self._definition(9), self._definition(14)), Path(directory), now
                    )

        self.assertEqual(
            calls,
            [
                ("FPT", FeatureBuildContract().feature_build_contract_hash),
                ("VCB", FeatureBuildContract().feature_build_contract_hash),
            ],
        )
        self.assertEqual(len(result), 2)

    def test_single_qualification_requires_valid_cache_choice_even_with_resolution(self):
        definition = self._definition(9)
        snapshot = self._snapshot("FPT", "a" * 64)
        contract = FeatureBuildContract()
        profile = FeatureProfile((definition.buy_predicates[0].primitive,))
        plan = FeaturePlan(
            __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(snapshot),
            contract,
            profile,
        )
        preflight = FeaturePreflight(
            snapshot,
            contract,
            plan,
            __import__("flexible_rulebook.features", fromlist=["CacheOffer"]).CacheOffer((), (), ()),
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "flexible_rulebook.service._evaluate_definition",
            return_value=object(),
        ):
            resolution = __import__("flexible_rulebook.features", fromlist=["resolve_feature_store"]).resolve_feature_store(
                snapshot, contract, profile, Path(directory), choice="rebuild", now=pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9)),
            )
            with self.assertRaisesRegex(ValueError, "cache_choice must be explicitly reuse or rebuild"):
                qualify_rulebook_for_ticker(
                    object(), definition, "FPT", preflight, Path(directory),
                    cache_choice=None, feature_resolution=resolution,
                )

    def test_group_qualification_uses_the_frozen_request_split(self):
        group = FrozenGroup(
            "BANK",
            "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0",
            ("FPT", "VCB"),
            "2026-08-23T12:56:27.040393+07:00",
        )
        definition = self._definition(9)
        snapshots = tuple(self._snapshot(ticker, ("a" if ticker == "FPT" else "b") * 64) for ticker in group.members)
        feature_snapshots = tuple(
            __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(item)
            for item in snapshots
        )
        contract = FeatureBuildContract()
        profile = FeatureProfile((definition.buy_predicates[0].primitive,))
        frozen_split = EvaluationSplit(
            "chronological_65_35",
            None,
            EvaluationPartition("training", snapshots[0].first_date, snapshots[0].first_date + timedelta(days=10), 0, 10, 11),
            EvaluationPartition("test", snapshots[0].first_date + timedelta(days=11), snapshots[0].as_of_date, 11, 39, 29),
        )
        request = CampaignRequest(
            "qualify", group.members, feature_snapshots, catalog_revision_1().catalog_hash,
            "flexible-engine-v1", (rulebook_id(definition),), (contract.feature_build_contract_hash,),
            tuple(FeaturePlan(item, contract, profile).feature_plan_hash for item in feature_snapshots),
            ExecutionContract(), frozen_split, RuntimeBudget(), SelectionPolicy(), 1,
        )
        observed: list[EvaluationSplit] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from flexible_rulebook.storage import write_rulebook_definition

            write_rulebook_definition(root, definition)
            with patch("flexible_rulebook.service.load_flexible_history", side_effect=lambda _engine, ticker: snapshots[group.members.index(ticker)]), patch(
                "flexible_rulebook.service._evaluate_definition",
                side_effect=lambda *_args, **kwargs: observed.append(kwargs["split"]) or type("Evaluation", (), {"state": "not_qualified"})(),
            ):
                qualify_rulebooks_for_group(
                    object(), (rulebook_id(definition),), group, request,
                    root=root, cache_choice="rebuild",
                    now=pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9)),
                )

        self.assertEqual(observed, [frozen_split, frozen_split])

    def test_group_qualification_keeps_audit_only_target_out_of_no_candidate_state(self):
        group = FrozenGroup(
            "BANK", "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0", ("FPT",),
            "2026-08-23T12:56:27.040393+07:00",
        )
        definition = self._definition(9)
        snapshot = self._snapshot("FPT", "a" * 64)
        contract = FeatureBuildContract()
        profile = FeatureProfile((definition.buy_predicates[0].primitive,))
        feature_snapshot = __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(snapshot)
        split = EvaluationSplit(
            "chronological_65_35", None,
            EvaluationPartition("training", snapshot.first_date, snapshot.first_date + timedelta(days=25), 0, 25, 26),
            EvaluationPartition("test", snapshot.first_date + timedelta(days=26), snapshot.as_of_date, 26, 39, 14),
        )
        request = CampaignRequest(
            "qualify", group.members, (feature_snapshot,), catalog_revision_1().catalog_hash,
            "flexible-engine-v1", (rulebook_id(definition),), (contract.feature_build_contract_hash,),
            (FeaturePlan(feature_snapshot, contract, profile).feature_plan_hash,),
            ExecutionContract(), split, RuntimeBudget(), SelectionPolicy(), 1,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from flexible_rulebook.storage import write_rulebook_definition

            write_rulebook_definition(root, definition)
            with patch("flexible_rulebook.service.load_flexible_history", return_value=snapshot), patch(
                "flexible_rulebook.service._evaluate_definition",
                return_value=type("Evaluation", (), {"state": "display_only"})(),
            ):
                result = qualify_rulebooks_for_group(
                    object(), (rulebook_id(definition),), group, request,
                    root=root, cache_choice="rebuild",
                    now=pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9)),
                )

        self.assertEqual(result.items[0].state, "data_ineligible")

    def test_group_qualification_keeps_targets_independent(self):
        group = FrozenGroup(
            "BANK",
            "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0",
            ("FPT", "VCB"),
            "2026-08-23T12:56:27.040393+07:00",
        )
        definition = self._definition(9)
        contract = FeatureBuildContract()
        profile = FeatureProfile((definition.buy_predicates[0].primitive,))
        fpt = self._snapshot("FPT", "a" * 64)
        vcb = self._snapshot("VCB", "b" * 64)
        split = EvaluationSplit(
            "chronological_65_35",
            None,
            EvaluationPartition("training", fpt.first_date, fpt.first_date + timedelta(days=25), 0, 25, 26),
            EvaluationPartition("test", fpt.first_date + timedelta(days=26), fpt.as_of_date, 26, 39, 14),
        )
        request = CampaignRequest(
            "qualify",
            group.members,
            tuple(
                __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(item)
                for item in (fpt, vcb)
            ),
            catalog_revision_1().catalog_hash,
            "flexible-engine-v1",
            (rulebook_id(definition),),
            (contract.feature_build_contract_hash,),
            tuple(
                FeaturePlan(
                    __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(item),
                    contract,
                    profile,
                ).feature_plan_hash
                for item in (fpt, vcb)
            ),
            ExecutionContract(),
            split,
            RuntimeBudget(),
            SelectionPolicy(),
            1,
        )
        snapshots = {"FPT": fpt, "VCB": vcb}
        seen: list[str] = []

        def evaluate(current, features, **_kwargs):
            ticker = features.store.snapshot.ticker
            seen.append(ticker)
            if ticker == "VCB":
                raise TimeoutError("one target timed out")
            return type("Evaluation", (), {"state": "qualified"})()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from flexible_rulebook.storage import write_rulebook_definition

            write_rulebook_definition(root, definition)
            with patch(
                "flexible_rulebook.service.load_flexible_history",
                side_effect=lambda _engine, ticker: snapshots[ticker],
            ), patch("flexible_rulebook.service._evaluate_definition", side_effect=evaluate), patch(
                "flexible_rulebook.service.write_signal_set",
                return_value=root / "qualified.json",
            ):
                result = qualify_rulebooks_for_group(
                    object(),
                    (rulebook_id(definition),),
                    group,
                    request,
                    root=root,
                    cache_choice="reuse",
                    now=pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9)),
                )

        self.assertEqual(seen, ["FPT", "VCB"])
        self.assertEqual(tuple(item.state for item in result.items), ("qualified", "failed"))
        self.assertEqual(result.state, "completed_with_errors")

    def test_group_qualification_marks_only_changed_target(self):
        group = FrozenGroup(
            "BANK",
            "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0",
            ("FPT", "VCB"),
            "2026-08-23T12:56:27.040393+07:00",
        )
        definition = self._definition(9)
        contract = FeatureBuildContract()
        profile = FeatureProfile((definition.buy_predicates[0].primitive,))
        fpt = self._snapshot("FPT", "a" * 64)
        expected_vcb = self._snapshot("VCB", "b" * 64)
        changed_vcb = self._snapshot("VCB", "c" * 64)
        feature_snapshot = __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(fpt)
        split = EvaluationSplit(
            "chronological_65_35",
            None,
            EvaluationPartition("training", fpt.first_date, fpt.first_date + timedelta(days=25), 0, 25, 26),
            EvaluationPartition("test", fpt.first_date + timedelta(days=26), fpt.as_of_date, 26, 39, 14),
        )
        request = CampaignRequest(
            "qualify", group.members,
            (feature_snapshot, __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(expected_vcb)),
            catalog_revision_1().catalog_hash, "flexible-engine-v1", (rulebook_id(definition),),
            (contract.feature_build_contract_hash,),
            (
                FeaturePlan(feature_snapshot, contract, profile).feature_plan_hash,
                FeaturePlan(
                    __import__("flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]).feature_snapshot_for_history(expected_vcb),
                    contract,
                    profile,
                ).feature_plan_hash,
            ),
            ExecutionContract(), split, RuntimeBudget(), SelectionPolicy(), 1,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from flexible_rulebook.storage import write_rulebook_definition

            write_rulebook_definition(root, definition)
            with patch(
                "flexible_rulebook.service.load_flexible_history",
                side_effect=lambda _engine, ticker: fpt if ticker == "FPT" else changed_vcb,
            ), patch(
                "flexible_rulebook.service._evaluate_definition",
                side_effect=lambda *_args, **_kwargs: type("Evaluation", (), {"state": "not_qualified"})(),
            ):
                result = qualify_rulebooks_for_group(
                    object(), (rulebook_id(definition),), group, request,
                    root=root, cache_choice="reuse",
                    now=pytz.timezone("Asia/Ho_Chi_Minh").localize(datetime(2026, 8, 27, 9)),
                )

        self.assertEqual(tuple(item.state for item in result.items), ("no_qualified_candidate_within_budget", "source_changed"))


if __name__ == "__main__":
    unittest.main()
