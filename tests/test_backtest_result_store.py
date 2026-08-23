import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backtest_engine import result_store
from backtest_engine.result_store import (
    assign_tickers_group,
    ensure_result_root,
    resolve_group_tickers,
)


class BacktestResultStoreTests(unittest.TestCase):
    def test_replace_group_tickers_replaces_and_retains_empty_group(self):
        replace = getattr(result_store, "replace_group_tickers", None)
        self.assertTrue(callable(replace))
        with TemporaryDirectory() as directory:
            assign_tickers_group(("VCB", "TCB"), "BANK", directory)
            replace("BANK", ("FPT",), directory)
            self.assertEqual(resolve_group_tickers("BANK", directory), ("FPT",))
            replace("BANK", (), directory)
            self.assertEqual(resolve_group_tickers("BANK", directory), ())

    def test_result_root_creates_only_v3_and_group_roots_without_migrating_v2(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "ticker-signals" / "VCB" / "VCB_signals_no-background-theme.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
            before = legacy.read_bytes()
            v3_root = root / "backtest-result" / "ticker-signals"

            result = ensure_result_root(str(v3_root))

            self.assertEqual(result, v3_root)
            self.assertTrue((root / "backtest-result" / "ticker-group").is_dir())
            self.assertEqual(legacy.read_bytes(), before)
            self.assertFalse((root / "backtest-result" / ".signal-root-migration.json").exists())


if __name__ == "__main__":
    unittest.main()
