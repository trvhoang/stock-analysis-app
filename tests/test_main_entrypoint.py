"""Entrypoint contracts without opening a database connection or HTTP server."""

from __future__ import annotations

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import types
import unittest
import uuid


@contextmanager
def _loaded_main(selected_page: str, session_state: dict[str, object] | None = None):
    """Load the real entrypoint while replacing only its process boundaries."""
    events: list[tuple[object, ...]] = []
    engine = object()
    session = session_state if session_state is not None else {}

    streamlit = types.ModuleType("streamlit")
    streamlit.session_state = session
    streamlit.sidebar = types.SimpleNamespace(selectbox=lambda *_args, **_kwargs: selected_page)
    streamlit.set_page_config = lambda **_kwargs: events.append(("page-config",))
    streamlit.cache_resource = lambda function: function
    streamlit.markdown = lambda *_args, **_kwargs: None
    streamlit.title = lambda *_args, **_kwargs: None

    data_page_module = types.ModuleType("pages.data_preparation")
    data_page_module.get_engine_with_retry = lambda _url: engine
    data_page_module.init_db = lambda received_engine: events.append(("init-db", received_engine))
    data_page_module.data_page = lambda received_engine: events.append(("page", "Data", received_engine))

    result_page_module = types.ModuleType("pages.result_visualization")
    result_page_module.result_page = lambda received_engine: events.append(("page", "Result", received_engine))
    analyze_page_module = types.ModuleType("pages.analyze_visualization")
    analyze_page_module.analyze_page = lambda received_engine: events.append(("page", "Analyze", received_engine))
    suggestion_page_module = types.ModuleType("pages.suggestion_visualization")
    suggestion_page_module.suggestion_page = lambda received_engine: events.append(("page", "Suggestion", received_engine))
    technical_page_module = types.ModuleType("pages.technical_visualization")
    technical_page_module.technical_analysis_page = lambda received_engine: events.append(
        ("page", "Technical Analyze", received_engine)
    )
    backtest_page_module = types.ModuleType("pages.backtest_lab")
    backtest_page_module.render_backtest_page = lambda **kwargs: events.append(
        ("page", "Backtest", kwargs["engine"], kwargs["engine_factory"])
    )
    flexible_page_module = types.ModuleType("pages.flexible_rulebook")
    flexible_page_module.render_flexible_rulebook_page = lambda received_engine: events.append(
        ("page", "Flexible Rulebook", received_engine)
    )

    class FakeFastAPI:
        def __init__(self, **_kwargs):
            self.state = types.SimpleNamespace()
            self.routers: list[tuple[object, str]] = []

        def include_router(self, router, prefix: str) -> None:
            self.routers.append((router, prefix))

    class FakeThread:
        def __init__(self, *, target, daemon: bool) -> None:
            self.target = target
            self.daemon = daemon

        def start(self) -> None:
            events.append(("server-start", self.daemon))
            self.target()

    router = object()
    fake_modules = {
        "streamlit": streamlit,
        "dotenv": types.ModuleType("dotenv"),
        "threading": types.ModuleType("threading"),
        "uvicorn": types.ModuleType("uvicorn"),
        "fastapi": types.ModuleType("fastapi"),
        "pages": types.ModuleType("pages"),
        "pages.data_preparation": data_page_module,
        "pages.result_visualization": result_page_module,
        "pages.analyze_visualization": analyze_page_module,
        "pages.suggestion_visualization": suggestion_page_module,
        "pages.technical_visualization": technical_page_module,
        "pages.backtest_lab": backtest_page_module,
        "pages.flexible_rulebook": flexible_page_module,
        "backtest_engine": types.ModuleType("backtest_engine"),
        "backtest_engine.pipeline": types.ModuleType("backtest_engine.pipeline"),
        "apis": types.ModuleType("apis"),
        "apis.routes": types.ModuleType("apis.routes"),
    }
    fake_modules["dotenv"].load_dotenv = lambda: events.append(("dotenv",))
    fake_modules["threading"].Thread = FakeThread
    fake_modules["uvicorn"].run = lambda app, **kwargs: events.append(("server-run", app, kwargs))
    fake_modules["fastapi"].FastAPI = FakeFastAPI
    fake_modules["backtest_engine.pipeline"].run_backtest_batch_from_env = object()
    fake_modules["apis.routes"].router = router
    fake_modules["pages"].__path__ = []
    fake_modules["backtest_engine"].__path__ = []
    fake_modules["apis"].__path__ = []

    saved_modules = {name: sys.modules.get(name) for name in fake_modules}
    sys.modules.update(fake_modules)
    module_name = f"_main_entrypoint_test_{uuid.uuid4().hex}"
    try:
        repository_root = Path(__file__).parents[1]
        source_candidates = (repository_root / "app" / "main.py", repository_root / "main.py")
        source_path = next((path for path in source_candidates if path.is_file()), None)
        assert source_path is not None
        spec = importlib.util.spec_from_file_location(module_name, source_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        yield module, events, engine, session, router
    finally:
        sys.modules.pop(module_name, None)
        for name, original in saved_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class MainEntrypointTests(unittest.TestCase):
    def test_bootstrap_configures_api_initializes_database_and_starts_daemon_server(self) -> None:
        with _loaded_main("Data") as (main_module, events, engine, _session, router):
            self.assertIs(engine, main_module.engine)
            self.assertIs(engine, main_module.api_app.state.engine)
            self.assertEqual([(router, "/api")], main_module.api_app.routers)
            self.assertIn(("init-db", engine), events)
            self.assertIn(("server-start", True), events)
            self.assertTrue(any(event[0] == "server-run" for event in events))

    def test_main_dispatches_each_supported_page_with_the_shared_engine(self) -> None:
        for page_name in ("Data", "Result", "Analyze", "Suggestion", "Technical Analyze", "Backtest", "Flexible Rulebook"):
            with self.subTest(page=page_name), _loaded_main(page_name) as (main_module, events, engine, _session, _router):
                main_module.main()
                routed_pages = [event for event in events if event[0] == "page"]
                self.assertEqual(page_name, routed_pages[-1][1])
                self.assertIs(engine, routed_pages[-1][2])

    def test_leaving_technical_analyze_clears_stale_page_state_before_result_render(self) -> None:
        session = {"previous_page": "Technical Analyze", "technical_snapshot": "stale"}
        with _loaded_main("Result", session) as (main_module, events, engine, loaded_session, _router):
            main_module.main()

        self.assertEqual({"previous_page": "Result"}, loaded_session)
        self.assertIn(("page", "Result", engine), events)


if __name__ == "__main__":
    unittest.main()
