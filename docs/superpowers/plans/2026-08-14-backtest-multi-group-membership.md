# Backtest Multi-Group Membership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a ticker retain memberships in multiple named ticker Groups while
keeping `N/A` as the derived no-membership selection.

**Architecture:** Group JSON files remain the sole membership source of truth.
The store permits a ticker across multiple Group files and makes successful
named-Group assignments add-only. Catalog rows hold an internal tuple of Group
names for membership filtering, so View Signals still renders exactly one row
per ticker/theme/signal-set candidate. Validate Signals continues reading the
selected Group's deterministic ticker list.

**Tech Stack:** Python 3.12, `unittest`, Streamlit, JSON filesystem store,
Docker.

## Global Constraints

- Preserve `Ticker 1 --- n saved signal sets`, `Ticker 1 --- n named Groups`,
  and `Named Group 1 --- n tickers`.
- `N/A` is derived from zero named memberships. It is not a Group JSON and a
  blank/`N/A` Collect value does not erase named memberships.
- A named Group is added only after that ticker's final Backtest attempt writes
  at least one certified signal set; it never removes another named Group.
- View Signals displays one candidate row only, with no Group column. Its
  `Ticker Groups` control filters by membership.
- Preserve UUID filenames, uppercase Group names, JSON atomic replacement,
  recovery journal, empty named Group files, 15-ticker Validate Group cap, and
  existing sequential Backtest behavior.
- Do not introduce dependencies or modify SQL, BIGINT pricing, signal artifact
  schemas, positions, Docker, credentials, `app/common_queries.py`, or commits.
- Work in the current feature branch. The user manages commit history: do not
  create, amend, reset, or otherwise change commits.
- Use test-first RED/GREEN execution in the running `stock_app` container.

---

## File Structure

- Modify: `app/backtest_engine/result_store.py`
  - owns validated Group JSON reads/writes, derived `N/A` membership, named
    Group resolution, and add-only membership persistence.
- Modify: `app/backtest_engine/signal_catalog.py`
  - attaches deterministic internal Group-name tuples to current catalog rows.
- Modify: `app/pages/backtest_lab.py`
  - derives View Signals options and row inclusion from the internal tuple,
    without adding a table column.
- Modify: `tests/test_backtest_persistence.py`
  - proves storage cardinality, add-only behavior, validation resolution, and
    retained malformed-file protection.
- Modify: `tests/test_backtest_signal_catalog.py`
  - proves a catalog candidate carries all memberships once.
- Modify: `tests/test_backtest_page.py`
  - proves both View Signals popovers filter a multi-group ticker once and
    derive `N/A` correctly.
- Modify only if a RED test proves no existing coverage: `tests/test_backtest_pipeline.py`
  - proves the existing post-qualification call path preserves membership via
    the changed store contract; production pipeline code should remain
    untouched unless this test reveals a real gap.
- Modify after every required test gate passes: `FOCUS.md`,
  `ai-context/current-status.md`, and the verification report created in Task
  4.

### Task 1: Group-store n-to-n and add-only contract

**Files:**

- Modify: `tests/test_backtest_persistence.py:143-258`
- Modify: `app/backtest_engine/result_store.py:118-315`

**Interfaces:**

- Consumes: `SignalGroup`, `list_groups(signal_dir)`, and existing atomic
  `_write_json_atomically()` / `_recover_group_move()` behavior.
- Produces: `groups_for_ticker(ticker: str, signal_dir: str =
  DEFAULT_SIGNAL_DIR) -> tuple[str, ...]`; updated
  `assign_ticker_group(ticker, group_name, signal_dir) -> None` with add-only
  named membership semantics.

- [x] **Step 1: Write failing n-to-n and derived-`N/A` storage tests**

  Replace the existing exclusive-membership test with this behavior:

  ```python
  assign("FPT", "Bank & Finance", str(signal_root))
  assign("FPT", "ETF VN30", str(signal_root))
  assign("FPT", "N/A", str(signal_root))
  assign("FPT", "", str(signal_root))

  self.assertEqual(
      groups_for_ticker("FPT", str(signal_root)),
      ("BANK & FINANCE", "ETF VN30"),
  )
  self.assertEqual(
      {group.group_name: group.tickers for group in list_groups(str(signal_root))},
      {"BANK & FINANCE": ("FPT",), "ETF VN30": ("FPT",)},
  )
  ```

  Add a fixture with `FPT` in two different valid Group files and assert that
  `list_groups()` accepts it. Retain the current malformed fixture that repeats
  `FPT` inside one Group file and assert it raises `ValueError` for invalid
  tickers. Update resolver coverage so `resolve_group_tickers("BANK")` returns
  its member while `resolve_group_tickers("N/A")` excludes every ticker that is
  a member of any named Group.

- [x] **Step 2: Run the focused test to verify RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_persistence.BacktestPersistenceTests.test_group_membership_uses_hidden_uuid_and_retains_empty_group tests.test_backtest_persistence.BacktestPersistenceTests.test_group_reader_rejects_duplicate_group_name_or_ticker tests.test_backtest_persistence.BacktestPersistenceTests.test_group_resolver_lists_real_and_no_group_artifact_tickers
  ```

  Expected: FAIL because the store rejects multi-Group `FPT`, removes it when
  given `N/A`, and exposes only the singular `group_for_ticker()` interface.

- [x] **Step 3: Implement the smallest add-only store change**

  In `_load_groups()`, retain Group ID/name checks but remove only the global
  `seen_tickers` duplicate-across-files rejection. `_group_from_payload()`
  remains responsible for rejecting duplicates inside one Group JSON.

  Replace the singular reader with:

  ```python
  def groups_for_ticker(
      ticker: str,
      signal_dir: str = DEFAULT_SIGNAL_DIR,
  ) -> tuple[str, ...]:
      normalized_ticker = _normalize_ticker(ticker)
      return tuple(
          group.group_name
          for group in list_groups(signal_dir)
          if normalized_ticker in group.tickers
      )
  ```

  Make `assign_ticker_group()` return immediately for a normalized blank/`N/A`
  name or when the ticker is already in the target Group. For a named target,
  journal and write only the target Group's before/after payload, adding the
  normalized ticker in sorted order. Do not inspect or update any other Group.
  Remove `group_for_ticker` from `__all__`; no production caller exists.

- [x] **Step 4: Run the focused storage tests to verify GREEN**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_persistence
  ```

  Expected: PASS, including valid cross-Group membership, no-op `N/A`, sorted
  memberships, derived resolver behavior, same-file duplicate rejection,
  malformed Group identity rejection, and journal recovery.

- [x] **Step 5: Inspect the persistence boundary**

  Confirm with:

  ```powershell
  rg -n "group_for_ticker|seen_tickers|duplicate ticker membership|assign_ticker_group" app\backtest_engine\result_store.py tests\test_backtest_persistence.py
  ```

  Expected: no singular reader remains; duplicate ticker validation is confined
  to one JSON payload; the writer has no source-Group removal branch.

- [x] **Step 6: Do not commit**

  The user owns commits. Leave the working tree and commit log unchanged apart
  from this task's uncommitted source/test edits.

### Task 2: Catalog membership attributes and non-duplicating filters

**Files:**

- Modify: `tests/test_backtest_signal_catalog.py:98-174`
- Modify: `tests/test_backtest_page.py:1462-1537`
- Modify: `app/backtest_engine/signal_catalog.py:141-190`
- Modify: `app/pages/backtest_lab.py:2234-2290`

**Interfaces:**

- Consumes: `list_groups(signal_dir) -> tuple[SignalGroup, ...]` and
  `groups_for_ticker()` contract from Task 1.
- Produces: catalog rows with private `_groups: tuple[str, ...]`; page-private
  `_catalog_group_names(row) -> tuple[str, ...]` and membership-aware filter
  logic.

- [x] **Step 1: Write failing catalog and AppTest coverage**

  Seed one V2 signal artifact for `FPT`, add it to `BANK` and `ETF VN30`, then
  assert the catalog contains exactly one `FPT` candidate row and:

  ```python
  self.assertEqual(catalog["valid"][0]["_groups"], ("BANK", "ETF VN30"))
  self.assertNotIn("Group", catalog["valid"][0])
  ```

  Update the two-popover AppTest fixture to use `_groups` tuples. Filter
  Collect by `BANK` and Validate by `ETF VN30`; each must display the one `FPT`
  row. Add an ungrouped `VCB` row: `N/A` must show only `VCB`, and `All` must
  list `FPT` once rather than once per membership.

- [x] **Step 2: Run the new tests to verify RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_page.BacktestPageTests.test_view_signals_popovers_filter_by_group_in_collect_and_validate
  ```

  Expected: FAIL because catalog rows expose scalar `_group` values and page
  filtering uses equality rather than Group membership.

- [x] **Step 3: Implement one private tuple-based catalog representation**

  In `list_current_signal_set_rows()`, construct a deterministic
  `dict[str, tuple[str, ...]]` from `list_groups()`. Attach `_groups` to valid
  and invalid rows, defaulting to `()`. Do not expand a row once per Group.

  Replace `_catalog_group_name()` with:

  ```python
  def _catalog_group_names(row: Mapping[str, object]) -> tuple[str, ...]:
      value = row.get("_groups", ())
      if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
          raise ValueError("saved signal catalog has invalid Group memberships")
      return tuple(sorted({item.strip().upper() for item in value if item.strip()}))
  ```

  Build `Ticker Groups` choices by flattening these tuples. Include `N/A` only
  when at least one row returns `()`. For a selected named Group, retain a row
  when the name is in its tuple; for selected `N/A`, retain it only when the
  tuple is empty. `SIGNAL_CATALOG_COLUMNS` remains the only display-column
  source, so no Group column is rendered.

- [x] **Step 4: Run the catalog/page tests to verify GREEN**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_signal_catalog tests.test_backtest_page
  ```

  Expected: PASS, including both View Signals popovers, valid/invalid artifacts,
  Group membership filtering, no duplicate candidate rows, uppercase filters,
  and unchanged signal-table columns.

- [x] **Step 5: Verify the UI has no redundant Group column**

  Run:

  ```powershell
  rg -n '"Group"|"_group"|"_groups"|SIGNAL_CATALOG_COLUMNS' app\pages\backtest_lab.py app\backtest_engine\signal_catalog.py
  ```

  Expected: Group is used only in Collect/Validate controls and private catalog
  filtering; no Group item is appended to `SIGNAL_CATALOG_COLUMNS`.

- [x] **Step 6: Do not commit**

  The user owns commits. Leave this completed task uncommitted.

### Task 3: Qualification-path regression and focused integration gate

**Files:**

- Modify only if RED coverage is absent: `tests/test_backtest_pipeline.py:426-560`
- Modify only if a RED test proves a defect: `app/backtest_engine/pipeline.py:174-330`

**Interfaces:**

- Consumes: unchanged `assign_ticker_group(ticker, group_name, output_dir)`
  call from the single and batch Backtest pipelines; add-only semantics from
  Task 1.
- Produces: evidence that named Group addition remains after a qualified final
  attempt and does not occur after a terminal empty result.

- [x] **Step 1: Add a failing qualification-path test only if one is missing**

  Use a temporary output directory, seed `FPT` in `BANK`, configure a batch
  whose `group_name` is `ETF VN30`, and patch `_prepare_ticker` / `_run_variant`
  to return a qualified final `FPT` result. Let the real store execute and
  assert:

  ```python
  self.assertEqual(
      groups_for_ticker("FPT", str(output_dir)),
      ("BANK", "ETF VN30"),
  )
  ```

  Add a terminal-empty fixture returning `(None, False)` and assert the
  existing `BANK` membership remains while no new `ETF VN30` Group is created.

- [x] **Step 2: Run the qualification-path test to verify RED**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_pipeline
  ```

  Expected: RED only if pipeline composition is not testable with the real
  Group store. If current code already satisfies this test after Task 1, record
  it as a direct GREEN regression proof and make no production pipeline edit.

  Result: direct GREEN — the expanded pipeline module passed 17/17 after Task
  1 because it already calls the shared store only after the final qualifying
  result. `pipeline.py` remains unchanged.

- [x] **Step 3: Make the smallest proven production change, if needed**

  Keep `pipeline.py` unchanged unless the RED test proves that it calls Group
  persistence before a final qualified result or bypasses `config.output_dir`.
  If such a defect is proven, change only that shared call site so it invokes
  the Task 1 add-only store after the final qualified result. Do not change
  retries, shared theme preflight, output paths, progress, or signal writes.

- [x] **Step 4: Run the focused integration gate**

  Run:

  ```powershell
  docker exec stock_app python -m unittest tests.test_backtest_persistence tests.test_backtest_signal_catalog tests.test_backtest_pipeline tests.test_backtest_job_runner tests.test_backtest_worker tests.test_backtest_page
  ```

  Expected: PASS. Existing empty-result behavior must preserve artifacts and
  Group memberships; qualified named-Group results must add one membership.

- [x] **Step 5: Do not commit**

  The user owns commits. Do not create a task commit.

### Task 4: Review, verification, and documentation handoff

**Files:**

- Create: `docs/superpowers/reports/2026-08-14-backtest-multi-group-membership-verification.md`
- Modify: `FOCUS.md:5-18`
- Modify: `ai-context/current-status.md:1-25`

**Interfaces:**

- Consumes: all passing Task 1–3 tests and the final changed-file diff.
- Produces: evidence-backed completed status and a truthful stopping point.

- [x] **Step 1: Run compilation and source audits**

  Run:

  ```powershell
  docker exec stock_app python -m compileall backtest_engine pages
  rg -n -F "group_for_ticker" app tests
  rg -n -P '\"_group\"' app tests
  docker exec stock_app python -c "from pages.backtest_lab import SIGNAL_CATALOG_COLUMNS; assert 'Group' not in SIGNAL_CATALOG_COLUMNS; print(SIGNAL_CATALOG_COLUMNS)"
  ```

  Expected: compilation succeeds; no singular reader/scalar `_group` membership
  remains; no View Signals table Group column exists.

- [x] **Step 2: Run protected-boundary and whitespace checks**

  Run:

  ```powershell
  git diff --check
  git diff -- app/commons/common_queries.py app/pages/data_preparation.py app/main.py docker/Dockerfile docker/docker-compose.yml
  ```

  Result: `git diff --check` passed with only pre-existing CRLF conversion
  notices. The pre-existing dirty worktree reports `app/main.py` and
  `app/pages/data_preparation.py` under protected paths; this task did not
  modify them. `app/commons/common_queries.py` and Docker files have no current
  tracked diff.

- [x] **Step 3: Perform implementation self-review**

  Read `ai-skills/skill-implementation-review.md`, then verify:

  - group names and ticker lists stay normalized/deterministically ordered;
  - `N/A` cannot be persisted or erase named memberships;
  - a row in multiple Groups remains one catalog row;
  - selected named Groups and derived `N/A` resolve disjoint ticker sets;
  - no production path still relies on a singular Group result;
  - no Group data affects strategy, theme, signal artifact, position, SQL, or
    BIGINT price logic.

  Fix every confirmed issue before completion, then rerun the affected focused
  Docker test gate.

- [x] **Step 4: Write evidence and update status only after every gate passes**

  Record the exact RED/GREEN commands, pass counts, compilation, audit, and
  boundary results in the verification report. Update `FOCUS.md` to mark the
  task completed and set the next stopping point. Add a concise completed-task
  entry to `ai-context/current-status.md`, preserving its existing historical
  entries and priorities. State explicitly that no commit was created.

- [x] **Step 5: Do not commit**

  The user owns commits. Report modified files and verification evidence without
  changing Git history.

## Plan self-review

- **Spec coverage:** Task 1 implements n-to-n Group JSON cardinality and
  derived `N/A`; Task 2 guarantees membership filtering without row/table
  duplication; Task 3 preserves qualified-result-only pipeline behavior; Task
  4 verifies and documents every protected boundary.
- **Type consistency:** `groups_for_ticker()` and catalog `_groups` are tuples
  of uppercase strings throughout. Named Group resolution continues returning
  ticker tuples.
- **Scope:** No central index, removal workflow, Group display column, schema
  migration, or unrelated Backtest/Data feature is included.
- **Placeholder scan:** No deferred implementation, unspecified function, or
  unbounded error-handling step remains. The conditional pipeline source edit
  is intentional: it avoids a no-op production diff unless a RED test proves
  the current shared call path is defective.
