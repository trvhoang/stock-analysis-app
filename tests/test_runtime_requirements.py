"""Installed runtime contract for the approved Streamlit web-runtime upgrade."""

from importlib.metadata import version
from pathlib import Path
import unittest


class RuntimeRequirementTests(unittest.TestCase):
    def test_streamlit_web_runtime_is_the_approved_compatible_set(self) -> None:
        self.assertEqual("1.62.0", version("streamlit"))
        self.assertEqual("0.141.1", version("fastapi"))
        self.assertEqual("0.52.4", version("uvicorn"))

    def test_indicator_runtime_is_the_highest_proven_compatible_set(self) -> None:
        self.assertEqual("2.2.6", version("numpy"))
        self.assertEqual("3.0.5", version("pandas"))
        self.assertEqual("0.4.71b0", version("pandas-ta"))

    def test_direct_timezone_dependency_is_declared(self) -> None:
        self.assertEqual("2025.2", version("pytz"))

    def test_entrypoint_remains_a_traditional_streamlit_script(self) -> None:
        from streamlit.web.server.app_discovery import discover_asgi_app

        repository_root = Path(__file__).resolve().parents[1]
        source_candidates = (
            repository_root / "app" / "main.py",
            repository_root / "main.py",
        )
        source_path = next(path for path in source_candidates if path.is_file())

        discovery = discover_asgi_app(source_path)

        self.assertFalse(discovery.is_asgi_app, discovery.import_string)

    def test_container_disables_streamlit_usage_statistics(self) -> None:
        process_args = Path("/proc/1/cmdline").read_bytes().split(b"\0")

        self.assertIn(b"--browser.gatherUsageStats=false", process_args)


if __name__ == "__main__":
    unittest.main()
