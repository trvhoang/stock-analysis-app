from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

import flexible_rulebook.group_adapter as group_adapter
from flexible_rulebook.group_adapter import (
    FrozenGroup,
    available_named_group_names,
    resolve_named_group_dir,
    snapshot_named_group,
)


class FlexibleRulebookGroupAdapterTests(unittest.TestCase):
    @staticmethod
    def _write(directory: Path, *, name: str = "BANK", tickers: list[str] | None = None, group_id: str = "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0") -> None:
        payload = {
            "group_id": group_id,
            "group_name": name,
            "metadata": {},
            "schema_version": 1,
            "tickers": ["FPT", "VCB"] if tickers is None else tickers,
            "updated_at": "2026-08-23T12:56:27.040393+07:00",
        }
        (directory / f"{name}-{group_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_snapshot_preserves_order_and_is_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, tickers=["vcb", "FPT"])
            snapshot = snapshot_named_group("bank", group_dir=root)
        self.assertEqual(snapshot, FrozenGroup("BANK", "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0", ("VCB", "FPT"), "2026-08-23T12:56:27.040393+07:00"))

    def test_dash_and_na_are_not_named_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "named group"):
                snapshot_named_group("-", group_dir=root)
            with self.assertRaisesRegex(ValueError, "named group"):
                snapshot_named_group("N/A", group_dir=root)

    def test_missing_or_conflicting_group_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "unavailable"):
                snapshot_named_group("BANK", group_dir=root)
            self._write(root)
            self._write(root, tickers=["VCB"] , group_id="06661359-aa1a-4d73-9e51-d27ca8d57e34")
            with self.assertRaisesRegex(ValueError, "conflicting"):
                snapshot_named_group("BANK", group_dir=root)

    def test_directory_resolution_is_app_relative_not_cwd(self):
        package_file = Path(group_adapter.__file__).resolve()
        expected = (package_file.parents[1] / "backtest-result" / "ticker-group").resolve()
        self.assertEqual(resolve_named_group_dir(), expected)

    def test_invalid_updated_at_or_duplicate_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, tickers=["FPT", "FPT"])
            with self.assertRaisesRegex(ValueError, "unique"):
                snapshot_named_group("BANK", group_dir=root)
            (root / "BANK-7d1ba3eb-6718-486b-9b86-0fb60e5f5df0.json").unlink()
            self._write(root)
            path = next(root.glob("*.json"))
            payload = json.loads(path.read_text())
            payload["updated_at"] = datetime(2026, 8, 23).isoformat()
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "timezone"):
                snapshot_named_group("BANK", group_dir=root)

    def test_named_group_may_be_empty_but_dash_and_na_are_not_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, tickers=[])
            snapshot = snapshot_named_group("BANK", group_dir=root)
        self.assertEqual(snapshot.members, ())

    def test_available_named_group_names_are_sorted_and_include_empty_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, name="TECH", tickers=[])
            self._write(root, name="BANK")
            (root / "pseudo-group.json").write_text(
                json.dumps(
                    {
                        "group_id": "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0",
                        "group_name": "N/A",
                        "schema_version": 1,
                        "tickers": [],
                        "updated_at": "2026-08-23T12:56:27.040393+07:00",
                    }
                ),
                encoding="utf-8",
            )

            names = available_named_group_names(group_dir=root)

        self.assertEqual(names, ("BANK", "TECH"))

    def test_available_named_group_names_omits_conflicting_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, name="BANK")
            self._write(root, name="BANK", tickers=["VCB"], group_id="06661359-aa1a-4d73-9e51-d27ca8d57e34")

            names = available_named_group_names(group_dir=root)

        self.assertEqual(names, ())

    def test_available_named_group_names_omits_group_with_malformed_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, name="BANK")
            (root / "BANK-malformed.json").write_text(
                json.dumps({"schema_version": 1, "group_name": "BANK"}),
                encoding="utf-8",
            )

            names = available_named_group_names(group_dir=root)

        self.assertEqual(names, ())

    def test_unicode_named_groups_are_available_and_snapshot_preserves_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, name="DẦU KHÍ")

            names = available_named_group_names(group_dir=root)
            snapshot = snapshot_named_group("dầu khí", group_dir=root)

        self.assertEqual(names, ("DẦU KHÍ",))
        self.assertEqual(snapshot.group_name, "DẦU KHÍ")


if __name__ == "__main__":
    unittest.main()
