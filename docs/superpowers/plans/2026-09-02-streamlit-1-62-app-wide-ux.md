# Streamlit 1.62 and App-wide UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the app to Streamlit 1.62.0 and deliver flat top navigation plus a consistent native Streamlit UX without changing any trading, data, artifact, job, or position behavior.

**Architecture:** Keep `app/main.py` as the only application entrypoint and move only routing to Streamlit's `st.navigation`. Add a deliberately small `app/commons/ui_controls.py` for presentation-only icon, notice, and read-only table conventions; every domain page retains its own state and callbacks. The Technical page owns its namespaced session cleanup so navigation can clear only its cache/snapshots when leaving that page.

**Tech Stack:** Python 3.12, Streamlit 1.62.0, FastAPI 0.141.1, Uvicorn 0.52.4, NumPy 2.2.6, pandas 3.0.5, pandas-ta 0.4.71b0, Plotly, unittest/AppTest, Docker Compose.

## Global Constraints

- Pin exactly `streamlit==1.62.0`, `fastapi==0.141.1`, `uvicorn==0.52.4`, `numpy==2.2.6`, `pandas==3.0.5`, `pandas-ta==0.4.71b0`, and `pytz==2025.2`. The latter two are existing runtime imports made explicit in `requirements.txt`, not new application capabilities.
- Preserve all SQL, `common_queries.py`, BIGINT price scaling, `get_engine_with_retry()`, credential loading, artifacts, jobs, position records, Flexible Rulebook contracts, and trading/risk calculations.
- Retain the visible flat page order: Data, Result, Analyze, Suggestion, Technical Analyze, Backtest, Flexible Rulebook.
- Use top navigation through `st.navigation(pages, position="top")`; do not create a `pages/`-directory navigation model or page groups.
- Familiar utilities use visible Material icon labels plus precise `help` text. Primary business actions retain readable text plus Material icon.
- Use `st.popover` only for small reversible settings; destructive writes/removals require `st.dialog` confirmation and cannot happen from the compact trigger.
- Read-only tables use `width="stretch"` and `hide_index=True` unless an individual table has a recorded reason not to. Checkbox-editing tables retain deterministic source order.
- Replace every supported `use_container_width=True` invocation deliberately; never make a narrow utility control stretch merely through a bulk replacement.
- Use `pytz.timezone('Asia/Ho_Chi_Minh')` for any new datetime code. This UX plan should not need new datetime logic.
- No Git commands, commits, resets, checkouts, or branch changes. The user explicitly prohibited Git action.
- Work test-first. Run the named focused Docker test gate after every task. Do not proceed if it fails.

---

## File structure

| File | Responsibility |
| --- | --- |
| `requirements.txt` | Direct compatible web, numerical/indicator, and timezone pins. |
| `app/commons/ui_controls.py` | Presentation-only Material icon map, tooltip-required icon buttons, persistent/transient feedback, and read-only dataframe kwargs. |
| `app/main.py` | Application bootstrap, flat top navigation, stable route definitions, and safe page-transition cleanup. |
| `app/pages/data_preparation.py` | Data retrieval primary action and responsive table/action sizing only. |
| `app/pages/result_visualization.py` | Responsive read-only result tables. |
| `app/pages/suggestion_visualization.py` | Labelled primary generation action and responsive suggestion tables. |
| `app/pages/analyze_visualization.py` | Popover-based export UI, primary-action icons, responsive tables. |
| `app/pages/technical_visualization.py` | Technical session-state owner, one cache utility, Streamlit-1.62 Plotly/table calls. |
| `app/pages/backtest_lab.py` | Shared icon controls, column-filter popover, confirmation-before-removal, responsive tables. |
| `app/pages/flexible_rulebook.py` | Consistent lifecycle action hierarchy, utility icons, and responsive tables. |
| `tests/test_runtime_requirements.py` | Direct runtime-pin contract. |
| `tests/test_ui_controls.py` | Common presentation helper contract. |
| `tests/test_main_entrypoint.py` | Top navigation, routing, bootstrap, and targeted Technical cleanup. |
| Existing page tests | Render/callback regression for each converted page. |
| `FOCUS.md`, `ai-context/current-status.md` | Completion evidence and only evidenced status updates. |

---

### Task 1: Prove and apply the compatible runtime set

**Files:**

- Create: `tests/test_runtime_requirements.py`
- Modify: `requirements.txt`
- Test: `tests/test_runtime_requirements.py`

**Interfaces:**

- Consumes: the actual installed web, numerical/indicator, and timezone distributions in the Docker app container.
- Produces: a checked runtime contract consumed by every later Streamlit 1.62 task.

- [x] **Step 1: Write the failing direct-pin test**

```python
from importlib.metadata import version
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


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the test and record the expected RED failure**

Run from the repository root after the normal Docker app is available:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_runtime_requirements -v
```

Observed: FAIL because the running container had Streamlit `1.32.0` and pandas
`3.0.2`. A second RED gate against the first rebuilt image proved `pytz` was
undeclared after pandas 3 stopped supplying it transitively. The development
container intentionally mounts only `app/`, so a container test cannot read
the repository-root `requirements.txt`; the clean build proves the edited pins
were applied.

- [x] **Step 3: Apply the approved compatible direct-pin set**

Replace the three relevant requirement lines with:

```text
streamlit==1.62.0
fastapi==0.141.1
uvicorn==0.52.4
numpy==2.2.6
pandas==3.0.5
pandas-ta==0.4.71b0
pytz==2025.2
```

Do not pin Starlette, Numba, protobuf, pyarrow, or other transitive dependencies by hand. The clean resolver chooses versions compatible with all direct pins. The Dockerfile's user-maintained manual pandas-ta URL remains commented and unchanged; normal installation is owned by `requirements.txt`.

- [x] **Step 4: Run the actual clean runtime compatibility gate, then GREEN test**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml build --no-cache app
docker compose --env-file .env -f docker/docker-compose.yml up -d --force-recreate app
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m pip check
docker compose --env-file .env -f docker/docker-compose.yml exec app python -c "import streamlit, fastapi, uvicorn; print(streamlit.__version__, fastapi.__version__, uvicorn.__version__)"
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_runtime_requirements -v
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_technical_analysis tests.test_technical_analysis_indicators tests.test_technical_dimension_grouping tests.test_technical_dimension_scoring tests.test_technical_snapshot tests.test_technical_visualization_ui -v
```

Expected: build succeeds, `pip check` reports no broken requirements, all seven
direct versions match, the runtime tests pass, and the 98 focused indicator/
Technical tests pass. Stop here if any transitive conflict or startup failure
occurs; do not start widget migration on an unresolved runtime.

- [x] **Step 5: Record no Git action**

Do not stage, commit, reset, checkout, or otherwise invoke Git. Continue only after the runtime gate is green.

**Observed compatibility amendments:** Streamlit 1.62 auto-discovers a direct
top-level `FastAPI(...)` assignment as the primary ASGI app. `main.py` now
constructs the same global API object through a helper, preserving its existing
thread/port contract while keeping the dashboard in traditional Streamlit
mode. The image also passes `--browser.gatherUsageStats=false`, preventing
1.62's machine-ID write into the root-owned named Streamlit cache volume.
Focused final evidence: `pip check` clean, 106/106 runtime/entrypoint/Technical
tests, healthy Docker, Streamlit root HTTP 200, health `ok`, and real-entrypoint
AppTest FastAPI docs HTTP 200.

### Task 2: Add the small shared presentation contract

**Files:**

- Create: `app/commons/ui_controls.py`
- Create: `tests/test_ui_controls.py`
- Test: `tests/test_ui_controls.py`

**Interfaces:**

- Consumes: Streamlit 1.62's `st.button`, `st.toast`, alert functions, and dataframe `width` API.
- Produces:

  ```python
  utility_icon_button(action: str, *, help: str, key: str, disabled: bool = False) -> bool
  read_only_dataframe_kwargs(*, height: int | None = None, column_config: object | None = None) -> dict[str, object]
  show_transient_success(message: str) -> None
  show_operational_notice(level: str, title: str, message: str) -> None
  ```

- [x] **Step 1: Write the failing helper tests**

```python
from unittest.mock import Mock, patch
import unittest

from commons import ui_controls


class UiControlsTests(unittest.TestCase):
    def test_remove_icon_button_uses_material_label_content_width_and_tooltip(self) -> None:
        with patch.object(ui_controls.st, "button", return_value=True) as button:
            self.assertTrue(ui_controls.utility_icon_button(
                "remove", help="Remove selected signals (2)", key="remove-two"
            ))

        button.assert_called_once_with(
            ":material/delete:", help="Remove selected signals (2)",
            key="remove-two", disabled=False, type="tertiary", width="content",
        )

    def test_icon_button_rejects_unknown_action_or_blank_tooltip(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown utility action"):
            ui_controls.utility_icon_button("unknown", help="Known", key="x")
        with self.assertRaisesRegex(ValueError, "tooltip"):
            ui_controls.utility_icon_button("remove", help="   ", key="x")

    def test_read_only_dataframe_kwargs_are_stretch_and_index_free(self) -> None:
        self.assertEqual(
            {"width": "stretch", "hide_index": True, "height": 360},
            ui_controls.read_only_dataframe_kwargs(height=360),
        )

    def test_operational_notice_uses_titled_persistent_message(self) -> None:
        warning = Mock()
        with patch.object(ui_controls.st, "warning", warning):
            ui_controls.show_operational_notice("warning", "Data quality", "History has a gap.")

        warning.assert_called_once_with(
            "**Data quality**\n\nHistory has a gap.", icon=":material/warning:"
        )
```

- [x] **Step 2: Run the focused test and record RED**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_ui_controls -v
```

Expected: FAIL because `commons.ui_controls` does not exist.

- [x] **Step 3: Implement only presentation helpers**

Implement the following concrete contract in `app/commons/ui_controls.py`:

```python
from __future__ import annotations

from typing import Literal
import streamlit as st


_UTILITY_ICONS = {
    "remove": ":material/delete:",
    "columns": ":material/view_column:",
    "refresh": ":material/refresh:",
    "clear_cache": ":material/delete_sweep:",
    "edit": ":material/edit:",
}
_NOTICE_ICONS = {
    "info": ":material/info:",
    "success": ":material/check_circle:",
    "warning": ":material/warning:",
    "error": ":material/error:",
}


def utility_icon_button(action: str, *, help: str, key: str, disabled: bool = False) -> bool:
    if action not in _UTILITY_ICONS:
        raise ValueError("unknown utility action")
    if not isinstance(help, str) or not help.strip():
        raise ValueError("icon utility tooltip is required")
    return st.button(
        _UTILITY_ICONS[action], help=help, key=key, disabled=disabled,
        type="tertiary", width="content",
    )


def read_only_dataframe_kwargs(*, height: int | None = None, column_config: object | None = None) -> dict[str, object]:
    result: dict[str, object] = {"width": "stretch", "hide_index": True}
    if height is not None:
        result["height"] = height
    if column_config is not None:
        result["column_config"] = column_config
    return result


def show_transient_success(message: str) -> None:
    st.toast(message, icon=_NOTICE_ICONS["success"])


def show_operational_notice(level: Literal["info", "success", "warning", "error"], title: str, message: str) -> None:
    if level not in _NOTICE_ICONS:
        raise ValueError("unknown notice level")
    getattr(st, level)(f"**{title}**\n\n{message}", icon=_NOTICE_ICONS[level])
```

Do not add a generic dialog wrapper, global CSS, page callbacks, artifact access, or domain-specific message copy to this module.

- [x] **Step 4: Run the GREEN helper gate**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_ui_controls -v
```

Expected: PASS. Also add a test that `show_transient_success` calls `st.toast` with the success Material icon.

- [x] **Step 5: Self-review the boundary**

Confirm the new module imports only Streamlit and typing, has no database/filesystem/job dependencies, has no session-state writes, and uses a nonempty visible Material label for every icon button. Do not invoke Git.

### Task 3: Replace global sidebar navigation with safe flat top navigation

**Files:**

- Modify: `app/main.py`
- Modify: `app/pages/technical_visualization.py`
- Modify: `tests/test_main_entrypoint.py`
- Modify: `tests/test_technical_visualization_ui.py`
- Test: `tests/test_main_entrypoint.py`, `tests/test_technical_visualization_ui.py`

**Interfaces:**

- Consumes: initialized global `engine`, existing seven page-render functions, and `clear_technical_session_state`.
- Produces:

  ```python
  clear_technical_session_state(state: MutableMapping[str, object]) -> None
  build_navigation_pages(engine: object) -> list[object]
  ```

- [x] **Step 1: Write failing navigation and cleanup tests**

Replace the fake `st.sidebar.selectbox` in `tests/test_main_entrypoint.py` with fake `st.Page` and `st.navigation` objects. Assert all of the following:

```python
expected = [
    ("Data", ":material/database:", "data"),
    ("Result", ":material/leaderboard:", "result"),
    ("Analyze", ":material/query_stats:", "analyze"),
    ("Suggestion", ":material/lightbulb:", "suggestion"),
    ("Technical Analyze", ":material/candlestick_chart:", "technical-analyze"),
    ("Backtest", ":material/science:", "backtest"),
    ("Flexible Rulebook", ":material/tune:", "flexible-rulebook"),
]
self.assertEqual(expected, fake_streamlit.created_pages)
self.assertEqual("top", fake_streamlit.navigation_position)
```

Add a session-transition test with:

```python
session = {
    "previous_page": "Technical Analyze",
    "tech_df": object(),
    "tech_ticker": "FPT",
    "tech_snapshot": object(),
    "tech_snapshot_params": ("FPT", "Day", 100, 5, 10),
    "tech_raw_history": {"FPT_Day_100": object()},
    "backtest_job": "must-survive",
    "flexible_campaign": "must-survive",
}
```

After selecting Result, assert every `tech_*` item is absent, `previous_page`
is `Result`, and the Backtest/Flexible values remain. In the technical UI test,
assert raw-history caching uses `tech_raw_history` rather than bare dynamic
session keys such as `FPT_Day_100`.

- [x] **Step 2: Run RED**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_main_entrypoint tests.test_technical_visualization_ui -v
```

Expected: FAIL because the current entrypoint creates a sidebar selectbox and calls global `st.session_state.clear()`.

- [x] **Step 3: Implement namespaced Technical cache ownership**

At module level in `app/pages/technical_visualization.py`, add and use these keys:

```python
TECHNICAL_RAW_HISTORY_KEY = "tech_raw_history"
TECHNICAL_SESSION_KEYS = (
    "tech_df", "tech_ticker", "tech_snapshot", "tech_snapshot_params",
    TECHNICAL_RAW_HISTORY_KEY,
)


def clear_technical_session_state(state) -> None:
    for key in TECHNICAL_SESSION_KEYS:
        state.pop(key, None)
```

Replace the current `data_key = f"{ticker}_{timeframe}_{limit}"` direct
session storage with a dictionary at `TECHNICAL_RAW_HISTORY_KEY`, keyed by
that same `data_key`. Make the in-page Clear Cache action call this same helper
with `st.session_state`.

- [x] **Step 4: Implement top navigation in the entrypoint**

Remove the legacy sidebar selectbox, its dispatch `if/elif`, CSS that hides
automatic sidebar navigation, and the global `Stock Analysis App` title. Keep
`st.set_page_config(layout="wide")`, environment loading, database
initialization, and API startup. Page-local headings remain. Define no-argument
page render wrappers and build pages like this:

```python
def build_navigation_pages(engine):
    return [
        st.Page(lambda: data_page(engine), title="Data", icon=":material/database:", url_path="data", default=True),
        st.Page(lambda: result_page(engine), title="Result", icon=":material/leaderboard:", url_path="result"),
        st.Page(lambda: analyze_page(engine), title="Analyze", icon=":material/query_stats:", url_path="analyze"),
        st.Page(lambda: suggestion_page(engine), title="Suggestion", icon=":material/lightbulb:", url_path="suggestion"),
        st.Page(lambda: technical_analysis_page(engine), title="Technical Analyze", icon=":material/candlestick_chart:", url_path="technical-analyze"),
        st.Page(lambda: render_backtest_page(engine=engine, engine_factory=run_backtest_batch_from_env), title="Backtest", icon=":material/science:", url_path="backtest"),
        st.Page(lambda: render_flexible_rulebook_page(engine), title="Flexible Rulebook", icon=":material/tune:", url_path="flexible-rulebook"),
    ]


def main():
    selected_page = st.navigation(build_navigation_pages(engine), position="top")
    selected_title = selected_page.title
    if st.session_state.get("previous_page") == "Technical Analyze" and selected_title != "Technical Analyze":
        clear_technical_session_state(st.session_state)
    st.session_state["previous_page"] = selected_title
    selected_page.run()
```

Use named wrapper functions rather than lambdas if test readability or a
static-analysis rule requires it; preserve the exact titles, icons, order,
paths, and behavior above. Do not use `st.session_state.clear()` anywhere.
Add a route-ownership regression proving the Backtest route invokes only
`render_backtest_page`, never `render_flexible_rulebook_page`.

- [x] **Step 5: Run GREEN and topology checks**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_main_entrypoint tests.test_technical_visualization_ui -v
rg -n "st\.sidebar\.selectbox|st\.session_state\.clear\(|stSidebarNav" app/main.py app/pages/technical_visualization.py
```

Expected: tests PASS; the search returns no legacy global-navigation/state-clear use. The Technical page may still use `st.sidebar` for its input controls.

- [x] **Step 6: Check page state safety manually**

Verified 2026-09-02 with local headless Chrome: Technical Analyze output was
present after Analyze, then absent after Technical Analyze, Backtest, Flexible
Rulebook, and return to Technical Analyze. Backtest and Flexible both rendered
their own headings; no Streamlit exception appeared. Automated namespaced-state
regression covers preservation of unrelated page state. No Git action.

### Task 4: Migrate simple data and ranking pages to the shared visual contract

**Files:**

- Modify: `app/pages/data_preparation.py`
- Modify: `app/pages/result_visualization.py`
- Modify: `app/pages/suggestion_visualization.py`
- Modify: `tests/test_data_preparation.py`
- Modify: `tests/test_result_visualization.py`
- Modify: `tests/test_suggestion_visualization.py`
- Test: `tests/test_data_preparation.py`, `tests/test_result_visualization.py`, `tests/test_suggestion_visualization.py`

**Interfaces:**

- Consumes: `read_only_dataframe_kwargs` from `commons.ui_controls`.
- Produces: unchanged data retrieval/ranking results rendered through Streamlit 1.62 width APIs.

- [x] **Step 1: Write failing display-contract tests**

Update the existing mocked Streamlit assertions to require `width="stretch"`
and `hide_index=True` for read-only Result and Suggestion tables. Add a data
page assertion that the retrieval action is called as:

```python
st.button(
    "Get data", icon=":material/cloud_download:",
    width="stretch",
)
```

Add a Suggestion assertion for:

```python
st.button("Generate Suggestions", icon=":material/lightbulb:")
```

Do not alter assertions for the returned dataframes or ranking order.

- [x] **Step 2: Run RED**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_data_preparation tests.test_result_visualization tests.test_suggestion_visualization -v
```

Expected: FAIL on the former `use_container_width=True` and missing icon arguments.

- [x] **Step 3: Make the smallest page-only updates**

Import `read_only_dataframe_kwargs` in Result and Suggestion and replace each
read-only dataframe call with the helper expansion:

```python
st.dataframe(df_volume, **read_only_dataframe_kwargs())
```

Use the equivalent form for all four Suggestion result tables. Update the Data
primary action and Suggestion primary action exactly as tested. Preserve all
loading/progress loops, SQL, dataframe transformations, and error wording.

- [x] **Step 4: Run GREEN and source audit**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_data_preparation tests.test_result_visualization tests.test_suggestion_visualization -v
rg -n "use_container_width" app/pages/data_preparation.py app/pages/result_visualization.py app/pages/suggestion_visualization.py
```

Expected: tests PASS; the source audit has no obsolete sizing argument in these three files.

- [x] **Step 5: Manual narrow-layout check**

At a narrow browser width, confirm Data's action is readable and the Result/
Suggestion tables scroll horizontally inside their table area rather than
forcing the whole application to overflow. Do not change ranking or data rules.

### Task 5: Modernize Analyze and Technical Analyze without changing analysis

**Files:**

- Modify: `app/pages/analyze_visualization.py`
- Modify: `app/pages/technical_visualization.py`
- Modify: `tests/test_analyze_export.py`
- Modify: `tests/test_technical_visualization_ui.py`
- Test: `tests/test_analyze_export.py`, `tests/test_technical_visualization_ui.py`, `tests/test_technical_snapshot.py`

**Interfaces:**

- Consumes: `utility_icon_button`, `read_only_dataframe_kwargs`, and the Task 3 Technical state helper.
- Produces: popover-contained export inputs, one cache-clearing control, and API-compatible table/chart rendering with identical analysis output.

- [x] **Step 1: Write failing UI tests**

In `tests/test_analyze_export.py`, assert Export is a labelled secondary
popover trigger and the export form is rendered inside it:

```python
st.popover("Export", icon=":material/download:")
```

Keep tests for invalid ticker/range handling, CSV bytes, generated filename,
and download button unchanged. Add assertions that `Analyze` and `Analyze
Portfolio` retain text labels and receive `:material/query_stats:` and
`:material/account_balance:` respectively.

In the technical UI test, assert exactly one clear-cache widget key remains,
it uses the `clear_cache` helper/tooltip, all dataframes use `width="stretch"`,
and the chart call is:

```python
st.plotly_chart(fig, width="stretch")
```

- [x] **Step 2: Run RED**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_analyze_export tests.test_technical_visualization_ui tests.test_technical_snapshot -v
```

Expected: FAIL because Export currently uses a session-state-controlled expander and Technical Analyze has two Clear Cache buttons plus the old Plotly API.

- [x] **Step 3: Convert Analyze action presentation**

Replace the `EXPORT_VISIBLE_KEY` toggle and `get_export_form_container()`
presentation path with this local structure while retaining the current export
validation and generated data keys:

```python
with st.popover("Export", icon=":material/download:"):
    with st.form("analyze_export_form"):
        export_ticker = st.text_input("Export Ticker Code", value=ticker)
        export_range = st.number_input("Export Time Range", min_value=1, value=30, step=1)
        export_unit = st.selectbox("Export Time Unit", EXPORT_RANGE_UNITS)
        include_percentage_change = st.checkbox("Include Percentage Change")
        include_ohlc_volume = st.checkbox("Include OHLC Prices and Trading Volume")
        export_submitted = st.form_submit_button("Prepare CSV")
    if export_submitted:
        st.session_state[EXPORT_CSV_KEY] = None
        st.session_state[EXPORT_FILENAME_KEY] = None
        export_values, export_error = validate_export_inputs(export_ticker, export_range, export_unit)
        if export_error:
            st.error(export_error)
        else:
            history_df = fetch_export_history(
                export_values["ticker"], export_values["range_value"], export_values["range_unit"], engine,
            )
            export_df = format_export_dataframe(history_df, include_percentage_change, include_ohlc_volume)
            if export_df.empty:
                st.warning("No trading history found for the requested range.")
            else:
                st.session_state[EXPORT_CSV_KEY] = export_df.to_csv(index=False).encode("utf-8")
                st.session_state[EXPORT_FILENAME_KEY] = build_export_filename(
                    export_values["ticker"], export_values["range_value"], export_values["range_unit"],
                )
    if st.session_state[EXPORT_CSV_KEY]:
        st.download_button(
            "Download CSV", data=st.session_state[EXPORT_CSV_KEY],
            file_name=st.session_state[EXPORT_FILENAME_KEY], mime="text/csv",
            key="analyze_export_download",
        )
```

The CSV and filename session keys remain because they hold generated export
data across the form submit rerun. Remove only the now-unused visibility key
and expander helper. Add approved icons to the two Analyse actions and replace
each read-only dataframe sizing call through `read_only_dataframe_kwargs`.

- [x] **Step 4: Convert Technical presentation**

Remove `clear_cache_sidebar`. Keep a single Clear Cache utility inside the
existing sidebar input section:

```python
if utility_icon_button(
    "clear_cache", help="Clear Technical Analyze cached data",
    key="technical_clear_cache",
):
    clear_technical_session_state(st.session_state)
```

Keep Analyse as a labelled text-plus-icon action:

```python
st.button("Analyze", icon=":material/query_stats:")
```

Replace all table sizing in this module with `read_only_dataframe_kwargs()` or
the equivalent explicit `width="stretch", hide_index=True` when a column
configuration is already present. Replace the single Plotly call with
`st.plotly_chart(fig, width="stretch")`. Do not change figure traces, price
scaling, indicator calculations, cache keys other than Task 3's namespace, or
chart data.

- [x] **Step 5: Run GREEN and API-removal audit**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_analyze_export tests.test_technical_visualization_ui tests.test_technical_snapshot -v
rg -n "EXPORT_VISIBLE_KEY|get_export_form_container|clear_cache_sidebar|use_container_width" app/pages/analyze_visualization.py app/pages/technical_visualization.py
```

Expected: test suite PASS; the audit has no removed presentation symbols or obsolete sizing calls.

- [x] **Step 6: Manually verify preserved outputs**

Run one Analyze export and one Technical Analyze chart. Confirm output filename,
CSV content, k-VND display, active chart indicator, and clear-cache behavior
match before the visual update. Do not invoke Git.

Completed 2026-09-02: live in-memory FPT export produced 250 rows, expected
OHLC/volume/percentage columns, and `FPT_1_years_price_history.csv`. Local
headless Chrome rendered Technical Analyze output with one Plotly chart,
`k VND` chart label, active `MA` selector, and Clear Cache removed the output.
No Git action.

### Task 6: Standardize Backtest controls while protecting signal evidence

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`
- Modify: `tests/test_backtest_signal_removal.py`
- Test: `tests/test_backtest_page.py`, `tests/test_backtest_signal_removal.py`

**Interfaces:**

- Consumes: Task 2 `utility_icon_button` and `read_only_dataframe_kwargs`; existing `remove_saved_signal_candidates` and `SignalRemovalBlockedError`.
- Produces: a column-selection popover and a two-step, state-safe View Signals removal flow. Candidate keys and removal service signatures do not change.

- [x] **Step 1: Write failing View Signals interaction tests**

Add/adjust tests so that:

```python
utility_icon_button(
    "columns", help="Choose visible View Signals columns",
    key="backtest_view_signal_columns_v5",
)
```

opens a popover that contains the existing optional-column multiselect. The
existing `Columns` selection state key and default Evidence/Theme hiding remain
unchanged.

For removal, test this sequence:

1. Clicking the `remove` utility stores the exact rendered `SignalCandidateKey`
   tuple under `_VIEW_SIGNAL_PENDING_REMOVAL_KEY` and does **not** call
   `remove_saved_signal_candidates`.
2. Cancelling the dialog clears only that pending key and calls no removal
   function.
3. Confirming calls the existing remove function once with that stored tuple,
   preserves blocked-position behavior, clears selection after success, and
   reruns once.

Add a source/render assertion that the `st.data_editor` keeps the present row
order and receives `width="stretch"`; do not introduce a sortable editable
grid that can disconnect selection from candidate identity.

- [x] **Step 2: Run RED**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_backtest_page tests.test_backtest_signal_removal -v
```

Expected: FAIL because the View Signals remove trigger invokes removal in the
same render and the visible-column selector is always shown inline.

- [x] **Step 3: Implement safe column and removal presentation state**

Add one module constant:

```python
_VIEW_SIGNAL_PENDING_REMOVAL_KEY = "backtest_view_signal_pending_removal_v5"
```

Place the existing selected-column multiselect inside a popover triggered by
the shared `columns` utility icon. Keep its current key
`_VIEW_SIGNAL_COLUMNS_KEY`, default columns, and filter behavior.

Replace both `🗑️` calls with
`utility_icon_button("remove", help=f"Remove selected signals ({len(selected_keys)})", key="backtest_view_signal_remove_v5", disabled=not selected_keys)`.
On click, copy the already computed `selected_keys` tuple into the pending key. Render a
local dialog only while that tuple exists:

```python
from typing import Callable, Sequence


def _complete_view_signal_removal(
    pending: Sequence[SignalCandidateKey], *, signal_dir: str,
    positions_dir: str, remove_fn: Callable, rerun_fn: Callable,
) -> None:
    try:
        result = remove_fn(pending, signal_dir=signal_dir, positions_dir=positions_dir)
    except SignalRemovalBlockedError as error:
        protected = "; ".join(
            f"{item.ticker} / {item.horizon} / {item.rulebook_id}"
            for item in error.protected
        )
        st.session_state[_VIEW_SIGNAL_FEEDBACK_KEY] = {
            "level": "error", "message": f"Removal blocked by saved position reference: {protected}",
        }
    except (OSError, TypeError, ValueError) as error:
        st.session_state[_VIEW_SIGNAL_FEEDBACK_KEY] = {
            "level": "error", "message": f"Unable to remove selected signals: {error}",
        }
    else:
        st.session_state[_VIEW_SIGNAL_FEEDBACK_KEY] = {
            "level": "success", "message": f"Removed {len(result.removed)} saved signal(s).",
        }
        st.session_state[_VIEW_SIGNAL_SELECTED_KEYS_KEY] = set()
        st.session_state[_VIEW_SIGNAL_RESET_SELECTION_KEY] = True
    st.session_state.pop(_VIEW_SIGNAL_PENDING_REMOVAL_KEY, None)
    rerun_fn()


@st.dialog("Remove selected signals?")
def confirm_view_signal_removal() -> None:
    st.warning("This removes the selected candidate evidence. Referenced position evidence is protected.")
    cancel, confirm = st.columns(2)
    if cancel.button("Cancel", key="backtest_view_signal_remove_cancel_v5"):
        st.session_state.pop(_VIEW_SIGNAL_PENDING_REMOVAL_KEY, None)
        st.rerun()
    if confirm.button(
        "Remove selected signals", icon=":material/delete:", type="primary",
        key="backtest_view_signal_remove_confirm_v5",
    ):
        pending = tuple(st.session_state[_VIEW_SIGNAL_PENDING_REMOVAL_KEY])
        _complete_view_signal_removal(
            pending, signal_dir=signal_dir, positions_dir=positions_dir,
            remove_fn=remove_fn, rerun_fn=rerun_fn,
        )
```

Place the dialog inside a renderer that closes over `signal_dir`,
`positions_dir`, `remove_fn`, and `rerun_fn`; invoke it only after confirming
the pending session value is a nonempty tuple of `SignalCandidateKey`. This
must not bypass the existing persistence-level position-reference guard.

Migrate Backtest read-only `st.dataframe` and editable `st.data_editor` width
arguments to `width="stretch"`. Update the Current Positions refresh glyph to
the shared `refresh` icon with its existing tooltip/semantics. Preserve every
job, artifact, position, filter, and risk path.

- [x] **Step 4: Run GREEN and safety regression**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_backtest_page tests.test_backtest_signal_removal -v
```

Expected: PASS. Then run the existing Backtest evidence/position regression
gate:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_backtest_evidence tests.test_backtest_position_store tests.test_backtest_position_monitor -v
```

Expected: PASS with no artifact or position semantic change.

- [x] **Step 5: Manual destructive-flow check**

Open View Signals, select one unreferenced candidate, click the Material delete
icon, cancel, and confirm the row remains. Repeat and confirm removal. Finally
select a candidate referenced by a saved position and confirm the persistent
blocked message appears while the artifact remains untouched. Do not use Git.

2026-09-02 read-only preflight: current saved positions contain zero schema-5
signal references, so no live referenced candidate exists for the final block
proof. Multiple unreferenced candidates exist, but selecting one for actual
removal would alter live evidence; no arbitrary candidate was chosen.
An isolated integration check copied the current real BVH Swing schema-5
artifact to a temporary root: dialog-cancel semantics preserved the copied
document, confirmed removal deleted exactly one of 15 candidates, and a
temporary schema-5 position reference blocked removal while preserving its
copied artifact. The required live operation remains pending only because its
referenced-candidate target does not exist.

Update 2026-09-02: user added live ACB schema-5 reference
`ACB / midterm / midterm_rulebook_v5__joint_trend`. The production guard's
non-mutating `_protected_selections` preflight returns that exact key. Invoking
the production removal service remains pending explicit authorization because a
guard regression could persistently delete the referenced live candidate.

Live guard execution approved and completed 2026-09-02: the exact service
raised `SignalRemovalBlockedError` for that ACB identity; the before/after
artifact documents are identical and no removal journal exists. The remaining
unchecked portion is only confirmed deletion of a separately approved,
unreferenced live candidate.

Completed 2026-09-02 with explicit user approval: unreferenced
`ACB / midterm / midterm_rulebook_v5__adx` was removed. The schema-5 artifact
remained valid, candidate count changed from seven to six, the exact rulebook
ID is absent afterward, and no transaction journal remains. Automated dialog
cancel coverage and the isolated real-format cancel check cover the no-write
cancel path.

### Task 7: Apply the native action hierarchy to Flexible Rulebook

**Files:**

- Modify: `app/pages/flexible_rulebook.py`
- Modify: `tests/test_flexible_rulebook_page.py`
- Test: `tests/test_flexible_rulebook_page.py`

**Interfaces:**

- Consumes: `utility_icon_button`, `read_only_dataframe_kwargs`; all existing campaign, scope, qualification, and BUY-scan services.
- Produces: presentation-only action/icon changes; exact lifecycle callback signatures, campaign IDs, policies, progress, and persistence remain unchanged.

- [x] **Step 1: Write failing visual-contract AppTests**

Extend the existing page tests to assert:

- `Refresh Discover` and `Refresh Scope Expansion` use the shared refresh icon
  and retain help text which names the refreshed scope.
- `Benchmark and Activate Scope`, `Preflight Discover`, `Start Discover`,
  `Run Cross-ticker Qualification`, and `Run Current Group BUY Scan` keep
  readable text labels and gain their specified Material icons.
- `Cancel Discover`, `Resume Discover`, and `Continue Discover` keep readable
  text labels because their lifecycle effect is not a generic utility action.
- Library, rejected-evidence, qualification-offer, and BUY-scan-offer tables
  receive `width="stretch"` and `hide_index=True`.
- Existing disabled conditions, progress bars, and exact source/cache-choice
  selectors remain present.

- [x] **Step 2: Run RED**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_flexible_rulebook_page -v
```

Expected: FAIL only on the new presentation assertions; campaign/business
tests must not be rewritten to permit a changed lifecycle.

- [x] **Step 3: Apply presentation-only changes**

Import the two Task 2 helpers. Make refresh controls compact shared icon
buttons with concrete tooltips, for example:

```python
if utility_icon_button(
    "refresh", help="Refresh Discover campaign status", key="flexible_refresh_discover_v1",
):
    rerun_fn()
```

Add Material icons to the labelled lifecycle buttons:

```python
st.button("Start Discover", icon=":material/play_arrow:", disabled=not can_start)
st.button("Run Cross-ticker Qualification", icon=":material/fact_check:")
st.button("Run Current Group BUY Scan", icon=":material/manage_search:")
```

Use `read_only_dataframe_kwargs()` for each read-only table. Keep current
expander titles, sidecar polling, `st.progress` text, preflight rules,
state-transition callbacks, and safe error messages exactly as they are.

- [x] **Step 4: Run GREEN and source scope audit**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_flexible_rulebook_page -v
rg -n "use_container_width|campaign_id|activation_policy_digest|request_hash|cache_choice" app/pages/flexible_rulebook.py
```

Expected: AppTests PASS. The source review has no `use_container_width`; the
identity/policy/cache expressions remain in place and are not changed by the
UI migration.

- [x] **Step 5: Manual lifecycle safety check (no live campaign mutation)**

Verified 2026-09-02 against recorded running campaign
`fcmp_0c46424e8250492a9be55abc4099732763fabb99b54162e29aa46756745e14eb`:
the campaign/state caption persisted across Refresh with zero AppTest
exceptions. Default unchanged inputs kept both Preflight Discover and Start
Discover disabled. No job or campaign mutation was submitted; no Git action.

### Task 8: Full verification, visual gate, and documentation handoff

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-09-02-streamlit-1-62-app-wide-ux-verification.md`
- Test: all affected tests and live Docker health/API smoke.

**Interfaces:**

- Consumes: completed Tasks 1–7 and their focused evidence.
- Produces: recorded final verification only after all automated and visual acceptance checks pass.

- [x] **Step 1: Run the complete affected automated gate**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m unittest tests.test_runtime_requirements tests.test_ui_controls tests.test_main_entrypoint tests.test_data_preparation tests.test_result_visualization tests.test_suggestion_visualization tests.test_analyze_export tests.test_technical_visualization_ui tests.test_technical_snapshot tests.test_backtest_page tests.test_backtest_signal_removal tests.test_backtest_evidence tests.test_backtest_position_store tests.test_backtest_position_monitor tests.test_flexible_rulebook_page -v
```

Expected: PASS. If any test fails, return to its owning task; do not mark the
feature complete or edit status documentation.

- [x] **Step 2: Run the compatibility and startup gate**

Run:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m pip check
docker compose --env-file .env -f docker/docker-compose.yml exec app python -m compileall app
Invoke-WebRequest http://localhost:8501/_stcore/health | Select-Object -ExpandProperty Content
Invoke-WebRequest http://localhost:3500/docs | Select-Object -ExpandProperty StatusCode
rg -n "use_container_width|st\.sidebar\.selectbox|st\.session_state\.clear\(|stSidebarNav" app
```

Expected: dependency check and compilation pass; Streamlit health response is
healthy; FastAPI docs returns HTTP 200; the source audit reports no prohibited
legacy calls. If the API/docs endpoint has an existing authenticated or routing
variant, use its established non-writing health endpoint and record that exact
response instead.

- [x] **Step 3: Perform the seven-page visual acceptance gate**

At desktop width and a narrow browser width, visit every page in this order:

1. Data
2. Result
3. Analyze
4. Suggestion
5. Technical Analyze
6. Backtest
7. Flexible Rulebook

Record that top navigation is flat and ordered, every icon-only control has a
correct tooltip, primary actions retain text, tables do not force page-wide
overflow, popovers fit their content, dialog cancellation performs no write,
and no Streamlit warning/exception appears. For Backtest and Flexible, inspect
existing data/status only; do not overwrite a signal artifact or start a
production job for this gate.

- [x] **Step 4: Write verification evidence**

Create the report with exact commands, test counts, resolved runtime versions,
health/API output, pages visually checked, and any pre-existing unrelated
failure. State explicitly that no SQL/BIGINT/artifact/job/risk logic, Docker
source, or Git state was changed.

- [x] **Step 5: Update active context only after all gates pass**

Update `FOCUS.md` and `ai-context/current-status.md` with the completed task,
design/plan/report links, exact test evidence, the targeted Technical state
cleanup change, and the fact that no Git action occurred. Do not claim visual
or full-suite success without recorded evidence.

Completed 2026-09-02: active context and verification report record the full
route/operational gate, ACB guard block, explicitly approved unreferenced ACB
candidate deletion, fresh 272/272 Backtest gate, compilation, and no Git
action.

- [x] **Step 6: Final self-critique**

Check the final diff for these failure modes:

- a new or altered domain calculation, SQL string, persistence write, or job callback;
- an icon-only action without a tooltip or an empty accessible label;
- a delete/remove callback that runs before dialog confirmation;
- an editable Backtest table whose sort/order can desynchronize selection;
- a direct global session clear or duplicated Technical cache control;
- any obsolete `use_container_width` call that would break Streamlit 1.62;
- an undocumented resolved dependency conflict.

Fix every finding, rerun its focused gate and the complete affected gate, then
update the report. Do not invoke Git.

---

## Plan self-review

| Specification requirement | Plan coverage |
| --- | --- |
| Coordinated runtime upgrade and clean dependency proof | Task 1, Task 8 Step 2 |
| Flat seven-page top navigation and stable routes | Task 3 |
| No global state wipe when leaving Technical Analyze | Task 3 |
| Native icons, tooltips, popovers, dialogs, feedback, table conventions | Task 2; Tasks 4–7 |
| Preserve data/trading/artifact/job behavior | Global constraints; Tasks 3, 5, 6, 7; Task 8 review |
| Replace obsolete sizing and Plotly usage | Tasks 4–7; Task 8 source audit |
| Regression, runtime, health/API, and visual verification | Task 8 |
| No Git action | Global constraints and every task closure |

Completeness scan: no deferred steps, unspecified interfaces, or unowned
acceptance criteria remain. Type/interface consistency: later tasks consume
only the helper names and Technical cleanup contract defined in Tasks 2 and 3.
