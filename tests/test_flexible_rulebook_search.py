"""Lazy seeded Flexible Rulebook candidate-frontier tests."""

from dataclasses import replace
from datetime import date, timedelta
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import numpy as np
import pytz

from flexible_rulebook.catalog import catalog_revision_1, feature_profile
from flexible_rulebook.contracts import ExecutionContract, FeatureBuildContract
from flexible_rulebook.execution import CompletedTrade
from flexible_rulebook.features import FeatureResolution, resolve_feature_store
from flexible_rulebook.history import HistorySnapshot, make_evaluation_split
from flexible_rulebook.search import DiscoveryResult, SearchBudget, assign_frontier, candidate_space, discover_and_evaluate, scheduled_candidates
from flexible_rulebook.service import discovery_ledger_rows


class FlexibleRulebookSearchTests(unittest.TestCase):
    def _small_catalog(self):
        catalog = catalog_revision_1()
        return replace(
            catalog,
            buy_ema_pairs=((3, 8),), rsi_periods=(5,), rsi_levels=(50,),
            breakout_lookbacks=(10,), relative_volume_windows=(5,),
            relative_volume_minima=catalog.relative_volume_minima[:1], adx_minima=(15,),
            timeout_bars=(10,),
        )

    def test_space_is_lazy_and_definition_index_is_stable(self) -> None:
        space = candidate_space(self._small_catalog())

        self.assertGreater(space.size, 1)
        self.assertEqual(space.definition_at(1), space.definition_at(1))

    def test_same_seed_ticker_window_replays_schedule_without_repeats(self) -> None:
        space = candidate_space(self._small_catalog())
        budget = SearchBudget(attempt_count=min(12, space.size))
        first = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=budget)
        second = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=budget)

        first_rows = tuple(scheduled_candidates(space, first))
        self.assertEqual(first_rows, tuple(scheduled_candidates(space, second)))
        self.assertEqual(len({row[2] for row in first_rows}), len(first_rows))

    def test_ticker_changes_schedule_not_canonical_definition_identity(self) -> None:
        space = candidate_space(self._small_catalog())
        budget = SearchBudget(attempt_count=min(12, space.size))
        vcb = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=budget)
        fpt = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="FPT", start_slot=0, budget=budget)

        vcb_rows = tuple(scheduled_candidates(space, vcb))
        fpt_rows = tuple(scheduled_candidates(space, fpt))
        self.assertNotEqual(tuple(row[2] for row in vcb_rows), tuple(row[2] for row in fpt_rows))
        self.assertEqual({row[3].to_semantic_dict().__class__ for row in vcb_rows}, {dict})

    def test_frozen_round_robin_quotas_cover_nonempty_structures(self) -> None:
        space = candidate_space(self._small_catalog())
        assignment = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=SearchBudget(attempt_count=min(24, space.size)))
        rows = tuple(scheduled_candidates(space, assignment))
        self.assertGreater(len(assignment.strata), 1)
        self.assertEqual(sum(item.quota for item in assignment.strata), len(rows))
        self.assertEqual({row[1] for row in rows}, {item.stratum_id for item in assignment.strata if item.quota})

    def test_continuation_window_never_repeats_prior_slots(self) -> None:
        space = candidate_space(self._small_catalog()); budget = SearchBudget(attempt_count=min(24, space.size // 2))
        first = tuple(scheduled_candidates(space, assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=budget)))
        second = tuple(scheduled_candidates(space, assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=budget.attempt_count, budget=budget)))
        self.assertTrue({row[2] for row in first}.isdisjoint({row[2] for row in second}))

    def test_admission_deadline_keeps_current_slot_uncommitted(self) -> None:
        catalog = self._small_catalog(); space = candidate_space(catalog)
        assignment = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=SearchBudget(attempt_count=1))
        dates = [date(2025, 1, 2) + timedelta(days=index) for index in range(8)]
        snapshot = HistorySnapshot("VCB", pd.DataFrame({"date": dates, "open": [100] * 8, "high": [101] * 8, "low": [99] * 8, "close": [100] * 8, "volume": [100] * 8}), "a" * 64, "eligible", dates[0], dates[-1], dates[0], dates[-1], "a" * 64)
        features = object.__new__(FeatureResolution)

        result = discover_and_evaluate(snapshot, features, space, assignment, monotonic=lambda: 16_200)

        self.assertEqual((result.state, result.chain_attempted_count, result.next_slot, result.uncommitted_slot), ("time_budget_exhausted", 0, 0, 0))

    def test_discovery_ledger_rows_reconstruct_frozen_slot_provenance(self) -> None:
        space = candidate_space(self._small_catalog())
        assignment = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=SearchBudget(attempt_count=1))
        slot, stratum_id, canonical, _ = next(scheduled_candidates(space, assignment))
        result = DiscoveryResult("no_qualified_candidate_within_budget", space.size, 1, 1, None, space.size - 1, (canonical,), (), ((slot, "training_threshold"),), ())

        rows = discovery_ledger_rows(space, assignment, result, feature_receipt_id="frpr_" + "d" * 64)

        self.assertEqual(rows[0]["global_slot"], 0)
        self.assertEqual(rows[0]["canonical_index"], canonical)
        self.assertEqual(rows[0]["stratum_id"], stratum_id)
        self.assertEqual(rows[0]["outcome"], "training_threshold")

    def test_training_pass_freezes_then_executes_untouched_test(self) -> None:
        catalog = self._small_catalog(); space = candidate_space(catalog)
        dates = [date(2025, 1, 2) + timedelta(days=index) for index in range(40)]
        snapshot = HistorySnapshot("VCB", pd.DataFrame({"date": dates, "open": [100 + index for index in range(40)], "high": [101 + index for index in range(40)], "low": [99 + index for index in range(40)], "close": [100 + index for index in range(40)], "volume": [100] * 40}), "a" * 64, "eligible", dates[0], dates[-1], dates[0], dates[-1], "a" * 64)
        with tempfile.TemporaryDirectory() as directory:
            features = resolve_feature_store(snapshot, FeatureBuildContract(), feature_profile(catalog), Path(directory), choice="rebuild", now=datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
            assignment = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=SearchBudget(attempt_count=1))
            def trades(partition):
                return tuple(CompletedTrade(f"trade-{partition.label}-{index}", dates[partition.start_ordinal + index], dates[partition.start_ordinal + index], dates[partition.start_ordinal + index], partition.start_ordinal + index, partition.start_ordinal + index, partition.start_ordinal + index, 100, 120.0, "timeout", 20.0) for index in range(12))
            with patch("flexible_rulebook.search.compose_entry_mask", return_value=np.ones(40, dtype=bool)), patch("flexible_rulebook.search.execute_rulebook", side_effect=[trades(type("P", (), {"label": "training", "start_ordinal": 0})()), trades(type("P", (), {"label": "test", "start_ordinal": 26})())]) as execute:
                result = discover_and_evaluate(snapshot, features, space, assignment, monotonic=lambda: 0)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual((result.frozen_rulebook_ids[0][:4], result.outcomes[0][1], len(result.evaluations)), ("frb_", "qualified", 1))

    def test_discovery_records_the_persisted_split_and_execution_contract(self) -> None:
        catalog = self._small_catalog(); space = candidate_space(catalog)
        dates = [date(2025, 1, 2) + timedelta(days=index) for index in range(40)]
        snapshot = HistorySnapshot("VCB", pd.DataFrame({"date": dates, "open": [100 + index for index in range(40)], "high": [101 + index for index in range(40)], "low": [99 + index for index in range(40)], "close": [100 + index for index in range(40)], "volume": [100] * 40}), "a" * 64, "eligible", dates[0], dates[-1], dates[0], dates[-1], "a" * 64)
        split = make_evaluation_split(snapshot)
        execution_contract = ExecutionContract(execution_revision="frozen-execution-v2")
        with tempfile.TemporaryDirectory() as directory:
            features = resolve_feature_store(snapshot, FeatureBuildContract(), feature_profile(catalog), Path(directory), choice="rebuild", now=datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
            assignment = assign_frontier(space, frontier_seed="frb-default-seed-v1", source_ticker="VCB", start_slot=0, budget=SearchBudget(attempt_count=1))
            def trades(partition):
                return tuple(CompletedTrade(f"trade-{partition.label}-{index}", dates[partition.start_ordinal + index], dates[partition.start_ordinal + index], dates[partition.start_ordinal + index], partition.start_ordinal + index, partition.start_ordinal + index, partition.start_ordinal + index, 100, 120.0, "timeout", 20.0) for index in range(12))
            with patch("flexible_rulebook.search.compose_entry_mask", return_value=np.ones(40, dtype=bool)), patch("flexible_rulebook.search.execute_rulebook", side_effect=[trades(split.training), trades(split.test)]):
                result = discover_and_evaluate(snapshot, features, space, assignment, monotonic=lambda: 0, split=split, execution_contract=execution_contract)

        self.assertEqual(result.evaluations[0].split, split)
        self.assertEqual(result.evaluations[0].execution_contract, execution_contract)


if __name__ == "__main__":
    unittest.main()
