# Live Delisted Status and Group Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude live-stale tickers from Backtest and new positions, and add a safe Backtest Group Manager.

**Architecture:** A new Backtest data-status module derives `Listed`/`Delisted` from the latest stored ticker and VN-Index sessions through one parameterized aggregate query. Pipeline, replay, Flexible Rulebook, and position flows consume this shared result. Group JSON mutations retain their existing journal and gain deletion-aware recovery; the Backtest tab renders that store plus live status.

**Tech Stack:** Python 3.12, pandas, SQLAlchemy, Streamlit 1.62, PostgreSQL, unittest, Docker Compose.

## Global Constraints

- Use `sqlalchemy.text()`, `engine.raw_connection()`, and `%(param)s` bindings for every new query.
- Never alter BIGINT price scaling, `common_queries.py`, credentials, Docker configuration, or schema-5 artifact contents.
- `Delisted` is live and automatically clears only when the ticker latest session exactly equals VN-Index latest session.
- Preserve historical artifacts and positions; do not write a regeneration marker merely for stale current data.
- No Git action or commit.

---

### Task 1: Live Listing Status Contract

**Files:**
- Create: `app/backtest_engine/listing_status.py`
- Test: `tests/test_backtest_listing_status.py`

**Interfaces:**
- Produces `ListingStatus(ticker, state, ticker_latest, vnindex_latest)` and `load_listing_statuses(tickers, engine)`.
- `state` is `listed` iff the two dates are equal; every missing ticker date or unequal date is `delisted`.
- Raises `VNIndexListingStatusUnavailable` when no VN-Index latest session is available.

- [ ] **Step 1: Write failing status tests**

```python
def test_statuses_mark_exact_vnindex_latest_as_listed_and_stale_as_delisted():
    rows = [("FPT", date(2026, 9, 8)), ("LTG", date(2026, 6, 19))]
    statuses = load_listing_statuses(("FPT", "LTG", "EMPTY"), FakeEngine(rows, date(2026, 9, 8)))
    assert statuses["FPT"].state == "listed"
    assert statuses["LTG"].state == statuses["EMPTY"].state == "delisted"
    assert statuses["LTG"].reason == "Delisted: ticker latest 2026-06-19; VN-Index latest 2026-09-08."
```

- [ ] **Step 2: Run the focused test and confirm it fails because the module does not exist**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_listing_status`

- [ ] **Step 3: Implement the immutable status object and one aggregate loader**

```python
@dataclass(frozen=True)
class ListingStatus:
    ticker: str
    state: Literal["listed", "delisted"]
    ticker_latest: date | None
    vnindex_latest: date

    @property
    def is_listed(self) -> bool:
        return self.state == "listed"

def load_listing_statuses(tickers: Sequence[str], engine) -> dict[str, ListingStatus]:
    # One text() query returns MAX(date) for VNINDEX and every requested ticker.
    # It normalizes every requested ticker and builds a ListingStatus for each.
    return _statuses_from_latest_rows(normalized_tickers, rows)
```

- [ ] **Step 4: Run the focused status tests**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_listing_status`

Expected: PASS.

### Task 2: Exclude Delisted Tickers From Active Backtest Work

**Files:**
- Modify: `app/backtest_engine/models.py`
- Modify: `app/backtest_engine/pipeline.py`
- Modify: `app/backtest_engine/job_runner.py`
- Modify: `app/pages/backtest_lab.py`
- Test: `tests/test_backtest_pipeline.py`
- Test: `tests/test_backtest_job_runner.py`
- Test: `tests/test_backtest_page.py`

**Interfaces:**
- Consumes `load_listing_statuses()` from Task 1.
- Produces `BatchTickerStatus(state="skipped", attempts=0, error_texts=(reason,))` for every Delisted request.
- The active `BacktestBatchConfig` contains only Listed tickers before `_resolve_lifetime_range()` and `_shared_confirmation()`.

- [ ] **Step 1: Add failing pipeline tests for a Listed HSG and Delisted LTG**

```python
def test_batch_skips_delisted_before_lifetime_range_and_preserves_fresh_common_as_of():
    statuses = run_backtest_batch_pipeline(config_for("HSG", "LTG"), None, engine)
    assert _status(statuses, "LTG")["state"] == "skipped"
    assert _status(statuses, "HSG")["state"] == "done"
    lifetime.assert_called_once_with(("HSG",), engine)
    assert hsg_evidence["common_as_of"] == "2026-09-08"
```

- [ ] **Step 2: Run failing pipeline tests**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_pipeline`

- [ ] **Step 3: Add `skipped` job/ticker status and preflight active tickers before Lifetime resolution**

```python
JOB_STATES = ("queued", "running", "done", "failed", "requires_regeneration", "skipped")
# BatchTickerStatus allows skipped only with attempts == 0 and nonempty reason.
listing = load_listing_statuses(config.tickers, engine)
active_tickers = tuple(ticker for ticker in config.tickers if listing[ticker].is_listed)
active_config = _resolve_lifetime_range(replace(config, tickers=active_tickers), engine)
```

- [ ] **Step 4: Make job/UI summaries render skipped tickers as deliberate outcomes, not errors**

```python
if status.state == "skipped":
    return f"{status.ticker}: skipped — {status.error_texts[-1]}"
```

- [ ] **Step 5: Run pipeline, job-runner, and page regressions**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_page`

Expected: PASS.

### Task 3: Guard Current Replay, Flexible Rulebook, and Position Actions

**Files:**
- Modify: `app/backtest_engine/early_warning.py`
- Modify: `app/backtest_engine/validation_advice.py`
- Modify: `app/backtest_engine/position_risk.py`
- Modify: `app/flexible_rulebook/history.py`
- Modify: `app/pages/backtest_lab.py`
- Test: `tests/test_backtest_early_warning.py`
- Test: `tests/test_backtest_validation_advice.py`
- Test: `tests/test_backtest_position_risk.py`
- Test: `tests/test_backtest_lab_helpers.py`
- Test: `tests/test_flexible_rulebook_history.py`

**Interfaces:**
- Consumes Task 1 status checks.
- A Delisted ticker returns `ticker_delisted` with both latest dates and never writes a marker.
- `_create_position_from_form` receives/uses a preflight guard before any manual-store write.

- [ ] **Step 1: Write failing tests for harmless Delisted handling**

```python
def test_validate_delisted_returns_unavailable_without_replacing_success_artifact():
    result = validate_saved_signals("LTG", engine, signal_dir, positions_dir)
    assert result["results"] == [{"availability": "unavailable", "reason": DELISTED_REASON}]
    assert load_rulebook_result(path)["terminal_state"] == "success"

def test_new_manual_position_rejects_delisted_ticker_before_write():
    with self.assertRaisesRegex(ValueError, "Delisted"):
        _create_position_from_form(
            "LTG", "Manual P&L only", {}, 20.0, date(2026, 9, 8), 100,
            "/tmp/positions", listing_guard=reject_delisted,
        )
    create_manual_position.assert_not_called()
```

- [ ] **Step 2: Run the focused replay/position/flexible tests and confirm failure**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_position_risk tests.test_backtest_lab_helpers tests.test_flexible_rulebook_history`

- [ ] **Step 3: Implement guards at every live entry point**

```python
status = load_listing_statuses((normalized,), engine)[normalized]
if not status.is_listed:
    return {
        "ticker": normalized,
        "results": [_unavailable(status.reason)],
        "historical_positions": _historical_positions(normalized, positions_dir),
    }

# Position submit checks status before calling create_manual_position.
# Mixed position validation emits an unavailable result for skipped rows and
# continues with all Listed selected rows.
```

- [ ] **Step 4: Verify no Delisted path writes `requires_regeneration`**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_position_risk tests.test_backtest_lab_helpers tests.test_flexible_rulebook_history`

Expected: PASS.

### Task 4: Atomic Group CRUD and Live Group Projection

**Files:**
- Modify: `app/backtest_engine/result_store.py`
- Modify: `app/pages/backtest_lab.py`
- Test: `tests/test_backtest_result_store.py`
- Test: `tests/test_backtest_page.py`

**Interfaces:**
- Produces `create_group(group_name, tickers, signal_dir)`, `rename_group(group_name, new_name, signal_dir)`, and `delete_group(group_name, signal_dir)`.
- Group projection accepts an ordered tuple of `SignalGroup` values and Task 1 statuses,
  producing Group/Ticker/Status/Ticker latest/VN-Index latest rows including
  named empty groups.

- [ ] **Step 1: Add failing journal and projection tests**

```python
def test_rename_recovery_writes_new_path_then_removes_old_path():
    rename_group("BANK", "BANKING", directory)
    assert [group.group_name for group in list_groups(directory)] == ["BANKING"]
    assert not old_path.exists()

def test_group_projection_filters_status_ticker_and_group_without_mutating_groups():
    rows = build_group_manager_rows(groups, statuses)
    assert filter_group_rows(rows, ticker="FPT", states={"Listed"}, group="BANK") == [expected]
```

- [ ] **Step 2: Run focused store/page tests and confirm failure**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_result_store tests.test_backtest_page`

- [ ] **Step 3: Extend journal recovery and CRUD operations**

```python
def _recover_group_move(group_dir: Path) -> None:
    before = _journal_entries(payload["before"], group_dir)
    after = _journal_entries(payload["after"], group_dir)
    for path, group_payload in after:
        _write_json_atomically(path, group_payload)
    for path, _ in before:
        if path not in {written for written, _ in after}:
            path.unlink(missing_ok=True)
    journal.unlink()
```

- [ ] **Step 4: Render Group Manager as the final Backtest tab**

```python
with group_manager:
    _render_group_manager(
        engine, signal_dir,
        groups_fn=list_groups,
        create_group_fn=create_group,
        rename_group_fn=rename_group,
        replace_members_fn=replace_group_tickers,
        delete_group_fn=delete_group,
        listing_statuses_fn=load_listing_statuses,
    )
# Filtered table includes Group, Ticker, Status, Ticker latest, VN-Index latest.
# Create/update/delete are native forms; delete uses confirmation and only calls delete_group.
```

- [ ] **Step 5: Run focused Group Manager tests**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_result_store tests.test_backtest_page`

Expected: PASS.

### Task 5: Regression, Documentation, and Status

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md`
- Test: `tests/test_backtest_listing_status.py`
- Test: all changed Backtest/Flexible tests from Tasks 1–4.

- [ ] **Step 1: Run the complete changed-scope suite**

Run: `docker compose -f docker/docker-compose.yml exec -T app python -m unittest tests.test_backtest_listing_status tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_early_warning tests.test_backtest_validation_advice tests.test_backtest_position_risk tests.test_backtest_lab_helpers tests.test_backtest_result_store tests.test_backtest_page tests.test_flexible_rulebook_history`

Expected: PASS with no skipped tests.

- [ ] **Step 2: Perform implementation self-review**

Check that every status query is parameterized, no stale status overwrites an artifact, status checking occurs before Lifetime/common-as-of, group delete cannot touch artifacts/positions, and no UI path can write a new Delisted position.

- [ ] **Step 3: Record completion and exact evidence in `FOCUS.md` and `ai-context/current-status.md`**

```markdown
**Live Delisted status and Group Manager (2026-09-08; complete):** Listed
requires an exact current VN-Index session match; Delisted tickers are skipped
from active work and blocked from new positions. Group Manager provides live
status and atomic CRUD. Record the exact passed test count.
```

## Plan self-review

- Spec coverage: Task 1 implements live status; Task 2 protects Collect and
  common-as-of; Task 3 protects replay, Flexible Rulebook, and positions;
  Task 4 implements Group Manager CRUD/filters; Task 5 verifies and records.
- Placeholder scan: no deferred behaviors or unspecified error paths remain.
- Type consistency: all consumers use `ListingStatus.is_listed`, with the
  status loader as the sole DB status interface.
