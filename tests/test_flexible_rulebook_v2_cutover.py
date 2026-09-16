"""Cutover contracts and read-only inventory coverage for Flexible Rulebook v2."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Docker bind-mounts host ``app`` directly at /app, while host tests run from
# the repository root. Resolve both layouts without consulting process CWD.
APP_ROOT = (
    PROJECT_ROOT / "app"
    if (PROJECT_ROOT / "app" / "pages").is_dir()
    else PROJECT_ROOT
)
FLEXIBLE_PAGE = APP_ROOT / "pages" / "flexible_rulebook.py"
BACKTEST_PAGE = APP_ROOT / "pages" / "backtest_lab.py"
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_flexible_rulebook_legacy.py"


def _literal_assignment(path: Path, name: str) -> object | None:
    """Read one module constant without importing the Streamlit application."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            try:
                return ast.literal_eval(node.value)
            except (TypeError, ValueError):
                return None
    return None


def _load_audit_module():
    """Load the standalone audit script only after its presence is asserted."""

    spec = importlib.util.spec_from_file_location("audit_flexible_rulebook_legacy", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("legacy audit script cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree_digest(root: Path) -> str:
    """Give test fixtures one stable byte-level before/after identity."""

    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


class FlexibleRulebookV2CutoverTests(unittest.TestCase):
    """Freeze the intended final public surface before replacement begins."""

    def test_final_page_has_only_three_user_authored_workspaces(self) -> None:
        self.assertEqual(
            _literal_assignment(FLEXIBLE_PAGE, "_WORKSPACES"),
            ("Rulebook Builder", "Rulebook Backtest", "Rulebook Library"),
        )

    def test_final_page_has_no_automated_discovery_runtime_reference(self) -> None:
        source = FLEXIBLE_PAGE.read_text(encoding="utf-8")
        forbidden = (
            "flexible_rulebook.activation",
            "flexible_rulebook.benchmark",
            "flexible_rulebook.campaigns",
            "flexible_rulebook.current_scan",
            "flexible_rulebook.discovery_activation",
            "flexible_rulebook.scope_expansion",
            "flexible_rulebook.search",
            "Cross-ticker Qualification",
            "Current Group BUY Scan",
        )

        self.assertEqual(
            [value for value in forbidden if value in source],
            [],
            "retired discovery dependencies remain in the active page",
        )

    def test_final_backtest_source_contract_defaults_to_standard(self) -> None:
        self.assertEqual(
            _literal_assignment(BACKTEST_PAGE, "BACKTEST_RULEBOOK_SOURCE_OPTIONS"),
            ("Standard", "Flexible"),
        )
        self.assertEqual(
            _literal_assignment(BACKTEST_PAGE, "BACKTEST_RULEBOOK_SOURCE_DEFAULT"),
            "Standard",
        )

    def test_legacy_audit_reports_inventory_without_modifying_fixture(self) -> None:
        self.assertTrue(AUDIT_SCRIPT.is_file(), "legacy audit script is not implemented")
        audit = _load_audit_module()
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            fixture_files = {
                "app/flexible_rulebook/activation.py": "from pathlib import Path\n",
                "app/pages/flexible_rulebook.py": "from flexible_rulebook.activation import load\n",
                "app/services/legacy_loader.py": (
                    '__import__("flexible_rulebook.contracts", fromlist=["RulebookDefinition"])\n'
                ),
                "app/jobs/legacy_worker.py": (
                    'subprocess.Popen([python, "-m", "flexible_rulebook.worker"])\n'
                ),
                "app/main.py": (
                    "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                ),
                "app/pages/backtest_lab.py": "source = 'flexible_rulebook'\n",
                "app/Flexible-Rulebook/signal-sets/a.json": '{"schema_version":1}\n',
                "tests/test_flexible_rulebook_activation.py": "import unittest\n",
                "tests/test_flexible_rulebook_v2_service.py": "import unittest\n",
                "tests/test_flexible_rulebook_v2_cutover.py": "import unittest\n",
                "data/flexible-benchmark/active-policy.json": '{"policy":"v1"}\n',
                "app/config.py": "POLICY = '/data/flexible-benchmark/active-policy.json'\n",
            }
            for relative, content in fixture_files.items():
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            before = _tree_digest(project)

            report = audit.collect_inventory(project)

            self.assertEqual(_tree_digest(project), before)
            self.assertEqual(report["legacy_runtime"]["module_count"], 1)
            self.assertEqual(report["legacy_tests"]["file_count"], 1)
            roots = {item["label"]: item for item in report["artifact_roots"]}
            self.assertEqual(roots["package_v1"]["kinds"], {"signal-sets": 1})
            self.assertEqual(roots["benchmark_v1"]["kinds"], {"root": 1})
            self.assertTrue(roots["package_v1"]["tree_digest"])
            self.assertIn(
                "app/pages/flexible_rulebook.py",
                report["references"]["flexible_imports"],
            )
            self.assertIn(
                "app/services/legacy_loader.py",
                report["references"]["flexible_imports"],
            )
            self.assertIn(
                "app/jobs/legacy_worker.py",
                report["references"]["subprocess_entry_points"],
            )
            self.assertIn("app/main.py", report["references"]["page_routes"])
            self.assertIn("app/config.py", report["references"]["benchmark_policy"])
            self.assertIn(
                "app/pages/backtest_lab.py",
                report["references"]["backtest_position"],
            )

    def test_package_root_exports_only_the_v2_namespace_after_cutover(self) -> None:
        import flexible_rulebook

        self.assertEqual(flexible_rulebook.__all__, ["v2"])

    def test_no_v1_runtime_or_behavior_tests_remain_after_cutover(self) -> None:
        audit = _load_audit_module()
        report = audit.collect_inventory(PROJECT_ROOT)

        self.assertEqual(report["legacy_runtime"]["module_count"], 0)
        self.assertEqual(report["legacy_tests"]["file_count"], 0)


if __name__ == "__main__":
    unittest.main()
