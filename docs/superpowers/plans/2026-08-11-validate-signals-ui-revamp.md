# Validate Signals UI Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure saved-signal validation and add manual current-position monitoring/editing without weakening position, price, or long-only contracts.

**Architecture:** `position_store.py` gains backward-compatible optional quantity and atomic field updates. A small `position_overview.py` boundary loads all local positions, fetches latest OPEN-ticker closes in one parameterized query, and derives display-ready P&L. `backtest_lab.py` composes these contracts into redesigned Validate Signals and Current Positions tabs.

**Tech Stack:** Python 3.12, Streamlit, pandas, SQLAlchemy, PostgreSQL, unittest.

## Global Constraints

- No commits, dependencies, Docker changes, unrelated SQL changes, or protected-boundary changes.
- All prices persist as raw BIGINT. Display only via `price_utils`; no SQL scaling.
- BUY/SELL remain explicit manual records; no automatic close, signal artifact mutation, job submission, or re-certification.
- Quantity is optional positive whole shares; absent quantity means per-share absolute P&L.
- Position edits overwrite current values, retain timestamps, and preserve frozen ATR/max hold. BUY-price edits recalculate only pinned SL/TP from frozen ATR.
- Latest-price loading uses `sqlalchemy.text()`, `engine.raw_connection()`, and `%(param)s` bindings.
- Every production change starts RED, proves GREEN, then receives implementation review.

---

### Task 1: Backward-Compatible Position Quantity and Atomic Edits

**Files:**

- Modify: `app/backtest_engine/position_store.py`
- Modify: `tests/test_backtest_position_store.py`

**Interfaces:**

- Produces `open_position(..., quantity: object = None)`.
- Produces `update_position(ticker, theme_variant, metric, position_id, updates, positions_dir)`.
- `updates` permits only `actual_buy_price`, `actual_sell_price`, and `quantity`.

- [x] Write failing tests for legacy history loading with `quantity is None`, opening with/without positive integer quantity, rejecting zero/fractional quantity, clearing quantity, and rejecting SELL-price edits on OPEN records.
- [x] Run `tests.test_backtest_position_store` and record expected RED failure.
- [x] Write failing tests proving an edit preserves `opened_at`, `closed_at`, BUY/SELL dates, status, frozen ATR, and max hold; changing BUY price must recompute SL/TP from frozen ATR while a quantity-only edit leaves risk intact.
- [x] Implement validation/defaulting for optional quantity and atomic `update_position`. Reuse existing history validation/write path. Recalculate only SL/TP after a valid BUY-price update.
- [x] Run `tests.test_backtest_position_store` GREEN.

### Task 2: Position Overview Read Model and One-Query Latest Prices

**Files:**

- Create: `app/backtest_engine/position_overview.py`
- Create: `tests/test_backtest_position_overview.py`

**Interfaces:**

- Produces `load_all_positions(positions_dir) -> (records, errors)`.
- Produces `load_latest_close_prices(tickers, engine) -> dict[str, dict[str, object]]`.
- Produces `summarize_positions(records, latest_prices) -> list[dict[str, object]]`.

- [x] Write failing tests for reading every ticker/theme/metric history, ignoring absent histories, isolating malformed files, and sorting rows by oldest `opened_at`.
- [x] Write failing tests for one bound latest-close query over unique OPEN tickers; assert no query for an empty ticker set and no per-row query loop.
- [x] Write failing P&L tests for OPEN latest-close reference, CLOSED SELL reference, per-share/quantity absolute P&L, percentage P&L, missing latest price, and `-` display source values for OPEN close fields.
- [x] Implement the narrow overview module. Use one `DISTINCT ON (ticker)` bounded query with `ticker = ANY(%(tickers)s)`; keep raw BIGINT values.
- [x] Run `tests.test_backtest_position_overview` and `tests.test_backtest_position_store` GREEN.

### Task 3: Validate Signals Hierarchy, Progress, and Individual Decisions

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- `render_backtest_page` continues existing injected callbacks and gains only optional injected overview/update callbacks needed for page tests.
- Validate result remains `validate_saved_signals` output; it is never written.

- [x] Write failing AppTests for a progress object created during validation and cleared on both success and `ValueError`; persisted result still renders on success.
- [x] Write failing AppTests for No theme before VN-Index AND, a collapsed summary per variant, default summary columns, hidden-column picker, simultaneous collapsed-by-default detail expanders, and no batch multiselect.
- [x] Write failing AppTests for one BUY form per eligible metric, one Close position form per SELL-eligible metric, optional BUY quantity persistence, and no automatic position close.
- [x] Implement the smallest page helpers: build summary rows from existing replay data, use session-only column visibility, replace batch BUY handling with one form per metric, label manual SELL submit as `Close position`, and clear progress in `finally`.
- [x] Run `tests.test_backtest_page`, `tests.test_backtest_early_warning`, and `tests.test_backtest_validation_advice` GREEN.

### Task 4: Current Positions Tab and Editable Records

**Files:**

- Modify: `app/pages/backtest_lab.py`
- Modify: `tests/test_backtest_page.py`

**Interfaces:**

- Third tab calls overview read model once on initial render and again only on explicit Refresh or after a successful position edit.
- Edit forms call `update_position` and invalidate cached overview state.

- [x] Write failing AppTests for the third tab, initial OPEN-only list, ticker and OPEN/CLOSED filters, oldest-first theme-neutral rows, explicit Refresh, and cached data on unrelated reruns.
- [x] Write failing AppTests for displayed raw-price-derived values, OPEN `-` SELL/closed fields, latest-price P&L, and independent edit forms.
- [x] Write failing AppTests for a BUY-price edit recalculating SL/TP through `update_position`, quantity add/change/clear, CLOSED SELL-price edit, and unchanged open/closed timestamps.
- [x] Implement Current Positions rendering and form inputs. Reuse shared price conversion for each editable actual price. Do not expose a SELL close action outside Validate Signals.
- [x] Run page, overview, store, monitor, validation-advice, and price utility modules GREEN.

### Task 5: Final Review, Live-Safe Verification, and Context

**Files:**

- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Create: `docs/superpowers/reports/2026-08-11-validate-signals-ui-revamp-verification.md`

- [x] Run the explicit package-named Backtest test gate so worker subprocess fixtures retain importable module names.
- [x] Compile `backtest_engine` and `pages/backtest_lab.py`; run scoped whitespace and protected-boundary checks.
- [x] Run a read-only live Current Positions refresh against current Docker data; do not create/edit a signal artifact, position file, database record, or commit.
- [x] Complete implementation review: BIGINT/display boundary, batched query, atomic overwrite semantics, no auto-close, and Streamlit cache invalidation.
- [x] Update FOCUS/current status/report with exact command results and stop without a commit.
