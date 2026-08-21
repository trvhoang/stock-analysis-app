import unittest

import pandas as pd

from backtest_engine.research_optimizer import (
    ResearchCandidate,
    candidate_entry_signal,
    enumerate_candidates,
)


def _entry_frame() -> pd.DataFrame:
    """Return small causal-gate fixture with intentionally mixed rows."""

    return pd.DataFrame(
        {
            "rulebook_rsi_upcross": [True, True, True],
            "rulebook_joint_trend_pass": [False, True, True],
            "rulebook_volume_gate": [False, False, True],
            "rulebook_adx_gate": [False, False, True],
            "rulebook_missing_required_input": [False, True, False],
        },
        index=pd.date_range("2025-01-06", periods=3, freq="B"),
    )


class ResearchCandidateTests(unittest.TestCase):
    def test_enumerates_each_nonempty_subset_in_both_v3_theme_variants(self):
        candidates = enumerate_candidates("swing")

        self.assertEqual(len(candidates), 30)
        self.assertEqual(
            sum(
                candidate.theme_variant == "no-background-theme"
                for candidate in candidates
            ),
            15,
        )
        self.assertEqual(
            sum(
                candidate.theme_variant == "background-theme"
                for candidate in candidates
            ),
            15,
        )
        self.assertEqual(
            candidates[0].identity,
            "swing:no-background-theme:rsi_upcross",
        )
        self.assertEqual(
            candidates[-1].identity,
            "swing:background-theme:rsi_upcross+joint_trend+volume+adx",
        )

    def test_rejects_empty_unknown_duplicate_or_reordered_gate_selection(self):
        invalid_selections = (
            (),
            ("unknown",),
            ("rsi_upcross", "rsi_upcross"),
            ("joint_trend", "rsi_upcross"),
        )

        for gates in invalid_selections:
            with self.subTest(gates=gates):
                with self.assertRaises(ValueError):
                    ResearchCandidate(
                        horizon="swing",
                        theme_variant="no-background-theme",
                        gates=gates,
                    )

    def test_selected_subset_and_missing_input_are_both_required(self):
        frame = _entry_frame()
        candidate = ResearchCandidate(
            horizon="swing",
            theme_variant="no-background-theme",
            gates=("rsi_upcross",),
        )

        actual = candidate_entry_signal(frame, candidate)

        pd.testing.assert_series_equal(
            actual,
            pd.Series([True, False, True], index=frame.index, dtype=bool),
        )

    def test_themed_candidate_requires_aligned_theme_and_never_weakens_price_entry(self):
        frame = _entry_frame()
        candidate = ResearchCandidate(
            horizon="swing",
            theme_variant="background-theme",
            gates=("rsi_upcross",),
        )
        theme = pd.Series([True, True, False], index=frame.index, dtype=bool)

        actual = candidate_entry_signal(frame, candidate, theme)

        pd.testing.assert_series_equal(
            actual,
            pd.Series([True, False, False], index=frame.index, dtype=bool),
        )
        with self.assertRaisesRegex(ValueError, "theme"):
            candidate_entry_signal(frame, candidate)
        with self.assertRaisesRegex(ValueError, "index"):
            candidate_entry_signal(
                frame,
                candidate,
                pd.Series([True, True, True], index=pd.RangeIndex(3), dtype=bool),
            )


if __name__ == "__main__":
    unittest.main()
