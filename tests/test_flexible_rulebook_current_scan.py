from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import pandas as pd
import numpy as np
import pytz

from flexible_rulebook.contracts import (
    EvaluationPartition,
    EvaluationSplit,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
    RuntimeBudget,
    SelectionPolicy,
)
from flexible_rulebook.campaigns import CampaignRequest
from flexible_rulebook.features import CacheOffer, FeaturePreflight, feature_snapshot_for_history
from flexible_rulebook.group_adapter import FrozenGroup
from flexible_rulebook.history import HistorySnapshot
from flexible_rulebook.catalog import catalog_revision_1


class FlexibleRulebookCurrentScanTests(unittest.TestCase):
    @staticmethod
    def _snapshot(ticker: str, as_of: date, fingerprint: str) -> HistorySnapshot:
        start = as_of - timedelta(days=39)
        dates = [start + timedelta(days=index) for index in range(40)]
        frame = pd.DataFrame({
            "date": dates,
            "open": [10_000 + index for index in range(40)],
            "high": [10_100 + index for index in range(40)],
            "low": [9_900 + index for index in range(40)],
            "close": [10_050 + index for index in range(40)],
            "volume": [100 + index for index in range(40)],
        })
        return HistorySnapshot(
            ticker=ticker,
            frame=frame,
            fingerprint=fingerprint,
            quality_state="eligible",
            requested_start=start,
            requested_as_of=as_of,
            first_date=start,
            as_of_date=as_of,
            evidence_prefix_fingerprint=fingerprint,
        )

    @staticmethod
    def _snapshot_dates(ticker: str, dates: list[date], fingerprint: str, *, quality_state: str = "eligible") -> HistorySnapshot:
        frame = pd.DataFrame({
            "date": dates,
            "open": [10_000 + index for index in range(len(dates))],
            "high": [10_100 + index for index in range(len(dates))],
            "low": [9_900 + index for index in range(len(dates))],
            "close": [10_050 + index for index in range(len(dates))],
            "volume": [100 + index for index in range(len(dates))],
        })
        return HistorySnapshot(
            ticker=ticker,
            frame=frame,
            fingerprint=fingerprint,
            quality_state=quality_state,
            requested_start=dates[0],
            requested_as_of=dates[-1],
            first_date=dates[0],
            as_of_date=dates[-1],
            evidence_prefix_fingerprint=fingerprint,
        )

    @staticmethod
    def _definition() -> RulebookDefinition:
        primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        return RulebookDefinition(
            buy_predicates=(PredicateSpec("buy", primitive, (("cross", "up"), ("level", Decimal("52")))),),
        )

    @staticmethod
    def _request(snapshots: tuple[HistorySnapshot, ...]) -> CampaignRequest:
        first = snapshots[0]
        split = EvaluationSplit(
            "chronological_65_35",
            None,
            EvaluationPartition("training", first.first_date, first.first_date + timedelta(days=25), 0, 25, 26),
            EvaluationPartition("test", first.first_date + timedelta(days=26), first.as_of_date, 26, 39, 14),
        )
        return CampaignRequest(
            "current_scan",
            tuple(snapshot.ticker for snapshot in snapshots),
            tuple(feature_snapshot_for_history(snapshot) for snapshot in snapshots),
            catalog_revision_1().catalog_hash,
            "flexible-engine-v1",
            (),
            (FeatureBuildContract().feature_build_contract_hash,),
            (),
            __import__("flexible_rulebook.contracts", fromlist=["ExecutionContract"]).ExecutionContract(),
            split,
            RuntimeBudget(),
            SelectionPolicy(),
            1,
            cache_choice="reuse",
        )

    def test_mismatched_latest_dates_block_whole_group_and_list_laggard(self):
        snapshots = {
            "FPT": self._snapshot("FPT", date(2026, 8, 21), "a" * 64),
            "VCB": self._snapshot("VCB", date(2026, 8, 20), "b" * 64),
        }
        with patch("flexible_rulebook.current_scan.load_flexible_history", side_effect=lambda _engine, ticker: snapshots[ticker]):
            result = __import__("flexible_rulebook.current_scan", fromlist=["preflight_common_as_of"]).preflight_common_as_of(
                object(), ("FPT", "VCB")
            )
        self.assertEqual(result.state, "blocked_common_as_of")
        self.assertEqual(result.lagging_tickers, ("VCB",))

    def test_stale_or_unqualified_ticker_never_becomes_no_current_setup(self):
        from flexible_rulebook.current_scan import scan_current_setup

        snapshots = {"FPT": self._snapshot("FPT", date(2026, 8, 21), "a" * 64)}
        request = self._request((snapshots["FPT"],))
        with tempfile.TemporaryDirectory() as directory:
            with patch("flexible_rulebook.current_scan.load_flexible_history", side_effect=lambda _engine, ticker: snapshots[ticker]):
                result = scan_current_setup(object(), request, Path(directory))
        self.assertEqual(result.items[0].state, "no_historically_qualified_rulebook")

    def test_display_only_current_source_never_becomes_current_setup(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        expected = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        stale = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        stale = HistorySnapshot(
            stale.ticker, stale.frame, stale.fingerprint, "display_only", stale.requested_start,
            stale.requested_as_of, stale.first_date, stale.as_of_date,
            stale.evidence_prefix_fingerprint, ("audit concern",), (),
        )
        definition = self._definition()
        pair = QualifiedCurrentPair(definition, "FPT", feature_snapshot_for_history(expected), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,)))
        result = self._run_scan(self._request((expected,)), {"FPT": stale}, (pair,), compose=lambda *_args: np.array([True], dtype=bool))
        self.assertEqual(result.items[0].state, "data_stale")

    def test_common_asof_preflight_happens_before_any_cache_resolution(self):
        from flexible_rulebook.current_scan import preflight_current_scan_features, preflight_common_as_of

        snapshots = {
            "FPT": self._snapshot("FPT", date(2026, 8, 21), "a" * 64),
            "VCB": self._snapshot("VCB", date(2026, 8, 20), "b" * 64),
        }
        calls: list[str] = []
        with patch("flexible_rulebook.current_scan.load_flexible_history", side_effect=lambda _engine, ticker: calls.append(f"load:{ticker}") or snapshots[ticker]):
            preflight = preflight_common_as_of(object(), ("FPT", "VCB"))
            with self.assertRaisesRegex(ValueError, "blocked"):
                preflight_current_scan_features(object(), preflight, (), Path(tempfile.gettempdir()), datetime_now())
        self.assertEqual(calls, ["load:FPT", "load:VCB"])

    def test_current_scan_uses_one_batch_cache_decision_after_fresh_fingerprint(self):
        from flexible_rulebook.current_scan import preflight_current_scan_features, preflight_common_as_of

        snapshots = {ticker: self._snapshot(ticker, date(2026, 8, 21), ("a" if ticker == "FPT" else "b") * 64) for ticker in ("FPT", "VCB")}
        group = FrozenGroup("BANK", "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0", ("FPT", "VCB"), "2026-08-23T12:56:27.040393+07:00")
        preflight = preflight_common_as_of(object(), group.members, snapshots=snapshots)
        definition = self._definition()
        calls: list[str] = []
        with patch("flexible_rulebook.current_scan.inspect_primitive_cache", side_effect=lambda snapshot, *_args: calls.append(snapshot.ticker) or CacheOffer((), (), ())):
            result = preflight_current_scan_features(
                object(), preflight, (), Path(tempfile.gettempdir()), datetime_now(), definitions=(definition,)
            )
        self.assertEqual(calls, ["FPT", "VCB"])
        self.assertEqual(set(result), {("FPT", FeatureBuildContract().feature_build_contract_hash), ("VCB", FeatureBuildContract().feature_build_contract_hash)})

    def test_current_cache_preflight_verifies_qualified_evidence_before_offering_components(self):
        from flexible_rulebook.current_scan import (
            QualifiedCurrentPair,
            preflight_common_as_of,
            preflight_current_scan_cache,
        )

        snapshot = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        common = preflight_common_as_of(object(), ("FPT",), snapshots={"FPT": snapshot})
        definition = self._definition()
        pair = QualifiedCurrentPair(
            definition,
            "FPT",
            feature_snapshot_for_history(snapshot),
            FeatureBuildContract(),
            FeatureProfile((definition.buy_predicates[0].primitive,)),
        )
        with tempfile.TemporaryDirectory() as directory, \
                patch("flexible_rulebook.current_scan.inspect_primitive_cache", return_value=CacheOffer(("cached",), (), ())):
            result = preflight_current_scan_cache(
                object(), common, Path(directory), now=datetime_now(), qualified=(pair,)
            )

        self.assertEqual(result.state, "ready")
        self.assertEqual(result.no_qualified_tickers, ())
        self.assertEqual(set(result.feature_preflights), {("FPT", FeatureBuildContract().feature_build_contract_hash)})

    def test_current_scan_profiles_are_grouped_by_contract_and_share_matching_components(self):
        from flexible_rulebook.current_scan import preflight_common_as_of, preflight_current_scan_features

        snapshot = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        preflight = preflight_common_as_of(object(), ("FPT",), snapshots={"FPT": snapshot})
        first = self._definition()
        second_primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 14),))
        second = RulebookDefinition(buy_predicates=(PredicateSpec("buy", second_primitive, (("cross", "up"), ("level", Decimal("52")))),))
        with patch("flexible_rulebook.current_scan.inspect_primitive_cache", return_value=CacheOffer((), (), ())):
            result = preflight_current_scan_features(object(), preflight, (), Path(tempfile.gettempdir()), datetime_now(), definitions=(first, second))
        profile = next(iter(result.values())).feature_plan.profile
        self.assertEqual({dict(spec.settings)["period"] for spec in profile.primitive_specs}, {9, 14})

    def test_current_scan_persists_all_feature_receipts_before_any_member_evaluates(self):
        from flexible_rulebook.current_scan import preflight_common_as_of, scan_current_setup

        snapshots = {ticker: self._snapshot(ticker, date(2026, 8, 21), ("a" if ticker == "FPT" else "b") * 64) for ticker in ("FPT", "VCB")}
        request = self._request(tuple(snapshots[ticker] for ticker in ("FPT", "VCB")))
        from flexible_rulebook.current_scan import QualifiedCurrentPair
        definition = self._definition()
        pairs = tuple(
            QualifiedCurrentPair(
                definition,
                ticker,
                feature_snapshot_for_history(snapshots[ticker]),
                FeatureBuildContract(),
                FeatureProfile((definition.buy_predicates[0].primitive,)),
            )
            for ticker in ("FPT", "VCB")
        )
        fake_resolution = SimpleNamespace(
            receipt=SimpleNamespace(receipt_id="frpr_" + "a" * 64),
            store=SimpleNamespace(dates=(date(2026, 8, 21),)),
        )
        order: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            with patch("flexible_rulebook.current_scan.load_flexible_history", side_effect=lambda _engine, ticker: snapshots[ticker]), \
                    patch("flexible_rulebook.current_scan.write_feature_resolution_receipt", side_effect=lambda *args: order.append("receipt")), \
                    patch("flexible_rulebook.current_scan.resolve_frozen_feature_bundle", return_value=fake_resolution), \
                    patch("flexible_rulebook.current_scan.compose_entry_mask", side_effect=lambda *args: order.append("evaluate") or np.array([False], dtype=bool)):
                result = scan_current_setup(object(), request, Path(directory), qualified=pairs)
        self.assertTrue(result.items)
        self.assertLess(max(index for index, value in enumerate(order) if value == "receipt"), min(index for index, value in enumerate(order) if value == "evaluate"))
        self.assertGreaterEqual(order.count("receipt"), 2)

    def _run_scan(self, request, snapshots, pairs, *, compose=None, resolver=None, anchor_result="match"):
        from flexible_rulebook.features import CacheOffer

        compose = (lambda *_args: np.array([False], dtype=bool)) if compose is None else compose
        resolver = SimpleNamespace(receipt=SimpleNamespace(receipt_id="frpr_" + "a" * 64), store=SimpleNamespace(dates=(date(2026, 8, 21),))) if resolver is None else resolver
        with tempfile.TemporaryDirectory() as directory:
            with patch("flexible_rulebook.current_scan.load_flexible_history", side_effect=lambda _engine, ticker: snapshots[ticker]), \
                    patch("flexible_rulebook.current_scan.verify_evidence_source_anchor", return_value=anchor_result), \
                    patch("flexible_rulebook.current_scan.inspect_primitive_cache", return_value=CacheOffer((), (), ())), \
                    patch("flexible_rulebook.current_scan.resolve_frozen_feature_bundle", side_effect=resolver if isinstance(resolver, BaseException) else None, return_value=None if isinstance(resolver, BaseException) else resolver), \
                    patch("flexible_rulebook.current_scan.write_feature_resolution_receipt"), \
                    patch("flexible_rulebook.current_scan.compose_entry_mask", side_effect=compose):
                return __import__("flexible_rulebook.current_scan", fromlist=["scan_current_setup"]).scan_current_setup(
                    object(), request, Path(directory), qualified=pairs, now=datetime_now()
                )

    def test_corrected_history_requires_requalification_not_old_buy_setup(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        old = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        corrected = self._snapshot("FPT", date(2026, 8, 21), "b" * 64)
        definition = self._definition()
        pair = QualifiedCurrentPair(definition, "FPT", feature_snapshot_for_history(old), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,)))
        result = self._run_scan(self._request((old,)), {"FPT": corrected}, (pair,))
        self.assertEqual(result.items[0].state, "source_changed")

    def test_no_current_setup_requires_every_qualified_definition_successful(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        snapshot = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        first = self._definition()
        second_primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 14),))
        second = RulebookDefinition(buy_predicates=(PredicateSpec("buy", second_primitive, (("cross", "up"), ("level", Decimal("52")))),))
        pairs = tuple(QualifiedCurrentPair(definition, "FPT", feature_snapshot_for_history(snapshot), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,))) for definition in (first, second))
        calls = [0]
        def compose(*_args):
            calls[0] += 1
            if calls[0] == 2:
                raise RuntimeError("evaluation failure")
            return np.array([False], dtype=bool)
        result = self._run_scan(self._request((snapshot,)), {"FPT": snapshot}, pairs, compose=compose)
        self.assertEqual(result.items[0].state, "current_evaluation_failed")

    def test_appended_bar_keeps_qualification_but_reports_evidence_age(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        old_dates = [date(2026, 7, 13) + timedelta(days=index) for index in range(40)]
        current_dates = old_dates + [date(2026, 8, 22)]
        old = self._snapshot_dates("FPT", old_dates, "a" * 64)
        current = self._snapshot_dates("FPT", current_dates, "b" * 64)
        definition = self._definition()
        pair = QualifiedCurrentPair(definition, "FPT", feature_snapshot_for_history(old), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,)), evidence_anchor=__import__("flexible_rulebook.history", fromlist=["make_evidence_source_anchor"]).make_evidence_source_anchor(old))
        result = self._run_scan(self._request((old,)), {"FPT": current}, (pair,), compose=lambda *_args: np.array([True], dtype=bool))
        self.assertEqual(result.items[0].state, "current_setup_found")

    def test_cache_miss_or_write_failure_never_reports_no_current_setup(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        snapshot = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        definition = self._definition()
        pair = QualifiedCurrentPair(definition, "FPT", feature_snapshot_for_history(snapshot), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,)))
        result = self._run_scan(self._request((snapshot,)), {"FPT": snapshot}, (pair,), resolver=OSError("write failed"))
        self.assertNotEqual(result.items[0].state, "no_current_setup")

    def test_receipt_difference_blocks_whole_current_scan_before_any_pair(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        snapshots = {ticker: self._snapshot(ticker, date(2026, 8, 21), ("a" if ticker == "FPT" else "b") * 64) for ticker in ("FPT", "VCB")}
        definition = self._definition()
        pairs = tuple(QualifiedCurrentPair(definition, ticker, feature_snapshot_for_history(snapshots[ticker]), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,))) for ticker in snapshots)
        mismatched = SimpleNamespace(plan=object(), receipt=SimpleNamespace(receipt_id="frpr_" + "a" * 64, plan=object()), store=SimpleNamespace(dates=(date(2026, 8, 21),)))
        result = self._run_scan(self._request(tuple(snapshots.values())), snapshots, pairs, resolver=mismatched)
        self.assertEqual(tuple(item.state for item in result.items), ("not_evaluated", "not_evaluated"))

    def test_common_asof_source_mismatch_blocks_before_evaluating_any_member(self):
        snapshots = {"FPT": self._snapshot("FPT", date(2026, 8, 21), "a" * 64), "VCB": self._snapshot("VCB", date(2026, 8, 20), "b" * 64)}
        request = self._request(tuple(snapshots.values()))
        with tempfile.TemporaryDirectory() as directory, patch("flexible_rulebook.current_scan.load_flexible_history", side_effect=lambda _engine, ticker: snapshots[ticker]):
            result = __import__("flexible_rulebook.current_scan", fromlist=["scan_current_setup"]).scan_current_setup(object(), request, Path(directory))
        self.assertEqual(tuple(item.state for item in result.items), ("blocked_common_as_of", "blocked_common_as_of"))

    def test_append_is_allowed_only_when_old_evidence_prefix_matches(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        old_dates = [date(2026, 7, 13) + timedelta(days=index) for index in range(40)]
        current_dates = old_dates + [date(2026, 8, 22)]
        old = self._snapshot_dates("FPT", old_dates, "a" * 64)
        current = self._snapshot_dates("FPT", current_dates, "b" * 64)
        definition = self._definition()
        pair = QualifiedCurrentPair(definition, "FPT", feature_snapshot_for_history(old), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,)), evidence_anchor=__import__("flexible_rulebook.history", fromlist=["make_evidence_source_anchor"]).make_evidence_source_anchor(old))
        result = self._run_scan(self._request((old,)), {"FPT": current}, (pair,), anchor_result="changed")
        self.assertEqual(result.items[0].state, "source_changed")

    def test_same_date_correction_or_moving_old_boundary_requires_requalification(self):
        from flexible_rulebook.current_scan import QualifiedCurrentPair

        old = self._snapshot("FPT", date(2026, 8, 21), "a" * 64)
        changed = self._snapshot("FPT", date(2026, 8, 21), "b" * 64)
        definition = self._definition()
        pair = QualifiedCurrentPair(definition, "FPT", feature_snapshot_for_history(old), FeatureBuildContract(), FeatureProfile((definition.buy_predicates[0].primitive,)))
        result = self._run_scan(self._request((old,)), {"FPT": changed}, (pair,))
        self.assertEqual(result.items[0].state, "source_changed")


def datetime_now():
    return pytz.timezone("Asia/Ho_Chi_Minh").localize(__import__("datetime").datetime(2026, 8, 27, 9))


if __name__ == "__main__":
    unittest.main()
