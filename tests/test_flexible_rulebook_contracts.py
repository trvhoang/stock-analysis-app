"""Contract tests for the isolated Flexible Rulebook core."""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import re
import unittest

from flexible_rulebook.contracts import (
    EvaluationPartition,
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    FeatureResolutionReceipt,
    FeatureSnapshot,
    PartitionMetrics,
    PredicateSpec,
    PrimitiveKey,
    PrimitiveSpec,
    RulebookDefinition,
    RulebookEvaluation,
    RuntimeBudget,
    SelectionPolicy,
    animal_alias,
    rulebook_id,
)
from flexible_rulebook.execution import CompletedTrade


class FlexibleRulebookContractTests(unittest.TestCase):
    def _rsi_primitive(self) -> PrimitiveSpec:
        return PrimitiveSpec(
            family="rsi",
            family_revision="rsi-wilder-v1",
            settings=(("period", 9),),
        )

    def _rsi_buy(self, level: Decimal = Decimal("52")) -> PredicateSpec:
        return PredicateSpec(
            role="buy",
            primitive=self._rsi_primitive(),
            condition=(("cross", "up"), ("level", level)),
        )

    def _ema_gate(self) -> PredicateSpec:
        return PredicateSpec(
            role="gate",
            primitive=PrimitiveSpec(
                family="ema",
                family_revision="ema-recursive-v1",
                settings=(("fast_period", 5), ("slow_period", 13)),
            ),
            condition=(("direction", "up"),),
        )

    def _definition(
        self,
        *,
        max_hold_bars: int = 22,
        rsi_level: Decimal = Decimal("52"),
        atr_stop_multiplier: Decimal | None = Decimal("1.5"),
    ) -> RulebookDefinition:
        return RulebookDefinition(
            buy_predicates=(self._rsi_buy(rsi_level),),
            gates=(self._ema_gate(),),
            filters=(),
            exits=(),
            atr_stop_multiplier=atr_stop_multiplier,
            atr_target_multiplier=Decimal("2.5"),
            atr_trailing_multiplier=None,
            min_hold_bars=3,
            max_hold_bars=max_hold_bars,
        )

    def _snapshot(self) -> FeatureSnapshot:
        return FeatureSnapshot(
            ticker="VCB",
            raw_history_fingerprint="a" * 64,
            requested_start=date(2011, 1, 3),
            requested_as_of=date(2026, 1, 2),
            first_date=date(2011, 1, 3),
            as_of_date=date(2026, 1, 2),
            quality_state="eligible",
            quality_revision="flexible-quality-v1",
        )

    def _contract(self, **changes: object) -> FeatureBuildContract:
        values: dict[str, object] = {
            "feature_algorithm_revision": "flexible-features-v1",
            "warmup_policy_revision": "full-history-causal-v1",
            "quality_policy_revision": "flexible-quality-v1",
            "numeric_runtime_revision": "numpy-pandas-flexible-v1",
            "raw_price_scale": 1000,
            "cache_schema_revision": "primitive-cache-v1",
            "append_extension_enabled": False,
            "append_extension_algorithm_revision": None,
            "append_stream_state_schema_revision": None,
        }
        values.update(changes)
        return FeatureBuildContract(**values)

    def _profile(self, *specs: PrimitiveSpec) -> FeatureProfile:
        return FeatureProfile(primitive_specs=specs)

    def _rsi14(self) -> PrimitiveSpec:
        return PrimitiveSpec(
            family="rsi",
            family_revision="rsi-wilder-v1",
            settings=(("period", 14),),
        )

    def _ema13(self) -> PrimitiveSpec:
        return PrimitiveSpec(
            family="ema",
            family_revision="ema-recursive-v1",
            settings=(("period", 13),),
        )

    def _plan(self, *specs: PrimitiveSpec) -> FeaturePlan:
        return FeaturePlan(
            snapshot=self._snapshot(),
            build_contract=self._contract(),
            profile=self._profile(*specs),
        )

    def _definition_primitives(self, definition: RulebookDefinition) -> tuple[PrimitiveSpec, ...]:
        """Return every base component required to evaluate a rulebook."""

        primitives = tuple(
            predicate.primitive
            for predicate in (
                *definition.buy_predicates,
                *definition.gates,
                *definition.filters,
                *definition.exits,
            )
        )
        if definition.atr_primitive is not None:
            return (*primitives, definition.atr_primitive)
        return primitives

    def _split(self) -> EvaluationSplit:
        return EvaluationSplit(
            method="calendar_10y_5y",
            requested_test_cutoff=date(2021, 1, 2),
            training=EvaluationPartition(
                label="training",
                start=date(2011, 1, 3),
                end=date(2021, 1, 1),
                start_ordinal=0,
                end_ordinal=2_499,
                row_count=2_500,
            ),
            test=EvaluationPartition(
                label="test",
                start=date(2021, 1, 4),
                end=date(2026, 1, 2),
                start_ordinal=2_500,
                end_ordinal=3_749,
                row_count=1_250,
            ),
        )

    def _metrics(self) -> PartitionMetrics:
        return PartitionMetrics(
            n=12,
            win_rate=65.0,
            total_return_pct=180.0,
            mean_return_pct=15.0,
            sharpe=1.25,
        )

    @staticmethod
    def _trades(count: int = 12) -> tuple[CompletedTrade, ...]:
        return tuple(
            CompletedTrade(
                trade_id=f"trade-{index:02d}",
                signal_date=date(2011, 1, 3),
                entry_date=date(2011, 1, 4),
                exit_date=date(2011, 1, 5),
                signal_bar_ordinal=index * 3,
                entry_bar_ordinal=index * 3 + 1,
                exit_bar_ordinal=index * 3 + 2,
                entry_price=100,
                exit_price=115.0,
                exit_reason="take_profit",
                return_pct=15.0,
            )
            for index in range(count)
        )

    def test_rulebook_hash_excludes_ticker_and_metrics(self) -> None:
        definition = self._definition()

        self.assertEqual(rulebook_id(definition), rulebook_id(self._definition()))
        self.assertTrue(rulebook_id(definition).startswith("frb_"))
        self.assertFalse({"ticker", "history", "metrics", "result"} & set(definition.to_semantic_dict()))

    def test_semantic_setting_change_creates_new_rulebook_id(self) -> None:
        self.assertNotEqual(
            rulebook_id(self._definition(max_hold_bars=22)),
            rulebook_id(self._definition(max_hold_bars=23)),
        )
        self.assertNotEqual(
            rulebook_id(self._definition(rsi_level=Decimal("52"))),
            rulebook_id(self._definition(rsi_level=Decimal("53"))),
        )

    def test_alias_is_deterministic_but_not_identity(self) -> None:
        identifier = rulebook_id(self._definition())

        first = animal_alias(identifier)

        self.assertEqual(first, animal_alias(identifier))
        self.assertRegex(first, r"^[A-Z][a-z]+-[A-Z][a-z]+$")
        self.assertNotEqual(first, identifier)

    def test_selection_policy_locks_training_overlap_threshold(self) -> None:
        policy = SelectionPolicy()

        self.assertEqual(policy.policy_revision, "timing-distinct-top3-v1")
        self.assertEqual(policy.training_overlap_ratio, Decimal("0.75"))

    def test_locked_scalar_contracts_reject_equal_but_wrong_python_types(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionContract(min_hold_bars=3.0)
        with self.assertRaises(ValueError):
            SelectionPolicy(max_representatives=3.0)
        with self.assertRaises(ValueError):
            SelectionPolicy(training_overlap_ratio=0.75)

    def test_native_bar_boundaries_reject_datetimes(self) -> None:
        with self.assertRaises(ValueError):
            FeatureSnapshot(
                ticker="VCB",
                raw_history_fingerprint="a" * 64,
                requested_start=datetime(2011, 1, 3),
                requested_as_of=date(2026, 1, 2),
                first_date=date(2011, 1, 3),
                as_of_date=date(2026, 1, 2),
                quality_state="eligible",
                quality_revision="flexible-quality-v1",
            )
        with self.assertRaises(ValueError):
            EvaluationPartition(
                label="training",
                start=datetime(2011, 1, 3),
                end=date(2021, 1, 1),
                start_ordinal=0,
                end_ordinal=2_499,
                row_count=2_500,
            )
        with self.assertRaises(ValueError):
            EvaluationSplit(
                method="calendar_10y_5y",
                requested_test_cutoff=datetime(2021, 1, 2),
                training=self._split().training,
                test=self._split().test,
            )

    def test_runtime_budget_rejects_deadlines_outside_under_five_hour_contract(self) -> None:
        budget = RuntimeBudget()

        self.assertEqual(budget.candidate_admission_seconds, 16_200)
        self.assertEqual(budget.normal_terminal_seconds, 17_700)
        self.assertEqual(budget.outer_worker_watchdog_seconds, 18_000)
        with self.assertRaises(ValueError):
            RuntimeBudget(candidate_admission_seconds=16_201)
        with self.assertRaises(ValueError):
            RuntimeBudget(normal_terminal_seconds=17_701)
        with self.assertRaises(ValueError):
            RuntimeBudget(candidate_admission_seconds=17_700, normal_terminal_seconds=17_700)

    def test_feature_build_contract_and_primitive_key_include_all_causal_revisions(self) -> None:
        primitive = self._rsi14()
        baseline = PrimitiveKey(self._snapshot(), self._contract(), primitive)
        revised = PrimitiveKey(
            self._snapshot(),
            self._contract(numeric_runtime_revision="numpy-pandas-flexible-v2"),
            primitive,
        )

        self.assertNotEqual(baseline.primitive_key, revised.primitive_key)

    def test_feature_build_contract_freezes_optional_append_stream_state_schema(self) -> None:
        first = self._contract(
            append_extension_enabled=True,
            append_extension_algorithm_revision="append-extension-v1",
            append_stream_state_schema_revision="rsi-stream-v1",
        )
        second = replace(first, append_stream_state_schema_revision="rsi-stream-v2")

        self.assertNotEqual(
            first.feature_build_contract_hash,
            second.feature_build_contract_hash,
        )
        with self.assertRaises(ValueError):
            self._contract(append_stream_state_schema_revision="rsi-stream-v1")

    def test_enabled_append_extension_algorithm_revision_changes_component_identity(self) -> None:
        primitive = self._rsi14()
        first = PrimitiveKey(
            self._snapshot(),
            self._contract(
                append_extension_enabled=True,
                append_extension_algorithm_revision="append-extension-v1",
                append_stream_state_schema_revision="rsi-stream-v1",
            ),
            primitive,
        )
        second = PrimitiveKey(
            self._snapshot(),
            self._contract(
                append_extension_enabled=True,
                append_extension_algorithm_revision="append-extension-v2",
                append_stream_state_schema_revision="rsi-stream-v1",
            ),
            primitive,
        )

        self.assertNotEqual(first.primitive_key, second.primitive_key)

    def test_feature_plan_is_derived_from_snapshot_contract_and_profile_not_cache_state(self) -> None:
        specs = (
            self._rsi14(),
            self._ema13(),
        )

        first = self._plan(*specs)
        second = self._plan(*reversed(specs))

        self.assertEqual(first.feature_plan_hash, second.feature_plan_hash)
        self.assertEqual(first.primitive_keys, second.primitive_keys)
        with self.assertRaises(TypeError):
            FeaturePlan(
                snapshot=self._snapshot(),
                build_contract=self._contract(),
                profile=self._profile(*specs),
                cache_path="ignored",
            )

    def test_receipt_identity_is_component_keys_and_digests_not_cache_path_or_age(self) -> None:
        plan = self._plan(self._rsi14())
        resolved = tuple((key.primitive_key, "b" * 64) for key in plan.primitive_keys)

        first = FeatureResolutionReceipt(plan=plan, resolved_components=resolved)
        second = FeatureResolutionReceipt(plan=plan, resolved_components=resolved)

        self.assertEqual(first.receipt_id, second.receipt_id)
        with self.assertRaises(TypeError):
            FeatureResolutionReceipt(
                plan=plan,
                resolved_components=resolved,
                cache_age_seconds=1,
            )

    def test_definition_rejects_empty_buy_and_nonportable_fields(self) -> None:
        with self.assertRaises(ValueError):
            RulebookDefinition(
                buy_predicates=(),
                gates=(),
                filters=(),
                exits=(),
                max_hold_bars=64,
            )
        with self.assertRaises(TypeError):
            RulebookDefinition(
                buy_predicates=(self._rsi_buy(),),
                gates=(),
                filters=(),
                exits=(),
                max_hold_bars=64,
                ticker="VCB",
            )
        with self.assertRaises(ValueError):
            PrimitiveSpec(
                family="rsi",
                family_revision="rsi-wilder-v1",
                settings=(("cache_path", "/tmp/cache"),),
            )
        with self.assertRaises(ValueError):
            PredicateSpec(
                role="buy",
                primitive=self._rsi_primitive(),
                condition=(("ticker", "VCB"),),
            )
        with self.assertRaises(ValueError):
            RulebookDefinition(
                buy_predicates=(self._rsi_buy(),),
                gates=(),
                filters=(),
                exits=(),
                min_hold_bars=3.0,
                max_hold_bars=64,
            )

    def test_definition_rejects_zero_or_negative_atr_exit_multiplier(self) -> None:
        with self.assertRaises(ValueError):
            self._definition(atr_stop_multiplier=Decimal("0"))
        with self.assertRaises(ValueError):
            self._definition(atr_stop_multiplier=Decimal("-1"))

    def test_price_exits_own_fixed_atr14_and_no_price_exit_owns_none(self) -> None:
        definition = self._definition()
        atr14 = PrimitiveSpec(
            family="atr",
            family_revision="atr-wilder-v1",
            settings=(("period", 14),),
        )

        self.assertEqual(definition.atr_primitive, atr14)
        self.assertEqual(definition.to_semantic_dict()["atr_primitive"], atr14.to_dict())
        no_price_exit = RulebookDefinition(
            buy_predicates=(self._rsi_buy(),),
            max_hold_bars=22,
        )
        self.assertIsNone(no_price_exit.atr_primitive)
        with self.assertRaisesRegex(ValueError, r"ATR\(14\)"):
            RulebookDefinition(
                buy_predicates=(self._rsi_buy(),),
                atr_stop_multiplier=Decimal("1.5"),
                atr_primitive=PrimitiveSpec(
                    family="atr",
                    family_revision="atr-wilder-v1",
                    settings=(("period", 13),),
                ),
                max_hold_bars=22,
            )

    def test_feature_profile_change_creates_new_profile_hash_not_rulebook_id(self) -> None:
        definition = self._definition()
        rsi = self._rsi14()
        ema = PrimitiveSpec(
            family="ema",
            family_revision="ema-recursive-v1",
            settings=(("period", 21),),
        )

        first = self._profile(rsi)
        second = self._profile(rsi, ema)

        self.assertNotEqual(first.feature_profile_hash, second.feature_profile_hash)
        self.assertEqual(rulebook_id(definition), rulebook_id(definition))

    def test_cache_metadata_cannot_enter_semantic_or_request_material(self) -> None:
        with self.assertRaises(ValueError):
            PrimitiveSpec(
                family="rsi",
                family_revision="rsi-wilder-v1",
                settings=(("cache_age_seconds", 1), ("period", 14)),
            )
        with self.assertRaises(TypeError):
            FeatureSnapshot(
                ticker="VCB",
                raw_history_fingerprint="a" * 64,
                requested_start=date(2011, 1, 3),
                requested_as_of=date(2026, 1, 2),
                first_date=date(2011, 1, 3),
                as_of_date=date(2026, 1, 2),
                quality_state="eligible",
                quality_revision="flexible-quality-v1",
                cache_hit=True,
            )

    def test_every_feature_build_contract_field_changes_primitive_key(self) -> None:
        primitive = self._rsi14()
        baseline_contract = self._contract()
        baseline_key = PrimitiveKey(self._snapshot(), baseline_contract, primitive).primitive_key
        revisions = (
            replace(baseline_contract, feature_algorithm_revision="flexible-features-v2"),
            replace(baseline_contract, warmup_policy_revision="full-history-causal-v2"),
            replace(baseline_contract, quality_policy_revision="flexible-quality-v2"),
            replace(baseline_contract, numeric_runtime_revision="numpy-pandas-flexible-v2"),
            replace(baseline_contract, raw_price_scale=1),
            replace(baseline_contract, cache_schema_revision="primitive-cache-v2"),
            self._contract(
                append_extension_enabled=True,
                append_extension_algorithm_revision="append-extension-v1",
                append_stream_state_schema_revision="rsi-stream-v1",
            ),
        )

        keys = {
            PrimitiveKey(self._snapshot(), revision, primitive).primitive_key
            for revision in revisions
        }
        self.assertNotIn(baseline_key, keys)
        self.assertEqual(len(keys), len(revisions))

    def test_threshold_change_reuses_base_component_but_changes_predicate_mask(self) -> None:
        rsi14 = self._rsi14()
        profile = self._profile(rsi14)
        first = self._definition(rsi_level=Decimal("52"))
        second = self._definition(rsi_level=Decimal("55"))

        first_plan = FeaturePlan(self._snapshot(), self._contract(), profile)
        second_plan = FeaturePlan(self._snapshot(), self._contract(), profile)

        self.assertEqual(first_plan.primitive_keys, second_plan.primitive_keys)
        self.assertNotEqual(rulebook_id(first), rulebook_id(second))

    def test_receipt_digest_change_is_detected_without_changing_rulebook_id(self) -> None:
        definition = self._definition()
        plan = self._plan(self._rsi14())
        key = plan.primitive_keys[0].primitive_key

        first = FeatureResolutionReceipt(plan, ((key, "c" * 64),))
        second = FeatureResolutionReceipt(plan, ((key, "d" * 64),))

        self.assertEqual(rulebook_id(definition), rulebook_id(definition))
        self.assertNotEqual(first.receipt_id, second.receipt_id)

    def test_and_group_order_is_semantic_and_duplicate_predicates_are_rejected(self) -> None:
        first = RulebookDefinition(
            buy_predicates=(self._rsi_buy(),),
            gates=(self._ema_gate(),),
            filters=(),
            exits=(),
            max_hold_bars=22,
        )
        second = RulebookDefinition(
            buy_predicates=(self._rsi_buy(),),
            gates=(),
            filters=(PredicateSpec(
                role="filter",
                primitive=self._ema_gate().primitive,
                condition=self._ema_gate().condition,
            ),),
            exits=(),
            max_hold_bars=22,
        )

        self.assertEqual(rulebook_id(first), rulebook_id(second))
        with self.assertRaises(ValueError):
            RulebookDefinition(
                buy_predicates=(self._rsi_buy(), self._rsi_buy()),
                gates=(),
                filters=(),
                exits=(),
                max_hold_bars=22,
            )

    def test_receipt_requires_exact_ordered_feature_plan_component_set(self) -> None:
        plan = self._plan(self._rsi14(), self._ema13())
        valid = tuple((key.primitive_key, "e" * 64) for key in plan.primitive_keys)

        self.assertEqual(
            len(FeatureResolutionReceipt(plan=plan, resolved_components=valid).resolved_components),
            2,
        )
        with self.assertRaises(ValueError):
            FeatureResolutionReceipt(plan=plan, resolved_components=valid[:-1])
        with self.assertRaises(ValueError):
            FeatureResolutionReceipt(plan=plan, resolved_components=tuple(reversed(valid)))

    def test_partition_metrics_require_null_sharpe_for_fewer_than_two_trades(self) -> None:
        with self.assertRaises(ValueError):
            PartitionMetrics(
                n=0,
                win_rate=None,
                total_return_pct=0.0,
                mean_return_pct=None,
                sharpe=0.0,
            )
        with self.assertRaises(ValueError):
            PartitionMetrics(
                n=1,
                win_rate=100.0,
                total_return_pct=15.0,
                mean_return_pct=15.0,
                sharpe=0.0,
            )
        self.assertIsNone(PartitionMetrics(
            n=1,
            win_rate=100.0,
            total_return_pct=15.0,
            mean_return_pct=15.0,
            sharpe=None,
        ).sharpe)

    def test_evaluation_requires_profile_to_cover_every_rulebook_primitive(self) -> None:
        definition = self._definition()
        incomplete_profile = self._profile(definition.buy_predicates[0].primitive)
        plan = FeaturePlan(self._snapshot(), self._contract(), incomplete_profile)
        receipt = FeatureResolutionReceipt(
            plan=plan,
            resolved_components=tuple(
                (key.primitive_key, "f" * 64)
                for key in plan.primitive_keys
            ),
        )

        with self.assertRaisesRegex(ValueError, "cover every rulebook primitive"):
            RulebookEvaluation(
                definition=definition,
                ticker="VCB",
                source_snapshot=self._snapshot(),
                catalog_hash="b" * 64,
                split=self._split(),
                execution_contract=ExecutionContract(),
                feature_build_contract=self._contract(),
                feature_profile=incomplete_profile,
                feature_receipt=receipt,
                training_metrics=self._metrics(),
                test_metrics=self._metrics(),
            )

    def test_evaluation_owns_ordered_partition_trade_evidence_matching_n(self) -> None:
        definition = self._definition()
        profile = self._profile(*self._definition_primitives(definition))
        plan = FeaturePlan(self._snapshot(), self._contract(), profile)
        receipt = FeatureResolutionReceipt(
            plan=plan,
            resolved_components=tuple((key.primitive_key, "f" * 64) for key in plan.primitive_keys),
        )
        trades = self._trades()
        common = dict(
            definition=definition, ticker="VCB", source_snapshot=self._snapshot(),
            catalog_hash="b" * 64, split=self._split(), execution_contract=ExecutionContract(),
            feature_build_contract=self._contract(), feature_profile=profile, feature_receipt=receipt,
            training_metrics=self._metrics(), test_metrics=self._metrics(),
        )

        evaluation = RulebookEvaluation(**common, training_trades=trades, test_trades=trades)
        self.assertEqual(evaluation.training_trades, trades)
        with self.assertRaisesRegex(ValueError, "count"):
            RulebookEvaluation(**common, training_trades=trades[:-1], test_trades=trades)

    def test_evaluation_keeps_rulebook_portable_but_locks_evidence_scope(self) -> None:
        definition = self._definition()
        profile = self._profile(*self._definition_primitives(definition), self._rsi14())
        plan = FeaturePlan(self._snapshot(), self._contract(), profile)
        receipt = FeatureResolutionReceipt(
            plan=plan,
            resolved_components=tuple(
                (key.primitive_key, "f" * 64)
                for key in plan.primitive_keys
            ),
        )
        common = {
            "definition": definition,
            "source_snapshot": self._snapshot(),
            "catalog_hash": "b" * 64,
            "split": self._split(),
            "execution_contract": ExecutionContract(),
            "feature_build_contract": self._contract(),
            "feature_profile": profile,
            "feature_receipt": receipt,
            "training_metrics": self._metrics(),
            "test_metrics": self._metrics(),
            "training_trades": self._trades(),
            "test_trades": self._trades(),
        }

        first = RulebookEvaluation(ticker="VCB", **common)
        second_snapshot = replace(self._snapshot(), ticker="FPT")
        second_plan = FeaturePlan(
            snapshot=second_snapshot,
            build_contract=self._contract(),
            profile=profile,
        )
        second = RulebookEvaluation(
            ticker="FPT",
            **(common | {
                "source_snapshot": second_snapshot,
                "feature_receipt": FeatureResolutionReceipt(
                    plan=second_plan,
                    resolved_components=tuple(
                        (key.primitive_key, "f" * 64)
                        for key in second_plan.primitive_keys
                    ),
                ),
            }),
        )

        self.assertEqual(first.rulebook_id, second.rulebook_id)
        self.assertNotEqual(first.evaluation_id, second.evaluation_id)

    def test_canonical_rulebook_identifier_is_full_sha256(self) -> None:
        identifier = rulebook_id(self._definition())

        self.assertRegex(identifier, r"^frb_[0-9a-f]{64}$")
        self.assertIsNotNone(re.fullmatch(r"frb_[0-9a-f]{64}", identifier))


if __name__ == "__main__":
    unittest.main()
