# Backtest Multi-Group Membership Design

Date: 2026-08-14  
Status: Design confirmed; awaiting written-spec review. Implementation not started.

## Goal

Allow one ticker to belong to zero or more named ticker Groups while retaining
the existing one-ticker-to-many-signal-sets relationship. A named Group also
continues to contain zero or more tickers. Groups remain management metadata:
they do not change certification, strategies, themes, replay, positions, or
Backtest scheduling.

## Relationship contract

```text
Ticker 1 --- n saved signal sets
Ticker 1 --- n named Groups
Named Group 1 --- n tickers
```

`N/A` is not a stored Group. It is the derived set of current signal-artifact
tickers that belong to zero named Groups. Therefore a ticker in one or more
named Groups is never included by an `N/A` filter or validation selection.

## Persistence design

Group JSON remains the only membership source of truth under
`app/backtest-result/ticker-group/`. The schema, UUID identity, uppercase
display name, safe filename, metadata placeholder, timestamp, and atomic file
replacement stay unchanged. No database column, per-ticker index JSON, or
Group value is added to a signal artifact.

Each Group JSON retains a deterministic, duplicate-free ticker list. The group
reader will still reject duplicate Group IDs, duplicate normalized Group names,
malformed payloads, and a duplicated ticker within one Group file. It will no
longer reject a ticker appearing in separate valid Group files.

The current move-style assignment operation becomes add-only:

- a successful qualifying Collect Signals run with a named Group adds that
  ticker to the selected Group, creating that Group if necessary;
- it retains every other named Group membership for the ticker;
- a blank or `N/A` Group value writes no membership change;
- empty named Group files remain reusable;
- no removal UI or removal API is introduced in this scope.

The existing journal and recovery path continue to protect each Group JSON
update. An add affects only the selected Group file, so it does not need a
new index or a cross-file membership move.

The pipeline continues to attempt a Group update only after that ticker's
final attempt produced at least one current certified signal set. An empty or
failed run preserves every existing named membership. A Group-store failure
continues to be a per-ticker terminal failure under the existing retry flow.

## Readers and UI behavior

Replace the ambiguous singular ticker-Group lookup with a deterministic tuple
of all named Groups for the ticker. Internal catalog rows carry that tuple only
for filtering; the View Signals table does not show a Group column and still
renders one row per ticker/theme/signal-set candidate.

`Ticker Groups` filter choices are `All`, `N/A` when ungrouped rows exist, and
the represented named Groups. A named choice retains every row whose ticker is
a member of that Group. `N/A` retains only rows with no named memberships. A
ticker in `BANK` and `ETF VN30` therefore appears once under `All`, once when
filtering `BANK`, and once when filtering `ETF VN30`; it never appears under
`N/A`.

Validate Signals keeps its current Group selector. Resolving a named Group
returns that Group file's ticker list once, in deterministic order. Resolving
`N/A` returns only signal-artifact tickers not present in any named Group file.
The existing fifteen-ticker cap, locked input, sequential execution, and
missing-artifact skip behavior remain unchanged.

## Non-goals

- Removing or replacing a ticker's named Group memberships.
- A Group-management page, Group chips, or Group display column in View
  Signals.
- Any change to saved signal schemas, position links, trading rules, prices,
  SQL, BIGINT scaling, Docker, credentials, dependencies, or commits.

## Test evidence required

1. A ticker can be added to `BANK` and `ETF VN30`; both Group JSON files retain
   it and the named-Group lookup returns both names deterministically.
2. Adding a third named Group never evicts existing memberships; blank and
   `N/A` inputs do not erase them.
3. Duplicate ticker entries within one Group file remain invalid, while the
   same ticker in two valid Group files is accepted. Existing UUID/name/schema
   validation and journal recovery remain covered.
4. Named Group and derived `N/A` validation resolution produce disjoint,
   deterministic ticker lists.
5. The catalog emits one row per signal candidate, hides Group data from the
   displayed table, and correctly filters a multi-group ticker without
   duplicate rows.
6. The batch pipeline adds the selected named Group only after a qualifying
   per-ticker result and preserves prior memberships on empty/failed results.
7. Focused Backtest regression tests, compilation, whitespace, and protected
   boundary checks pass.

## Spec self-review

- The requested n-to-n relationship is explicit and conflicts with neither
  current V2 signal candidates nor Group JSON ownership.
- `N/A` is defined only once as a derived no-membership set; it never competes
  with named Groups or erases them.
- Catalog filtering cannot duplicate a signal row because memberships remain
  internal attributes rather than expanded rows.
- Add-only semantics prevent a qualifying rerun from silently removing a
  separately meaningful Group membership.
- Removal, a central index, and artifact/schema changes are explicitly out of
  scope, avoiding an unapproved management subsystem.
