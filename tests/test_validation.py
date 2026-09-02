"""Unit tests for statistical validation and split helpers."""

from datetime import date, timedelta
import unittest

import pandas as pd

from commons.validation import (
    _dominant_outcome,
    _empty_frame,
    _normalize_result,
    MIN_VALIDATION_BUCKET_SIZE,
    build_validation_report,
    compare_trend_classifications,
    current_statistical_trend,
    legacy_statistical_trend,
    score_to_direction,
    select_global_split_date,
)


class ValidationTests(unittest.TestCase):

    def test_validation_private_helpers_normalize_results_and_ties_deterministically(self) -> None:
        self.assertEqual(list(_empty_frame(["ticker", "result"]).columns), ["ticker", "result"])
        self.assertEqual(_normalize_result(" Strong Up "), "Up")
        self.assertEqual(_normalize_result("No Change"), "No Change")
        self.assertIsNone(_normalize_result(float("nan")))
        self.assertEqual(_dominant_outcome(40, 40), "Up")
        self.assertEqual(_dominant_outcome(10, 70), "Down")
        self.assertEqual(_dominant_outcome("bad", 10), None)
    def test_legacy_and_current_trend_boundaries_are_deterministic(self) -> None:
        self.assertEqual(legacy_statistical_trend(70), "Up")
        self.assertEqual(legacy_statistical_trend(70.01), "Strong Up")
        self.assertEqual(current_statistical_trend(40, 53), "Down")
        self.assertEqual(current_statistical_trend(40, 52.99), "Sideways")

    def test_trend_helpers_return_none_for_invalid_probabilities(self) -> None:
        self.assertIsNone(legacy_statistical_trend("not-a-number"))
        self.assertIsNone(current_statistical_trend(None, 50))

    def test_score_to_direction_uses_inclusive_score_bands(self) -> None:
        self.assertEqual(score_to_direction(53), "Up")
        self.assertEqual(score_to_direction(48), "No Change")
        self.assertEqual(score_to_direction(47.99), "Down")
        self.assertIsNone(score_to_direction("invalid"))

    def test_select_global_split_date_uses_sorted_unique_signal_dates(self) -> None:
        dates = [date(2026, 1, 1) + timedelta(days=index) for index in (3, 0, 3, 1, 2)]
        observations = pd.DataFrame({"signal_date": dates})
        self.assertEqual(select_global_split_date(observations, train_fraction=0.6), pd.Timestamp(date(2026, 1, 3)))

    def test_select_global_split_date_rejects_invalid_fraction_and_empty_dates(self) -> None:
        observations = pd.DataFrame({"signal_date": ["not-a-date"]})
        with self.assertRaises(ValueError):
            select_global_split_date(observations, train_fraction=1)
        with self.assertRaisesRegex(ValueError, "no valid"):
            select_global_split_date(observations)

    def test_compare_trend_classifications_adds_eligibility_and_change_columns(self) -> None:
        records = pd.DataFrame(
            {
                "ticker": ["FPT", "VCB"],
                "possibility_up": [75, 40],
                "possibility_down": [10, 60],
                "total_signals": [MIN_VALIDATION_BUCKET_SIZE, MIN_VALIDATION_BUCKET_SIZE - 1],
            }
        )
        result = compare_trend_classifications(records)
        self.assertEqual(result.loc[0, "legacy_trend"], "Strong Up")
        self.assertEqual(result.loc[0, "current_trend"], "Strong Up")
        self.assertTrue(bool(result.loc[0, "eligible"]))
        self.assertFalse(bool(result.loc[1, "eligible"]))

    def test_build_validation_report_excludes_invalid_rows_and_gates_comparison(self) -> None:
        rows = []
        for index in range(4):
            rows.append(
                {
                    "ticker": "FPT",
                    "signal_date": date(2026, 1, 1) + timedelta(days=index),
                    "result": "Up" if index % 2 == 0 else "Down",
                    "result_delta": 1.0 if index % 2 == 0 else -1.0,
                    "legacy_score": 60,
                    "new_score": 40,
                }
            )
        rows.append({"ticker": "FPT", "signal_date": "bad", "result": "Up", "result_delta": 1, "legacy_score": 60, "new_score": 60})
        report = build_validation_report(pd.DataFrame(rows), train_fraction=0.5, min_bucket_size=1)
        self.assertEqual(report["excluded_rows"], 1)
        self.assertEqual(report["split_date"], pd.Timestamp(date(2026, 1, 2)))
        self.assertEqual(set(report["comparison"]["phase"]), {"in_sample", "out_of_sample"})

    def test_build_validation_report_requires_complete_input_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing validation columns"):
            build_validation_report(pd.DataFrame({"ticker": ["FPT"]}))


if __name__ == "__main__":
    unittest.main()
