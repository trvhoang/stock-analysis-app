"""Fresh schema-5 current-rulebook replay and invalidation contracts."""

from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from tests.test_backtest_signal_catalog import _success_document
from backtest_engine.early_warning import check_current_situation, load_current_rulebook_document
from backtest_engine.evidence import assess_evidence
from backtest_engine.persistence import save_rulebook_result


def _history(end: str) -> pd.DataFrame:
    dates = pd.bdate_range("2011-01-03", end)
    close = pd.Series(range(100_000, 100_000 + len(dates)), dtype="int64")
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close + 100,
        "low": close - 100,
        "close": close,
        "volume": 1_000_000,
    })


def _document_for_sources(ticker_raw: pd.DataFrame, vnindex_raw: pd.DataFrame) -> dict[str, object]:
    document = _success_document()
    common = pd.Timestamp(ticker_raw["date"].iloc[-1]).date()
    document["evidence_eligibility"] = assess_evidence(
        ticker_raw,
        vnindex_raw,
        common,
        ticker="FPT",
        audit_eligible=True,
    ).to_dict()
    return document


class BacktestEarlyWarningTests(unittest.TestCase):
    def test_preferred_top_rulebook_replays_selected_gates_without_score_fields(self):
        ticker_raw = _history("2026-01-02")
        vnindex_raw = _history("2026-01-02")
        document = _document_for_sources(ticker_raw, vnindex_raw)
        candidate = document["candidates"][0]
        facts = {
            "as_of_date": "2026-08-20", "literal_entry": False,
            "gate_facts": {"rulebook_adx_gate": True}, "missing_required_input": False,
        }
        with TemporaryDirectory() as directory:
            save_rulebook_result("FPT", document, directory)
            with patch(
                "backtest_engine.early_warning.load_ticker_history",
                side_effect=[ticker_raw, vnindex_raw],
            ), patch("backtest_engine.early_warning._current_rulebook_facts", return_value=facts) as current:
                replay = check_current_situation("FPT", horizon="swing", rulebook_id=candidate["rulebook_id"], engine=object(), output_dir=directory)
            loaded = load_current_rulebook_document("FPT", "swing", directory)

        self.assertEqual(loaded["schema_version"], 5)
        self.assertEqual(replay["preferred_variant"], "no-background-theme")
        self.assertEqual(replay["candidate"]["rulebook_id"], candidate["rulebook_id"])
        self.assertNotIn("current_score", replay["current"])
        self.assertEqual(current.call_args.args[2], ("rulebook_adx_gate",))

    def test_appended_common_session_invalidates_before_candidate_replay(self):
        frozen_ticker = _history("2026-01-02")
        frozen_vnindex = _history("2026-01-02")
        current_ticker = _history("2026-01-05")
        current_vnindex = _history("2026-01-05")
        document = _document_for_sources(frozen_ticker, frozen_vnindex)
        candidate = document["candidates"][0]

        with TemporaryDirectory() as directory:
            save_rulebook_result("FPT", document, directory)
            with patch(
                "backtest_engine.early_warning.load_ticker_history",
                side_effect=[current_ticker, current_vnindex],
            ), patch(
                "backtest_engine.early_warning.write_regeneration_marker"
            ) as marker, patch(
                "backtest_engine.early_warning._current_rulebook_facts"
            ) as current:
                replay = check_current_situation(
                    "FPT",
                    horizon="swing",
                    rulebook_id=candidate["rulebook_id"],
                    engine=object(),
                    output_dir=directory,
                )

        self.assertIsNone(replay["candidate"])
        self.assertEqual(replay["reason"], "source_history_changed")
        marker.assert_called_once()
        self.assertEqual(
            marker.call_args.kwargs["reason"],
            "Source history changed; regenerate Backtest schema 5.",
        )
        current.assert_not_called()


if __name__ == "__main__":
    unittest.main()
