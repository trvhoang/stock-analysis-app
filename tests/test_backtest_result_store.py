import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backtest_engine import result_store
from backtest_engine.result_store import (
    assign_tickers_group,
    ensure_result_root,
    list_validation_group_choices,
    resolve_group_tickers,
)


class BacktestResultStoreTests(unittest.TestCase):
    def test_group_crud_keeps_uuid_on_rename_and_deletes_only_group_metadata(self):
        create = getattr(result_store, "create_group", None)
        rename = getattr(result_store, "rename_group", None)
        delete = getattr(result_store, "delete_group", None)
        self.assertTrue(callable(create))
        self.assertTrue(callable(rename))
        self.assertTrue(callable(delete))
        with TemporaryDirectory() as directory:
            signal_dir = str(Path(directory) / "backtest-result" / "ticker-signals")
            created = create("Bank", ("VCB",), signal_dir)
            old_path = created.path
            renamed = rename("BANK", "Banking", signal_dir)

            self.assertEqual(created.group_id, renamed.group_id)
            self.assertEqual("BANKING", renamed.group_name)
            self.assertEqual(("VCB",), renamed.tickers)
            self.assertFalse(old_path.exists())
            self.assertEqual(
                ("BANKING",),
                tuple(group.group_name for group in result_store.list_groups(signal_dir)),
            )

            delete("BANKING", signal_dir)

            self.assertEqual((), result_store.list_groups(signal_dir))

    def test_group_update_renames_and_replaces_members_in_one_recoverable_mutation(self):
        update = getattr(result_store, "update_group", None)
        self.assertTrue(callable(update))
        with TemporaryDirectory() as directory:
            signal_dir = str(Path(directory) / "backtest-result" / "ticker-signals")
            created = result_store.create_group("BANK", ("VCB",), signal_dir)

            updated = update("BANK", "BANKING", ("FPT", "TCB"), signal_dir)

            self.assertEqual(created.group_id, updated.group_id)
            self.assertEqual("BANKING", updated.group_name)
            self.assertEqual(("FPT", "TCB"), updated.tickers)
            self.assertEqual(("FPT", "TCB"), resolve_group_tickers("BANKING", signal_dir))

    def test_replace_group_tickers_replaces_and_retains_empty_group(self):
        replace = getattr(result_store, "replace_group_tickers", None)
        self.assertTrue(callable(replace))
        with TemporaryDirectory() as directory:
            assign_tickers_group(("VCB", "TCB"), "BANK", directory)
            replace("BANK", ("FPT",), directory)
            self.assertEqual(resolve_group_tickers("BANK", directory), ("FPT",))
            replace("BANK", (), directory)
            self.assertEqual(resolve_group_tickers("BANK", directory), ())

    def test_all_group_unions_named_members_and_unassigned_artifact_tickers(self):
        with TemporaryDirectory() as directory:
            assign_tickers_group(("VCB", "TCB"), "BANK", directory)
            assign_tickers_group(("TCB", "FPT"), "TECH", directory)

            with patch.object(
                result_store,
                "_artifact_tickers",
                return_value=("FPT", "HPG", "TCB"),
            ):
                self.assertEqual(
                    list_validation_group_choices(directory),
                    ("-", "N/A", "ALL", "BANK", "TECH"),
                )
                self.assertEqual(
                    resolve_group_tickers("ALL", directory),
                    ("FPT", "HPG", "TCB", "VCB"),
                )
                self.assertEqual(resolve_group_tickers("N/A", directory), ("HPG",))

            with self.assertRaisesRegex(ValueError, "reserved"):
                assign_tickers_group(("HPG",), "ALL", directory)

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
