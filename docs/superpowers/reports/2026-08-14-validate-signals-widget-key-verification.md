# Validate Signals Duplicate Widget-Key Fix — Verification

Date: 2026-08-14

## Scope

Fix the Validate Signals failure when one request renders two tickers with the
same theme variant:

```text
DuplicateWidgetID: backtest_validate_summary_no-background-theme_Identity: Ticker
```

## Root Cause

`_render_signal_summary(ticker, theme_variant, ...)` rendered its column
checkboxes, data editor, and Create trade button with keys derived only from
`theme_variant`. `_render_validate_tab()` calls that function once per completed
ticker. Two no-theme (or two VN-Index AND) summaries therefore registered the
same Streamlit keys.

## Change

`app/pages/backtest_lab.py` now creates one summary key prefix from both ticker
and theme variant. It applies that prefix to every stateful summary control:

- summary-column checkboxes;
- summary data editor;
- Create trade button.

The change is UI state isolation only. It does not change saved signal data,
replay, positions, price conversion, database access, or backtest behavior.

## Test-First Evidence

New AppTest:
`BacktestPageTests.test_validate_two_tickers_scopes_summary_widget_keys`.

RED command:

```text
docker exec stock_app python -m unittest tests.test_backtest_page.BacktestPageTests.test_validate_two_tickers_scopes_summary_widget_keys
```

Before the production change it failed with the exact reported key:
`backtest_validate_summary_no-background-theme_Identity: Ticker`.

GREEN command: same command after the change. Result: `Ran 1 test ... OK`.
The test submits `FPT, VCB`, confirms both no-theme results rendered, and
confirms the validator received both tickers in order.

## Final Verification

```text
docker exec stock_app python -m unittest tests.test_backtest_page
Ran 48 tests ... OK

docker exec stock_app python -m unittest \
  tests.test_backtest_persistence tests.test_backtest_signal_catalog \
  tests.test_backtest_pipeline tests.test_backtest_job_runner \
  tests.test_backtest_worker tests.test_backtest_page
Ran 98 tests ... OK

docker exec stock_app python -m compileall backtest_engine pages
Exit 0

docker exec stock_app python -c "... http://127.0.0.1:3501/_stcore/health ..."
200 ok
```

The focused Backtest gate emits the expected synthetic failure traceback from
the job-runner test fixture but exits successfully with all 98 tests passing.
Streamlit dependency `SyntaxWarning` messages are pre-existing third-party
warnings and do not affect the result.

## Implementation Review

| Area | Result |
| --- | --- |
| Logic | Pass — ticker plus theme uniquely identifies each rendered summary. |
| SQL/data integrity | Not applicable — no query, persistence, or price code changed. |
| Performance | Pass — no extra work, data, or network calls. |

No new dependency or commit was created.
