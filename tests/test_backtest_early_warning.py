"""Preferred schema-4 current-rulebook replay contracts."""

from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.test_backtest_signal_catalog import _success_document
from backtest_engine.early_warning import check_current_situation, load_current_rulebook_document
from backtest_engine.persistence import save_rulebook_result


class BacktestEarlyWarningTests(unittest.TestCase):
    def test_preferred_top_rulebook_replays_selected_gates_without_score_fields(self):
        document = _success_document()
        candidate = document["candidates"][0]
        facts = {
            "as_of_date": "2026-08-20", "literal_entry": False,
            "gate_facts": {"rulebook_adx_gate": True}, "missing_required_input": False,
        }
        with TemporaryDirectory() as directory:
            save_rulebook_result("FPT", document, directory)
            with patch("backtest_engine.early_warning._current_rulebook_facts", return_value=facts) as current:
                replay = check_current_situation("FPT", horizon="swing", rulebook_id=candidate["rulebook_id"], engine=object(), output_dir=directory)
            loaded = load_current_rulebook_document("FPT", "swing", directory)

        self.assertEqual(loaded["schema_version"], 4)
        self.assertEqual(replay["preferred_variant"], "no-background-theme")
        self.assertEqual(replay["candidate"]["rulebook_id"], candidate["rulebook_id"])
        self.assertNotIn("current_score", replay["current"])
        self.assertEqual(current.call_args.args[2], ("rulebook_adx_gate",))


if __name__ == "__main__":
    unittest.main()
