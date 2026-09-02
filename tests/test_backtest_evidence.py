"""Schema-5 source identity and evidence-density contracts."""

from dataclasses import FrozenInstanceError
import unittest

import pandas as pd

from backtest_engine.evidence import assess_evidence, source_fingerprint


def _session_frame(rows: int = 100) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=rows)
    close = pd.Series(range(50_000, 50_000 + rows), dtype="int64")
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 100,
            "low": close - 100,
            "close": close,
            "volume": [1_000] * rows,
        }
    )


class BacktestEvidenceTests(unittest.TestCase):
    def test_fingerprint_changes_for_append_and_historical_correction(self):
        original = _session_frame(100)
        first = source_fingerprint(
            "VCB",
            original,
            original["date"].iloc[-1].date(),
        )
        corrected = original.copy(deep=True)
        corrected.loc[10, "close"] += 1_000
        appended = pd.concat(
            [original, _session_frame(101).iloc[[-1]]],
            ignore_index=True,
        )

        self.assertNotEqual(
            first,
            source_fingerprint(
                "VCB",
                corrected,
                corrected["date"].iloc[-1].date(),
            ),
        )
        self.assertNotEqual(
            first,
            source_fingerprint(
                "VCB",
                appended,
                appended["date"].iloc[-1].date(),
            ),
        )

    def test_fingerprint_is_order_independent_and_numeric_canonical(self):
        original = _session_frame(20)
        shuffled = original.sample(frac=1.0, random_state=42).reset_index(drop=True)
        numeric_float = original.copy(deep=True)
        numeric_float[["open", "high", "low", "close", "volume"]] = numeric_float[
            ["open", "high", "low", "close", "volume"]
        ].astype(float)
        common = original["date"].iloc[-1].date()

        expected = source_fingerprint(" vcb ", original, common)

        self.assertEqual(expected, source_fingerprint("VCB", shuffled, common))
        self.assertEqual(expected, source_fingerprint("VCB", numeric_float, common))
        self.assertNotEqual(expected, source_fingerprint("FPT", original, common))
        numeric_float.loc[3, "close"] += 0.5
        with self.assertRaisesRegex(ValueError, "raw integer"):
            source_fingerprint("VCB", numeric_float, common)

    def test_fingerprint_rejects_duplicate_effective_dates(self):
        original = _session_frame(20)
        duplicate = pd.concat([original, original.iloc[[5]]], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "duplicate"):
            source_fingerprint(
                "VCB",
                duplicate,
                original["date"].iloc[-1].date(),
            )

    def test_recent_listing_uses_only_effective_session_denominator(self):
        vnindex = _session_frame(rows=500)
        ticker = vnindex.iloc[-490:].copy()

        evidence = assess_evidence(
            ticker,
            vnindex,
            ticker["date"].iloc[-1].date(),
        )

        self.assertTrue(evidence.eligible)
        self.assertEqual(490, evidence.expected_sessions)
        self.assertEqual(490, evidence.observed_sessions)
        self.assertEqual(ticker["date"].iloc[0].date(), evidence.first_available_bar)

    def test_exact_ninety_five_percent_passes_but_94_99_percent_fails(self):
        vnindex = _session_frame(rows=10_000)
        missing_500 = list(range(10, 9_991, 20))
        at_threshold = vnindex.drop(index=missing_500).reset_index(drop=True)
        below_threshold = vnindex.drop(index=[*missing_500, 11]).reset_index(drop=True)
        common = vnindex["date"].iloc[-1].date()

        eligible = assess_evidence(at_threshold, vnindex, common)
        ineligible = assess_evidence(below_threshold, vnindex, common)

        self.assertEqual(0.95, eligible.coverage_ratio)
        self.assertTrue(eligible.eligible)
        self.assertEqual(0.9499, ineligible.coverage_ratio)
        self.assertFalse(ineligible.eligible)
        self.assertIn("coverage_ratio_below_0.95", ineligible.reasons)

    def test_more_than_twenty_missing_sessions_is_ineligible(self):
        vnindex = _session_frame(rows=100)
        ticker = vnindex.drop(index=range(30, 51)).reset_index(drop=True)

        evidence = assess_evidence(
            ticker,
            vnindex,
            vnindex["date"].iloc[-1].date(),
        )

        self.assertFalse(evidence.eligible)
        self.assertEqual(21, evidence.max_gap_sessions)
        self.assertIn("max_gap_sessions_exceeds_20", evidence.reasons)

    def test_missing_latest_bar_and_unclean_audit_are_independent_reasons(self):
        vnindex = _session_frame(rows=100)
        ticker = vnindex.iloc[:-1].copy()

        evidence = assess_evidence(
            ticker,
            vnindex,
            vnindex["date"].iloc[-1].date(),
            audit_eligible=False,
        )

        self.assertFalse(evidence.eligible)
        self.assertIn("latest_bar_mismatch", evidence.reasons)
        self.assertIn("raw_audit_not_clean", evidence.reasons)

    def test_ticker_and_vnindex_fingerprints_are_independent_and_result_is_frozen(self):
        ticker = _session_frame(rows=100)
        vnindex = ticker.copy(deep=True)
        common = ticker["date"].iloc[-1].date()
        first = assess_evidence(ticker, vnindex, common)
        changed_vnindex = vnindex.copy(deep=True)
        changed_vnindex.loc[10, "close"] += 1_000
        second = assess_evidence(ticker, changed_vnindex, common)

        self.assertEqual(first.ticker_fingerprint, second.ticker_fingerprint)
        self.assertNotEqual(first.vnindex_fingerprint, second.vnindex_fingerprint)
        self.assertEqual("eligible", first.to_dict()["status"])
        with self.assertRaises(FrozenInstanceError):
            first.eligible = False


if __name__ == "__main__":
    unittest.main()
