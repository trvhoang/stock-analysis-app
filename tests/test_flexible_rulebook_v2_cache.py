"""Integrity contracts for the v2 computed-component cache."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pytz

from flexible_rulebook.v2.cache import (
    ComponentIdentity,
    acquire_build_lease,
    component_digest,
    read_component,
    safe_read_component,
    try_write_component,
    write_component,
)


class FlexibleRulebookV2CacheTests(unittest.TestCase):
    def _identity(self, **overrides: object) -> ComponentIdentity:
        values = {
            "source_fingerprint": "a" * 64,
            "calendar_fingerprint": "b" * 64,
            "build_revision": "feature-store-v2",
            "family": "rsi",
            "formula_revision": "rsi-wilder-sma-seeded-v1",
            "settings": {"period": 9},
        }
        values.update(overrides)
        return ComponentIdentity(**values)

    def _now(self) -> datetime:
        return datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))

    def test_identity_binds_source_calendar_build_and_math_settings_but_not_threshold_masks(self) -> None:
        baseline = self._identity()

        self.assertNotEqual(
            baseline.key,
            self._identity(calendar_fingerprint="c" * 64).key,
        )
        self.assertNotEqual(
            baseline.key,
            self._identity(build_revision="feature-store-v3").key,
        )
        self.assertNotEqual(
            baseline.key,
            self._identity(settings={"period": 14}).key,
        )
        self.assertEqual("rsi", baseline.family)

    def test_round_trip_persists_computed_arrays_with_full_identity_and_digest(self) -> None:
        identity = self._identity()
        arrays = {"rsi": np.array([float("nan"), 50.0, 55.0])}
        state = {"warmup": 9}
        expected_digest = component_digest(identity, arrays, state)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_component(root, identity, arrays, state, self._now())
            loaded = read_component(root, identity)

        self.assertEqual(expected_digest, loaded.digest)
        self.assertEqual(55.0, loaded.arrays["rsi"].tolist()[-1])
        self.assertEqual("feature-store-v2", loaded.identity.build_revision)

    def test_completion_time_is_normalized_to_project_timezone(self) -> None:
        identity = self._identity()
        utc_now = datetime(2026, 9, 16, 1, 0, tzinfo=pytz.UTC)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_component(root, identity, {"rsi": np.array([50.0])}, {}, utc_now)
            loaded = read_component(root, identity)

        self.assertEqual("Asia/Ho_Chi_Minh", getattr(loaded.completed_at.tzinfo, "zone", None))
        self.assertEqual(8, loaded.completed_at.hour)

    def test_corrupt_or_identity_mismatched_files_are_safe_cache_misses(self) -> None:
        identity = self._identity()
        mismatch = self._identity(calendar_fingerprint="c" * 64)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_component(root, identity, {"rsi": np.array([50.0])}, {}, self._now())
            self.assertIsNone(safe_read_component(root, mismatch))
            manifest = root / "v2" / "cache" / "primitives" / identity.key[:2] / f"{identity.key}.json"
            manifest.write_text("{", encoding="utf-8")
            self.assertIsNone(safe_read_component(root, identity))

    def test_wrong_json_top_level_is_a_safe_cache_miss(self) -> None:
        identity = self._identity()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_component(root, identity, {"rsi": np.array([50.0])}, {}, self._now())
            manifest = root / "v2" / "cache" / "primitives" / identity.key[:2] / f"{identity.key}.json"
            manifest.write_text("[]", encoding="utf-8")

            self.assertIsNone(safe_read_component(root, identity))

    def test_second_writer_cannot_overwrite_different_deterministic_component(self) -> None:
        identity = self._identity()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_component(root, identity, {"rsi": np.array([50.0])}, {}, self._now())
            result = try_write_component(root, identity, {"rsi": np.array([51.0])}, {}, self._now())
            retained = read_component(root, identity)

        self.assertEqual("nondeterministic_build", result.state)
        self.assertEqual([50.0], retained.arrays["rsi"].tolist())

    def test_cache_key_and_paths_reject_escape_attempts_and_lock_contention_is_a_safe_miss(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self._identity(source_fingerprint="../escape")

        identity = self._identity()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lease = acquire_build_lease(root, identity)
            assert lease is not None
            try:
                result = try_write_component(root, identity, {"rsi": np.array([50.0])}, {}, self._now())
            finally:
                lease.release()

        self.assertEqual("uncached_locked", result.state)


if __name__ == "__main__":
    unittest.main()
