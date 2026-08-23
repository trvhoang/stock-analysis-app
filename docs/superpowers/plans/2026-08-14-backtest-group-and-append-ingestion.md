# Backtest Group Management and Append-Only Data Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. Checklist steps are tracking truth, not permission to skip verification.

**Goal:** Centralize current Backtest artifacts, add crash-safe UUID Group membership and Group-driven validation, and append Stock/VN-Index data atomically without changing old rows.

**Architecture:** A new focused result-store module owns result paths, one-time V2 migration, Group JSON validation, membership, and recovery journals. Existing persistence, catalog/replay, pipeline, and page consume it without duplicating filesystem rules. Data ingestion downloads both sources before one raw-connection transaction stages and appends only eligible newer rows.

**Tech Stack:** Python 3.12, Streamlit 1.32, pandas, SQLAlchemy, psycopg2, PostgreSQL, Docker, unittest, Streamlit AppTest.

## Global Constraints

- New current result roots are app/backtest-result/ticker-signals and app/backtest-result/ticker-group. Historical app/backtest-status JSON is read-only history and is never rewritten.
- Migrate exact current V2 artifacts BID, TCX, VCB, and VCI byte-preserved. V1 is neither read nor converted. Successful migration never reads legacy ticker-signals.
- Group filename is SAFE-UPPERCASE-SLUG-UUID.json. UUID is never UI/table/artifact data. Blank or N/A means no membership. Empty real Group JSON stays reusable.
- A ticker belongs to at most one Group JSON. Both Group moves and migration use durable journals recovered before each result/Group read or write.
- Group changes only when final Backtest attempt wrote a nonempty current signal artifact. A nonempty no-theme artifact qualifies despite themed failure.
- Manual Collect/Validate ticker input remains ordered, unique, uppercase 1–5. A selected Validate Group or N/A resolves a locked list of at most 15; 16+ shows all and runs nothing.
- Existing OHLCV remains immutable. Get data downloads/extracts both sources first, then commits every new Stock/VN-Index row or rolls back every one. No table/index drop, no historical backfill, no silent retry.
- Existing ticker source date must be later than MAX(date); new ticker date must be on/after report_date minus 365*gaps. Final insert retains ON CONFLICT (ticker, date) DO NOTHING.
- Use sqlalchemy.text() SQL definitions, get_engine_with_retry() and one engine.raw_connection() transaction, and %(name)s bindings for dynamic SQL.
- Preserve existing price * 1000 BIGINT conversion. Do not modify common_queries.py, credentials, Docker, dependencies, or commit history. No commit.

## File Map

- Create: app/backtest_engine/result_store.py — roots, migration journal, Group JSON schema, Group journal, resolvers.
- Modify: app/backtest_engine/config.py — owns shared result-path constants, default signal path, and immutable batch group_name only.
- Modify: app/backtest_engine/persistence.py, early_warning.py, signal_catalog.py, validation_advice.py — central-root reads/writes and internal catalog Group metadata.
- Modify: app/backtest_engine/pipeline.py — final-attempt qualified Group assignment.
- Modify: app/pages/backtest_lab.py — Collect Group, reusable Group-filtered View Signals, Group-selected Validate flow.
- Modify: app/pages/data_preparation.py — source-first, one-transaction append ingestion.
- Modify tests: test_backtest_persistence.py, test_backtest_pipeline.py, test_backtest_signal_catalog.py, test_backtest_page.py, test_backtest_worker.py, test_data_preparation.py.
- Modify FOCUS.md and ai-context/current-status.md; create dated verification report after evidence.

---

### Task 1: Central result roots, V2 migration, and Group JSON store

**Files:**

- Create: app/backtest_engine/result_store.py
- Modify: app/backtest_engine/config.py:1-260
- Modify: app/backtest_engine/persistence.py:1-180
- Modify: app/backtest_engine/early_warning.py:250-270
- Modify: app/backtest_engine/signal_catalog.py:1-280
- Modify: app/backtest_engine/validation_advice.py:260-315
- Test: tests/test_backtest_persistence.py, tests/test_backtest_signal_catalog.py, tests/test_backtest_worker.py

**Interfaces:**

- config.py owns DEFAULT_SIGNAL_DIR = "backtest-result/ticker-signals", DEFAULT_GROUP_DIR = "backtest-result/ticker-group", and LEGACY_SIGNAL_DIR = "ticker-signals"; result_store imports them, avoiding a config/result-store import cycle.
- SignalGroup is immutable with group_id, group_name, tickers, metadata, and path.
- ensure_result_root(signal_dir, legacy_signal_dir=None) -> Path; list_groups(signal_dir) -> tuple[SignalGroup, ...]; assign_ticker_group(ticker, group_name, signal_dir) -> None; group_for_ticker(ticker, signal_dir) -> str; resolve_group_tickers(selection, signal_dir) -> tuple[str, ...].
- BacktestBatchConfig.group_name defaults N/A and serializes. BacktestConfig remains Group-free.

- [x] **Step 1: Write RED storage tests**

Create temporary legacy BID/TCX/VCB/VCI V2 JSON files plus one historical status file. Pass that temporary legacy path explicitly to ensure_result_root. Assert migration hashes match byte-for-byte, sources disappear only after all target hashes verify, and status bytes never change.

~~~python
ensure_result_root(str(new_signal_root), legacy_signal_dir=str(legacy_root))
self.assertEqual(sha256(target.read_bytes()).hexdigest(), source_hash)
self.assertFalse(source.exists())
self.assertEqual(status_path.read_bytes(), status_before)
~~~

Add Group cases: Bank & Finance becomes display BANK & FINANCE and filename BANK-FINANCE-UUID.json; same name reuses UUID; N/A removes membership; empty prior Group remains; duplicate Group name/ticker JSON rejects; seeded Group journal recovers after payload before a reader returns.

- [x] **Step 2: Run RED storage tests**

Run:

~~~powershell
docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_signal_catalog tests.test_backtest_worker -v
~~~

Expected: FAIL because roots, migration, Group JSON, journal recovery, and batch Group serialization do not exist.

- [x] **Step 3: Implement result-store**

Use stdlib uuid.uuid4, hashlib.sha256, json, tempfile, os.replace, and fsync only. Write a Group payload with schema_version 1, hidden group_id, uppercase group_name, sorted tickers, empty metadata, and Asia/Ho_Chi_Minh updated_at.

Implement migration only when a legacy root is explicitly supplied or when the signal root is DEFAULT_SIGNAL_DIR. Its .signal-root-migration.json records source, target, digest for exact BID/TCX/VCB/VCI. Verify/move remaining entries on recovery before consumers read the new root. Group .move journal stores validated before/after payloads; readers complete after state before resolving membership.

Make every default artifact read/write call ensure_result_root first. Update the seven old default literals to DEFAULT_SIGNAL_DIR. Add group_name to BacktestBatchConfig, uppercase blank to N/A, include it in to_dict(), and preserve worker restore.

- [x] **Step 4: Add catalog Group metadata**

After strict artifact validation, attach internal _group = BANK or N/A to valid and invalid catalog rows. Return valid, invalid, and warnings; corrupt Group JSON creates a warning but cannot hide valid artifact rows. Keep nine visible catalog columns unchanged.

~~~python
return {"valid": valid_rows, "invalid": invalid_rows, "warnings": group_warnings}
~~~

- [x] **Step 5: Run GREEN storage tests**

Run Step 2 command. Expected: PASS; V2 strict loading stays strict, catalog hides UUID, worker round-trip keeps group_name.

- [x] **Step 6: Review**

Run git diff --check and search app for old ticker-signals literals. Only LEGACY_SIGNAL_DIR may retain it. Do not commit.

### Task 2: Assign Group only from fresh final qualified batch output

**Files:**

- Modify: app/backtest_engine/pipeline.py:80-300
- Test: tests/test_backtest_pipeline.py:228-465

**Interfaces:**

- Private _run_variant(...) returns tuple[str, bool]: artifact path and whether this just-written artifact has nonempty signal_sets.
- Public run_backtest_pipeline still returns list[str].
- Batch pipeline calls assign_ticker_group(ticker, config.group_name, config.output_dir) exactly once after final attempt only if that attempt wrote nonempty output.

- [x] **Step 1: Write RED batch tests**

Assert empty output never assigns Group; no-theme nonempty plus themed failure assigns on final retry partial result; Group-store failure records ticker failure but next ticker completes; saved no-theme output remains in output_paths.

~~~python
assign.assert_called_once_with("FPT", "BANK", config.output_dir)
self.assertEqual(result["ticker_results"][1]["state"], "done")
self.assertIn("Group", result["ticker_results"][0]["error_texts"][-1])
~~~

- [x] **Step 2: Run RED**

~~~powershell
docker exec stock_app python -m unittest tests.test_backtest_pipeline -v
~~~

Expected: FAIL because variant result has no qualification boolean and pipeline has no Group boundary.

- [x] **Step 3: Implement final-attempt assignment**

Retain computed signal_sets boolean in _run_variant. In run_ticker retain paths/booleans only from current attempt. After the retry-aware final attempt, apply Group only if any current attempt variant is nonempty. Preserve no-theme then theme, shared preflight, ticker continuation, retry order, status/progress, and error text.

- [x] **Step 4: Run GREEN**

~~~powershell
docker exec stock_app python -m unittest tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_worker -v
~~~

Expected: PASS; Group management changes no strategy/theme scheduling.

- [x] **Step 5: Review**

Confirm BacktestConfig and V2 artifact payloads contain no group_id/group_name. Do not commit.

### Task 3: Collect Group and reusable Group-filtered View Signals

**Files:**

- Modify: app/pages/backtest_lab.py:150-185 and 2100-2310
- Test: tests/test_backtest_page.py, tests/test_backtest_signal_catalog.py

**Interfaces:**

- build_backtest_batch_config(..., include_theme=False, group_name="N/A") -> BacktestBatchConfig.
- _render_current_signal_catalog(catalog, key_prefix) -> None; Collect and Validate pass different prefixes.

- [x] **Step 1: Write RED UI/catalog tests**

Use BANK, TECH, N/A catalog fixtures. Assert five Collect controls ordered Tickers, Time range, Horizon, Group, Action. Group defaults N/A, locks while job busy, and submitted config has BANK. Assert both View Signals popovers have Group default All; BANK filtering leaves BANK rows only; invalid rows remain red and Group warnings leave valid rows visible.

~~~python
self.assertEqual(app.text_input[group_index].value, "N/A")
self.assertEqual(app.selectbox[group_filter_index].value, "All")
self.assertEqual([row["Ticker"] for row in filtered_rows], ["FPT"])
~~~

- [x] **Step 2: Run RED**

~~~powershell
docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_page -v
~~~

Expected: FAIL because Collect has four columns, only ticker filter, and Validate has no View Signals popover.

- [x] **Step 3: Implement page management controls**

Use st.columns(5), insert Group after Horizon, uppercase/default N/A, retain busy lock, and pass it only to batch config. Shared popover places Group selectbox beside ticker filter; options All, represented N/A, sorted Group names; filters active tab by _group and ticker. Render warnings. Add native View Signals popover to Validate with validate_view_signals_ keys. No Group column/action button.

- [x] **Step 4: Run GREEN**

Run Step 2 command. Expected: PASS; all existing catalog columns and red invalid highlighting survive.

- [x] **Step 5: Review**

Confirm Group cannot alter horizon/theme/result rendering. Do not commit.

### Task 4: Validate selected Group/N/A safely

**Files:**

- Modify: app/backtest_engine/result_store.py
- Modify: app/pages/backtest_lab.py:934-1015 and 2300-2310
- Test: tests/test_backtest_page.py, tests/test_backtest_signal_catalog.py

**Interfaces:**

- list_validation_group_choices(signal_dir) -> tuple[str, ...] returns -, N/A, then real Group names.
- resolve_group_tickers(selection, signal_dir) returns sorted Group membership or artifact tickers without membership for N/A.
- tickers_with_no_saved_signal(tickers, signal_dir) returns absent, empty, or unreadable artifact tickers.
- Page result becomes {"request": tuple, "completed": list[dict], "skipped": tuple[str, ...]} and includes ticker tuple, Group selection, theme selection in request identity.

- [x] **Step 1: Write RED Validate tests**

Use temporary real signal/Group fixtures. Assert dropdown beside Tickers defaults -, preserves manual 1–5 input, and selected BANK/N/A fills/locks Tickers. For 16 members, show all symbols, call validator zero times, show reduce/rerun error. For 15-or-fewer, call validator sequentially; no-theme output precedes themed per ticker; absent/empty/bad signal ticker skips without halting and final message lists it.

~~~python
self.assertTrue(validate_tickers_widget.disabled)
self.assertEqual(calls, ["FPT", "VCB"])
self.assertIn("MBB", skipped_message.value)
self.assertEqual(over_cap_calls, [])
~~~

- [x] **Step 2: Run RED**

~~~powershell
docker exec stock_app python -m unittest tests.test_backtest_page tests.test_backtest_signal_catalog -v
~~~

Expected: FAIL because Validate supports one editable ticker, no Group resolver/cap, and one result mapping.

- [x] **Step 3: Implement resolved-list loop**

Leave validate_saved_signals single-ticker API unchanged. Group selection sets Streamlit state before Tickers renders, fills comma-separated resolved symbols, disables the field; - retains manual parser. Reject zero/16+ before progress. For allowed list, precompute skipped, invoke existing validate_fn one ticker at a time, advance/empty progress in finally, isolate per-ticker errors, save ordered batch result, then render skipped list only after completion.

- [x] **Step 4: Run GREEN**

Run Step 2 command. Expected: PASS; existing advice, multi-metric detail, BUY/SELL, and no-theme-first behavior still render for each completed ticker.

- [x] **Step 5: Review**

Confirm Group selection never permits ticker edits; manual selection never exceeds five; Group UUID never reaches page/session display. Do not commit.

### Task 5: Append-only source-first Data Page ingestion

**Files:**

- Modify: app/pages/data_preparation.py:1-365
- Test: tests/test_data_preparation.py

**Interfaces:**

- _download_and_extract_source(report_date, data_type, root) -> ExtractedSource performs no DB mutation.
- _ensure_schema(cursor), _latest_dates(cursor), _eligible_chunk(chunk, latest_dates, cutoff_date, ticker_filter, exchange), and _stage_source(cursor, source, latest_dates, cutoff_date) do not commit.
- Public init_db(engine) retains startup call compatibility. run_full_ingestion owns one raw connection and exactly one commit or rollback.

- [x] **Step 1: Write RED append/rollback tests**

Build temporary CSV fixtures with old/new FPT dates, new ticker above/below cutoff, and duplicate rows. Raw-connection double must prove one commit, no table/index drop, and exact eligible rows. Inject a VN-Index stage failure after Stock staging: assert rollback once, no commit, and failure return. Download failure must not call raw_connection. Update expected progress to start, sources downloaded, schema/old data preserved, Stock staged, VN-Index staged, committed, complete.

~~~python
self.assertEqual(connection.commit.call_count, 1)
connection.rollback.assert_not_called()
self.assertNotIn("DROP TABLE", executed_sql)
self.assertEqual(eligible[["ticker", "date"]].values.tolist(), [["FPT", newer_day]])
~~~

- [x] **Step 2: Run RED**

~~~powershell
docker exec stock_app python -m unittest tests.test_data_preparation -v
~~~

Expected: FAIL because current flow drops data, commits per file/source, rebuilds index, and reports reset.

- [x] **Step 3: Implement one transaction**

Delete obsolete download_and_process_data/per-file transaction path. Download/extract Stock and Index into one TemporaryDirectory first. Then acquire one engine.raw_connection; call _ensure_schema, read latest date map once, create one transaction-scoped staging table with ticker/date uniqueness, stream all chunks, preserve exact *1000 price conversions, stage via fixed execute_values statement, and final insert ON CONFLICT DO NOTHING.

Use this mask:

~~~python
latest = chunk["Ticker"].map(latest_dates)
eligible = (latest.notna() & (chunk["DTYYYYMMDD"] > latest)) | (
    latest.isna() & (chunk["DTYYYYMMDD"] >= cutoff_date)
)
chunk = chunk.loc[eligible]
~~~

Commit only after final VN-Index stage succeeds. Every parse/schema/stage/index/insert exception rolls back/returns False; no silent retry. Create idx_ticker_date only with CREATE INDEX IF NOT EXISTS. Update UI to no reset phase and show No new data was saved. Please rerun Get data manually. on False.

- [x] **Step 4: Run GREEN**

~~~powershell
docker exec stock_app python -m unittest tests.test_data_preparation -v
~~~

Expected: PASS; one aligned Data Page control row and expanded details remain, reset text/spinner gone.

- [x] **Step 5: Review boundary**

Verify conversion lines remain chunk["Open"] * 1000 and High/Low/Close equivalents. No SQL price division; no common_queries.py diff; no commit.

### Task 6: Full verification, approved real migration, and documentation

**Files:**

- Modify: FOCUS.md
- Modify: ai-context/current-status.md
- Create: docs/superpowers/reports/2026-08-14-backtest-group-and-append-ingestion-verification.md

**Interfaces:**

- App result root holds four migrated V2 artifacts; Group root exists; old status JSON bytes are unchanged.

- [x] **Step 1: Run focused regression gate**

~~~powershell
docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_signal_catalog tests.test_backtest_page tests.test_data_preparation -v
docker exec stock_app python -m compileall backtest_engine pages
git diff --check
~~~

Expected: all pass before actual migration.

- [x] **Step 2: Perform and verify approved move**

Capture SHA-256 for exact four source artifacts and all job-status JSON. Call ensure_result_root(DEFAULT_SIGNAL_DIR). Verify target/source hashes equal, sources absent, ticker-group exists, all status hashes equal. If journal recovery errors, stop; never manually delete or rewrite status.

~~~python
ensure_result_root(DEFAULT_SIGNAL_DIR)
assert target_hashes == source_hashes
assert status_hashes_after == status_hashes_before
~~~

- [x] **Step 3: Live UI smoke**

Without submitting a production Backtest/Get data job, verify Collect default N/A, both View Signals filters, Validate manual -, selected Group lock, 16+ rejection, skipped summary, and append-only Data progress.

- [x] **Step 4: Evidence and tracking**

Record exact commands/test counts, migration hashes (not payloads), UI smoke result, and limitations. Mark plan/docs complete only with evidence. Do not commit.
