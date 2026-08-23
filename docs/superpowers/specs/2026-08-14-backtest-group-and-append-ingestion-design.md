# Backtest Group Management and Append-Only Data Ingestion Design

Date: 2026-08-14
Status: Design confirmed; awaiting written-spec review. Implementation not started.

## Goal

Add user-managed ticker Groups to Backtest without altering strategy, theme, or
rerun logic. Improve Data Page ingestion so every Get data run preserves old
market rows, appends only new rows, and commits Stock plus VN-Index additions
atomically.

## Non-goals

- Group does not affect certification, indicators, themes, replay, positions,
  ranking, validation advice, trading rules, or Backtest scheduling.
- Group is not a theme property and is not duplicated into the no-theme or
  background-theme signal artifacts.
- Ingestion never updates existing OHLCV values and does not repair historical
  gaps before a ticker's already-stored latest date.
- No new dependency, Docker, credential, `common_queries.py`, BIGINT storage,
  or commit change.

## Backtest Group Contract

### Group JSON source of truth

Backtest result storage is centralized under `app/backtest-result`:

```text
app/backtest-result/
  ticker-signals/<TICKER>/<TICKER>_signals_<theme>.json
  ticker-group/<SAFE-UPPERCASE-SLUG>-<group-uuid>.json
```

`group-uuid` is a system-generated UUID and is never displayed in the UI. The
safe filename slug is derived from the Group name: uppercase, Unicode-normalized
to ASCII where possible, every non-alphanumeric run replaced by one `-`, trimmed
of `-`, and fallback `GROUP` if empty. Thus `Bank & Finance` can be
`BANK-FINANCE-<uuid>.json`, while the UI retains its full uppercase display
name. The UUID, not the slug, establishes uniqueness.

Each payload contains `schema_version`, hidden `group_id`, uppercase
`group_name`, normalized `tickers`, empty-object `metadata` reserved for later
use, and an `Asia/Ho_Chi_Minh` update timestamp. A ticker's effective Group ID
is the UUID of the one Group JSON that lists it. There is no per-ticker metadata
file, database column, or duplicated Group field in a signal artifact.

### One-time V2 artifact migration

The four existing schema-v2 artifacts (`BID`, `TCX`, `VCB`, and `VCI`) move
byte-preserved from `app/ticker-signals` to
`app/backtest-result/ticker-signals`. They create no Group JSON and resolve as
`N/A` until a later qualifying Backtest assigns a real Group. Historical
`app/backtest-status` request/result JSON remains untouched, even though it
continues to record historical old output paths.

Because four independent renames cannot be one filesystem-atomic operation, a
short-lived migration journal records every source, target, and checksum before
any move. It atomically moves each file within the same filesystem, verifies the
target checksum, then removes the journal only after all four moves succeed.
Startup/first catalog access completes an interrupted journal before reading
the new root. The old artifact root is no longer read after a successful
migration; its empty directory may remain on disk.

Group input is free text. Trim then uppercase it for display/storage, so `Bank`
and `bank` both reuse `BANK` and its UUID. Blank or case-insensitive `N/A`
means no Group: no Group JSON membership. A missing historical membership also
reads as `N/A` and is not rewritten merely by opening a catalog. UUID filenames
keep arbitrary Group names out of filesystem paths.

Each ticker may occur in at most one Group JSON; ticker lists are stored in
deterministic alphabetical order. Empty Group JSON remains after its last ticker
leaves, preserving metadata and allowing later reuse. Duplicate normalized
Group names, duplicate ticker membership, malformed JSON, or duplicate UUIDs
are Group-data errors; the system refuses an ambiguous update.

### Batch, move, and update semantics

`BacktestBatchConfig` carries one requested Group name for its one-to-five
tickers. The worker serializes it as management metadata only; it never enters
the strategy, theme, replay, or saved signal-set payload.

After each ticker's final attempt (including its one allowed retry), change its
membership only when an artifact written by that attempt has a non-empty
`signal_sets` list. A partial themed run qualifies when its new no-theme
artifact is nonempty. All-empty/no-artifact results retain prior membership;
stale output from an earlier run never qualifies a move. A Group-write failure
is a recorded ticker failure and follows the existing retry behavior.

A qualifying update can add, move, or ungroup a ticker, potentially changing
two Group JSON files. The store writes/fsyncs a short-lived move journal in
`app/backtest-result/ticker-group`, holding validated before/after payloads,
atomically replaces every affected Group JSON with its after payload, then
fsyncs/removes the journal. Before every Group read or write, a pending journal
is recovered by completing its recorded after state. This provides crash
recovery rather than pretending that independent file replaces are atomic. Empty
prior Groups are retained.

### Catalog and Collect Signals UI

Collect Signals gets a Group text input between Horizon and Action. It begins
as `N/A`, follows the same busy-job lock as the other request-defining inputs,
and applies to the whole submitted ticker batch.

The existing View Signals popover gets a Group selectbox beside its ticker
textbox. Its values are `All`, then `N/A` when ungrouped rows exist, then unique
Group names represented by the currently listed signal tickers. Matching is
case-insensitive and displays uppercase names; `All` is the default. Group is
an internal catalog row attribute for filtering only; no Group table column is
added by this request. Invalid artifacts retain their ticker Group when Group
JSON is readable, or `N/A` otherwise.

The same catalog renderer is reused in Validate Signals. It receives a key
prefix so Collect and Validate popovers do not collide in Streamlit session
state.

### Validate Signals multi-ticker flow

Replace the single Ticker input with an uppercase, comma/space-separated
Tickers input using the existing ordered, unique 1–5 parser; preserve current
`FPT` as its default. One click validates the input order sequentially. The
existing progress bar advances per ticker and is removed on completion or
error. Stored request/result state uses the ticker tuple and theme checkbox,
preventing stale results after any selection change.

Each ticker renders its No theme result first, then its VN-Index AND result
when requested. A failing/unavailable ticker surfaces its own clear result and
does not stop the remaining selected tickers.

Validate adds a Group dropdown beside the Tickers textbox. Its default is `-`,
meaning no Group selection and the existing user-editable one-to-five Tickers
flow. Other choices are `N/A` plus real uppercase Group names from valid Group
JSON. Selecting a real Group fills Tickers from its Group JSON membership;
selecting `N/A` fills Tickers from all current signal-artifact tickers with no
Group membership. While a Group (including `N/A`) is selected, Tickers is
disabled so the requested group list cannot be edited.

Every selected Group list is capped at fifteen tickers. If it contains sixteen or
more, validation does not start; the UI displays the complete resolved ticker
list and tells the user to reduce the Group before manually rerunning. A Group
with fifteen or fewer tickers runs in resolved deterministic ticker order, one at a
time. For every selected member, validation first checks for a current saved
signal set. A member with none is skipped without aborting later members; after
the run, UI lists every skipped ticker. A saved artifact that is empty or
unreadable is treated as no saved signal for this purpose.

## Append-Only Data Ingestion Contract

### Existing data and deduplication

Get data never drops `trading_data`. Schema verification remains
non-destructive. Existing `(ticker, date)` rows are immutable and remain
unchanged. A single bound query reads latest stored date per ticker once. New
imports retain only rows after that ticker's latest stored date; a new ticker
uses the selected Year gaps cutoff. `ON CONFLICT (ticker, date) DO NOTHING`
remains the final race-safe guard.

This is deliberately append-only: it does not backfill an older missing date
behind a ticker's latest stored session. A later dedicated repair workflow can
address that separate data-quality problem.

### Transaction and performance

Both remote source ZIPs download and extract before database mutation. Then one
`get_engine_with_retry()` raw connection owns one database transaction. It
verifies/creates the static schema/index non-destructively, creates a
transaction-scoped staging table, stages Stock and VN-Index chunks, and inserts
eligible rows into `trading_data`. Download/extract failure opens no transaction;
parse, validation, stage, index, or insert failure rolls back every new row
from this Get data run. Old rows remain intact. The UI shows a clear failure
stating that no new data was saved and the user must rerun manually.

The remote CafeF flow supplies an up-to-date snapshot rather than a delta
endpoint. Each run must still download the source snapshot, but one latest-date
lookup and chunk filtering avoid staging and conflict-checking historical rows
already stored locally. The existing single ingestion lock remains the in-process
guard; the database primary key remains the cross-process consistency guard.

Progress becomes append truthful: start, schema/old-data preserved, Stock
staged, VN-Index staged, commit complete, done. There is no reset phase.

## Error handling

- Invalid Group JSON/artifact data does not hide valid catalog rows; it is
  marked invalid through the existing catalog warning path.
- Group writes use atomic temporary-file/fsync/replace operations plus the
  durable cross-file move journal.
- One invalid ticker validation reports its ticker-specific issue and processing
  continues for later selected tickers.
- Ingestion returns failure after rollback and leaves the UI unlocked for a
  manual rerun; it never silently retries network or database work.

## Test evidence required before completion

- Backtest config/worker Group serialization, UUID creation/reuse, uppercase
  normalization, safe-slug filename creation, `N/A` no-membership behavior,
  empty-Group retention, duplicate-membership rejection, crash-journal recovery,
  non-empty-current-attempt-only moves, and partial themed result behavior.
- Byte-preserved migration of the four current V2 artifacts, interrupted-
  migration recovery, new-root-only catalog reads after success, and no
  historical `backtest-status` rewrite.
- Catalog Group options/filtering in both popovers, independent Streamlit keys,
  and `N/A` fallback.
- Validate 1–5 ordered tickers, per-ticker error isolation, no-theme-before-
  themed rendering, stale-state rejection, and cleaned-up progress; plus Group
  dropdown `-`/real/`N/A` resolution, locked group Tickers, all-group fifteen-
  ticker cap and complete over-cap list, sequential group validation, and skipped-
  missing-signal summary.
- Seeded append ingestion keeps existing raw BIGINT OHLCV values unchanged,
  adds only later rows, ignores a duplicate conflict, and rolls back every new
  Stock/VN-Index row when a later stage fails.
- Existing Backtest/Data Page UI and focused engine regression gates, syntax,
  whitespace, protected-boundary, and non-writing live health checks.

## Spec Self-Review

- No Group ID appears in UI or signal artifacts; Group JSON owns membership.
- `N/A` unambiguously means no membership, while an empty real Group persists.
- The move journal supplies crash recovery for multi-file writes.
- The V2 migration preserves bytes and uses its own journal/checksum recovery;
  old job-status records remain historical evidence, not rewritten data.
- A fresh qualifying artifact, not stale output, is required for a Group move.
- Group-selected validation cannot silently run an edited or over-cap Group;
  it locks the resolved list and reports skipped no-signal tickers.
- Data runs preserve existing BIGINT data and have one Stock-plus-VN-Index
  mutation transaction; existing price scaling is not changed.
