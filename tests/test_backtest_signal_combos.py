"""Boolean V3 rulebook-entry contracts."""

import unittest

import pandas as pd

from backtest_engine.config import rulebook_for
from backtest_engine.indicators import joint_trend_pass
from backtest_engine.models import RulebookExecution
from backtest_engine.signal_combos import (
    gate_subsets,
    generate_rulebook_executions,
    rulebook_entry_signal,
)


def frame_with_all_gates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "rulebook_rsi_upcross": [False, True],
            "rulebook_joint_trend_pass": [False, True],
            "rulebook_volume_gate": [False, True],
            "rulebook_adx_gate": [False, True],
            "rulebook_missing_required_input": [True, False],
        }
    )


class RulebookEntryTests(unittest.TestCase):
    def test_generator_emits_all_subsets_with_paired_treatments(self):
        executions = generate_rulebook_executions("midterm")

        self.assertEqual(len(gate_subsets()), 15)
        self.assertEqual(
            [(item.theme_variant, item.theme_mode) for item in executions[:2]],
            [
                ("no-background-theme", None),
                ("background-theme", "AND"),
            ],
        )
        self.assertEqual(len(executions), 30)
        self.assertTrue(all(isinstance(item, RulebookExecution) for item in executions))
        self.assertEqual(executions[0].selected_gates, ("rulebook_adx_gate",))
        self.assertEqual(executions[-1].selected_gates, tuple(sorted(gate_subsets()[-1])))

    def test_entry_requires_selected_gates_and_theme_is_additional_and(self):
        frame = frame_with_all_gates()
        no_theme = RulebookExecution(
            rulebook_for("swing"),
            ("rulebook_joint_trend_pass", "rulebook_rsi_upcross"),
        )
        themed = RulebookExecution(
            rulebook_for("swing"),
            ("rulebook_joint_trend_pass", "rulebook_rsi_upcross"),
            theme_variant="background-theme",
            theme_mode="AND",
        )

        self.assertTrue(bool(rulebook_entry_signal(frame, no_theme).iloc[-1]))
        no_volume = frame.copy(deep=True)
        no_volume.loc[no_volume.index[-1], "rulebook_volume_gate"] = False
        self.assertTrue(bool(rulebook_entry_signal(no_volume, no_theme).iloc[-1]))
        self.assertFalse(
            bool(rulebook_entry_signal(frame, themed, pd.Series([False, False])).iloc[-1])
        )
        self.assertTrue(
            bool(rulebook_entry_signal(frame, themed, pd.Series([False, True])).iloc[-1])
        )

    def test_missing_required_indicator_is_explicitly_not_an_entry(self):
        frame = frame_with_all_gates()
        frame.loc[frame.index[-1], "rulebook_missing_required_input"] = True

        result = rulebook_entry_signal(
            frame,
            RulebookExecution(rulebook_for("swing"), ("rulebook_rsi_upcross",)),
        )

        self.assertFalse(bool(result.iloc[-1]))

    def test_joint_trend_requires_both_rulebook_indicators_to_be_up(self):
        execution = RulebookExecution(
            rulebook_for("swing"), ("rulebook_joint_trend_pass",)
        )
        for ma_point, alligator_point, expected_entry in (
            (3, 2, False),  # Up + Sideways
            (1, 3, False),  # Down + Up
            (3, 3, True),  # Up + Up
        ):
            with self.subTest(ma_point=ma_point, alligator_point=alligator_point):
                frame = frame_with_all_gates()
                frame.loc[frame.index[-1], "rulebook_joint_trend_pass"] = joint_trend_pass(
                    ma_point,
                    alligator_point,
                )

                self.assertEqual(
                    bool(rulebook_entry_signal(frame, execution).iloc[-1]),
                    expected_entry,
                )


if __name__ == "__main__":
    unittest.main()
