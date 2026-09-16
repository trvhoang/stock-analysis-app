"""Public semantic and lifecycle contracts for user-authored Flexible v2."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID
import unittest

import pytz

from flexible_rulebook.v2.contracts import (
    AtrExitV2,
    EvaluationRequest,
    EvaluationResult,
    PredicateV2,
    PublishedRulebook,
    RulebookDefinitionV2,
    RulebookDraft,
    canonical_json,
    collision_safe_short_ids,
)
from flexible_rulebook.v2.registry import DEFAULT_INDICATOR_REGISTRY


HCM = pytz.timezone("Asia/Ho_Chi_Minh")
NOW = HCM.localize(datetime(2026, 9, 15, 9, 0, 0))


def rsi_buy(*, threshold: object = 52) -> PredicateV2:
    return PredicateV2(
        role="buy",
        family="rsi",
        family_revision="rsi-wilder-sma-seeded-v1",
        settings={"period": 9},
        operator="upcross",
        condition={"threshold": threshold},
    )


def ema_gate() -> PredicateV2:
    return PredicateV2(
        role="gate",
        family="ema",
        family_revision="ema-close-adjust-false-v1",
        settings={"fast_period": 5, "slow_period": 13},
        operator="bullish_state",
    )


def rsi_exit() -> PredicateV2:
    return PredicateV2(
        role="technical_sell",
        family="rsi",
        family_revision="rsi-wilder-sma-seeded-v1",
        settings={"period": 9},
        operator="downcross",
        condition={"threshold": 48},
    )


class RulebookDefinitionV2Tests(unittest.TestCase):
    def test_semantic_content_has_canonical_predicate_order_and_scalar_normalization(self) -> None:
        first = RulebookDefinitionV2(
            horizon="swing",
            entry_operator="all",
            buy_predicates=(rsi_buy(threshold=52.0),),
            gates=(ema_gate(),),
            technical_exits=(rsi_exit(),),
            atr_exit=AtrExitV2(stop_multiplier=Decimal("1.50")),
            max_hold_bars=22,
        )
        second = RulebookDefinitionV2(
            horizon="swing",
            entry_operator="all",
            buy_predicates=(rsi_buy(threshold=Decimal("52.000")),),
            gates=(ema_gate(),),
            technical_exits=(rsi_exit(),),
            atr_exit=AtrExitV2(stop_multiplier=1.5),
            max_hold_bars=22,
        )

        self.assertEqual(first.semantic_digest, second.semantic_digest)
        self.assertEqual(canonical_json(first.to_semantic_dict()), canonical_json(second.to_semantic_dict()))
        self.assertEqual(first.native_timeframe, "daily")

    def test_entry_operator_is_all_or_any_and_requires_one_buy_predicate(self) -> None:
        all_entry = RulebookDefinitionV2(
            horizon="swing", entry_operator="all", buy_predicates=(rsi_buy(),), max_hold_bars=22
        )
        any_entry = RulebookDefinitionV2(
            horizon="swing", entry_operator="any", buy_predicates=(rsi_buy(),), max_hold_bars=22
        )
        self.assertNotEqual(all_entry.semantic_digest, any_entry.semantic_digest)
        with self.assertRaisesRegex(ValueError, "entry_operator"):
            RulebookDefinitionV2(
                horizon="swing", entry_operator="xor", buy_predicates=(rsi_buy(),), max_hold_bars=22
            )
        with self.assertRaisesRegex(ValueError, "at least one BUY"):
            RulebookDefinitionV2(
                horizon="swing", entry_operator="all", buy_predicates=(), max_hold_bars=22
            )

    def test_gates_and_technical_exits_are_order_independent_and_separate(self) -> None:
        first = RulebookDefinitionV2(
            horizon="swing",
            entry_operator="any",
            buy_predicates=(rsi_buy(),),
            gates=(ema_gate(),),
            technical_exits=(rsi_exit(),),
            max_hold_bars=22,
        )
        second = RulebookDefinitionV2(
            horizon="swing",
            entry_operator="any",
            buy_predicates=(rsi_buy(),),
            gates=tuple(reversed(first.gates)),
            technical_exits=tuple(reversed(first.technical_exits)),
            max_hold_bars=22,
        )

        self.assertEqual(first.semantic_digest, second.semantic_digest)
        self.assertEqual(first.gates[0].role, "gate")
        self.assertEqual(first.technical_exits[0].role, "technical_sell")

    def test_grammar_rejects_wrong_roles_duplicates_and_invalid_hold_rules(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            RulebookDefinitionV2(
                horizon="swing",
                entry_operator="any",
                buy_predicates=(rsi_buy(), rsi_buy()),
                max_hold_bars=22,
            )
        with self.assertRaisesRegex(ValueError, "gates"):
            RulebookDefinitionV2(
                horizon="swing",
                entry_operator="all",
                buy_predicates=(rsi_buy(),),
                gates=(rsi_buy(),),
                max_hold_bars=22,
            )
        with self.assertRaisesRegex(ValueError, "technical_exits"):
            RulebookDefinitionV2(
                horizon="swing",
                entry_operator="all",
                buy_predicates=(rsi_buy(),),
                technical_exits=(ema_gate(),),
                max_hold_bars=22,
            )
        with self.assertRaisesRegex(ValueError, "min_hold_bars"):
            RulebookDefinitionV2(
                horizon="swing",
                entry_operator="all",
                buy_predicates=(rsi_buy(),),
                min_hold_bars=2,
                max_hold_bars=22,
            )
        with self.assertRaisesRegex(ValueError, "4 through 64"):
            RulebookDefinitionV2(
                horizon="swing", entry_operator="all", buy_predicates=(rsi_buy(),), max_hold_bars=65
            )

    def test_operational_fields_never_change_definition_identity(self) -> None:
        definition = RulebookDefinitionV2(
            horizon="midterm",
            entry_operator="all",
            buy_predicates=(rsi_buy(),),
            max_hold_bars=16,
        )
        first = RulebookDraft.new(
            name="Income trend",
            description="first display text",
            definition=definition,
            now=NOW,
        )
        second = first.with_changes(
            name="Renamed for a different ticker",
            description="different note",
            now=NOW,
        )

        self.assertEqual(first.definition.semantic_digest, second.definition.semantic_digest)
        self.assertEqual(first.draft_id, second.draft_id)
        self.assertEqual(second.revision, first.revision + 1)
        self.assertIsInstance(UUID(first.draft_id), UUID)
        self.assertEqual(first.created_at.tzinfo.zone, "Asia/Ho_Chi_Minh")

    def test_midterm_definition_records_completed_wfri_native_semantics(self) -> None:
        definition = RulebookDefinitionV2(
            horizon="midterm", entry_operator="all", buy_predicates=(rsi_buy(),), max_hold_bars=16
        )

        self.assertEqual(definition.native_timeframe, "weekly")
        self.assertEqual(definition.weekly_frequency, "W-FRI")
        self.assertEqual(definition.to_semantic_dict()["weekly_frequency"], "W-FRI")

    def test_definition_validates_every_predicate_against_registry(self) -> None:
        unsupported = PredicateV2(
            role="buy",
            family="atr",
            family_revision="atr-wilder-sma-seeded-v1",
            settings={"period": 14},
            operator="above",
            condition={"threshold": 1},
        )
        definition = RulebookDefinitionV2(
            horizon="swing", entry_operator="all", buy_predicates=(unsupported,), max_hold_bars=22
        )
        draft = RulebookDraft.new(name="Invalid ATR BUY", definition=definition, now=NOW)

        with self.assertRaisesRegex(ValueError, "does not support role"):
            draft.validate(DEFAULT_INDICATOR_REGISTRY)


class LifecycleAndEvidenceTests(unittest.TestCase):
    def test_editing_draft_changes_semantic_digest_and_invalidates_old_evidence(self) -> None:
        original = RulebookDraft.new(
            name="RSI turn",
            definition=RulebookDefinitionV2(
                horizon="swing", entry_operator="all", buy_predicates=(rsi_buy(threshold=52),), max_hold_bars=22
            ),
            now=NOW,
        )
        evidence = EvaluationResult.completed(
            semantic_digest=original.definition.semantic_digest,
            ticker="VCB",
            source={"start": "2011-01-01", "end": "2026-09-15"},
            split={"training": 0.65, "test": 0.35},
            metrics={"training": {"n": 0}, "test": {"n": 0}},
        )
        edited = original.with_changes(
            definition=RulebookDefinitionV2(
                horizon="swing", entry_operator="all", buy_predicates=(rsi_buy(threshold=55),), max_hold_bars=22
            ),
            now=HCM.localize(datetime(2026, 9, 15, 10, 0, 0)),
        )

        self.assertNotEqual(edited.definition.semantic_digest, original.definition.semantic_digest)
        self.assertFalse(edited.is_evaluated_by((evidence,)))
        self.assertTrue(original.is_evaluated_by((evidence,)))

    def test_publish_is_immutable_and_retirement_keeps_true_identity(self) -> None:
        definition = RulebookDefinitionV2(
            horizon="swing", entry_operator="all", buy_predicates=(rsi_buy(),), max_hold_bars=22
        )
        published = PublishedRulebook.publish(definition, published_at=NOW)
        retired = published.retire(retired_at=HCM.localize(datetime(2026, 9, 15, 11, 0, 0)))

        self.assertRegex(published.rulebook_id, r"^frb2_[0-9a-f]{64}$")
        self.assertEqual(retired.rulebook_id, published.rulebook_id)
        self.assertEqual(retired.definition, published.definition)
        self.assertTrue(retired.is_retired)
        with self.assertRaisesRegex(Exception, "cannot assign"):
            published.rulebook_id = "frb2_" + "0" * 64  # type: ignore[misc]

    def test_collision_safe_short_ids_extend_all_colliding_prefixes(self) -> None:
        alpha = "frb2_" + "abcdef12" + "a" * 56
        beta = "frb2_" + "abcdef12" + "b" * 56
        gamma = "frb2_" + "ff00ff00" + "c" * 56

        resolved = collision_safe_short_ids((alpha, beta, gamma), minimum_length=8)

        self.assertEqual(set(resolved), {alpha, beta, gamma})
        self.assertNotEqual(resolved[alpha], resolved[beta])
        self.assertGreater(len(resolved[alpha]), len("FR-ABCDEFGH"))
        self.assertEqual(resolved[gamma], "FR-FF00FF00")
        self.assertEqual(alpha, "frb2_" + "abcdef12" + "a" * 56)


class EvaluationRequestTests(unittest.TestCase):
    def test_request_normalizes_tickers_and_restricts_training_ratio(self) -> None:
        request = EvaluationRequest(
            semantic_digest="a" * 64,
            tickers=("vcb", "fpt"),
            training_ratio=65,
            use_cache=True,
        )

        self.assertEqual(request.tickers, ("VCB", "FPT"))
        self.assertEqual(request.training_ratio, Decimal("0.65"))
        with self.assertRaisesRegex(ValueError, "training_ratio"):
            EvaluationRequest(semantic_digest="a" * 64, tickers=("VCB",), training_ratio=66)


if __name__ == "__main__":
    unittest.main()
