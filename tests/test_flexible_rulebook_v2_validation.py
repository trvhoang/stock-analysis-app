"""Boolean support and BUY-eligibility contracts for Flexible Rulebook v2."""

from decimal import Decimal
import unittest

import pandas as pd

from flexible_rulebook.v2.contracts import PredicateV2, RulebookDefinitionV2
from flexible_rulebook.v2.features import PredicateEvaluation
from flexible_rulebook.v2.validation import (
    assess_progressive_state,
    classify_monitoring,
    compose_rulebook,
    determine_buy_action,
)


class FlexibleRulebookV2ValidationTests(unittest.TestCase):
    def _predicate(self, role: str, operator: str, threshold: int) -> PredicateV2:
        return PredicateV2(
            role=role, family="rsi", family_revision="rsi-wilder-sma-seeded-v1",
            settings={"period": 9}, operator=operator, condition={"threshold": threshold},
        )

    @staticmethod
    def _facts(mask: list[bool], support: list[bool]) -> PredicateEvaluation:
        return PredicateEvaluation(pd.Series(mask, dtype=bool), pd.Series(support, dtype=bool), ())

    def test_all_buy_and_all_gates_are_hard_entry_requirements_and_each_is_a_support_fact(self) -> None:
        first = self._predicate("buy", "upcross", 52)
        second = self._predicate("buy", "above", 55)
        gate = self._predicate("gate", "above", 50)
        definition = RulebookDefinitionV2("swing", "all", (first, second), (gate,))
        composition = compose_rulebook(definition, {
            first: self._facts([False, True], [True, True]),
            second: self._facts([False, True], [False, True]),
            gate: self._facts([True, True], [True, False]),
        })

        self.assertEqual([False, True], composition.entry_mask.tolist())
        self.assertEqual(2 / 3 * 100.0, composition.support_percentage(1))
        self.assertFalse(composition.all_gates_support(1))

    def test_any_buy_is_one_combined_support_fact_and_technical_exits_do_not_enter_entry_composition(self) -> None:
        first = self._predicate("buy", "upcross", 52)
        second = self._predicate("buy", "above", 55)
        exit_predicate = self._predicate("technical_sell", "downcross", 48)
        second_exit = self._predicate("technical_sell", "downcross", 40)
        definition = RulebookDefinitionV2("swing", "any", (first, second), technical_exits=(exit_predicate, second_exit))
        composition = compose_rulebook(definition, {
            first: self._facts([False, False], [False, False]),
            second: self._facts([False, True], [False, True]),
            exit_predicate: self._facts([True, True], [True, True]),
            second_exit: self._facts([False, False], [False, False]),
        })

        self.assertEqual([False, True], composition.entry_mask.tolist())
        self.assertEqual(100.0, composition.support_percentage(1))
        self.assertEqual([True, True], composition.technical_exit_mask.tolist())

    def test_multiple_gates_all_must_hold_for_entry_and_remain_independent_support_facts(self) -> None:
        buy = self._predicate("buy", "upcross", 52)
        first_gate = self._predicate("gate", "above", 55)
        second_gate = self._predicate("gate", "above", 60)
        definition = RulebookDefinitionV2("swing", "all", (buy,), (first_gate, second_gate))
        composition = compose_rulebook(definition, {
            buy: self._facts([False, True], [False, True]),
            first_gate: self._facts([True, True], [True, True]),
            second_gate: self._facts([True, False], [True, False]),
        })

        self.assertEqual([False, False], composition.entry_mask.tolist())
        self.assertEqual(2 / 3 * 100.0, composition.support_percentage(1))
        self.assertFalse(composition.all_gates_support(1))

    def test_classification_boundaries_and_buy_action_require_every_live_fact(self) -> None:
        self.assertEqual("Closely Match", classify_monitoring(Decimal("85.0001"), "Fresh"))
        self.assertEqual("Nearly Match", classify_monitoring(Decimal("65"), "On-going"))
        self.assertEqual("No Match", classify_monitoring(Decimal("85"), "Weakening"))
        self.assertEqual("No Match", classify_monitoring(Decimal("64.99"), "Fresh"))
        self.assertEqual("can BUY", determine_buy_action(
            has_prior_event=True, trend_state="On-going", live_entry_support=True,
            all_gates_support=True, evidence_available=True, is_listed=True, has_open_position=False,
        ))
        for missing_fact in ("has_prior_event", "live_entry_support", "all_gates_support", "evidence_available", "is_listed"):
            facts = {
                "has_prior_event": True,
                "trend_state": "Fresh",
                "live_entry_support": True,
                "all_gates_support": True,
                "evidence_available": True,
                "is_listed": True,
                "has_open_position": False,
            }
            facts[missing_fact] = False
            self.assertEqual("expired BUY", determine_buy_action(**facts))
        self.assertEqual("expired BUY", determine_buy_action(
            has_prior_event=True, trend_state="Weakening", live_entry_support=True,
            all_gates_support=True, evidence_available=True, is_listed=True, has_open_position=False,
        ))
        self.assertEqual("HOLD", determine_buy_action(
            has_prior_event=True, trend_state="Fresh", live_entry_support=True,
            all_gates_support=True, evidence_available=True, is_listed=True, has_open_position=True,
        ))

    def test_progressive_state_requires_price_and_live_support_after_the_fresh_window(self) -> None:
        self.assertEqual("Fresh", assess_progressive_state(
            has_prior_event=True, age_native_bars=0, price_change_atr=0.0,
            drawdown_from_high_atr=0.0, recent_price_decline=False,
            source_support=True, gates_support=True,
        ))
        self.assertEqual("On-going", assess_progressive_state(
            has_prior_event=True, age_native_bars=3, price_change_atr=0.2,
            drawdown_from_high_atr=-0.1, recent_price_decline=False,
            source_support=True, gates_support=True,
        ))
        self.assertEqual("Weakening", assess_progressive_state(
            has_prior_event=True, age_native_bars=2, price_change_atr=-0.6,
            drawdown_from_high_atr=-0.6, recent_price_decline=True,
            source_support=True, gates_support=True,
        ))
        self.assertEqual("Weakening", assess_progressive_state(
            has_prior_event=True, age_native_bars=7, price_change_atr=0.8,
            drawdown_from_high_atr=-0.2, recent_price_decline=False,
            source_support=False, gates_support=True,
        ))
        self.assertEqual("Invalidated", assess_progressive_state(
            has_prior_event=True, age_native_bars=4, price_change_atr=0.8,
            drawdown_from_high_atr=-0.2, recent_price_decline=False,
            source_support=True, gates_support=False,
        ))


if __name__ == "__main__":
    unittest.main()
