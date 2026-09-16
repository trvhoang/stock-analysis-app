# Streamlit 1.62 App-wide UX — Verification

Date: 2026-09-02

## Completed automated evidence

- Exact direct runtime: Streamlit 1.62.0, FastAPI 0.141.1, Uvicorn 0.52.4,
  NumPy 2.2.6, pandas 3.0.5, pandas-ta 0.4.71b0, and pytz 2025.2.
- `python -m pip check` returned `No broken requirements found.`
- Focused task gates passed: navigation/Technical 14 tests; Data/Result/
  Suggestion 14; Analyze/Technical 25; Backtest View Signals/removal 57 plus
  20 evidence/position regressions; Flexible Rulebook 39.
- Final affected-suite gate passed **170/170** tests.
- `python -m compileall -q main.py apis commons pages backtest_engine flexible_rulebook`
  passed in the app container.
- Streamlit health at `http://localhost:3501/_stcore/health` returned `ok`.
- A real `AppTest.from_file('/app/main.py')` had zero exceptions and its
  FastAPI `/docs` probe returned HTTP 200.
- A real read-only Analyze AppTest reached `Final Advice` with zero exceptions.
- A real read-only Technical Analyze AppTest rendered one Plotly chart with
  zero exceptions.
- The live in-memory one-year FPT export returned 250 rows with the expected
  OHLC/volume/percentage columns and filename
  `FPT_1_years_price_history.csv`; no CSV file was written.
- Local headless Chrome rendered one Technical Analyze Plotly chart with its
  `k VND` label and active `MA` selector; Clear Cache removed that output.
- Recorded running Flexible campaign
  `fcmp_0c46424e8250492a9be55abc4099732763fabb99b54162e29aa46756745e14eb`
  retained its state caption across a read-only Refresh with zero AppTest
  exceptions; default unchanged input kept Preflight Discover and Start
  Discover disabled.
- Local headless Chrome ran Technical Analyze, navigated to Backtest and
  Flexible Rulebook, and returned to Technical Analyze. The prior Technical
  output was gone; Backtest/Flexible rendered their own headings; no Streamlit
  exception appeared. The existing automated regression separately proves only
  the namespaced `tech_*` state is cleared.
- The full app source audit found no `use_container_width`,
  `st.sidebar.selectbox`, `st.session_state.clear()`, or `stSidebarNav` use.

## UX and safety contracts verified

- The seven flat routes are ordered Data, Result, Analyze, Suggestion,
  Technical Analyze, Backtest, and Flexible Rulebook. The old global
  `Stock Analysis App` title is absent.
- Leaving Technical Analyze clears only its namespaced cache/snapshot values;
  Backtest and Flexible state survives.
- Backtest confirms a selected immutable candidate tuple before invoking the
  existing deletion service. Cancel performs no removal, and a referenced
  saved position remains protected by the persistence-level guard.
- Flexible lifecycle identities, activation-policy checks, request hashes, and
  cache-choice handling are unchanged by the presentation migration.

## Environment note

Compiling container root (`compileall .`) also visits the intentionally
read-only mounted `/app/scripts` directory and fails only while writing its
bytecode. The targeted writable application compilation above is clean. The
live FastAPI listener is started by the existing Streamlit script lifecycle;
therefore the real-entrypoint AppTest is the reliable non-writing API smoke
check and returned HTTP 200.

## Visual acceptance status

Completed with a local headless Chrome/DevTools session against the running
Docker app. The valid routes `/`, `/result`, `/analyze`, `/suggestion`,
`/technical-analyze`, `/backtest`, and `/flexible-rulebook` each rendered their
expected page heading without a page-not-found or Streamlit exception overlay.

Desktop and 390-pixel narrow checks confirmed that the global app title is
absent, page-local headings have the recovered space, the top navigation is
flat (and collapses to its native narrow control), and controls/tables stay
within the page width. Backtest showed only its own Collect Signals UI; no
Flexible Discover content appeared. Flexible Rulebook showed only its own
Discover workspace. Automated UI tests cover icon tooltips, popover controls,
and dialog cancellation without a persistence write. No production job,
artifact deletion, or scope-expansion action was submitted for this gate.

## Operational checks

The live read-only analysis and export-generation paths are verified. The
complete saved-candidate removal flow is verified by dialog-cancel automation,
isolated real-format evidence, a live protected-candidate block, and one
explicitly approved live unreferenced-candidate removal.

Read-only preflight found zero schema-5 signal references among current saved
positions. Therefore no live candidate can exercise the reference block. Many
unreferenced candidates are available, but removing one would change live
evidence; this verification did not choose one arbitrarily.

An isolated temporary-root integration check copied the current BVH Swing
schema-5 artifact. It confirmed cancellation leaves the copied 15-candidate
document unchanged, confirmed removal deletes exactly one candidate, and
confirmed a temporary schema-5 saved-position reference blocks removal while
preserving its copied artifact. No live Backtest artifact or position changed.

After this check, the user added a live ACB schema-5 signal-backed position for
`ACB / midterm / midterm_rulebook_v5__joint_trend`. The production read-only
protection preflight returns that exact identity. The production removal service
was not invoked: if its guard regressed, it could delete live evidence, so that
irreversible invocation needs explicit authorization.

The user then explicitly approved that exact production guard call. It raised
the expected `SignalRemovalBlockedError`; the ACB artifact before/after
documents are identical and no removal journal exists. The user also explicitly
approved removal of `ACB / midterm / midterm_rulebook_v5__adx`: the artifact
remained schema-valid, changed from seven to six candidates, excluded that
exact rulebook ID afterward, and left no transaction journal. Fresh Backtest
test discovery passes **272/272** plus compilation.

## Post-verification fractional-ATR repair

The saved-signal New Position path treated exact Wilder ATR as if it were a
raw stored close price. TCB reproduced the error with Swing ATR
`979.5087091830576`. The repair accepts only a finite positive ATR and freezes
it with Decimal half-up rounding to one raw-price unit; all close-price checks
remain integer-only. TCB now produces frozen ATR `980`, stop `31930`, and
target `35850`. The complete Backtest test discovery passes **272/272** and
`python -m compileall -q backtest_engine pages/backtest_lab.py` passes.

## Boundary review

No SQL, BIGINT price scaling, artifact schema, job workflow, risk calculation,
or trading logic changed. No Git action occurred. `docker/Dockerfile` was
previously changed only to add Streamlit's telemetry-off command flag needed
by 1.62; its user-maintained commented pandas-ta URL remains untouched.
