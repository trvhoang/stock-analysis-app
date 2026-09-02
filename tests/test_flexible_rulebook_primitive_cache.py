"""Persistent computed-primitive cache integrity tests."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytz

from flexible_rulebook.primitive_cache import (
    acquire_build_lease,
    component_digest,
    read_component,
    safe_read_component,
    try_write_component,
    write_component,
)


class PrimitiveCacheTests(unittest.TestCase):
    def test_component_round_trip_uses_manifest_digest_not_npz_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            arrays = {"rsi": np.array([float("nan"), 50.0, 55.0])}
            key = "a" * 64
            digest = component_digest(key, arrays, {"state": "seed"})
            write_component(path, key, arrays, {"state": "seed"}, datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
            loaded = read_component(path, key)

        self.assertEqual(loaded.digest, digest)
        self.assertEqual(loaded.arrays["rsi"].tolist()[1:], [50.0, 55.0])

    def test_corrupt_component_is_safe_cache_miss(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = "b" * 64
            write_component(root, key, {"rsi": np.array([50.0])}, {"state": "seed"}, datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))
            (root / "cache" / "bb" / f"{key}.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_component(root, key)
            self.assertIsNone(safe_read_component(root, key))

    def test_primitive_key_prefix_is_a_valid_cache_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = "frpk_" + "c" * 64
            write_component(root, key, {"rsi": np.array([50.0])}, {"state": "seed"}, datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")))

            self.assertEqual(read_component(root, key).arrays["rsi"].tolist(), [50.0])

    def test_second_writer_cannot_overwrite_different_component_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = "d" * 64; now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
            write_component(root, key, {"rsi": np.array([50.0])}, {"state": "seed"}, now)

            result = try_write_component(root, key, {"rsi": np.array([51.0])}, {"state": "seed"}, now)

            self.assertEqual(result.state, "nondeterministic_build")
            self.assertEqual(read_component(root, key).arrays["rsi"].tolist(), [50.0])

    def test_low_disk_write_stays_uncached_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = "e" * 64; now = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
            with patch("flexible_rulebook.primitive_cache.shutil.disk_usage") as usage:
                usage.return_value = type("Usage", (), {"free": 0})()
                result = try_write_component(root, key, {"rsi": np.array([50.0])}, {"state": "seed"}, now)

            self.assertEqual(result.state, "uncached_low_disk")
            self.assertIsNone(safe_read_component(root, key))

    def test_lease_is_exclusive_and_released(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = "f" * 64
            first = acquire_build_lease(root, key)
            self.assertIsNotNone(first)
            self.assertIsNone(acquire_build_lease(root, key))
            assert first is not None
            first.release()
            second = acquire_build_lease(root, key)
            self.assertIsNotNone(second)
            assert second is not None
            second.release()

    def test_locked_write_stays_uncached_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); key = "a" * 64
            lease = acquire_build_lease(root, key)
            assert lease is not None
            try:
                result = try_write_component(
                    root, key, {"rsi": np.array([50.0])}, {"state": "seed"}, datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")),
                )
            finally:
                lease.release()

            self.assertEqual(result.state, "uncached_locked")


if __name__ == "__main__":
    unittest.main()
