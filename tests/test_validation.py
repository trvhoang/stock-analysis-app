import unittest

import pandas as pd

from commons.validation import (
    MIN_VALIDATION_BUCKET_SIZE,
    build_validation_report,
    compare_trend_classifications,
    current_statistical_trend,
    legacy_statistical_trend,
    select_global_split_date,
)


def make_observations(row_count=40):
    rows = []
    dates = pd.date_range("2024-01-01", periods=row_count, freq="D")
    for ticker in ("AAA", "BBB"):
        for index, signal_date in enumerate(dates):
            is_up = index < row_count // 2
            rows.append(
                {
                    "ticker": ticker,
                    "signal_date": signal_date,
                    "result": "Up" if is_up else "Down",
                    "result_delta": 2.0 if is_up else -3.0,
                    "legacy_score": 60.0,
                    "new_score": 60.0 if is_up else 20.0,
                }
            )
    return pd.DataFrame(rows)


class TestValidation(unittest.TestCase):
    def test_selects_one_split_date_from_pooled_unique_dates(self):
        observations = make_observations()

        split_date = select_global_split_date(observations, train_fraction=0.5)

        self.assertEqual(split_date, pd.Timestamp("2024-01-20"))

    def test_uses_same_split_for_every_ticker_and_pools_buckets(self):
        report = build_validation_report(make_observations(), train_fraction=0.5)

        observations = report["observations"]
        self.assertEqual(observations.groupby("ticker")["split_date"].nunique().to_dict(), {"AAA": 1, "BBB": 1})
        self.assertEqual(observations["split_date"].nunique(), 1)
        self.assertEqual(set(observations["phase"]), {"in_sample", "out_of_sample"})

        buckets = report["buckets"]
        in_up = buckets[
            (buckets["model"] == "legacy")
            & (buckets["phase"] == "in_sample")
            & (buckets["predicted_direction"] == "Up")
        ].iloc[0]
        self.assertEqual(in_up["sample_size"], 40)
        self.assertTrue(in_up["eligible"])
        self.assertEqual(MIN_VALIDATION_BUCKET_SIZE, 30)

    def test_reports_hit_rate_expectancy_and_new_minus_old_deltas(self):
        comparison = build_validation_report(
            make_observations(), train_fraction=0.5
        )["comparison"]

        in_sample = comparison[comparison["phase"] == "in_sample"].iloc[0]
        out_of_sample = comparison[comparison["phase"] == "out_of_sample"].iloc[0]

        self.assertEqual(in_sample["legacy_hit_rate"], 100.0)
        self.assertEqual(in_sample["new_hit_rate"], 100.0)
        self.assertEqual(in_sample["hit_rate_delta"], 0.0)
        self.assertEqual(out_of_sample["legacy_hit_rate"], 0.0)
        self.assertEqual(out_of_sample["new_hit_rate"], 100.0)
        self.assertEqual(out_of_sample["hit_rate_delta"], 100.0)
        self.assertEqual(out_of_sample["expectancy_delta"], 0.0)

    def test_excludes_invalid_rows_and_flags_under_30_pooled_buckets(self):
        observations = make_observations(row_count=10).iloc[:10].copy()
        observations.loc[0, "result"] = "Unknown"
        observations["result_delta"] = observations["result_delta"].astype(object)
        observations.loc[1, "result_delta"] = "bad"

        report = build_validation_report(observations, train_fraction=0.5)

        self.assertEqual(report["excluded_rows"], 2)
        self.assertTrue((~report["buckets"]["eligible"]).all())
        self.assertTrue(report["comparison"].empty)

    def test_rejects_missing_required_columns(self):
        with self.assertRaises(ValueError):
            build_validation_report(pd.DataFrame({"ticker": ["AAA"]}))


class TestTrendClassificationValidation(unittest.TestCase):
    def make_record(self, up, down, total_signals=40):
        return {
            "ticker": "AAA",
            "validation_days": 5,
            "result_days": 5,
            "signal_date": "2025-01-07",
            "possibility_up": up,
            "possibility_down": down,
            "total_signals": total_signals,
        }

    def test_legacy_classifier_thresholds(self):
        cases = [
            (70.01, "Strong Up"),
            (70.0, "Up"),
            (53.0, "Up"),
            (52.99, "Sideways"),
            (48.0, "Sideways"),
            (47.99, "Down"),
            (30.0, "Down"),
            (29.99, "Strong Down"),
        ]
        for probability, expected in cases:
            with self.subTest(probability=probability):
                self.assertEqual(legacy_statistical_trend(probability), expected)

    def test_current_classifier_uses_direct_down_probability(self):
        cases = [
            ((40.0, 70.01), "Strong Down"),
            ((40.0, 70.0), "Down"),
            ((40.0, 53.0), "Down"),
            ((40.0, 52.99), "Sideways"),
            ((70.01, 0.0), "Strong Up"),
            ((70.0, 0.0), "Up"),
        ]
        for probabilities, expected in cases:
            with self.subTest(probabilities=probabilities):
                self.assertEqual(current_statistical_trend(*probabilities), expected)

    def test_comparison_marks_no_change_mass_as_expected_divergence(self):
        records = pd.DataFrame([self.make_record(40.0, 10.0)])

        result = compare_trend_classifications(records)

        self.assertEqual(result.loc[0, "legacy_trend"], "Down")
        self.assertEqual(result.loc[0, "current_trend"], "Sideways")
        self.assertEqual(result.loc[0, "dominant_outcome"], "No Change")
        self.assertTrue(result.loc[0, "changed"])
        self.assertTrue(result.loc[0, "eligible"])
        self.assertEqual(result.loc[0, "total_signals"], 40)

    def test_comparison_handles_equal_and_zero_probabilities_deterministically(self):
        records = pd.DataFrame([
            self.make_record(40.0, 40.0),
            self.make_record(0.0, 0.0),
        ])

        result = compare_trend_classifications(records)

        self.assertEqual(result.loc[0, "dominant_outcome"], "Up")
        self.assertEqual(result.loc[1, "dominant_outcome"], "No Change")

    def test_comparison_keeps_invalid_rows_without_classifying_them(self):
        records = pd.DataFrame([
            self.make_record("bad", 10.0, total_signals=40),
            self.make_record(40.0, 10.0, total_signals=0),
        ])

        result = compare_trend_classifications(records)

        self.assertTrue(pd.isna(result.loc[0, "legacy_trend"]))
        self.assertTrue(pd.isna(result.loc[0, "current_trend"]))
        self.assertTrue(pd.isna(result.loc[0, "dominant_outcome"]))
        self.assertFalse(result.loc[0, "changed"])
        self.assertFalse(result.loc[0, "eligible"])
        self.assertEqual(result.loc[1, "current_trend"], "Sideways")
        self.assertFalse(result.loc[1, "eligible"])

    def test_comparison_rejects_missing_probability_columns(self):
        with self.assertRaisesRegex(ValueError, "Missing validation columns"):
            compare_trend_classifications(pd.DataFrame({"ticker": ["AAA"]}))


if __name__ == "__main__":
    unittest.main()
