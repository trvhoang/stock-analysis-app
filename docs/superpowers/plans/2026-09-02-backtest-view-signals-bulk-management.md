# Backtest View Signals — Filtering and Bulk Candidate Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make schema-5 View Signals reviewable across multiple tickers and safely remove user-selected saved candidates without breaking position history or artifact invariants.

**Architecture:** Keep the page as a projection: it creates immutable `(ticker, horizon, rulebook_id)` selections and delegates every mutation to one backtest-engine service. The service preflights all artifacts and every saved position, prepares complete replacement documents, then uses a durable journal to make multi-artifact deletion logically all-or-nothing across interruption or process failure.

**Tech Stack:** Python 3.12, Streamlit native widgets, pandas, JSON schema-5 persistence, `unittest` / Streamlit `AppTest`.

**Status:** Complete (2026-09-02). Docker compilation passed; focused persistence/catalog/removal/page suites passed 68/68; canonical `unittest discover -s tests -v` passed 790/790. No git action or dependency change was made.

## Global Constraints

- No schema, rulebook, ranking threshold, collection, validation, SQL, Docker, dependency, or BIGINT-scaling change.
- Ticker filtering is view-only: comma/whitespace tokens, uppercase, deduplicated, exact membership, and no 15-ticker limit.
- Default visible columns are `No`, `Select`, `Ticker`, `Horizon`, `Train-test`, `n`, `Win rate %`, `Profit %`, and `Sharpe`; `Evidence` and `Theme` remain selectable but hidden by default. `No`, `Select`, and `Ticker` are fixed.
- Removal identity is exactly `(ticker, horizon, rulebook_id)`; table ordinal and displayed values are never identities.
- A reference from either an OPEN or CLOSED saved schema-5 position blocks the entire request before any artifact write.
- Nonselected candidates remain in their full `candidates` collection. Recompute `top_rulebook_ids` with the existing immutable rank: training win rate, training profit percentage, training Sharpe, lexical `rulebook_id`.
- Removing an artifact's final candidate writes an `empty` schema-5 document with rejection reason `All saved candidates were removed by user.`; do not delete the artifact.
- No git action or commit. Use `apply_patch` for all source and document edits.

---

## File map

- Create `app/backtest_engine/signal_removal.py`: validated schema-5 candidate identity, position-reference preflight, durable batch journal, removal/recovery service.
- Modify `app/backtest_engine/persistence.py`: expose one validated atomic replacement function that preserves an already-valid document's `evaluated_at` when an administrative removal rewrites it.
- Modify `app/backtest_engine/signal_catalog.py`: recover a pending removal transaction before exposing current catalog/options; surface recovery failures as a safe catalog warning rather than display possibly mixed state.
- Modify `app/pages/backtest_lab.py`: exact multi-ticker parser/filter, concise table projection, native selection/column controls, action feedback, and removal delegation.
- Create `tests/test_backtest_signal_removal.py`: engine-boundary contract and crash-recovery tests with temporary artifacts/positions.
- Modify `tests/test_backtest_page.py`: pure projection/filter and Streamlit View Signals behavior tests.
- Modify `FOCUS.md`: mark this plan's tested stopping point after implementation; do not change unrelated work.

## Public interfaces

```python
# app/backtest_engine/signal_removal.py
@dataclass(frozen=True, order=True)
class SignalCandidateKey:
    ticker: str
    horizon: str
    rulebook_id: str

@dataclass(frozen=True)
class SignalRemovalResult:
    removed: tuple[SignalCandidateKey, ...]

class SignalRemovalBlockedError(ValueError):
    protected: tuple[SignalCandidateKey, ...]

def remove_saved_signal_candidates(
    selections: Iterable[SignalCandidateKey | Mapping[str, object]],
    *, signal_dir: str = DEFAULT_SIGNAL_DIR,
    positions_dir: str = "backtest-positions",
) -> SignalRemovalResult: ...

def recover_pending_signal_removal(signal_dir: str = DEFAULT_SIGNAL_DIR) -> None: ...
```

```python
# app/backtest_engine/persistence.py
def replace_validated_rulebook_result(
    ticker: str, horizon: str, result: Mapping[str, object], output_dir: str,
) -> str: ...
```

`replace_validated_rulebook_result` copies, validates, and atomically writes one
already-complete schema-5 document. Unlike `save_rulebook_result`, it does not
replace `evaluated_at`; manual removal preserves the original evaluation evidence time.

### Task 1: Add the candidate-removal persistence boundary

**Files:**
- Modify: `app/backtest_engine/persistence.py:425-470`
- Create: `app/backtest_engine/signal_removal.py`
- Create: `tests/test_backtest_signal_removal.py`

**Consumes:** `load_rulebook_result`, `validate_rulebook_document`, `signal_artifact_path`, and the existing private `_candidate_rank` from `persistence.py`; `load_all_positions` from `position_overview.py`.

**Produces:** `SignalCandidateKey`, `SignalRemovalResult`, `SignalRemovalBlockedError`, `remove_saved_signal_candidates`, `recover_pending_signal_removal`, and `replace_validated_rulebook_result`.

- [ ] **Step 1: Write failing persistence and removal tests**

Build a valid schema-5 success document fixture with four candidates in deliberately non-rank order and write it through the ordinary `save_rulebook_result` path. Test these public outcomes:

```python
def test_removal_preserves_unselected_candidates_and_promotes_ranked_fourth(self):
    result = remove_saved_signal_candidates(
        [SignalCandidateKey("VCB", "swing", "rulebook-a")],
        signal_dir=self.signals, positions_dir=self.positions,
    )
    document = load_rulebook_result(signal_artifact_path("VCB", "swing", self.signals))
    self.assertEqual(result.removed, (SignalCandidateKey("VCB", "swing", "rulebook-a"),))
    self.assertEqual({item["rulebook_id"] for item in document["candidates"]},
                     {"rulebook-b", "rulebook-c", "rulebook-d"})
    self.assertEqual(document["top_rulebook_ids"], ["rulebook-b", "rulebook-c", "rulebook-d"])

def test_removal_of_last_candidate_writes_valid_regeneratable_empty_document(self):
    remove_saved_signal_candidates([SignalCandidateKey("VCB", "swing", "rulebook-a")],
                                   signal_dir=self.signals, positions_dir=self.positions)
    document = load_rulebook_result(signal_artifact_path("VCB", "swing", self.signals))
    self.assertEqual((document["terminal_state"], document["empty"], document["candidates"],
                      document["top_rulebook_ids"], document["rejection_reason"]),
                     ("empty", True, [], [], "All saved candidates were removed by user."))
    self.assertTrue(validate_rulebook_document(document))

def test_stale_or_invalid_selection_writes_nothing(self):
    before = self._read_artifact("VCB", "swing")
    with self.assertRaisesRegex(ValueError, "is not present"):
        remove_saved_signal_candidates([SignalCandidateKey("VCB", "swing", "missing")],
                                       signal_dir=self.signals, positions_dir=self.positions)
    self.assertEqual(self._read_artifact("VCB", "swing"), before)
```

Create an OPEN and a CLOSED generic manual position, each holding a valid schema-5
reference to a selected candidate. Assert either status raises
`SignalRemovalBlockedError`, `error.protected` lists the requested immutable
identity, and two selected artifacts remain byte-equivalent to their snapshots.

Add recovery fixtures with two affected artifacts and a prepared journal: if one
artifact equals its `after` document and the other remains `before`, recovery
restores both `before` documents; if both equal `after`, recovery only clears the
journal. Assert a malformed journal raises without modifying any artifact.

- [ ] **Step 2: Run the new tests to verify the boundary is absent**

Run: `docker compose exec app python -m unittest tests.test_backtest_signal_removal -v`

Expected: FAIL because `signal_removal` and the validated administrative rewrite path do not exist.

- [ ] **Step 3: Expose the one-document validated atomic rewrite**

Add this public function beside `save_rulebook_result`; it deliberately preserves
every field supplied by the preflighted document:

```python
def replace_validated_rulebook_result(
    ticker: str, horizon: str, result: Mapping[str, object], output_dir: str,
) -> str:
    normalized_ticker = _normalize_ticker(ticker)
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    payload = json.loads(json.dumps(result))
    if payload.get("ticker") != normalized_ticker or payload.get("horizon") != horizon:
        raise ValueError("rulebook result identity differs from replacement target")
    validate_rulebook_document(payload)
    target = signal_artifact_path(normalized_ticker, horizon, output_dir)
    _write_json_atomically(target, payload)
    return str(target)
```

Export it in `__all__`. Do not alter `save_rulebook_result` or its worker
timestamp behavior.

- [ ] **Step 4: Implement the durable removal service**

Use a hidden root journal named `.backtest-signal-removal-transaction.json`. Its
strict JSON shape is:

```python
{
  "schema_version": 1,
  "operation": "backtest_signal_removal",
  "entries": [
    {"ticker": "VCB", "horizon": "swing", "before": {...}, "after": {...}}
  ]
}
```

Normalize and deduplicate selection mappings using this exact validation:

```python
def _candidate_key(value: SignalCandidateKey | Mapping[str, object]) -> SignalCandidateKey:
    if isinstance(value, SignalCandidateKey):
        value = {"ticker": value.ticker, "horizon": value.horizon,
                 "rulebook_id": value.rulebook_id}
    if not isinstance(value, Mapping) or set(value) != {"ticker", "horizon", "rulebook_id"}:
        raise ValueError("signal candidate selection is invalid")
    ticker = _normalize_ticker(value["ticker"])
    horizon = value["horizon"]
    rulebook_id = value["rulebook_id"]
    if horizon not in HORIZONS or not isinstance(rulebook_id, str) or not rulebook_id:
        raise ValueError("signal candidate selection is invalid")
    return SignalCandidateKey(ticker, horizon, rulebook_id)
```

Reject an empty selection. For every affected `(ticker, horizon)`, strict-load the
artifact, require `terminal_state == "success"`, and require every requested ID
exists in its full `candidates` list. Construct a deep-copied `after` document:
remove all requested IDs, sort the remaining candidates with `_candidate_rank`,
and set the first three IDs. If none remain, set only:

```python
after.update({
    "terminal_state": "empty", "empty": True,
    "failure_reason": None,
    "rejection_reason": "All saved candidates were removed by user.",
    "candidates": [], "top_rulebook_ids": [],
})
```

Validate every `before` and `after` document before touching disk. Call
`load_all_positions(positions_dir)` once and treat every record with a mapping
`signal_reference` of schema version 5 and matching ticker/horizon/rulebook ID
as protected, regardless of its `status`. Raise one error containing the sorted
unique protected keys before creating a journal or replacement file.

Write the validated journal atomically and fsync it using the same temporary-file
plus `os.replace` pattern as persistence. Then call
`replace_validated_rulebook_result` for every sorted entry. Delete the journal
only after all replacements succeed. If an exception occurs after the journal
exists, retain it and re-raise; the next reader restores a coherent state.

`recover_pending_signal_removal` must first validate the journal path is the
expected canonical path for each entry (never accept an arbitrary file path),
and validate every stored `before`/`after` document. It then compares the
current parsed documents exactly:

- all `after`: deletion completed; remove only the journal;
- all `before`: no deletion was applied; remove only the journal;
- any mixed state: rewrite every `before` document through
  `replace_validated_rulebook_result`, then remove the journal;
- missing, changed-to-third-value, or malformed document/journal: raise with no
  additional artifact write and leave the journal for diagnosis.

This yields a recoverable all-or-nothing logical transaction even if a process
stops between independent file replacements. Do not create a generic migration
framework or touch legacy artifacts.

- [ ] **Step 5: Run the removal boundary tests**

Run: `docker compose exec app python -m unittest tests.test_backtest_signal_removal -v`

Expected: PASS. The suite proves reranking, final-empty conversion, stale-input
no-write, OPEN/CLOSED blocking, and journal recovery.

### Task 2: Make catalog readers recovery-aware

**Files:**
- Modify: `app/backtest_engine/signal_catalog.py:1-168`
- Modify: `tests/test_backtest_signal_removal.py`

**Consumes:** `recover_pending_signal_removal(signal_dir)` from Task 1.

**Produces:** Catalog reads that never present a mixed transaction as a valid
signal list.

- [ ] **Step 1: Add a failing catalog recovery test**

Create a prepared mixed journal fixture as in Task 1, then call
`list_current_signal_set_rows(self.signals)`. Assert it exposes the pre-removal
rows after recovery and the journal no longer exists. Create a corrupt journal
fixture and assert the catalog returns no `valid` rows plus a warning beginning
`Signal removal recovery is required:`.

- [ ] **Step 2: Run the focused catalog test**

Run: `docker compose exec app python -m unittest tests.test_backtest_signal_removal.SignalRemovalCatalogRecoveryTests -v`

Expected: FAIL because catalog currently reads paths without transaction recovery.

- [ ] **Step 3: Recover before each schema-5 catalog entry point**

At the beginning of `list_current_signal_set_rows`, call recovery before
`ensure_result_root` traversal. On `OSError`, `TypeError`, or `ValueError`, return
the standard catalog shape with empty `valid`/`terminal`/`invalid` lists and one
warning:

```python
return {
    "valid": [], "terminal": [], "invalid": [],
    "warnings": [f"Signal removal recovery is required: {error}"],
}
```

Call recovery in `list_saved_signal_options` and
`tickers_with_no_saved_signal` too, letting their existing consumer-safe failure
behavior apply: options returns an empty list; the missing-ticker helper treats
the ticker as missing. Do not change catalog ordering or the Top-3 projection.

- [ ] **Step 4: Run Task 1 and Task 2 tests**

Run: `docker compose exec app python -m unittest tests.test_backtest_signal_removal -v`

Expected: PASS.

### Task 3: Add exact View Signals projection and selection helpers

**Files:**
- Modify: `app/pages/backtest_lab.py:44-70,494-568`
- Modify: `tests/test_backtest_page.py:210-350`

**Consumes:** Catalog row `Rulebook`, `Ticker`, and `Horizon`; `SignalCandidateKey`
from Task 1.

**Produces:** `_parse_view_signal_tickers`, exact `_filter_view_signal_rows`,
selection-safe table rows, and fixed/default column constants.

- [ ] **Step 1: Write failing pure-helper tests**

Replace the partial-ticker expectation with exact membership tests:

```python
def test_view_ticker_parser_uses_exact_comma_or_space_membership(self):
    self.assertEqual(backtest_lab._parse_view_signal_tickers(" vcb, FPT  vcb "),
                     ("VCB", "FPT"))
    rows = [{"Ticker": "VCB", "Horizon": "Swing"},
            {"Ticker": "VC", "Horizon": "Swing"},
            {"Ticker": "FPT", "Horizon": "Mid-term"}]
    self.assertEqual(backtest_lab._filter_view_signal_rows(rows, "vcb fpt", "Both"),
                     [rows[0], rows[2]])
```

Assert invalid-looking/unknown token text is simply normalized and yields no
match; it must not be sent to a database. Add projection assertions that each
row retains private immutable fields `_ticker`, `_horizon`, `_rulebook_id`, and
that `_view_signal_table_rows` yields `No` 1 then 2 and `Select == False`.
Assert the default columns exclude `Evidence` and `Theme` while fixed columns
remain first as `("No", "Select", "Ticker")`.

- [ ] **Step 2: Run the page pure-helper test slice**

Run: `docker compose exec app python -m unittest tests.test_backtest_page.BacktestPageTests.test_view_ticker_parser_uses_exact_comma_or_space_membership -v`

Expected: FAIL because the page only accepts a three-character substring filter.

- [ ] **Step 3: Implement parser, projection identity, and column helpers**

Add these constants without changing other page keys:

```python
_VIEW_SIGNAL_FIXED_COLUMNS = ("No", "Select", "Ticker")
_VIEW_SIGNAL_OPTIONAL_COLUMNS = (
    "Horizon", "Train-test", "n", "Win rate %", "Profit %", "Sharpe",
    "Evidence", "Theme",
)
_VIEW_SIGNAL_DEFAULT_COLUMNS = _VIEW_SIGNAL_OPTIONAL_COLUMNS[:-2]
```

Use `re.split(r"[\\s,]+", value.strip())` to parse nonempty tokens, uppercase
them, and retain first occurrence via `tuple(dict.fromkeys(tokens))`. Do not use
`_uppercase_ticker_state` or `max_chars` for this field. Filter with
`not requested or str(row["Ticker"]).upper() in requested`, then the unchanged
horizon condition.

Extend `_view_signal_rows` with private values copied only from catalog data:

```python
"_ticker": str(row["Ticker"]),
"_horizon": "swing" if row["Horizon"] == "Swing" else "midterm",
"_rulebook_id": str(row["Rulebook"]),
```

Create `_view_signal_table_rows(rows)` that adds `No` and `Select` and never
renders private fields. Create `_view_signal_key(row)` that returns the
`SignalCandidateKey` from those private fields. Reject malformed catalog rows
with `ValueError` rather than substituting an identity.

- [ ] **Step 4: Run the complete View Signals helper tests**

Run: `docker compose exec app python -m unittest tests.test_backtest_page -k view_signal -v`

Expected: PASS after updating the prior substring/projection expectations.

### Task 4: Render native column controls, visible-only selection, and safe removal

**Files:**
- Modify: `app/pages/backtest_lab.py:569-600,1598-1645`
- Modify: `tests/test_backtest_page.py:258-340`

**Consumes:** Task 1 removal service and errors; Task 3 projected rows and
immutable keys.

**Produces:** An interactive View Signals table with user-controlled optional
columns and a disabled-until-selected bulk-removal action.

- [ ] **Step 1: Write failing Streamlit UI tests**

Use `AppTest.from_string` and injectable functions to assert:

```python
app = AppTest.from_string(
    "import pages.backtest_lab as lab\n"
    "lab.list_current_signal_set_rows = lambda _dir: catalog\n"
    "lab._render_view('signals', 'positions', remove_fn=lambda *_a, **_k: None)\n"
).run()
self.assertEqual([item.label for item in app.text_input], ["Ticker"])
self.assertEqual([item.label for item in app.multiselect], ["Columns"])
self.assertEqual(app.multiselect[0].value,
                 ["Horizon", "Train-test", "n", "Win rate %", "Profit %", "Sharpe"])
self.assertEqual(list(app.data_editor[0].value.columns)[:3], ["No", "Select", "Ticker"])
self.assertTrue(next(button for button in app.button
                     if button.label == "Remove selected signals (0)").disabled)
```
Then check that toggling the visible-row header checkbox marks only filtered
visible row identities, its button label becomes `Remove selected signals (N)`,
and a filter change cannot retain an invisible selection. Check a successful
injected remover receives only immutable keys, clears selection, and reruns;
check `SignalRemovalBlockedError` reports all protected identities and clears
selection without calling a second removal.

- [ ] **Step 2: Run the View Signals AppTest slice**

Run: `docker compose exec app python -m unittest tests.test_backtest_page -k view_signals -v`

Expected: FAIL because the current page has a static dataframe and no removal action.

- [ ] **Step 3: Replace the static dataframe rendering with native editor controls**

Change `_render_view` signature to:

```python
def _render_view(
    signal_dir: str, positions_dir: str = "backtest-positions", *,
    remove_fn: Callable = remove_saved_signal_candidates,
    rerun_fn: Callable = st.rerun,
) -> None:
```

Use a `st.multiselect("Columns", _VIEW_SIGNAL_OPTIONAL_COLUMNS,
default=_VIEW_SIGNAL_DEFAULT_COLUMNS, ...)`; form the displayed order from
fixed columns plus its result. Use one checkbox labelled `Select all visible`
immediately above the table as the native header-level control. It may only add
or remove keys from the *current filtered visible key set*; it must never select
hidden rows.

Render with `st.data_editor`, not `st.dataframe`:

```python
edited = st.data_editor(
    frame.loc[:, visible_columns], hide_index=True, use_container_width=True,
    height=720, key=table_key,
    column_config={"Select": st.column_config.CheckboxColumn("Select"),
                   "No": st.column_config.NumberColumn("No", format="%d")},
    disabled=[column for column in visible_columns if column != "Select"],
)
```

Keep a session-state set of immutable key tuples, prune it to the visible key
set on each filter signature change, and rebuild `Select` from that set before
each editor render. This is the required guard against removing an invisible
prior-filter row. Compare a sorted full-catalog identity tuple on rerun; when it
changes, clear the selection and editor key state. Never take a key from `No` or
the displayed ticker text.

After reading `edited`, translate checked records using the private backing
frame to `SignalCandidateKey` values. Place the exact button text
`Remove selected signals (N)` below the table and disable it when `N == 0`.
On click, invoke `remove_fn(selected, signal_dir=signal_dir,
positions_dir=positions_dir)`. On success clear all View Signals selection and
table keys, show `st.success`, then `rerun_fn()`. On
`SignalRemovalBlockedError`, clear selection, emit one `st.error` containing
every sorted `ticker / horizon / rulebook_id`, and do not rerun. On
`OSError`, `TypeError`, or `ValueError`, clear selection and show the error;
the service's journal recovery protects the next catalog read.

Add optional `remove_signals_fn` to `render_backtest_page` and pass it plus
`positions_dir`/`rerun_fn` into `_render_view`, preserving all other dependency
injection signatures.

- [ ] **Step 4: Run UI tests and the affected page regression**

Run: `docker compose exec app python -m unittest tests.test_backtest_page -v`

Expected: PASS. The previous terminal-row test must now assert one
`data_editor`, fixed first columns, default absence of Evidence/Theme, and
height 720 rather than the old static dataframe columns.

### Task 5: Integrated verification and context handoff

**Files:**
- Modify: `FOCUS.md`
- Modify: `ai-context/current-status.md` only if a real residual issue is discovered

**Consumes:** Tasks 1–4.

**Produces:** Evidence that the UI and storage boundary are complete, and an
accurate project checkpoint.

- [ ] **Step 1: Run focused engine and page tests**

Run:

```powershell
docker compose exec app python -m unittest tests.test_backtest_signal_removal -v
docker compose exec app python -m unittest tests.test_backtest_page -v
```

Expected: both PASS. Record test totals and commands actually used; do not claim
a Docker result unless the command ran successfully.

- [ ] **Step 2: Run the canonical non-writing regression gate**

Run: `docker compose exec app python -m unittest discover -s tests -v`

Expected: PASS with no new failures. If this environment is unavailable, stop
and record the exact blocker in `FOCUS.md`; do not call the change complete.

- [ ] **Step 3: Perform the required self-criticism**

Review these failure modes against tests and implementation:

1. a selected non-Top-3 candidate cannot be forged from UI state because the
   service re-loads full artifacts and verifies IDs;
2. an OPEN **or** CLOSED schema-5 position blocks the full batch before journal
   creation;
3. a final removal is a validated `empty` artifact, never an unlink;
4. a crash after one of several replacements returns the next catalog read to
   either all-before or all-after, never a mixed user-visible set;
5. table ordinal, filter text, and row order never become candidate identity;
6. `Evidence` and `Theme` remain display-only optional columns and no removal
   changes eligibility/evidence metadata.

Correct any demonstrated defect before progressing. Do not expand scope to
legacy position/artifact migration or rulebook recalculation.

- [ ] **Step 4: Update active context**

Update the current View Signals entry in `FOCUS.md` with completed tasks,
actual verification results, the journal safety behavior, and the exact next
stopping point. Add to `ai-context/current-status.md` only a reproducible
remaining issue; otherwise leave it unchanged.

## Plan self-review

- **Spec coverage:** Task 3 covers exact multi-ticker filtering, column defaults,
and row ordinals. Task 4 covers native selection, select-all-visible, disabled
action, and messages. Task 1 covers full-candidate removal, reranking,
final-empty conversion, position protection, validation, and all-or-nothing
recovery. Task 2 ensures no catalog reader displays an interrupted mixed state.
Task 5 verifies and records the result.
- **Blind-spot correction:** Independent `os.replace` calls cannot by themselves
be atomic across multiple artifacts. The plan therefore uses a validated durable
before/after journal and deterministic rollback on the next reader, rather than
claiming that a sequence of per-file atomic writes is automatically batch-atomic.
- **Type consistency:** The UI creates `SignalCandidateKey`; the service accepts
that type or the exact mapping shape and returns `SignalRemovalResult`. The
position preflight uses complete validated position records, while persistence
continues to own all schema-5 validation and artifact paths.
- **Scope check:** The feature spans one page projection and one schema-5 write
boundary; they must ship together because a selectable static view without the
safe domain mutation would be unusable. No unrelated subsystem is included.
