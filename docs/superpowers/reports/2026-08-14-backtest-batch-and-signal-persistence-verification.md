# Backtest Batch Input and Saved-Signal Persistence Verification

## Scope

- Plain metric labels across Backtest result, Validate Signals, and saved-set
  option displays.
- Validate Signals default table order begins Ticker, Metric, Match Level, and
  Match Classification.
- View Signals popovers visibly label filters `Ticker` and `Ticker Groups`.
- Collect Signals accepts up to fifteen sequential ticker inputs; manual
  Validate Signals input remains capped at five.
- Empty certification preserves an existing current artifact and creates no
  artifact for a new ticker. Nonempty results retain atomic per-ticker/theme
  create-or-overwrite behavior.

## RED evidence

- UI/catalog gate: 4 label/order failures showed the old `Best by` text and
  source-order summary rendering.
- Expanded UI gate: 3 label/order failures plus 2 missing-label lookup errors
  showed old View Signals labels and the renderer-order defect.
- Batch-cap gate: 3 failures showed the old five-ticker configuration/parser
  limits.
- Persistence gate: 2 failures showed an empty run returning a saved path and
  batch status retaining a `None` path.

## GREEN evidence

| Check | Result |
|---|---|
| UI + signal catalog | Docker `tests.test_backtest_page tests.test_backtest_signal_catalog`: 52/52 |
| Collect 15-ticker boundary | Docker contracts/page/pipeline: 69/69 |
| Empty-result persistence | Docker pipeline/persistence: 29/29 |
| Batch-cap Job Runner regression | Docker Job Runner: 10/10 |
| Final focused Backtest gate | Docker persistence/pipeline/job-runner/worker/catalog/page: 94/94 |
| Syntax | Docker `python -m compileall backtest_engine pages`: exit 0 |
| Metric-copy audit | No `Best by` text in Backtest page or saved-signal catalog production modules |
| Whitespace | Targeted `git diff --check`: no whitespace errors |

The test output includes two pre-existing Streamlit dependency `SyntaxWarning`
messages and the expected synthetic failed-job traceback exercised by Job Runner
tests; neither represents a test failure.

## Scope review

- No SQL, database, BIGINT-price, replay, signal strategy, position,
  dependency, Docker, credential, or commit change.
- The existing batch runner remains sequential and retains its retry/preflight
  behavior.
- Existing dirty worktree files outside this feature were not changed.
