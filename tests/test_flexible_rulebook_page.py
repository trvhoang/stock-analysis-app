"""Standalone Flexible Rulebook page tests."""

from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from flexible_rulebook.contracts import (
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
    canonical_json,
    rulebook_id,
)
from flexible_rulebook.features import CacheOffer, FeaturePreflight, feature_snapshot_for_history
from flexible_rulebook.group_adapter import FrozenGroup
from flexible_rulebook.history import HistorySnapshot

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - host-only optional Streamlit runtime
    AppTest = None


@unittest.skipIf(AppTest is None, "Streamlit AppTest runtime is unavailable")
class FlexibleRulebookPageTests(unittest.TestCase):
    @staticmethod
    def _snapshot(ticker: str, fingerprint: str) -> HistorySnapshot:
        start = date(2026, 1, 2)
        dates = [start + timedelta(days=index) for index in range(40)]
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": [10_000 + index for index in range(40)],
                "high": [10_100 + index for index in range(40)],
                "low": [9_900 + index for index in range(40)],
                "close": [10_050 + index for index in range(40)],
                "volume": [100 + index for index in range(40)],
            }
        )
        return HistorySnapshot(
            ticker,
            frame,
            fingerprint,
            "eligible",
            dates[0],
            dates[-1],
            dates[0],
            dates[-1],
            fingerprint,
        )

    def test_discover_anchor_summary_shows_each_policy_benchmark_as_of(self) -> None:
        """The page exposes anchor dates so the active scope is operationally auditable."""

        from types import SimpleNamespace

        from pages.flexible_rulebook import _policy_anchor_summary

        policy = SimpleNamespace(
            source_anchors=(
                ("VCB", canonical_json({"requested_as_of": "2026-08-28"})),
                ("FPT", canonical_json({"requested_as_of": "2026-08-27"})),
            )
        )

        self.assertEqual(
            _policy_anchor_summary(policy),
            "VCB: 2026-08-28; FPT: 2026-08-27",
        )

    def test_single_ticker_qualification_group_keeps_its_deterministic_identity(self) -> None:
        """Discover UI cleanup cannot remove the UUID dependency of Qualification."""

        from pages.flexible_rulebook import _single_ticker_group

        group = _single_ticker_group("FPT")

        self.assertEqual(group.members, ("FPT",))
        self.assertTrue(group.group_id)

    def test_page_uses_one_radio_workspace_and_exposes_the_four_safe_areas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (None, 'missing'), rerun_fn=lambda: None)\n"
            ).run()

        self.assertEqual(app.exception, [])
        self.assertEqual(len(app.radio), 1)
        self.assertEqual(
            app.radio[0].options,
            ["Discover", "Rulebook Library", "Cross-ticker Qualification", "Current Group BUY Scan"],
        )
        self.assertEqual(len(app.tabs), 0)
        self.assertTrue(any("Exploratory — gross" in item.value for item in app.markdown))

    def test_discover_shows_the_safe_policy_and_cannot_start_with_zero_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (None, 'missing'), rerun_fn=lambda: None)\n"
            ).run()

        self.assertEqual(app.exception, [])
        buttons = {item.label: item for item in app.button}
        self.assertIn("Start Discover", buttons)
        start = buttons["Start Discover"]
        self.assertTrue(start.disabled)
        self.assertTrue(any("Candidate space" in item.value for item in app.markdown))
        self.assertTrue(any("0 attempts" in item.value for item in app.markdown))

    def test_discover_scope_expansion_generates_metadata_for_added_tickers(self) -> None:
        """A valid additive ticker scope starts with editable audit metadata."""

        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "from types import SimpleNamespace\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=8, worker_count=1)\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Discover").run()
            next(item for item in app.text_input if item.label == "Additional tickers").set_value(
                "FPT, HPG REE"
            ).run()

        self.assertEqual(app.exception, [])
        operator = next(item for item in app.text_input if item.label == "Operator identity")
        note = next(item for item in app.text_area if item.label == "Approval note")
        benchmark = next(item for item in app.button if item.label == "Benchmark and Activate Scope")
        self.assertRegex(operator.value, r"^admin \d{2}[A-Z][a-z]{2}\d{2}$")
        self.assertEqual(
            note.value,
            "FPT, HPG and REE scope expansion for Flexible Rulebook discovery.",
        )
        self.assertFalse(benchmark.disabled)

    def test_discover_scope_expansion_preserves_manual_note_when_tickers_change(self) -> None:
        """A later ticker edit must not replace the operator's audit wording."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "from types import SimpleNamespace\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=8, worker_count=1)\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Discover").run()
            next(item for item in app.text_input if item.label == "Additional tickers").set_value("FPT").run()
            next(item for item in app.text_area if item.label == "Approval note").set_value(
                "operator-specific approval"
            ).run()
            next(item for item in app.text_input if item.label == "Additional tickers").set_value(
                "FPT HPG"
            ).run()

        self.assertEqual(app.exception, [])
        note = next(item for item in app.text_area if item.label == "Approval note")
        self.assertEqual(note.value, "operator-specific approval")

    def test_discover_scope_expansion_replaces_preexisting_blank_metadata_once(self) -> None:
        """A browser state from before defaults must not keep the button locked."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "if not st.session_state.get('test_scope_defaults_loaded'):\n"
                "    st.session_state['test_scope_defaults_loaded'] = True\n"
                "    st.session_state['flexible_scope_additional_tickers_v1'] = 'FPT'\n"
                "    st.session_state['flexible_scope_operator_v1'] = ''\n"
                "    st.session_state['flexible_scope_note_v1'] = ''\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=8, worker_count=1)\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Discover").run()

        operator = next(item for item in app.text_input if item.label == "Operator identity")
        note = next(item for item in app.text_area if item.label == "Approval note")
        benchmark = next(item for item in app.button if item.label == "Benchmark and Activate Scope")
        self.assertRegex(operator.value, r"^admin \d{2}[A-Z][a-z]{2}\d{2}$")
        self.assertEqual(note.value, "FPT scope expansion for Flexible Rulebook discovery.")
        self.assertFalse(benchmark.disabled)

    def test_discover_scope_expansion_requires_metadata_and_submits_union_with_common_as_of(self) -> None:
        """One button freezes the additive union and latest common completed bar."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from datetime import date\n"
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=8, worker_count=1)\n"
                "def common(_engine, members):\n"
                "    st.session_state['common_members'] = tuple(members)\n"
                "    return SimpleNamespace(state='ready', common_as_of=date(2026, 8, 27))\n"
                "def submit(request, **_kwargs):\n"
                "    st.session_state['scope_request'] = request\n"
                "    return request.job_id\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), common_as_of_preflight_fn=common, scope_submit_fn=submit, scope_benchmark_directory_fn=lambda: Path({str(root)!r}), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Discover").run()
            next(item for item in app.text_input if item.label == "Additional tickers").set_value("FPT, vcb").run()
            next(item for item in app.text_input if item.label == "Additional seeds").set_value("seed-b").run()
            next(item for item in app.text_input if item.label == "Operator identity").set_value("operator-1").run()
            next(item for item in app.text_area if item.label == "Approval note").set_value("approved expansion").run()
            next(item for item in app.button if item.label == "Benchmark and Activate Scope").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["common_members"], ("FPT", "VCB"))
        request = app.session_state["scope_request"]
        self.assertEqual(request.tickers, ("FPT", "VCB"))
        self.assertEqual(request.seeds, ("seed-a", "seed-b"))
        self.assertEqual(request.benchmark_as_of, date(2026, 8, 27))
        self.assertEqual(request.approved_by, "operator-1")

    def test_discover_scope_expansion_renders_durable_progress_and_safe_failure(self) -> None:
        """Refresh reads the sidecar; a failed job cannot imply activation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from flexible_rulebook.scope_expansion import ScopeExpansionStatus\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "st.session_state['flexible_scope_expansion_job_v1'] = 'fse_' + 'b' * 64\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=8, worker_count=1)\n"
                "def status(_job, _root): return ScopeExpansionStatus(job_id='fse_' + 'b' * 64, state='failed', phase='benchmark', completed_pairs=1, total_pairs=2, completed_windows=100, required_windows=100, safe_error='BENCHMARK.INELIGIBLE')\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), scope_status_fn=status, scope_benchmark_directory_fn=lambda: Path({str(root)!r}), rerun_fn=lambda: None)\n"
            ).run()
        self.assertEqual(app.exception, [])
        self.assertTrue(any("Scope expansion progress" in item.value for item in app.subheader))
        self.assertTrue(any("BENCHMARK.INELIGIBLE" in item.value for item in app.warning))

    def test_discover_scope_expansion_polls_a_running_sidecar(self) -> None:
        """An active scope job reruns promptly instead of leaving progress frozen."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "import pages.flexible_rulebook as flexible_page\n"
                "from flexible_rulebook.scope_expansion import ScopeExpansionStatus\n"
                "st.session_state['flexible_scope_expansion_job_v1'] = 'fse_' + 'b' * 64\n"
                "st.session_state['scope_refresh_count'] = 0\n"
                "def refresh(): st.session_state['scope_refresh_count'] += 1\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=8, worker_count=1)\n"
                "def status(_job, _root): return ScopeExpansionStatus(job_id='fse_' + 'b' * 64, state='running', phase='benchmark', completed_pairs=0, total_pairs=1, completed_windows=1, required_windows=100, current_ticker='VCB', current_seed='seed-a')\n"
                f"flexible_page.render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), scope_status_fn=status, scope_benchmark_directory_fn=lambda: Path({str(root)!r}), scope_refresh_fn=refresh, scope_rerun_fn=lambda: None, rerun_fn=lambda: None)\n"
            ).run(timeout=5)

        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["scope_refresh_count"], 1)
        self.assertTrue(any("Progress updates every 3 seconds" in item.value for item in app.caption))


    def test_main_registers_only_the_standalone_flexible_rulebook_route(self) -> None:
        workspace = Path(__file__).resolve().parents[1]
        main_path = workspace / "main.py"
        if not main_path.is_file():
            main_path = workspace / "app" / "main.py"
        main_source = main_path.read_text(encoding="utf-8")

        self.assertIn("from pages.flexible_rulebook import render_flexible_rulebook_page", main_source)
        self.assertIn('"Flexible Rulebook"', main_source)
        self.assertIn("render_flexible_rulebook_page(engine)", main_source)

    def test_library_empty_state_explains_missing_flexible_artifacts_and_safe_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Rulebook Library").run()

        self.assertEqual(app.exception, [])
        visible = "\n".join(item.value for item in (*app.info, *app.warning, *app.caption))
        self.assertIn("No Flexible Rulebook definitions or signal-set evidence found", visible)
        self.assertIn("/tmp", visible)
        self.assertIn("Discover is paused", visible)
        self.assertIn("Legacy V3 artifacts are not used", visible)

    def test_current_scan_copy_uses_next_session_model_not_v3_can_buy_wording(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Current Group BUY Scan").run()

        self.assertEqual(app.exception, [])
        visible = "\n".join(item.value for item in (*app.markdown, *app.info, *app.caption))
        self.assertIn("BUY setup — next-session open model", visible)
        self.assertNotIn("can BUY", visible)

    def test_current_scan_request_freezes_all_preflight_sources_and_explicit_cache_choice(self) -> None:
        from pages.flexible_rulebook import build_current_scan_request

        snapshots = (self._snapshot("FPT", "a" * 64), self._snapshot("VCB", "b" * 64))
        request = build_current_scan_request(snapshots, cache_choice="rebuild")

        self.assertEqual(request.operation, "current_scan")
        self.assertEqual(request.frozen_members, ("FPT", "VCB"))
        self.assertEqual(
            tuple(item.raw_history_fingerprint for item in request.source_snapshots),
            ("a" * 64, "b" * 64),
        )
        self.assertEqual(request.cache_choice, "rebuild")

    def test_ready_current_preflight_runs_only_the_frozen_group_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from datetime import date, timedelta\n"
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "import pandas as pd\n"
                "from flexible_rulebook.history import HistorySnapshot\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "dates = [date(2026, 1, 2) + timedelta(days=index) for index in range(40)]\n"
                "frame = pd.DataFrame({'date': dates, 'open': [10000 + index for index in range(40)], 'high': [10100 + index for index in range(40)], 'low': [9900 + index for index in range(40)], 'close': [10050 + index for index in range(40)], 'volume': [100 + index for index in range(40)]})\n"
                "snapshot = HistorySnapshot('FPT', frame, 'a' * 64, 'eligible', dates[0], dates[-1], dates[0], dates[-1], 'a' * 64)\n"
                "def group_snapshot(_name): return SimpleNamespace(members=('FPT',))\n"
                "def preflight(_engine, _members): return SimpleNamespace(state='ready', common_as_of=snapshot.as_of_date, snapshots=(snapshot,), lagging_tickers=())\n"
                "def cache_preflight(_engine, _preflight, _root, *, now): return SimpleNamespace(state='ready', feature_preflights={})\n"
                "def scan(_engine, request, _root):\n"
                "    import streamlit as st\n"
                "    st.session_state['current_request'] = (request.operation, request.frozen_members, request.cache_choice)\n"
                "    return SimpleNamespace(state='completed', items=(SimpleNamespace(ticker='FPT', state='current_setup_found'),))\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), group_snapshot_fn=group_snapshot, common_as_of_preflight_fn=preflight, current_cache_preflight_fn=cache_preflight, scan_current_setup_fn=scan, rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Current Group BUY Scan").run()
            next(item for item in app.text_input if item.label == "Named Group").set_value("BANK").run()
            next(item for item in app.button if item.label == "Preflight Current Group").click().run()
            next(item for item in app.button if item.label == "Run Current Group BUY Scan").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["current_request"], ("current_scan", ("FPT",), "rebuild"))
        visible = "\n".join(item.value for item in (*app.markdown, *app.success, *app.info))
        self.assertIn("FPT: BUY setup — next-session open model", visible)

    def test_qualification_request_freezes_preflight_members_rulebooks_and_plans(self) -> None:
        from pages.flexible_rulebook import build_qualification_request

        snapshot = self._snapshot("FPT", "a" * 64)
        contract = FeatureBuildContract()
        profile = FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),))
        preflight = FeaturePreflight(
            snapshot,
            contract,
            FeaturePlan(feature_snapshot_for_history(snapshot), contract, profile),
            CacheOffer((), (), ("rsi-9",)),
        )
        group = FrozenGroup(
            "BANK",
            "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0",
            ("FPT",),
            "2026-08-27T09:00:00+07:00",
        )
        request = build_qualification_request(
            group,
            ("frb_" + "a" * 64,),
            {preflight.key: preflight},
        )

        self.assertEqual(request.operation, "qualify")
        self.assertEqual(request.frozen_members, ("FPT",))
        self.assertEqual(request.rulebook_ids, ("frb_" + "a" * 64,))
        self.assertEqual(request.feature_plan_hashes, (preflight.feature_plan.feature_plan_hash,))

    def test_qualification_request_preserves_group_order_not_preflight_mapping_order(self) -> None:
        from pages.flexible_rulebook import build_qualification_request

        contract = FeatureBuildContract()
        profile = FeatureProfile((PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),)),))
        fpt = self._snapshot("FPT", "a" * 64)
        vcb = self._snapshot("VCB", "b" * 64)
        fpt_preflight = FeaturePreflight(
            fpt, contract, FeaturePlan(feature_snapshot_for_history(fpt), contract, profile), CacheOffer((), (), ()),
        )
        vcb_preflight = FeaturePreflight(
            vcb, contract, FeaturePlan(feature_snapshot_for_history(vcb), contract, profile), CacheOffer((), (), ()),
        )
        group = FrozenGroup(
            "BANK", "7d1ba3eb-6718-486b-9b86-0fb60e5f5df0", ("VCB", "FPT"), "2026-08-27T09:00:00+07:00",
        )
        request = build_qualification_request(
            group,
            ("frb_" + "a" * 64,),
            {fpt_preflight.key: fpt_preflight, vcb_preflight.key: vcb_preflight},
        )

        self.assertEqual(request.frozen_members, ("VCB", "FPT"))
        self.assertEqual(tuple(item.ticker for item in request.source_snapshots), ("VCB", "FPT"))

    def test_qualification_workspace_requires_selected_ids_target_and_preflight_before_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Cross-ticker Qualification").run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any(item.label == "Immutable rulebook IDs" for item in app.multiselect))
        self.assertTrue(any(item.label == "Qualification target" for item in app.selectbox))
        self.assertTrue(any(item.label == "Preflight Qualification" for item in app.button))

    def test_qualification_rulebook_dropdown_lists_only_available_full_ids(self) -> None:
        from flexible_rulebook.storage import write_rulebook_definition

        primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        definition = RulebookDefinition(
            (PredicateSpec("buy", primitive, (("cross", "up"), ("level", 52))),)
        )
        identifier = rulebook_id(definition)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            write_rulebook_definition(root, definition)
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Cross-ticker Qualification").run()

        self.assertEqual(app.exception, [])
        selector = next(item for item in app.multiselect if item.label == "Immutable rulebook IDs")
        self.assertEqual(selector.options, [identifier])

    def test_qualification_named_group_dropdown_uses_available_group_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), group_names_fn=lambda: ('BANK', 'TECH'), rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Cross-ticker Qualification").run()
            next(item for item in app.selectbox if item.label == "Qualification target").set_value("Named Group").run()

        self.assertEqual(app.exception, [])
        selector = next(item for item in app.selectbox if item.label == "Named Group")
        self.assertEqual(selector.options, ["—", "BANK", "TECH"])

    def test_discover_gate_explains_how_to_continue_without_authorizing_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (None, 'missing'), rerun_fn=lambda: None)\n"
            ).run()

        self.assertEqual(app.exception, [])
        visible = "\n".join(item.value for item in (*app.info, *app.warning, *app.markdown, *app.caption))
        self.assertIn("cannot authorize a discovery cap", visible)
        self.assertIn("Rulebook Library", visible)
        self.assertIn("Cross-ticker Qualification", visible)

    def test_discover_active_policy_requires_preflight_and_explicit_cache_choice(self) -> None:
        """An active policy may enable only its preflight-backed scoped start."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "snapshot = SimpleNamespace(ticker='VCB', fingerprint='b' * 64, as_of_date='2026-08-29')\n"
                "def preflight(_engine, ticker, seed, loaded_policy, *, root, now):\n"
                "    st.session_state['discover_preflight_call'] = (ticker, seed, loaded_policy.policy_digest, root)\n"
                "    return SimpleNamespace(policy=loaded_policy, ticker=ticker, seed=seed, snapshot=snapshot, cache_offer=SimpleNamespace(reusable_keys=('rsi-9',), stale_keys=(), missing_keys=()))\n"
                "def submit(preflight, *, cache_choice, root):\n"
                "    st.session_state['discover_submit_call'] = (preflight.ticker, cache_choice, root)\n"
                "    return 'fcmp_' + 'c' * 64\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), discovery_preflight_fn=preflight, discovery_submit_fn=submit, rerun_fn=lambda: None)\n"
            ).run()
            ticker_selector = next(item for item in app.selectbox if item.label == "Source ticker")
            self.assertEqual(ticker_selector.options, ["— Select ticker —", "VCB"])
            ticker_selector.set_value("VCB").run()
            next(item for item in app.selectbox if item.label == "Seed").set_value("seed-a").run()

            start = next(item for item in app.button if item.label == "Start Discover")
            self.assertTrue(start.disabled)
            next(item for item in app.button if item.label == "Preflight Discover").click().run()

            cache = next(item for item in app.selectbox if item.label == "Indicator cache")
            self.assertEqual(cache.options, ["— Select cache treatment —", "reuse", "rebuild"])
            self.assertTrue(next(item for item in app.button if item.label == "Start Discover").disabled)
            cache.set_value("reuse").run()
            next(item for item in app.button if item.label == "Start Discover").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["discover_preflight_call"][:3], ("VCB", "seed-a", "a" * 64))
        self.assertEqual(app.session_state["discover_submit_call"][:2], ("VCB", "reuse"))
        self.assertEqual(app.session_state["flexible_discovery_campaign_id_v2"], "fcmp_" + "c" * 64)

    def test_discover_policy_change_invalidates_old_preflight_before_start(self) -> None:
        """A preflight from one immutable policy cannot start after pointer replacement."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "first = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "second = SimpleNamespace(policy_digest='d' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=9, worker_count=1)\n"
                "if 'discover_active_policy_test' not in st.session_state: st.session_state['discover_active_policy_test'] = first\n"
                "st.session_state['discover_second_policy_test'] = second\n"
                "snapshot = SimpleNamespace(ticker='VCB', fingerprint='b' * 64, as_of_date='2026-08-29')\n"
                "def preflight(_engine, ticker, seed, policy, *, root, now): return SimpleNamespace(policy=policy, ticker=ticker, seed=seed, snapshot=snapshot, cache_offer=SimpleNamespace(reusable_keys=(), stale_keys=('rsi-9',), missing_keys=()))\n"
                "render_flexible_rulebook_page(engine=object(), root=Path(" + repr(str(root)) + "), discover_policy_loader_fn=lambda: (st.session_state['discover_active_policy_test'], 'active'), discovery_preflight_fn=preflight, rerun_fn=lambda: None)\n"
            ).run()
            next(item for item in app.selectbox if item.label == "Source ticker").set_value("VCB").run()
            next(item for item in app.selectbox if item.label == "Seed").set_value("seed-a").run()
            next(item for item in app.button if item.label == "Preflight Discover").click().run()
            next(item for item in app.selectbox if item.label == "Indicator cache").set_value("rebuild").run()
            self.assertFalse(next(item for item in app.button if item.label == "Start Discover").disabled)
            app.session_state["discover_active_policy_test"] = app.session_state["discover_second_policy_test"]
            app.run()

        self.assertEqual(app.exception, [])
        self.assertTrue(next(item for item in app.button if item.label == "Start Discover").disabled)

    def test_discover_policy_scope_change_resets_an_old_selector_value(self) -> None:
        """A replacement policy cannot leave an out-of-scope Streamlit selection behind."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "first = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "second = SimpleNamespace(policy_digest='d' * 64, allowed_tickers=('FPT',), allowed_seeds=('seed-b',), cap_attempts=9, worker_count=1)\n"
                "if 'discover_scope_policy_test' not in st.session_state: st.session_state['discover_scope_policy_test'] = first\n"
                "st.session_state['discover_scope_second_policy_test'] = second\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (st.session_state['discover_scope_policy_test'], 'active'), rerun_fn=lambda: None)\n"
            ).run()
            next(item for item in app.selectbox if item.label == "Source ticker").set_value("VCB").run()
            next(item for item in app.selectbox if item.label == "Seed").set_value("seed-a").run()
            app.session_state["discover_scope_policy_test"] = app.session_state[
                "discover_scope_second_policy_test"
            ]
            app.run()

        self.assertEqual(app.exception, [])
        ticker = next(item for item in app.selectbox if item.label == "Source ticker")
        seed = next(item for item in app.selectbox if item.label == "Seed")
        self.assertEqual(ticker.options, ["— Select ticker —", "FPT"])
        self.assertEqual(ticker.value, "— Select ticker —")
        self.assertEqual(seed.value, "— Select seed —")

    def test_discover_selector_excludes_tickers_outside_active_policy_scope(self) -> None:
        """Only uppercase immutable policy members may reach Discover preflight."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "def reject(*_args, **_kwargs): raise AssertionError('page selector allowed an out-of-scope request')\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), discovery_preflight_fn=reject, rerun_fn=lambda: None)\n"
            ).run()
            selector = next(item for item in app.selectbox if item.label == "Source ticker")

        self.assertEqual(app.exception, [])
        self.assertEqual(selector.options, ["— Select ticker —", "VCB"])
        self.assertTrue(next(item for item in app.button if item.label == "Preflight Discover").disabled)

    def test_discover_anchor_mismatch_does_not_leave_a_startable_preflight(self) -> None:
        """A failed policy anchor proof cannot be retained as UI start authority."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "def reject(*_args, **_kwargs): raise ValueError('benchmark source anchor changed')\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), discovery_preflight_fn=reject, rerun_fn=lambda: None)\n"
            ).run()
            next(item for item in app.selectbox if item.label == "Source ticker").set_value("VCB").run()
            next(item for item in app.selectbox if item.label == "Seed").set_value("seed-a").run()
            next(item for item in app.button if item.label == "Preflight Discover").click().run()

        self.assertEqual(app.exception, [])
        self.assertTrue(next(item for item in app.button if item.label == "Start Discover").disabled)
        self.assertTrue(any("benchmark source anchor changed" in item.value for item in app.warning))

    def test_discover_cache_change_rejects_and_clears_the_stale_preflight(self) -> None:
        """A delayed Start must guide the user back to a new cache preflight."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "snapshot = SimpleNamespace(ticker='VCB', fingerprint='b' * 64, as_of_date='2026-08-29')\n"
                "def preflight(_engine, ticker, seed, loaded_policy, *, root, now): return SimpleNamespace(policy=loaded_policy, ticker=ticker, seed=seed, snapshot=snapshot, cache_offer=SimpleNamespace(reusable_keys=(), stale_keys=('rsi-9',), missing_keys=()))\n"
                "def submit(*_args, **_kwargs): raise ValueError('cache preflight changed; run Preflight Discover again')\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), discovery_preflight_fn=preflight, discovery_submit_fn=submit, rerun_fn=lambda: None)\n"
            ).run()
            next(item for item in app.selectbox if item.label == "Source ticker").set_value("VCB").run()
            next(item for item in app.selectbox if item.label == "Seed").set_value("seed-a").run()
            next(item for item in app.button if item.label == "Preflight Discover").click().run()
            next(item for item in app.selectbox if item.label == "Indicator cache").set_value("rebuild").run()
            next(item for item in app.button if item.label == "Start Discover").click().run()
            app.run()

        self.assertEqual(app.exception, [])
        self.assertNotIn("flexible_discovery_preflight_v2", app.session_state)
        self.assertTrue(next(item for item in app.button if item.label == "Start Discover").disabled)

    def test_discover_resume_uses_the_persisted_campaign_even_after_pointer_changes(self) -> None:
        """Resuming an old immutable campaign must not depend on the current pointer digest."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "current = SimpleNamespace(policy_digest='d' * 64, allowed_tickers=('FPT',), allowed_seeds=('other-seed',), cap_attempts=9, worker_count=1)\n"
                "old_request = SimpleNamespace(activation_policy_digest='a' * 64, frontier_assignment=None, per_ticker_budget=7)\n"
                "def reader(campaign_id, _root): return SimpleNamespace(campaign_id=campaign_id, state='cancelled', request=old_request, next_slot=None, chain_attempted_count=0, uncommitted_slot=None, safe_error_code=None)\n"
                "def resume(campaign_id, *, root): st.session_state['resumed_campaign'] = (campaign_id, root); return campaign_id\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (current, 'active'), campaign_reader_fn=reader, resume_discovery_fn=resume, rerun_fn=lambda: None)\n"
            ).run()
            app.session_state["flexible_discovery_campaign_id_v2"] = "fcmp_" + "c" * 64
            app.run()
            next(item for item in app.button if item.label == "Resume Discover").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["resumed_campaign"][0], "fcmp_" + "c" * 64)

    def test_discover_continue_is_hidden_for_a_partial_terminal_window(self) -> None:
        """The UI must not offer an activated continuation shorter than the measured cap."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "request = SimpleNamespace(activation_policy_digest='a' * 64, frontier_assignment=SimpleNamespace(strata=(SimpleNamespace(size=20),)), per_ticker_budget=7)\n"
                "def reader(campaign_id, _root): return SimpleNamespace(campaign_id=campaign_id, state='completed', request=request, next_slot=14, chain_attempted_count=14, uncommitted_slot=None, safe_error_code=None)\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), campaign_reader_fn=reader, rerun_fn=lambda: None)\n"
            ).run()
            app.session_state["flexible_discovery_campaign_id_v2"] = "fcmp_" + "c" * 64
            app.run()

        self.assertEqual(app.exception, [])
        self.assertFalse(any(item.label == "Continue Discover" for item in app.button))

    def test_discover_running_campaign_exposes_refresh_and_cancel_only(self) -> None:
        """A running policy-bound campaign has no illegal resume or continuation action."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "request = SimpleNamespace(activation_policy_digest='a' * 64, frontier_assignment=SimpleNamespace(start_slot=0, attempt_count=7, strata=(SimpleNamespace(size=20),)), per_ticker_budget=7)\n"
                "def reader(campaign_id, _root): return SimpleNamespace(campaign_id=campaign_id, state='running', request=request, next_slot=0, chain_attempted_count=0, uncommitted_slot=None, safe_error_code=None)\n"
                "def cancel(campaign_id, root): st.session_state['cancelled_campaign'] = (campaign_id, root)\n"
                "def refresh(): st.session_state['discover_refresh_count'] = st.session_state.get('discover_refresh_count', 0) + 1\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), campaign_reader_fn=reader, cancel_campaign_fn=cancel, rerun_fn=refresh)\n"
            ).run()
            app.session_state["flexible_discovery_campaign_id_v2"] = "fcmp_" + "c" * 64
            app.run()
            labels = {item.label for item in app.button}
            self.assertTrue({"Refresh Discover", "Cancel Discover"}.issubset(labels))
            self.assertFalse({"Resume Discover", "Continue Discover"} & labels)
            next(item for item in app.button if item.label == "Refresh Discover").click().run()
            next(item for item in app.button if item.label == "Cancel Discover").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["discover_refresh_count"], 2)
        self.assertEqual(app.session_state["cancelled_campaign"][0], "fcmp_" + "c" * 64)

    def test_discover_contiguous_terminal_window_can_continue(self) -> None:
        """A full remaining policy cap exposes the receipt-bound Continue action."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "import streamlit as st\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "policy = SimpleNamespace(policy_digest='a' * 64, allowed_tickers=('VCB',), allowed_seeds=('seed-a',), cap_attempts=7, worker_count=1)\n"
                "request = SimpleNamespace(activation_policy_digest='a' * 64, frontier_assignment=SimpleNamespace(start_slot=7, attempt_count=7, strata=(SimpleNamespace(size=20),)), per_ticker_budget=7)\n"
                "def reader(campaign_id, _root): return SimpleNamespace(campaign_id=campaign_id, state='completed', request=request, next_slot=13, chain_attempted_count=13, uncommitted_slot=None, safe_error_code=None)\n"
                "def continue_campaign(campaign_id, *, root): st.session_state['continued_campaign'] = (campaign_id, root); return 'fcmp_' + 'd' * 64\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), discover_policy_loader_fn=lambda: (policy, 'active'), campaign_reader_fn=reader, continue_discovery_fn=continue_campaign, rerun_fn=lambda: None)\n"
            ).run()
            app.session_state["flexible_discovery_campaign_id_v2"] = "fcmp_" + "c" * 64
            app.run()
            next(item for item in app.button if item.label == "Continue Discover").click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual(app.session_state["continued_campaign"][0], "fcmp_" + "c" * 64)
        self.assertEqual(app.session_state["flexible_discovery_campaign_id_v2"], "fcmp_" + "d" * 64)

    def test_qualification_input_change_invalidates_the_old_preflight(self) -> None:
        primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        identifier = rulebook_id(
            RulebookDefinition((PredicateSpec("buy", primitive, (("cross", "up"), ("level", 52))),))
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from datetime import date, timedelta\n"
                "from pathlib import Path\n"
                "import pandas as pd\n"
                "from flexible_rulebook.contracts import FeatureBuildContract, FeaturePlan, FeatureProfile, PredicateSpec, PrimitiveSpec, RulebookDefinition, rulebook_id\n"
                "from flexible_rulebook.features import CacheOffer, FeaturePreflight, feature_snapshot_for_history\n"
                "from flexible_rulebook.history import HistorySnapshot\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "primitive = PrimitiveSpec('rsi', 'rsi-wilder-v1', (('period', 9),))\n"
                "definition = RulebookDefinition((PredicateSpec('buy', primitive, (('cross', 'up'), ('level', 52))),))\n"
                "identifier = rulebook_id(definition)\n"
                "def snapshot(ticker):\n"
                "    dates = [date(2026, 1, 2) + timedelta(days=index) for index in range(40)]\n"
                "    frame = pd.DataFrame({'date': dates, 'open': [10000 + index for index in range(40)], 'high': [10100 + index for index in range(40)], 'low': [9900 + index for index in range(40)], 'close': [10050 + index for index in range(40)], 'volume': [100 + index for index in range(40)]})\n"
                "    return HistorySnapshot(ticker, frame, 'a' * 64 if ticker == 'FPT' else 'b' * 64, 'eligible', dates[0], dates[-1], dates[0], dates[-1], 'a' * 64 if ticker == 'FPT' else 'b' * 64)\n"
                "def preflight(_engine, group, definitions, _root, _now):\n"
                "    item = snapshot(group.members[0]); contract = FeatureBuildContract(); profile = FeatureProfile((definitions[0].buy_predicates[0].primitive,)); result = FeaturePreflight(item, contract, FeaturePlan(feature_snapshot_for_history(item), contract, profile), CacheOffer((), (), ('rsi',))); return {result.key: result}\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), rulebook_loader_fn=lambda _root: (definition,), qualification_preflight_fn=preflight, rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Cross-ticker Qualification").run()
            app.multiselect[0].set_value([identifier]).run()
            next(item for item in app.text_input if item.label == "Ticker").set_value("FPT").run()
            next(item for item in app.button if item.label == "Preflight Qualification").click().run()
            next(item for item in app.text_input if item.label == "Ticker").set_value("VCB").run()

        self.assertEqual(app.exception, [])
        self.assertFalse(any(item.label == "Run Cross-ticker Qualification" for item in app.button))

    def test_library_filters_rows_in_memory_without_replaying_evidence(self) -> None:
        from pages.flexible_rulebook import filter_library_rows

        rows = (
            {"Ticker": "FPT", "Rulebook ID": "frb_" + "a" * 64},
            {"Ticker": "VCB", "Rulebook ID": "frb_" + "b" * 64},
        )

        self.assertEqual(
            filter_library_rows(rows, ticker_filter="fp", rulebook_filter=""),
            (rows[0],),
        )
        self.assertEqual(
            filter_library_rows(rows, ticker_filter="", rulebook_filter="b" * 8),
            (rows[1],),
        )

    def test_library_reads_the_linked_selection_snapshot_without_cross_campaign_guessing(self) -> None:
        from pages.flexible_rulebook import selection_state_for_document
        from flexible_rulebook.storage import write_selection_snapshot

        identifier = "frb_" + "a" * 64
        evaluation_id = "frev_" + "e" * 64
        campaign_id = "fcmp_" + "d" * 64
        snapshot = {
            "searched_window_truth": "complete_assigned_window",
            "input_ledger_digest": "b" * 64,
            "input_evaluation_digest": "c" * 64,
            "selection_scope": "ticker=FPT",
            "selection_policy_revision": "timing-distinct-top3-v1",
            "pairing_algorithm_revision": "inclusive-two-pointer-v1",
            "ranked_rulebook_ids": [identifier],
            "selected_rulebook_ids": [identifier],
            "blocker_relations": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = write_selection_snapshot(root, campaign_id, snapshot)
            member_path = root / "campaigns" / campaign_id / "selections" / "members" / f"{evaluation_id}.json"
            member_path.parent.mkdir(parents=True)
            member_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "artifact_kind": "flexible_campaign_selection_member",
                        "campaign_id": campaign_id,
                        "selection_snapshot_id": path.stem,
                        "evaluation_id": evaluation_id,
                        "rulebook_id": identifier,
                        "ticker": "FPT",
                        "source_fingerprint": "f" * 64,
                        "split": {"training": {}, "test": {}},
                    }
                ),
                encoding="utf-8",
            )
            state = selection_state_for_document(
                root,
                {
                    "rulebook_id": identifier,
                    "evaluation_id": evaluation_id,
                    "ticker": "FPT",
                    "source_snapshot": {"raw_history_fingerprint": "f" * 64},
                    "split": {"training": {}, "test": {}},
                },
            )

        self.assertEqual(state["Training rank"], 1)
        self.assertEqual(state["Selection status"], "Top 3 selected")
        self.assertEqual(state["Duplicate blocker"], "—")

    def test_library_decodes_canonical_metric_and_split_values_for_display_only(self) -> None:
        from pages.flexible_rulebook import _display_scalar, _split_label

        self.assertEqual(_display_scalar({"$float": "65.0"}), 65.0)
        self.assertEqual(
            _split_label(
                {
                    "split": {
                        "training": {"end": {"$date": "2021-01-01"}},
                        "test": {"start": {"$date": "2021-01-04"}},
                    },
                }
            ),
            "train ≤ 2021-01-01; test ≥ 2021-01-04",
        )

    def test_library_includes_immutable_definition_before_any_ticker_evaluation(self) -> None:
        from pages.flexible_rulebook import _library_rows
        from flexible_rulebook.storage import write_rulebook_definition

        primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        definition = RulebookDefinition(
            (PredicateSpec("buy", primitive, (("cross", "up"), ("level", 52))),)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            write_rulebook_definition(root, definition)
            rows = _library_rows(root)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Rulebook ID"], rulebook_id(definition))
        self.assertEqual(rows[0]["Ticker"], "—")

    def test_current_scan_rejects_an_oversized_group_before_source_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from types import SimpleNamespace\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "members = tuple(f'T{index:02d}' for index in range(16))\n"
                "def group_snapshot(_name): return SimpleNamespace(members=members)\n"
                "def preflight(_engine, _members): raise AssertionError('source preflight must not run')\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), group_snapshot_fn=group_snapshot, common_as_of_preflight_fn=preflight, rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Current Group BUY Scan").run()
            next(item for item in app.text_input if item.label == "Named Group").set_value("BANK").run()
            next(item for item in app.button if item.label == "Preflight Current Group").click().run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any("limited to 15" in item.value for item in app.warning))
        self.assertFalse(any(item.label == "Run Current Group BUY Scan" for item in app.button))

    def test_qualification_rejects_an_oversized_group_before_component_preflight(self) -> None:
        primitive = PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", 9),))
        identifier = rulebook_id(
            RulebookDefinition((PredicateSpec("buy", primitive, (("cross", "up"), ("level", 52))),))
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from flexible_rulebook.contracts import PredicateSpec, PrimitiveSpec, RulebookDefinition\n"
                "from flexible_rulebook.group_adapter import FrozenGroup\n"
                "from pages.flexible_rulebook import render_flexible_rulebook_page\n"
                "primitive = PrimitiveSpec('rsi', 'rsi-wilder-v1', (('period', 9),))\n"
                "definition = RulebookDefinition((PredicateSpec('buy', primitive, (('cross', 'up'), ('level', 52))),))\n"
                "members = tuple(f'T{index:02d}' for index in range(16))\n"
                "def group_snapshot(_name): return FrozenGroup('BANK', '7d1ba3eb-6718-486b-9b86-0fb60e5f5df0', members, '2026-08-27T09:00:00+07:00')\n"
                "def preflight(*_args): raise AssertionError('component preflight must not run')\n"
                f"render_flexible_rulebook_page(engine=object(), root=Path({str(root)!r}), group_snapshot_fn=group_snapshot, rulebook_loader_fn=lambda _root: (definition,), qualification_preflight_fn=preflight, rerun_fn=lambda: None)\n"
            ).run()
            app.radio[0].set_value("Cross-ticker Qualification").run()
            next(item for item in app.selectbox if item.label == "Qualification target").set_value("Named Group").run()
            next(item for item in app.selectbox if item.label == "Named Group").set_value("BANK").run()
            app.multiselect[0].set_value([identifier]).run()
            next(item for item in app.button if item.label == "Preflight Qualification").click().run()

        self.assertEqual(app.exception, [])
        self.assertTrue(any("limited to 15" in item.value for item in app.warning))
        self.assertFalse(any(item.label == "Run Cross-ticker Qualification" for item in app.button))


if __name__ == "__main__":
    unittest.main()
