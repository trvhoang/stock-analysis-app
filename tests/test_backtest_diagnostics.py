"""Read-only schema-4 diagnostic contracts."""

import inspect
import unittest

import pandas as pd

import backtest_engine.diagnostics as diagnostics
from backtest_engine.config import BacktestConfig


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=25, freq="B"),
        "open": [100] * 25, "high": [101] * 25, "low": [99] * 25,
        "close": [100] * 25, "volume": [1000] * 25, "ATR_14": [2] * 25,
    })


class BacktestDiagnosticsTests(unittest.TestCase):
    def test_diagnostic_reports_paired_exploratory_evidence_without_writes(self):
        report = diagnostics.collect_rulebook_diagnostics(BacktestConfig.for_ticker("FPT"), object(), raw_history=_frame())
        self.assertEqual(report["write_boundary"], {"database": False, "jobs": False, "artifacts": False})
        self.assertEqual(report["evaluation_label"], "Exploratory — gross")
        self.assertEqual(report["theme_treatments"], ["no-background-theme", "background-theme:AND"])
        self.assertIn("rulebook_joint_trend_pass", report["gate_rejections"])
        self.assertIn("N/A", report["p_value_policy"])

    def test_diagnostics_has_no_binary_certification_path(self):
        source = inspect.getsource(diagnostics)
        self.assertNotIn("validate_rulebook_treatments", source)
        self.assertNotIn("significance_method", source)


if __name__ == "__main__":
    unittest.main()
