import unittest

from pages.analyze_visualization import provide_advice


class TestAnalyzeTrendClassification(unittest.TestCase):
    def make_stats(self, up, down, total_signals=10):
        return {
            "current_delta": 3.5,
            "total_signals": total_signals,
            "possibility_up": up,
            "possibility_down": down,
        }

    def classify(self, up, down):
        _, trend = provide_advice(5, 10, self.make_stats(up, down))
        return trend

    def test_preserves_existing_strong_and_moderate_directional_results(self):
        cases = [
            (55, 20, "Up"),
            (72, 5, "Strong Up"),
            (15, 80, "Strong Down"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                self.assertEqual(self.classify(up, down), expected)

    def test_uses_sideways_when_low_up_probability_is_no_change_mass(self):
        self.assertEqual(self.classify(40, 10), "Sideways")

    def test_uses_direct_down_probability_for_bearish_classification(self):
        self.assertEqual(self.classify(25, 60), "Down")

    def test_applies_up_threshold_boundaries(self):
        cases = [
            (53, 0, "Up"),
            (70, 0, "Up"),
            (71, 0, "Strong Up"),
            (52, 0, "Sideways"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                self.assertEqual(self.classify(up, down), expected)

    def test_applies_down_threshold_boundaries(self):
        cases = [
            (0, 53, "Down"),
            (0, 70, "Down"),
            (0, 71, "Strong Down"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                self.assertEqual(self.classify(up, down), expected)

    def test_returns_sideways_when_directional_evidence_is_absent_or_equal(self):
        self.assertEqual(self.classify(0, 0), "Sideways")
        self.assertEqual(self.classify(10, 10), "Sideways")

    def test_preserves_message_and_tuple_contract(self):
        cases = [
            (40, 10, "Sideways"),
            (25, 60, "Down"),
            (10, 80, "Strong Down"),
        ]

        for up, down, expected in cases:
            with self.subTest(up=up, down=down):
                result = provide_advice(5, 10, self.make_stats(up, down))

                self.assertIsInstance(result, tuple)
                self.assertEqual(len(result), 2)
                self.assertIn("3.50%", result[0])
                self.assertIn(expected, result[0])
                self.assertEqual(result[1], expected)

    def test_returns_unknown_without_historical_signals(self):
        message, trend = provide_advice(
            5,
            10,
            self.make_stats(0, 0, total_signals=0),
        )

        self.assertEqual(trend, "Unknown")
        self.assertIn("no historical data matches", message.lower())


if __name__ == "__main__":
    unittest.main()
