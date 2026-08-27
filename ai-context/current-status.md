﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿# Current Project Status

This document provides a snapshot of the project's current state, including finished tasks, ongoing work, known issues, and next steps.

## 0. Active execution gate

- **Collect Signals Edit Group: complete and verified (2026-08-23).** Named
  Groups have a hidden-until-selected Edit Group popover with draft Add/Remove
  and one atomic Save; empty Groups remain selectable. Collect rows are now
  Tickers/Group/Edit Group then Horizon/Range/Run Backtest. Docker store/page
  evidence: 39/39 pass; compilation passed. Verification:
  `docs/superpowers/reports/2026-08-23-collect-signals-edit-group-verification.md`.

- **Validate Signals Position-Action Filter: complete and verified
  (2026-08-23).** Validate now places Tickers and Ticker group on its first
  row, then Monitoring classifications, Position actions, and Validate on its
  second. Position actions is a local `ALL`/`can BUY`/`expired BUY`/`can SELL`/
  `HOLD` dropdown ANDed with classifications over the latest cached result; it
  never replays validation and a fresh session stays empty. Docker page
  evidence: 37/37 pass. Design, plan, and verification:
  `docs/superpowers/specs/2026-08-23-validate-signals-position-action-filter-design.md`,
  `docs/superpowers/plans/2026-08-23-validate-signals-position-action-filter.md`,
  and
  `docs/superpowers/reports/2026-08-23-validate-signals-position-action-filter-verification.md`.

- **Current Positions SELL Default and Validate Actions: complete and verified
  (2026-08-23).** New OPEN Position renders an empty SELL date (`None`) and
  still persists null SELL fields. Validate Signals now renders progress for
  every sequential attempted ticker, including failures; its first result line
  is Monitoring plus `can BUY`, `expired BUY`, `can SELL`, or `HOLD`, and its
  diagnostic JSON is collapsed. `can SELL` is read-only advice based on a
  matching OPEN rulebook position's frozen SL/TP or failed current literal
  entry; it does not execute a SELL. Docker focused evidence: 40/40 pass.
  Design, plan, and verification:
  `docs/superpowers/specs/2026-08-23-current-positions-sell-default-and-validate-actions-design.md`,
  `docs/superpowers/plans/2026-08-23-current-positions-sell-default-and-validate-actions.md`,
  and
  `docs/superpowers/reports/2026-08-23-current-positions-sell-default-and-validate-actions-verification.md`.

- **View Signals Ticker and Horizon Filters: complete and verified
  (2026-08-23).** The shared read-only View Signals table now supports an
  optional uppercase partial Ticker filter and a Horizon select box of `Both`
  (default), `Swing`, and `Mid-term`. The filters intersect in-memory against
  the existing projected valid rows; warnings and terminal-row suppression are
  unchanged. Docker page evidence: 33/33 pass; module compilation passed.
  Design, plan, and verification:
  `docs/superpowers/specs/2026-08-23-view-signals-ticker-horizon-filter-design.md`,
  `docs/superpowers/plans/2026-08-23-view-signals-ticker-horizon-filter.md`,
  and
  `docs/superpowers/reports/2026-08-23-view-signals-ticker-horizon-filter-verification.md`.

- **Horizon V3 exploratory multi-rulebook: complete (2026-08-22).** The
  approved schema-4 design and plan are implemented and verified. The
  verification report is
  `docs/superpowers/reports/2026-08-22-horizon-v3-exploratory-multi-rulebook-verification.md`.
  Legacy V3 artifacts and job sidecars have been replaced by
  `requires_regeneration` markers without payload parsing; fresh VCB Swing
  collection succeeded with 15 candidates and a clean audit.
- **Flexible Rulebook Core Plan Tasks 3–7 verified complete (2026-08-27).**
  This is a new isolated daily Swing research subsystem, not a V3 extension.
  Task 1 is complete: the isolated `flexible_rulebook` package supplies immutable portable
  rulebook, feature-source/build, split, budget, metric, and evaluation
  contracts; full-SHA-256 canonical rulebook IDs; and display-only deterministic
  animal aliases. Its Docker contract gate passes 25/25 and container
  compilation passes. Task 2 adds Flexible-owned bounded history quality,
  ordered raw-OHLCV fingerprints, evidence anchors, and deterministic native-bar
  splits. It may call only the existing bounded raw-history loader; it imports no
  V3 validation or audit logic. Malformed raw data is invalid; >1% OHLC ordering
  mismatch or >=15% adjacent close discontinuity is display-only; warnings stay
  usable. Focused Docker contracts/history evidence passes 36/36 and container
  compilation passes. Catalog-v1 now locks EMA 3/8, 5/13, 5/21, 8/21;
  RSI 5/9/14 at 50/52/55; breakout 10/20/40; volume 5/10/20 at
  1.10/1.20/1.30; ADX(14) at 15/20/25; mirrored exits; ATR(14); and timeouts
  10/15/22/30 with BUY/gate caps two. `features.py` now resolves only
  source/contract-compatible computed primitive components, constructs a
  request-scoped receipt, and never persists raw OHLCV/masks/trades. Cache age
  only offers reuse after a fresh source fingerprint. Corrupt, partial, locked,
  low-space, write, and non-deterministic build states retain safe in-memory or
  prior valid components. Task 4 has fixed `atr-wilder-v1` ATR(14), reference
  execution, and an inert event-plan identity guard. Its fixtures cover
  next-open, E+3, technical queue/discard, trailing, gaps, deadline precedence,
  sparse/dense signals, interruption, and source/receipt/mask/partition checks.
  Host and canonical Docker focused Flexible gate pass 73/73 plus compilation.
  Task 6 now has its finite ATR automatic variant: stop 2.0×, target 3.0×,
  trailing absent; no-price-exit remains permitted by the approved optional
  price-exit grammar. Its first lazy CandidateSpace/ticker-seeded affine
  frontier Docker tests pass 4/4. Task 6 is now complete: lazy multi-axis
  CandidateSpace, seeded structural quota order, continuation-safe affine slots,
  deadline terminal truth, compact rejections, and frozen typed train/test
  evidence. Core Docker gate passes 80/80 plus compilation. Task 7 now writes
  immutable definitions and qualified/explicitly-saved signal evidence, requires
  frozen assignment provenance plus a prewritten feature receipt for ledger
  outcomes, records verified immutable Continue selection chains, and excludes
  cache paths from signal-set traversal. Core Flexible Docker gate passes 96/96
  plus compilation. Campaign manifest/resume cursor wiring belongs to the
  dependent Campaigns and Current Scan plan. Task 5 is complete: immutable train/test
  trade evidence, scope validation, first-overlap pairing, exact 75% duplicate
  filtering, and training-only Top 3 selection. Focused Flexible gate passes
  56/56 plus compilation. Core portable-rulebook
  discovery/qualification must finish before durable campaigns/current Group
  BUY Scan/UI. The approved amendment adds lazy seeded
  structurally stratified CandidateSpace/FrontierAssignment discovery,
  cursor-based continuation, native-bar split boundaries, explicit exit
  precedence, and Top-3 training timing distinctness: one-to-one paired training
  holding windows are hard near-duplicates at overlap_ratio >= 0.75; training
  metrics choose the representative and test remains evidence.
  
  Every new operation fresh-loads/fingerprints ordered raw OHLCV before
  indicator-cache use. Individual PrimitiveComponents persist/reuse only after
  exact source/build-contract validation; FeatureBundles are request-scoped
  assembly only. <=24 hours gives an explicit Reuse/Recalculate choice, while
  expired/missing/corrupt/mismatched components rebuild. Continue/Resume
  validates its frozen source and either uses/rebuilds identical primitives
  without prompting or stops as source_changed; it never moves to latest data.
  Historical evidence uses append-safe prefix anchors, and Top-3 membership is
  stored only in immutable campaign-chain SelectionSnapshots: a completed cap is
  `complete_assigned_window`, never a global-search claim.
  The performance amendment freezes a FeaturePlan/FeatureResolutionReceipt before
  a candidate commits, so Resume/Continue after cache eviction must reproduce
  identical component digests. It keeps a reference executor as the oracle;
  event-driven execution and exact-prefix append extension are optional,
  disabled until deterministic parity and measured benchmark gates pass. Fixed
  candidate caps require cold p99 preflight plus at least 100 maximal-slot
  samples; warm cache cannot increase the search scope.
  Each ticker has a 4h30 candidate-admission deadline and 4h55 normal terminal
  limit, with fixed benchmark-backed caps/quotas unaffected by cache warmth.
  The standalone UI is planned as radio/selectbox workspaces, not eager tabs.
  No V3, database schema, Docker, dependency, campaign, or UI source may change.
  Design: `docs/superpowers/specs/2026-08-25-flexible-rulebook-design.md`.
  Plans: `docs/superpowers/plans/2026-08-25-flexible-rulebook-core.md` then
  `docs/superpowers/plans/2026-08-25-flexible-rulebook-campaigns-and-current-scan.md`.
- **Flexible Campaigns and Current Scan Task 1: in progress (2026-08-27).**
  Frozen CampaignRequest/Manifest contracts, semantic request hashes, lifecycle
  transitions, item-state validation, and source-verified Continue cursors are
  isolated in `flexible_rulebook.campaigns`. Cache diagnostics do not affect
  identity. Focused Docker evidence passes 8/8 plus compilation; durable
  manifest persistence and reconciliation are next within Task 1.
- **Validate Positions Phase A: complete and verified (2026-08-22).** The
  four-tab page retains View Signals as a read-only popover in Collect and
  Validate, adds an inert Validate Positions tab, and presents each logical
  position as BUY/SELL rows with existing management controls. Current V3
  saved-set documents are schema-4; Phase A reads no V2 artifacts and writes
  no risk value. Docker focused evidence: 41/41 pass; compilation and
  whitespace checks pass. Verification:
  `docs/superpowers/reports/2026-08-22-validate-positions-phase-a-verification.md`.
  Phase B's deterministic contract is now approved at
  `docs/superpowers/specs/2026-08-22-validate-positions-risk-phase-b-design.md`.
  Its executable plan is
  `docs/superpowers/plans/2026-08-22-validate-positions-risk-phase-b.md`.
  Phase B is complete and verified (2026-08-25). Focused Docker evidence is
  68/68 plus container compilation; final evidence is
  `docs/superpowers/reports/2026-08-25-validate-positions-phase-b-verification.md`.
  Risk suggestion text uses one line per horizon and a one-decimal score. Legacy
  records remain historical P&L only, with no Phase B evaluation dependency.
  Parent Horizon historical Tasks 7--9 remain separately governed; V2 deletion
  remains unapproved.
- **Backtest Signal Tabs and Batch Group Validation: complete and verified
  (2026-08-22).** Replaced Collect and
  Validate `View Signals` popovers with a shared second tab and no View
  Signals buttons; page order becomes Collect, View Signals, Validate, Current
  Positions, Validate Positions.
  Validate group selection locks its resolved ticker list and processes every
  member serially in 15-ticker chunks. Design:
  `docs/superpowers/specs/2026-08-22-backtest-signal-tabs-and-batch-group-validation-design.md`.
  Plan:
  `docs/superpowers/plans/2026-08-22-backtest-signal-tabs-and-batch-group-validation.md`.
  Docker focused evidence: 24/24 pass. Verification:
  `docs/superpowers/reports/2026-08-22-backtest-signal-tabs-and-batch-group-validation-verification.md`.
- **View Signals Summary Columns: complete and verified (2026-08-22).** View
  Signals projects current schema-4/V3
  catalog data into train/test metric pairs, hide rulebook/raw fields, and
  suppress terminal rows without changing terminal JSON. Design:
  `docs/superpowers/specs/2026-08-22-view-signals-summary-columns-design.md`.
  Plan: `docs/superpowers/plans/2026-08-22-view-signals-summary-columns.md`.
  Docker focused evidence: 25/25 pass. Verification:
  `docs/superpowers/reports/2026-08-22-view-signals-summary-columns-verification.md`.
- **New Position saved-set refresh: complete and verified (2026-08-22).** A
  committed ticker is uppercased and replayed only into New Position session
  state. The refresh does not overwrite Validate Signals batch state; it
  resets the selected option. Schema-4 sets remain selectable only when
  currently BUY-eligible. FPT currently has six saved sets, all audit-ineligible,
  so the UI correctly retains Manual P&L only and explains the block. Docker
  page evidence: 27/27 pass; compilation passed. Verification:
  `docs/superpowers/reports/2026-08-22-new-position-saved-set-refresh-verification.md`.
- **Collect Signals Group selector: complete and verified (2026-08-22).**
  Group defaults to `N/A`; `New group…` accepts a non-duplicate name and keeps
  manual tickers, while an existing selection disables Tickers and uses every
  member. The batch pipeline remains the only atomic group writer at Run
  Backtest. Docker page evidence: 29/29 pass; compilation passed. Verification:
  `docs/superpowers/reports/2026-08-22-collect-signals-group-selector-verification.md`.
- **Collect Signals result grid: complete and verified (2026-08-22).**
  Completed Collect output artifacts now render in stable order, four items per
  row. Captions, terminal-state copy, downloads, job handling, and artifact
  reads are unchanged. Docker page evidence: 30/30 pass; compilation passed.
  Verification:
  `docs/superpowers/reports/2026-08-22-collect-signals-result-grid-verification.md`.
- **Validate Signals classification refresh: complete and verified (2026-08-22).**
  Classification changes locally re-render the latest nonempty successful
  validation batch; fresh sessions do nothing and no replay runs. A failed
  later attempt retains the prior successful list. Docker page evidence:
  31/31 pass; compilation passed. Verification:
  `docs/superpowers/reports/2026-08-22-validate-signals-classification-refresh-verification.md`.

## 1. Recently Completed Tasks

- **Collect Group Membership Independent of Backtest Results (2026-08-15):**
  A named Collect Signals Group now atomically adds every requested batch
  ticker before theme preflight or ticker execution. Empty certification,
  ticker failures, retries, and theme failures do not remove membership;
  Group-write failures abort before backtest work. Blank/`N/A` remains no-op.
  Validate preserves its existing no-saved-signal skip and continues eligible
  named-Group siblings. Group JSON now accepts unordered uppercase unique
  tickers and returns sorted members, while duplicate/non-uppercase tickers
  remain invalid; the existing BANK Group required no rewrite. Docker focused
  Backtest tests pass 108/108, compilation and Streamlit health `200` on port
  `3501` pass. No SQL, BIGINT price, artifact, position, replay, dependency,
  Docker, credential, runtime-data, or commit change. Design, plan, and
  verification:
  `docs/superpowers/specs/2026-08-14-collect-group-membership-independent-of-results-design.md`,
  `docs/superpowers/plans/2026-08-15-collect-group-membership-independent-of-results.md`,
  and
  `docs/superpowers/reports/2026-08-15-collect-group-membership-independent-of-results-verification.md`.

- **Validate Signals Date-Only Display and Date-Range Filter (2026-08-14):**
  Validate now renders in-scope datetime values as `YYYY-MM-DD`; Projected
  exit contains only its date. The local Match classification, Date type,
  From date, and To date controls combine with AND. Signal date is default;
  bounds are optional and inclusive; a reversed range displays an error and
  hides successful result rows. Validate's View Signals catalog alone renders
  Certified at as a date, while Collect keeps its timestamp. Docker page
  tests pass 54/54, focused Backtest gate 104/104, compilation, and Streamlit
  health `200` on port `3501` pass. No artifact, position, replay, SQL,
  BIGINT-price, dependency, Docker, credential, or commit change. Design,
  plan, and verification:
  `docs/superpowers/specs/2026-08-14-validate-signals-date-filter-design.md`,
  `docs/superpowers/plans/2026-08-14-validate-signals-date-filter.md`, and
  `docs/superpowers/reports/2026-08-14-validate-signals-date-filter-verification.md`.

- **Validate Signals Match-Classification Filter (2026-08-14):** Stored
  validation results now have a local `Match classification` multi-select with
  all classes selected by default: Observe, Nearly match, and Closely match.
  It filters available signal-summary rows and metric detail panels only; it
  never submits another validation run or changes request identity, artifacts,
  positions, replay, pricing, or trading advice. Empty selection hides result
  rows and displays `Select classification`; invalid artifact feedback is not a
  classification option. Docker RED proved the control/message were missing, then green
  AppTests cover default, one-class filtering, and empty selection. Final
  Docker page tests pass 50/50; focused Backtest gate 100/100, compilation,
  and Streamlit health `200` on port `3501` pass. No SQL, BIGINT-price,
  dependency, Docker, credential, or commit change. Design, plan, and
  verification:
  `docs/superpowers/specs/2026-08-14-validate-signals-match-classification-filter-design.md`,
  `docs/superpowers/plans/2026-08-14-validate-signals-match-classification-filter.md`,
  and
  `docs/superpowers/reports/2026-08-14-validate-signals-match-classification-filter-verification.md`.

- **Validate Signals Duplicate Summary Widget-Key Fix (2026-08-14):** Rendering
  two or more tickers of one theme variant previously generated duplicate
  Streamlit keys for summary column checkboxes; after that first collision,
  the table editor and Create trade control would also collide. Summary widget
  keys now include ticker and theme variant, so every rendered ticker owns its
  own controls and session state. A new two-ticker AppTest reproduced the
  reported `DuplicateWidgetID` before the fix and passes after it. Docker page
  tests pass 48/48; focused Backtest gate 98/98, compilation, and the live
  Streamlit health endpoint `200` on port `3501` pass. No artifact, position,
  replay, SQL, BIGINT-price, dependency, Docker, credential, or commit change.
  Verification:
  `docs/superpowers/reports/2026-08-14-validate-signals-widget-key-verification.md`.

- **Backtest Multi-Group Membership (2026-08-14):** A ticker may now retain
  zero or more named Group JSON memberships, while a named Group contains zero
  or more tickers. Successful named Collect runs add membership only after a
  final qualified result; they never evict another named Group. `N/A` remains
  derived for current signal-artifact tickers with no named membership and
  blank/`N/A` writes are no-ops. View Signals stores private membership tuples,
  filters one unmodified ticker/theme/signal-set row by Group, and does not
  display redundant Group table data. Validate selected-Group and `N/A`
  resolution remain deterministic and disjoint. Docker gates: persistence
  14/14, catalog/page 53/53, pipeline 17/17, focused Backtest 97/97;
  compilation and Streamlit HTTP 200 pass. No SQL, BIGINT, artifact schema,
  position, Docker, credential, dependency, or commit change. Verification:
  `docs/superpowers/reports/2026-08-14-backtest-multi-group-membership-verification.md`.

- **Backtest Group Management and Append-Only Data Ingestion (2026-08-14):**
  Centralized current V2 artifacts in `app/backtest-result/ticker-signals` and
  moved BID/TCX/VCB/VCI byte-for-byte; all 70 historical job-status JSON files
  are unchanged. UUID Group JSON keeps identifiers out of UI/artifacts; empty
  real Groups remain reusable and `N/A` has no membership. Collect assigns Group
  only after a final qualified output; both View Signals popovers filter by
  Group. Validate supports manual one-to-five tickers or a locked Group/N/A
  list up to fifteen, skipping unavailable artifacts. Data ingestion now
  downloads both sources before one raw-connection append-only transaction; old
  rows remain immutable and failures roll back all new rows. Container gate:
  96/96, compilation, and Streamlit HTTP 200 pass. No production Backtest/Get
  data job or commit. Verification:
  `docs/superpowers/reports/2026-08-14-backtest-group-and-append-ingestion-verification.md`.
- **Backtest Multi-Metric Certified Candidates and Sequential Batch
  (2026-08-14):** Replaced scalar metric-keyed signal artifacts with strict
  schema-v2 candidate lists. Each exact winning indicator combination is
  persisted once with every certification metric it wins; V1 artifacts are
  rejected, never converted or replayed. Catalog, validation, saved-set replay,
  and frozen position references retain every metric in a grouped candidate;
  existing frozen legacy position snapshots remain readable only in history.
  Collect Signals now accepts one to five ordered unique tickers and submits one
  auto-polled sequential job. No-theme runs ticker-by-ticker; themed batches
  compute one shared VN-Index preflight, then produce no-theme followed by
  VN-Index AND per ticker. Ticker errors retry once after all first passes and
  remain terminally recorded without stopping siblings. Final focused Docker
  gate: 127/127 passed. The six inspected V1 FPT/TCB/VCB artifacts were deleted
  after verification; no V2 artifact remains, so the user will regenerate later.
  Syntax, container compilation, whitespace, Docker app/database health, and
  Streamlit `200 ok` pass. No Backtest, database, position, job-status,
  dependency, Docker, credential, SQL, BIGINT, or commit change. Verification:
  `docs/superpowers/reports/2026-08-14-backtest-v2-multi-metric-batch-verification.md`.
- **Collect Signals Control-Row Layout (2026-08-13):** Reorganized Collect
  Signals into one first row: Ticker, Time range, Horizon, and `VN-Index
  theme`. Time range now defaults to `15y`; Horizon is a dropdown defaulting
  to `-`, which maps to the existing required-horizon validation. Custom dates
  and Run backtest remain below. Validation tab wording, job locking, config
  generation, SQL, BIGINT prices, persistence, dependencies, Docker, and
  commit history are unchanged. Final Backtest verification: 190 pass, one
  expected skip; page suite 37/37, compilation, and Streamlit health passed.
  Verification:
  `docs/superpowers/reports/2026-08-13-collect-signals-control-row-verification.md`.
- **Current Positions Native New Position Popover Restoration (2026-08-13):**
  Restored the compact native `st.popover("New position")` form and removed
  panel-only visibility state, placeholder, and Close button. Streamlit 1.32
  has no supported programmatic popover-close API, so users dismiss unsaved
  forms through click-outside or Escape; `TODO(streamlit-upgrade)` records
  reevaluation when supported explicit dismissal becomes available. Ticker
  normalization, validation, persistence, SQL, BIGINT handling, and position
  semantics are unchanged. AppTest proves native popover structure and manual
  creation; it cannot simulate browser open/dismiss. Final Backtest
  verification: 190 pass, one expected skip; compilation and Streamlit health
  passed. No dependency, Docker, credential, or commit change. Verification:
  `docs/superpowers/reports/2026-08-13-current-positions-native-popover-restoration-verification.md`.
- **Current Positions UI Regression Fix (2026-08-12):** Repaired the Select
  all visible state lifecycle: its Streamlit callback now writes every visible
  row ID before the data editor is rebuilt, so selecting and clearing it
  correctly enables and disables bulk deletion. Replaced the Streamlit 1.32
  New position popover with a state-controlled panel and Close button; Close
  hides the unsaved panel without writing position data. Regression AppTests
  prove both paths. Final Backtest verification: 190 pass, one expected skip;
  Docker compilation and Streamlit health passed. No schema, SQL, BIGINT,
  dependency, Docker, credential, or commit change. Verification:
  `docs/superpowers/reports/2026-08-12-current-positions-ui-regression-fix-verification.md`.
- **Current Positions Bulk Delete UI Enhancement (2026-08-12):** Reordered
  Current Positions controls into the approved three-line layout, added
  individual/all-visible selection, and retained exactly-one selection for
  inline Save changes. Batch delete prevalidates every manual/legacy immutable
  locator before its first writer, confirms every selected record once, runs in
  visible table order, stops at the first failure, and never claims partial
  success. Pending confirmation is invalidated by filter, sort, selection, or
  refresh changes. A full-success message is visible for two seconds. Final
  Backtest verification: 188 pass, one expected skip; compilation, whitespace,
  protected-boundary inspection, and Streamlit health pass. Verification:
  `docs/superpowers/reports/2026-08-12-current-positions-bulk-delete-verification.md`.
- **Current Positions Inline Management (2026-08-12):** Replaced separate
  Current Positions add/edit/refresh controls with the approved two-row
  toolbar, native New Position popover, one-row inline editor, exact locator
  routing, lifecycle close/reopen support, and two-step permanent deletion.
  Ticker and saved signal associations remain immutable; derived P&L/audit
  values remain read-only. The final package-qualified Backtest gate passes
  185 with one expected skip; compilation, boundary hashes, and configured
  Streamlit health passed. Verification:
  `docs/superpowers/reports/2026-08-12-current-positions-inline-management-verification.md`.
- **Validate Signals Drafts and Manual Positions (2026-08-12):** Match score
  similarity is independent from VN-Index eligibility, while theme eligibility
  still blocks advice/actions. Validate Signals now groups equivalent metric
  summaries, presents a collapsed checkbox column selector, uses a selected
  row to create one gated session-only BUY/SELL draft, and no longer persists
  directly from details. Current Positions supports generic atomic P&L-only
  and frozen saved-set records, direct OPEN/CLOSED manual creation, locator
  routed edits/closes, optional volume, legacy-history compatibility, and
  per-position hold time derived only from ticker database OHLCV sessions.
  Docker Backtest gate: 172 pass, one expected unmounted-script skip. Read-only
  live VCB themed replay: match `100.0`, theme ineligible, advice Observe.
  Verification: `docs/superpowers/reports/2026-08-12-validate-signals-drafts-manual-positions-verification.md`.
- **Repair Validate Signals Compact Artifact Replay (2026-08-11):** Persisted
  compact signal artifacts use alphabetically sorted JSON keys, but compact
  strategy IDs originally compared indicator dimensions in rulebook order. The
  shared `IndicatorCombo` contract now validates semantic content, then
  canonicalizes the approved order; it continues rejecting duplicate, missing,
  extra, and incorrect dimensions. The RED/GREEN persisted-JSON regression
  test passes. Explicit Docker Backtest package gate: 144/144 pass with one
  expected skip. Read-only live VCB replay reports both no-theme and VN-Index
  AND variants available; no artifact, position, database, or commit changed.
- **Backtest Compact Strategy Revamp:** Completed Tasks 0–7 with the fixed
  three-strategy long-only rulebook, causal Backtest-only Alligator, unique
  native-clock events, per-ticker certification, and current-database audit.
  The read-only frozen-universe diagnostic selected `VCB, DHC, HJS, ELC, VPL,
  C47, HAP, CSM` and evaluated all four horizon/theme variants (96 results).
  It reused one candidate load and one VN-Index load, returned 27 qualified
  combinations, and wrote no job, database row, or signal artifact. VCB Swing
  has five qualified sets; VCB Mid-term has none because no-theme variants fail
  DSR and themed variants fail `n >= 30`, not because of data quality. Final
  Docker Backtest gate: 66/66 pass with one expected unmounted CLI skip;
  compilation and whitespace checks pass. Current-DB evidence is in
  `docs/superpowers/reports/2026-08-10-backtest-compact-strategy-evidence.md`.
- **Complete FPT Backtest Zero-Signal Investigation:** The source-level
  score-input mismatch, Swing minimum-hold boundary, and Mid-term timeframe
  mismatch are resolved and verified. Read-only FPT probes now demonstrate
  viable Swing candidates and all-weekly Mid-term BUY crossings. The explicit
  Backtest Docker gate passes 60/60; generic discovery remains a documented
  pre-existing test-layout limitation. Evidence remains in
  `docs/superpowers/plans/2026-08-04-backtest-zero-signal-investigation.md`
  and `docs/superpowers/reports/2026-08-04-backtest-zero-signal-triage.md`.
- **Harden Backtest Runtime Configuration and Split Backtest Lab:** Added a
  test-proven URL-port guard before SQLAlchemy engine creation, so an empty
  explicit port returns `RuntimeError: DATABASE_URL has an invalid port`
  instead of an opaque `ValueError: int('')`. Worker failures now retain one
  job-ID traceback in Docker logs while the persisted UI status remains
  concise. Backtest Lab now groups every existing control, automatic status
  update, result, and download under `Collect Signals`; `Validate Signals` is
  a deliberately static future-work placeholder. Docker Backtest tests pass
  75/75; compilation, whitespace, and the non-writing `postgresql`/`db`/`5432`
  runtime preflight pass. A later live failure isolated the source to Compose
  interpolation: `env_file: ../.env` populated `POSTGRES_PORT=5432` inside the
  container only after Compose had already constructed `DATABASE_URL` as
  `...@db:`. The required operational start command is `docker compose
  --env-file .env -f docker/docker-compose.yml up -d --force-recreate app`.
  The user confirmed the Backtest function then ran without error. No signal
  artifact, SQL, BIGINT, Docker-file, credential, dependency, or commit change
  was made.
- **Enhance Backtest Page Run Variants and Control Lock:** Replaced the default
  Horizon selectbox with an unselected-by-default Swing/Mid-term radio and
  replaced the theme mode selectbox with an unchecked
  `INCLUDE_THEME_OPTION`. An unchecked request submits one selected-horizon
  no-theme job; a checked request submits that job plus the VN-Index `AND`
  variant. All request-defining controls and Run are disabled while any job is
  queued/running/unreadable, then terminal success/error output is rendered
  before a new request may replace the job list. Docker page tests pass 9/9;
  the focused Backtest/Technical gate passes 124/124. The engine, persistence,
  SQL, BIGINT, Docker, dependencies, and commit history are unchanged.
- **Technical Indicator Enhancement — Phase 2:** Added pure pandas/numpy ATR, Bollinger Bands, OBV, ADX, and paired trend classifiers. Added 58 focused tests; full unittest suite passes 86 tests. Functions are not wired into scoring or UI until later phases.
- **Technical Indicator Enhancement — Phase 3 implementation:** Added the resolved five-dimension registry, alias-safe grouping helper, explicit ADX `votes=False` metadata, and vectorized trend-key correlation helper. Focused suite passes 5 tests; full suite passes 91 tests. Real multi-ticker correlation remains pending because Docker/PostgreSQL is unavailable. `IMPLEMENTED.md` was intentionally not referenced or modified.
- **Technical Indicator Enhancement — Phase 4:** Replaced flat indicator voting with named equal weights across available voting dimensions, averaged indicators within each dimension, renormalized weights when groups are missing, and excluded ADX from scoring. Updated both common/API and Analyze page-local advice paths. Added 7 focused tests; full suite passes 98 tests. Thresholds and return shapes remain unchanged; ADX gating is deferred to Phase 5. `IMPLEMENTED.md` was not modified.
- **Technical Indicator Enhancement — Phase 5:** Added copy-on-write ADX gating: `ADX < 20` multiplies `trend_direction` by `0.5`; `ADX >= 20` keeps full weight; missing/Unknown/NaN ADX skips gating. Passed latest ADX through common/API, Analyze ticker, portfolio, and historical scoring paths without adding an ADX vote or extra query. Related tests pass 87/87; full suite passes 106 tests. Binary-boundary limitation and sideways-market trade-off are documented; empirical recalibration remains Phase 6 work. `IMPLEMENTED.md` was not modified.
- **Technical Indicator Enhancement — Phase 6 framework:** Added pure pooled validation utilities enforcing one global split date across tickers, pooled minimum-30 buckets, hit-rate, expectancy, and eligible old/new deltas. Focused suite passes 5 tests; full suite passes 111 tests. Docker is unavailable and local data contains only one trading day, so live market validation remains blocked; no empirical performance claim is made. `IMPLEMENTED.md` was not modified.
- **Implement API support functions:**
  - Implement API endpoint `POST /api/prepare-data` to support trigger Data preparation: default values: 
    . Select Report Date: latest trading date
    . Gaps of data (years): 1 (year)
- **FastAPI Integration:**
  - Implemented REST API endpoint `GET /api/analyze/{ticker}` to trigger full statistical and technical analysis.
  - Developed Pydantic schemas for structured JSON responses (`TickerAnalysisResponse`).
  - Integrated the API server as a background thread within the Streamlit application for unified service management.
  - **Fix:** Resolved a bug in `synthesize_all_advice` where `result_days` was hardcoded to 10; it now respects API query parameters.
  - **Refactor Technical Trend Context:** Refactored the historical technical context summary to analyze the trend of the result category with the highest statistical frequency (Up vs Down vs No Change).
- **API Data Management:**
  - Implemented `POST /api/prepare-data` endpoint to trigger historical data ingestion.
  - Integrated `BackgroundTasks` to handle long-running downloads without HTTP timeouts.
  - Added a global `threading.Lock` to ensure thread-safety between UI and API-triggered ingestion.
- **Environment & Performance Fixes:**
  - Resolved Numba `RuntimeError` in Docker by configuring `NUMBA_CACHE_DIR` and optimizing `load_dotenv()` placement.
  - Fixed `StreamlitAPIException` by ensuring `st.set_page_config` is the absolute first command in `main.py`.
- **Project Restructuring:**
  - Modularized the application into `apis/` (REST), `commons/` (Shared logic), and `pages/` (Streamlit UI).
  - Updated all internal absolute imports to support the new package structure.
  - Centralized business logic in `app/commons/common_functions.py` to ensure consistency between the UI and API.
- **Refactor Ticker Analyze Tab (Historical Technical Context):**
  - Added 'Technical score' column to 'Block Day and Delta Statistical Report' to calculate technical strength at historical signal points.
  - Implemented a technical trend summary below 'Statistical Advice' using specific thresholds (Up $\ge 53\%$, Down $< 48\%$).
  - Optimized performance by calculating scores only for historical rows matching the predicted outcome.
- **Implement Trend Classification & State Management:**
  - Refactored the "Technical Analyze" page to use `st.session_state`, caching indicator data to prevent re-calculation on UI toggles.
  - Implemented business logic in `technical_analysis.py` to classify the current trend for MA Cross (based on <2% price spread for "Sideways") and RSI (based on a 30-period lookback analysis).
  - Added "Current Trend" metrics to the MA and RSI tabs in the UI.
- **Implement RSI (14) Indicator:**
  - Added `calculate_rsi` function to `technical_analysis.py`.
  - Added a "Show RSI (14)" checkbox to the "Technical Analyze" page.
  - Implemented a dynamic 3-row chart layout to display the RSI indicator in a separate subplot below the price and volume charts.
  - Added overbought (70) and oversold (30) threshold lines to the RSI chart.
  - Populated the "RSI" data tab with the latest indicator values.
- **Finalize MA and MA Cross Indicator:**
 - **Implement Stochastic (10, 3, 3) Indicator:**
  - Implemented `calculate_stochastic` function to `technical_analysis.py`.
  - Added logic to display the Stochastic (10, 3, 3) indicator.
  - Added logic to determine trend classifications (Up/Down/Sideways) on Stochastic.
  - Populated the "Stochastic" data tab with the latest indicator values.
  - Implemented UI controls for MA/MA Cross on the "Technical Analyze" page.
  - **Refactor UI of technical visualization page to optimize space and display as much as possible.**
  - Added timeframe-aware MA pair selection (Day, Week, Month).
  - Visualized SMA lines and Golden/Death cross signals on the main price chart.
  - Collapsed the raw data table by default to improve layout.
- **Technical Analyzed Page Implementation:**
  - Created a new page named "Technical Analyzed Page" using `pandas-ta` and `plotly`.
  - Implemented UI with Ticker, Timeframe, and Lookback controls.
  - Implemented interactive Price (Candlestick) and Volume (Bar) charts.
  - Created placeholder structure for technical indicators.
  - **Fix:** Resolved `AttributeError` in `fetch_data` by using `engine.raw_connection()` to bypass pandas/SQLAlchemy compatibility issues.
- **Refactor Number Formatting in Analyze Page:**
  - Refactored all numbers in analyze page (Ticker and Portfolio tabs) to have 2 decimal numbers after floating point.
- **Refactoring Core SQL Logic:**
  - Extracted common SQL CTEs for delta calculation into `common_queries.py`.
  - Updated `analyze_visualization.py` and `suggestion_visualization.py` to use the shared queries, reducing code duplication.
- **AI Context Documentation:**
  - Created and populated the entire `/ai-context` folder with all required documentation files (`README.md`, `project-overview.md`, `architecture.md`, `conventions.md`, `business-logic.md`, `decisions.md`, `boundaries.md`, `glossary.md`, `workflows.md`, `current-status.md`).
- **Bug Fixes:**
  - Resolved `ImportError` related to relative imports after refactoring.
  - Corrected SQL syntax errors (`ProgrammingError`) in both the Analyze and Suggestion pages.
- **Refactoring Suggestion & Analyze Page Logic:**
  - Implemented dynamic delta calculation for both Suggestion and Analyze pages.
  - Centralized 'Up'/'Down' thresholds in `common_queries.py`.
  - Added error handling to `analyze_ticker`.
  - Updated Analyze page to display 'Current Delta' metric.
- **Portfolio Analysis UI Refinement:**
  - Implemented conditional formatting for delta columns in the Portfolio Analyze tab to improve readability.
- **Documentation Sync:**
  - Updated `project-overview.md`, `architecture.md`, `business-logic.md`, `decisions.md`, `glossary.md`, and `README.md` to reflect the new "Context-Aware" logic and the addition of the Portfolio Analyze tab.
- **UI & Logic Standardization:**
  - Standardized the "day range" logic across the application, where an input of `N` now consistently represents an `N`-trading-day window (implemented as a lag of `N-1`).
  - Updated the "Analyze Page" UI to display the specific start and end dates for the current signal being analyzed.
- **Refactor "Ticker Analyze" Tab:**
  - Refactored the "Ticker Analyze" tab to use the centralized `analyze_ticker` function from `common_functions.py`.
  - This eliminated redundant helper functions and resolved the long-standing "Fragile String Parsing" known issue.

- **UI Enhancement: Remove Chart Gaps on Non-Trading Days:**
  - Reviewed the "Technical Analyze" page and confirmed the Plotly chart implementation already uses `rangebreaks` to remove gaps for weekends and holidays, making the x-axis continuous for trading days. The task is complete.
- **Refactor Data Preparation Page UI:**
  - In Data page, when receiving data and manipulation in progress, show the loading progress icon beside the Page title.
  - After all progress is done, hide the loading progress icon, show a check icon beside the page title
- **Fix Bug: Technical Analysis Page Crash (KeyError):**
  - Resolved `KeyError: 'cross_5_10'` in `technical_visualization.py` by adding a defensive check ensuring the signal column exists before plotting markers.
- **Fix Bug: MA Cross Signal Calculation Logic:**
  - Fixed logic in `technical_analysis.py` where the signal column creation was skipped due to a premature existence check, causing "Not enough data" errors despite sufficient data.
- **Fix Bug: Analyze Page & Result Page DB Compatibility:**
  - Refactored `analyze_ticker`, `analyze_price_movement`, and `result_page` to use `engine.raw_connection()` and safe string replacement for SQL parameters.
  - This resolves pandas/SQLAlchemy compatibility issues that caused silent query failures (`psycopg2.errors.InvalidSchemaName: schema "np" does not exist`) and `TypeError: Query must be a string unless using sqlalchemy`.
- **Refactor Analyze Page UI:**
  - Added a "Technical Report" table displaying Stochastic, RSI, MA, and MA Cross indicators with trend direction.
  - Implemented dynamic timeframe selection for technical indicators (Day vs Week) based on the validation day range.
  - Organized the "Block Day and Delta Statistical Report" into a collapsed expander, while keeping the "Analyzed Statistical Report" visible by default.
  - **Fix Bug: Analyze Page Crash (ValueError):**
    - Resolved `ValueError: too many values to unpack` in `analyze_page` by updating `provide_advice` to return a tuple `(message, trend)`.
    - **Refactor:** Standardized emoji usage across advice functions using a global `TREND_EMOJIS` constant, eliminating fragile string parsing logic.
  - **Refactor Analyze Page UI Layout:**
    - Reordered the "Ticker Analyze" tab to follow a strict 1-5 display order (Signal -> Stats -> Tech -> Final -> Explanation).
    - Removed legacy placeholder logic for cleaner linear rendering.
  - **Refine Final Advice Logic:**
    - Implemented a decision matrix combining Statistical and Technical trends to generate the Final Advice.
    - Documented the logic in `business-logic.md`.
  - **Refactor Portfolio Analyze UI:**
    - Converted the Portfolio table to a lightweight version with columns: `No`, `ticker`, `statistical trend`, `possibility`, `delta`, `technical trend`, `score`, `final advice`.
    - Integrated technical analysis (Trend & Score) for batch processing.
    - Added emoji support for trend visualization.
  - **Update RSI Trend Logic:**
    - Refined RSI trend classification rules: Sideways range (40-55), 2-consecutive period check for trends, and adjusted Strong/Over/Under thresholds.
  - **Update MA Trend Logic:**
    - Added bullish and bearish reversal pattern detection to the `calculate_ma_trend` function based on 3 consecutive periods of MA movement and their gap.

  - **Fix Bug: Inconsistent Technical Advice between Analyze Tabs:**
    - **Root Cause:** The `calculate_ma_cross` function incorrectly coupled the trend logic for MA spread and MA cross events, leading to inconsistent trend assignments.
    - **Fix:** Refactored the logic into two separate functions: `calculate_ma_trend` (for spread/reversal) and `calculate_ma_cross_trend` (for events). Both "Ticker Analyze" and "Portfolio Analyze" were updated to call these distinct functions, ensuring consistent and correct trend calculation for each indicator.
- **Enhance logic of Suggestion Page**: Implemented the filtering and multi-tier sorting logic for the Suggestion Page, combining statistical probabilities with technical scores and exchange-based priorities (HSX > HNX > UPCOM).
- **Implement Suggestion API:** Created a new FastAPI endpoint (`GET /api/suggestions`) to provide market-wide ticker suggestions. Supported top 5 categories by probability and delta with default parameter handling and structured JSON output.
- **Implement Analyze Page Export Function:** Added hidden-by-default export form, validated ticker/range inputs, bounded parameterized history query, BIGINT price scaling, optional percentage change, safe feedback, deterministic CSV filename, and focused unit tests. Verified with 18 passing tests; live PostgreSQL verification remains pending because Docker daemon is unavailable.
- **Enhance Analyze Page Export Form:** Added native Streamlit collapse/expand control around the export form without changing export behavior. Focused and full unittest suites pass (10 and 19 tests).
- **Enhance Analyze Page Export Data:** Added optional full OHLC prices and trading-volume columns while preserving required ticker/range/unit fields and optional percentage change. Optional OHLC values remain original BIGINT storage values; default close-price export remains display-scaled. Full unittest suite passes (20 tests).
- **Technical Indicator Enhancement — implementation complete:** Phases 0, 2, 3, 4, 5, and 6 plus the approved UI integration are complete and documented. Phase 1 (`pandas_ta` tech debt) remains intentionally deferred because its effort was assessed high. The shared indicators, dimension-aware scoring, ADX gating, pooled validation framework, shared snapshot workflow, and eight-indicator UI are implemented. `IMPLEMENTED.md` was not modified.
- **Enhance Analyze Trend Classification:** The page-local trend classification implementation is complete and covered by focused tests; live database comparison remains a separate validation task.
- **Technical Indicator UI Integration — complete:** Shared snapshot, Technical Analyze UI, Analyze/API reuse, historical score precomputation, raw-price export behavior, and verification are complete. Docker discovery passes 128/128; PostgreSQL/AppTest and headless Chrome smoke are clean. Remaining warning: historical SQL intentionally reads full ticker history until a warmup-preserving as-of bound is separately designed and approved.
- **Trend Classification Validation — complete:** Compared legacy Up-probability-only labels with current direct Up/Down labels across 64 deterministic tickers, three fixed windows, 190 valid observations, and 151 eligible observations. Eligible labels changed 65/151 (43.05%); the full transition matrix and review-worthy Down-dominant Sideways cases are documented in `docs/superpowers/reports/2026-08-02-trend-classification-validation.md`. Docker focused tests pass 22/22 and full discovery passes 137/137. No production threshold or UI behavior changed.
## 2. Technical Indicator UI Integration — Completed Verification Record
- **Technical Indicator UI Integration — COMPLETE (historical verification record):**
  - **Task 1 complete — shared snapshot:** Added `build_technical_snapshot()`
    to calculate MA, MA cross, RSI, Stochastic, ADX, OBV, ATR, and Bollinger
    once per OHLCV frame, returning shared chart data, scorer signals, report
    records, and one latest ADX value. Removed the unused Ichimoku function
    stub. Focused snapshot plus technical regression tests pass 82/82 in the
    Docker application container.
  - **Task 2 complete — Technical Analyze UI:** Added the default-open
    Overview plus one detail tab per implemented indicator, a single
    dropdown-selected indicator visualization, permanent candlestick/volume
    charts, cached snapshot reuse, ADX gate status, safe short-data handling,
    and no Ichimoku placeholder. Docker focused UI/snapshot/regression tests
    pass 84/84; the page module compiles; Streamlit health returns HTTP 200.
    Initial browser-level visual smoke was pending because no browser
    automation was available at that checkpoint; later headless Chrome smoke
    covered the rendered MA and RSI states.
  - **Price display/export correction complete:** Added shared
    `prepare_price_for_output()` context handling. Technical/UI price values
    are divided by 1000 and labeled k VND; export CSV prices always preserve
    original BIGINT values regardless of export options. Docker focused price,
    export, technical, ADX, and snapshot-reuse tests pass; non-malformed full
    discovery passes 118/118. `IMPLEMENTED.md` was not modified.
  - **Task 3 complete — Analyze/API shared workflow:** `analyze_ticker()` now
    builds the shared snapshot once and exposes JSON-safe `technical_signals`,
    `technical_report`, and `technical_adx_value` fields. API synthesis reuses
    those fields with a legacy compatibility fallback; Analyze Ticker renders
    all eight indicators and ADX gate status; portfolio analysis reuses the
    same result without another technical fetch. Focused shared-flow tests
    pass 28/28 and all non-malformed discovered tests pass 115/115. Full
    discovery was later repaired during Task 5 and now passes 128/128.
  - **Task 4 complete — historical path performance protection:** Verified
    that `analyze_ticker()` builds one current snapshot, portfolio/API paths
    reuse it, and the historical path retains one full-history query and
    binary-search date alignment. Historical technical scores are now
    precomputed once with bounded as-of classifier contexts, then looked up by
    event date. Deterministic prefix-parity tests and 174 sampled indices from
    the largest 3,740-row ticker match existing scores. Processing is linear in history instead
    of O(events x history); the SQL query stays full-history to preserve exact
    prefix/as-of semantics. Docker focused Analyze/API, historical, trend,
    snapshot-reuse, and ADX tests pass.
  - **Task 5 verification handoff:** Exact Docker discovery now runs 128 tests
    and all 128 pass after splitting the two assertions that previously shared
    one line in `tests/test_validation.py:67`. `git diff --check` is clean
    except normal CRLF warnings. Docker `app` and `db` are healthy and
    Streamlit health is `ok`. Real PostgreSQL smoke for MHP fetched 45 rows,
    produced all eight technical reports, and returned a non-empty
    `analyze_ticker()` result. Streamlit AppTest rendered Analyze with zero
    errors/warnings and three dataframes; Technical Analyze initial render also
    had zero errors/warnings and the expected controls. A Plotly 5.20
    compatibility crash from unsupported Candlestick `hovertemplate` was fixed
    with supported `text`/`hoverinfo` properties and covered by a regression
    test. Live API smoke now returns HTTP 200. AppTest now exercises every one
    of the eight chart-selector options with zero exceptions, errors, or
    warnings; a report-name alias regression found during that smoke was fixed
    and covered by a focused test. Headless Chrome visual smoke covered the
    rendered MA and RSI states without a visible error state. Implementation
    review is PASS WITH WARNINGS: date-unbounded historical query and existing raw SQL-string
    compatibility pattern remain documented.
    PostgreSQL-backed MHP smoke rendered both pages with zero AppTest
    exceptions/errors/warnings across all eight chart options; unknown ticker
    `ZZZ` returned the expected safe no-data warning. Headless Chrome visual
    smoke inspected Technical Analyze MA and RSI states: candlestick, volume,
    k VND labels, controls, and indicator tabs rendered with no visible error.
  - **Large-history performance check:** The real export path returned 2,497
    rows for one 10-year REE request in 27 ms. Eight sequential 5-year requests
    returned 9,968 rows in 170 ms and formatted all CSV rows successfully. This
    simulated a group workload only; multi-ticker query support was not added.
    The existing `(ticker, date)` index is used, so no pagination or query guard
    change is justified for these tested ranges. The historical technical
    context query remains unbounded by date until a warmup-preserving as-of
    design is approved.
  - **Technical Indicator empirical validation (initial sample complete):** A
    read-only probe over REE, SSI, PPC, PVT, OGC, SBT, MSN, and PET for five years
    with 5-day validation/result windows produced 9,928 observations, zero
    excluded rows, and one pooled split date of 2025-07-25. In-sample hit-rate
    changed from 46.41% legacy to 45.73% new (-0.68 points); out-of-sample changed
    from 42.34% to 45.26% (+2.92 points). Expectancy delta was 0.00 in both
    phases. Strongest observed correlations were OBV/Bollinger (0.763),
    Stochastic/OBV (0.732), and MA cross/Stochastic (0.727). This is a measured
    sample only; no recalibration or market-performance claim is made.
  - **Broader validation and warmup probe:** A deterministic read-only sample
    of 64 from 1,500 tickers with at least five years of coverage used 50 events
    per ticker and produced 3,141 observations. The pooled split date was
    2025-05-05; in-sample hit-rate changed from 41.25% legacy to 39.77% new
    (-1.49 points), while out-of-sample changed from 36.54% to 36.40%
    (-0.14 points). Expectancy delta was 0.00 in both phases. A full
    eight-ticker prefix-scoring warmup probe exceeded 124 seconds, confirming
    O(events × history) cost. A reduced 400-event fidelity probe found 90
    calendar days preserved 100% of sampled Day scores; weekly scores reached
    98.0% at 365 days and 99.5% at 540 days. No production bound or recalibration
    was applied.
  - **Technical Analyze Page:** Define how MA, MA cross, RSI, Stochastic, ATR,
    Bollinger Bands, OBV, and ADX are displayed, selected, labeled, and
    explained in charts, metrics, and data tabs.
  - **Analyze Page:** Define how the new dimension-aware technical score and
    ADX gate appear in the Technical Report and flow through ticker, portfolio,
    historical, Statistical Advice, and Final Advice outputs.
  - Make the ADX rule explicit: ADX is a gate, not a vote; ADX `<20` halves the
    trend-direction contribution; ADX `>=20` keeps full weight; missing or
    unknown ADX skips gating to avoid double-penalization.
  - Preserve existing thresholds, scoring contracts, display scaling, and
    output shapes. Avoid repeated indicator calculations and extra queries.
  - Approved design uses one shared technical snapshot per analysis run. The
    dropdown changes only the selected chart visualization; it must not refetch
    data or recalculate indicators.
  - Remove Ichimoku from placeholders and implementation code. Add the
    default-open Overview plus one detail tab per implemented indicator.
  - Ticker Analyze Technical Report will show all eight indicator final
    results; existing Technical Advice thresholds/output and Final Advice
    matrix remain authoritative.
  - Historical technical context must not gain a per-event new-indicator loop;
    use precomputed/as-of data only if expansion is later proven safe.
  - Detailed plan saved to
    `docs/superpowers/plans/2026-08-01-technical-indicator-ui-integration.md`.
## 3. Work In Progress (WIP)

### Top priority — Horizon Rulebook Signal Redesign (2026-08-15)

#### Authoritative update — schema-4 exploratory multi-rulebook replacement (2026-08-22)

Written design:
`docs/superpowers/specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`.
It supersedes the binary-certification/schema-3 amendment below. Implementation
has not started. Approved replacement plan:
`docs/superpowers/plans/2026-08-22-horizon-v3-exploratory-multi-rulebook.md`.
Fixed
changes are Swing volume `>=1.15x`, Mid-term RSI upcross `65`, and Mid-term
volume `>=1.3x`. Required contract: evaluate all 15 gate subsets with both
treatments, persist every no-theme-training `n >=5` exploratory candidate,
choose a treatment by training DSR only, rank Top 3 by training
win rate/profit/Sharpe/lexical ID, and retain
10y/5y or chronological 65%/35% train/test evidence. P-values are
informational only. Schema-4 owns one ticker/horizon artifact; old artifacts
and job sidecars become filename-only `requires_regeneration` markers. Audit
ineligible output is display-only and BUY-blocked. Parent Horizon Tasks 7--9
still block Validate Positions after amendment implementation completes. Validate
monitoring uses only selected candidate gates with equal weights, plus the
preferred VN-Index treatment factor when present.

**Completion override (2026-08-25):** The Horizon Rulebook Signal Redesign is
complete through its approved schema-4 exploratory replacement, verified at
`docs/superpowers/reports/2026-08-22-horizon-v3-exploratory-multi-rulebook-verification.md`.
The historical Task 7--9 wording below is retained only as implementation
history; it is not active work. Original V2 deletion remains unapproved and
was not performed.

- Task 0 repaired diagnostics and published the read-only literal-roster
  report: `docs/superpowers/reports/2026-08-15-v3-price-audit.md`.
  `price_audit_clean` and `study_history_sufficient` are separate fields;
  every roster ticker meets the five-year Swing daily/eight-year closed
  Mid-term weekly floors, but only VCB is clean. Future V3 research must
  exclude REE, FPT, SSI, VIC, PLX, DHG, and HPG without changing normal UI
  availability. Remove only the temporary roster input—not the report—after
  the full plan and separately approved V2 cleanup.

- Task 1 added immutable canonical Swing/Mid-term `RulebookSpec` values and
  `RulebookExecution` identity. Request configs carry no caller-controlled
  rule minimum, hold, threshold, or indicator-period field; both payloads are
  V3 and a single request decodes to the common batch-of-one service. The
  focused Docker config/contracts/worker gate passed 18 tests. Task 2 must
  replace legacy compact scoring with the new causal rulebook frame and entry
  gates before any Backtest run is valid again.

- Task 2 replaced compact score generation with pure Backtest-owned causal
  EMA/SMA, RSI, SMMA Alligator, prior-only volume, ATR, ADX, completed
  `W-FRI`, required-input, and AND-only Boolean entry contracts. The focused
  Docker gate passed 10 tests, including no-look-ahead daily/weekly and
  holiday-short-week coverage. Task 3 now replaces the retained legacy score
  execution loop with one non-overlapping flat-to-flat rulebook sequence.

- Task 3 now executes one native-frame, flat-to-flat V3 rulebook sequence:
  next-open BUY, raw-ATR 1.5x/2.5x exits, conservative stop-first handling,
  one-open-trade suppression, Swing bar-22 inclusive timeout, and Mid-term
  next-week exit/bar-16 timeout. The focused Docker gate passed 7 tests.
  Task 4 replaced legacy multi-combo DSR validation and pipeline wiring.

- Task 4's original PSR/no-theme and themed-only DSR implementation is
  superseded by the approved 2026-08-21 gate/statistics amendment design and
  executable plan; implementation has not started. Its current policy is
  no-theme default `min_n >=5` plus permutation only; checkbox-on runs
  no-theme and VN-Index-AND as a two-Sharpe DSR family for both rows, Swing
  `DSR >=0.90`, Mid-term `DSR >=0.85`. V3 PSR is removed. The focused Docker
  Task 0--4 gate passed 65 tests under the original policy only.

- Task 5 now atomically writes only schema-3 horizon-qualified terminal
  documents, each with explicit `success`/`empty`/`failed` state, paired date
  ranges, immutable rulebook data, and freshly recomputed raw-history audit
  metadata. V2 paths, migration/recovery hooks, artifact readers, and catalog
  discovery are absent from current results; retained V2 files are ignored.
  A shared theme-preflight failure still completes the no-theme treatment and
  writes each themed path as terminal `failed`. The combined Tasks 0--5 Docker
  gate passed 76 tests. Task 6 owns rulebook replay, position-history boundary,
  and V3 UI consumers.

- Task 6 now replays only independently-addressable V3 horizon/theme
  rulebooks and calculates monitoring from literal current gate facts. New
  saved-set positions persist one frozen V3 all-metrics reference and a
  horizon-owned risk snapshot; Swing and Mid-term sets can coexist. Pre-V3
  positions remain only manual/P&L history and are editable, closable, or
  deletable without artifact lookup. Current Positions renders raw BIGINT
  prices as k VND. The isolated job runner also supplies a module-level
  factory's source path to its child process, so its V3 batch-of-one worker
  remains runnable under discovery. Task 6's prescribed Docker suite passed
  20 tests; the full Backtest Docker suite passed 129 tests. Task 7 must now
  produce read-only evidence before requesting one manual nonempty V3 result.

- Task 7 now has a read-only V3 diagnostic with explicit rulebook inputs,
  trial family, sequential gate rejections, non-overlap skips, exit reasons,
  `n`, and a truthful unavailable calibration/holdout result. Its VCB evidence
  is recorded at
  `docs/superpowers/reports/2026-08-15-horizon-rulebook-signal-redesign-verification.md`:
  only VCB is both clean and history-sufficient, yet it has just 8 Swing and
  4 Mid-term no-theme exits, below the locked 22/20 floors. No rule was tuned;
  no V2 artifact was inspected; no write was made. The 90-test focused Docker,
  5-test diagnostic, and final 132-test full Backtest Docker gates pass. The
  final read-only proof preflight found every locked-roster no-theme Swing
  result empty (`n=5--8`, below 22), so none can satisfy Task 7 Step 6. The
  2026-08-21 user-run Swing Collect job `ef0412da7a504a76843fe3abb7657b95`
  for TCB, VCB, REE, FPT, HPG, and MSN then completed without errors and wrote
  all 12 requested V3 documents, but each is an `empty` `min_n` result.
  No-theme completed exits were 2, 8, 5, 5, 6, and 8 respectively; themed
  exits were 2, 5, 5, 4, 5, and 6. TCB/VCB were audit-clean; REE/FPT/HPG/MSN
  were ordering-mismatch audit-ineligible but remain normal results by design.
  Task 7 Step 6 remains unmet and Task 8 remains blocked pending a valid,
  nonempty user-run V3 Collect proof. Run evidence:
  `docs/superpowers/reports/2026-08-21-swing-collect-min-n-run.md`.
  A 2026-08-21 read-only VCB/REE counterfactual with Swing `min_n=15` and
  Mid-term `min_n=10` still produced only `empty: min_n` treatments; it made
  no canonical rulebook, artifact, job, or DB change. Evidence:
  `docs/superpowers/reports/2026-08-21-vcb-ree-counterfactual-min-n-run.md`.
  Separate VCB-only read-only signal-optimizer research has an approved design
  at
  `docs/superpowers/specs/2026-08-21-vcb-read-only-signal-optimizer-design.md`
  and execution plan at
  `docs/superpowers/plans/2026-08-21-vcb-read-only-signal-optimizer.md`.
  Its isolated `backtest_engine.research_optimizer` implementation and
  15-year VCB live run are complete. It evaluates all 60 candidates through
  native V3 frames/execution without V3 persistence or configuration changes;
  report:
  `docs/superpowers/reports/2026-08-21-vcb-15y-signal-optimizer.md`.
  Swing had 16 DSR and 14 PSR rejections; Mid-term had 25 PSR, four `min_n`,
  and one PSR-computation rejection, so no candidate is fully eligible under
  the approved search-wide contract. The focused Docker gate passed 39/39.
  V3 and Task 7 remain untouched.

- The 2026-08-21 amendment design and plan are superseded by the approved
  schema-4 exploratory replacement design and plan at
  `docs/superpowers/specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`
  and
  `docs/superpowers/plans/2026-08-22-horizon-v3-exploratory-multi-rulebook.md`.
  The following original-policy summary is historical only:
  historical Swing entry is joint trend plus RSI only; historical Mid-term
  entry is joint trend plus volume only; RSI/volume/ADX values not selected by
  that horizon remain monitoring-only; Swing ADX(14) is `>=17`; Mid-term
  ADX(14) is `>=20`; both horizons use `n >=5`. The previous Task 7 proof is
  pre-amendment evidence and must be rerun after implementation.

- Replace `ma_cross_rsi_obv`, `alligator_rsi_obv`, and
  `consensus_rsi_obv` with one deterministic long-only rulebook for Swing and
  one for Mid-term. Volume becomes a prior-only magnitude gate, not a score
  vote. MA and Alligator must each be strict local `Up` (`point >=3`) through
  one shared joint-trend predicate; no average or 60-point trend bucket is
  permitted. RSI upcross, volume, ADX, and optional VN-Index AND are required
  entry gates. Rulebook indicator functions are Backtest-owned and import
  nothing from Analyze; named missing or non-finite required inputs explicitly
  block entry before Boolean gates. Monitoring maps the same joint predicate to
  trend strength `1.0` or `0.0`, so a disagreement cannot inflate the match
  level.
- Swing: daily EMA(5/13), RSI(9) upcross 52, causal Alligator 8/5/3 with
  5/3/2 lags, volume >=1.3× prior 10-session average, ADX(14) >=20, minimum
  exit delay three completed sessions, inclusive max hold 22 bars, `n >=22`.
- Mid-term: weekly SMA(8/21), RSI(14) upcross 70, causal Alligator 13/8/5 with
  8/5/3 lags, volume >=1.5× prior 8-week average, ADX(14) >=25, exit eligible
  next weekly bar, inclusive max hold 16 bars, `n >=20`. Resample `W-FRI` and
  exclude the last labelled week while today is on/before its Friday label;
  retain a holiday-short week after its Friday label passes. The named boundary
  fixture excludes the labelled row on Thursday/Friday and includes it on
  Saturday/following Monday; there is no Monday-only block.
- No-theme is a genuine one-trial PSR result and never runs a hidden VN-Index
  companion. A themed request runs no-theme and VN-Index AND in the same
  ticker/horizon; only the themed result uses their two-trial DSR family. No
  daily/weekly return series are mixed.
- Monitoring classifications are treatment-specific: Swing themed `<=50`,
  `>50–<65`, `>=65–<90`, `>=90`; Swing no-theme `<=50`, `>50–<65`,
  `>=65–<80`, `>=80`; Mid-term themed `<=40`, `>40–<60`, `>=60–<85`,
  `>=85`; Mid-term no-theme `<=40`, `>40–<60`, `>=60–<80`, `>=80`
  (No Match, Weak, Nearly, Closely). With failed joint trend and every other
  factor full strength, the `85/75/80/75` ceilings stay below `Closely`.
- V2 artifacts have no reader, fallback, conversion, warning, or maintenance
  path. V3 uses horizon-qualified paths. After the full V3 gate passes and one
  manual Backtest proves a valid nonempty V3 signal set, an explicit bulk
  backfill inventories legacy filenames only and runs every target across both
  horizons with theme enabled, writing no-theme and themed V3 results. Every
  requested treatment gets one `success`, `empty`, or `failed(reason)` terminal
  V3 document; a completed batch tracker—not a fictional multi-file atomic
  write—gates cleanup. Empty certification records one controlled rejection
  reason (including `missing required no-theme DSR companion`); unavailable
  date ranges are paired null dates with a reason. Failed targets do not retain
  V2 as current evidence.
  Only after its terminal report may the user approve exact V2-path deletion.
  Existing frozen position snapshots stay usable without an
  artifact lookup. The approved V3-only cutover also removes V2 batch-job
  protocol acceptance, result-root migration/recovery, compact score replay,
  V2 catalog/group `N/A` discovery, and V2 result/download paths. Validate must
  use V3 rulebook gate/match data and scope every result/widget by
  ticker+horizon+theme. New saved-set position identity is
  ticker+horizon+theme+rulebook+metric-group; old positions remain
  P&L/manual-management history only. Every V3 result generates fresh
  `audit_eligibility`: clean needs valid OHLCV, <=1% OHLC mismatch, and no
  >=15% close discontinuity; indeterminate/ordering-only-invalid normal
  results remain available but audit-ineligible.
- Diagnostics now use `_requested_dates`, `_build_confirmation_frame`, and the
  current two-argument `_theme_signal`; the Task 0 focused Docker gate passed
  24 tests with one expected scripts-not-mounted skip. The roster audit uses
  one bounded parameterized raw-connection query and made no database, job, or
  signal-artifact write. Earlier V2 frozen-universe counts remain historical
  evidence only.

Design:
`docs/superpowers/specs/2026-08-15-horizon-rulebook-signal-redesign-design.md`.

Plan:
`docs/superpowers/plans/2026-08-15-horizon-rulebook-signal-redesign.md`.

### Completed — Validate Positions Risk and Trade-row Presentation Phase A (2026-08-22)

**Status:** Phase A and Phase B are complete and verified against the current
schema-4 V3 replacement. Phase B evidence:
`docs/superpowers/reports/2026-08-25-validate-positions-phase-b-verification.md`.

- Phase A adds the unavailable-risk-model tab and collapsible BUY/SELL rows.
  `View Signals` stays a read-only popover in Collect and Validate, so the page
  has exactly four top-level tabs. Filters, sort, refresh, New Position,
  selection/delete, local edit, save, manual close, and confirmed deletion are
  preserved. BUY Risk Suggestion is `N/A` until Phase B; a CLOSED position
  strikes only a non-`N/A` saved value.
- Phase B remains unimplemented. Its risk formula, bands, full result table,
  risk persistence, batch evaluation, and any V2/pre-V3 treatment require a
  separate approved design and plan.

Design:
`docs/superpowers/specs/2026-08-16-validate-positions-risk-and-trade-rows-design.md`.

Plan:
`docs/superpowers/plans/2026-08-16-validate-positions-risk-and-trade-rows.md`.

Verification:
`docs/superpowers/reports/2026-08-22-validate-positions-phase-a-verification.md`.

- **Completed archive — Backtest Batch Input and Saved-Signal Persistence
  (2026-08-14):**
  - Backtest metric displays now use plain `Win Rate`, `%Profit`, and `Sharpe`;
    Validate Signals defaults to Ticker, Metric, Match Level, and Match
    Classification first. View Signals filter labels are `Ticker` and `Ticker
    Groups` without changing filter behavior.
  - Collect Signals now accepts one through fifteen unique uppercase
    comma/space-separated tickers in entered order and runs the existing
    sequential batch. Manual Validate Signals remains one through five.
  - Empty certification never creates or overwrites a ticker/theme artifact;
    a nonempty result atomically creates or replaces only its current variant.
    Docker gates pass 52/52, 69/69, 29/29, Job Runner 10/10, and final focused
    Backtest 94/94. Compilation, metric-copy, and whitespace audits pass. No
    SQL, price, signal, position, dependency, Docker, credential, or commit
    change. Design, plan, and verification:
    `docs/superpowers/specs/2026-08-14-backtest-batch-and-signal-persistence-design.md`,
    `docs/superpowers/plans/2026-08-14-backtest-batch-and-signal-persistence.md`,
    and
    `docs/superpowers/reports/2026-08-14-backtest-batch-and-signal-persistence-verification.md`.
- **Completed archive — View Signals Current-Tab Ticker Filter (2026-08-13):**
  - Add one label-hidden View Signals textbox with placeholder `ticker name`.
  - Use the existing auto-capitalize callback and case-insensitive partial
    ticker matching; filter only the currently displayed result table.
  - Warnings and tab availability remain intact. No catalog artifacts, actions,
    jobs, replay, position state, SQL, BIGINT prices, dependencies, Docker, or
    commit history changed. The Backtest page/catalog gate passes 44/44;
    compilation, whitespace, and live health checks pass. Design, plan, and
    verification:
    `docs/superpowers/specs/2026-08-13-view-signals-ticker-filter-design.md`
    `docs/superpowers/plans/2026-08-13-view-signals-current-tab-ticker-filter.md`,
    and
    `docs/superpowers/reports/2026-08-13-view-signals-current-tab-ticker-filter-verification.md`.
- **Completed archive — View Current Signal Sets Popover (2026-08-13):**
  - Add native `View Signals` beside Collect Signals `Run backtest`; it must
    close through native click-outside/Escape behavior and contain no actions.
  - Read every current ticker/theme artifact only. Valid rows show Ticker,
    Theme YES/NO, Metric, Horizon, Certified at, n, Win rate %, Profit %, and
    Sharpe.
  - Invalid artifacts become red rows with these same fields and separate
    warnings. Render All/Valid/Invalid only if invalid data exists; otherwise
    render All only.
  - Preserve job, replay, persistence, SQL, BIGINT, dependencies, Docker, and
    commit behavior. The read-only catalog uses the existing artifact loader;
    malformed artifacts become red rows plus warnings without hiding valid
    rows. The Backtest page/catalog gate passes 43/43; compile, whitespace,
    and live health checks pass. No commit was created. Plan and verification:
    `docs/superpowers/plans/2026-08-13-view-current-signal-sets.md` and
    `docs/superpowers/reports/2026-08-13-view-current-signal-sets-verification.md`.
- **Completed archive — Collect Signals Theme-Checkbox Alignment (2026-08-13):**
  - An `Action` label above `VN-Index theme` aligns it with the
    ticker input and dropdown boxes.
  - Checkbox default, disabled state, config variants, SQL, BIGINT pricing,
    dependencies, Docker, and commit history remain unchanged.
  - RED/GREEN AppTest coverage is recorded in
    `docs/superpowers/reports/2026-08-13-collect-signals-theme-alignment-verification.md`;
    the Backtest/Data Page gate passed 39/39.
- **Completed archive — Data Page Phase-Progress UI (2026-08-13):**
  - Put `Up-to date`, `Year gaps`, and `Get data` on one first row; an `Action`
    label aligns the button with the date and number input boxes.
  - Replace the loading spinner with truthful phase progress: reset, schema,
    stock, VN-Index, and completion, from 0 to 100%.
  - Keep detailed ingestion messages inside an initially-expanded `Progress
    details` section. Failure keeps the last completed phase; never show false
    success.
  - The optional callback must retain API/background headless behavior and must
    not alter reset semantics, URLs, schema, BIGINT `* 1000` price scaling,
    SQL, credentials, Docker, dependencies, or commit history.
  - Detailed test-first plan and verification:
    `docs/superpowers/plans/2026-08-13-data-page-phase-progress.md` and
    `docs/superpowers/reports/2026-08-13-data-page-phase-progress-verification.md`.
  - Focused Data Page tests and the wider Streamlit gate pass 39/39;
    compilation, diff check, and live health pass. No real ingestion or commit
    was made.
- **Completed archive — Current Positions Bulk Delete UI Enhancement
  (2026-08-12):** Design:
  `docs/superpowers/specs/2026-08-12-current-positions-bulk-delete-design.md`.
  Test-first plan:
  `docs/superpowers/plans/2026-08-12-current-positions-bulk-delete.md`.
  Verification:
  `docs/superpowers/reports/2026-08-12-current-positions-bulk-delete-verification.md`.
  All four tasks are complete; no commit was created.
- **Completed archive — Validate Signals Drafts and Manual Positions (2026-08-12):**
  - Design:
    `docs/superpowers/specs/2026-08-11-validate-signals-drafts-and-manual-positions-design.md`.
    Detailed test-first plan:
    `docs/superpowers/plans/2026-08-12-validate-signals-drafts-manual-positions.md`.
  - Fix Match Level root cause: score similarity must be independent of
    VN-Index theme eligibility; eligibility still blocks Validate Signals BUY
    and SELL draft actions.
  - Replace summary multiselect/direct forms with grouped one-row selection,
    gated session-only BUY/SELL drafts, leaf-only indicator labels, date-only
    signal dates, `k` price labels, and hidden-by-default Date range.
  - Add generic atomic manual history for optional saved-set links and P&L-only
    records; retain legacy tuple histories without migration. Direct Current
    Positions actions may create OPEN/CLOSED records and close exact OPEN
    records without advisory-gate enforcement.
  - Add database-derived completed-session hold time. For non-trading manual
    BUY dates, signal monitoring begins at first ticker session on/after BUY.
  - Do not change artifacts, replay rules, database data, price scaling,
    protected boundaries, Docker, dependencies, or commit history.
- **Revamp Validate Signals UI (completed 2026-08-11):**
  - Approved design and implementation plan:
    `docs/superpowers/specs/2026-08-11-validate-signals-ui-revamp-design.md`
    and `docs/superpowers/plans/2026-08-11-validate-signals-ui-revamp.md`.
    Tasks 1–5 are complete. Verification evidence:
    `docs/superpowers/reports/2026-08-11-validate-signals-ui-revamp-verification.md`.
  - Docker RED/GREEN coverage now proves Validate hierarchy/progress, individual
    manual decisions, Current Positions filtering, P&L presentation, and price/
    quantity edits. A dedicated `Remove quantity` control makes optional
    quantity reversible after it was originally recorded.
  - After the user clicks `Validate saved signals`, show progress only until
    the current read-only validation request returns or fails; hide it after
    either terminal outcome.
  - Render No theme result first, then VN-Index AND; each group title owns its
    corresponding signal sets. Render a collapsible signal-set summary next,
    then a collapsible detail view for each selected signal set; users may
    expand several detail panels at once. Summary and detail panels start
    collapsed.
  - Redesign explicit manual BUY/SELL recording for one-or-more selected signal
    sets while preserving independent ticker/theme/metric positions, locked BUY
    as-of dates, and never-auto-close behavior.
  - Summary default fields: Identity (ticker, selected metric); Strategy
    (indicators, BUY threshold); Backtest performance (`n`, win rate %, profit
    %, Sharpe, deflated Sharpe, p-value, date range); Current match (match %,
    classification, advice, theme eligibility); Current trade signal (signal
    date, entry, SL, TP, projected exit); Existing-position state (status,
    holding/suggested holding, SELL allowed/reasons, pinned SL/TP). Other
    available fields start hidden; a column-visibility filter controls their
    display and resets each browser session. Retain current per-set detail
    content.
  - Add `Current Positions` as a third top-level Backtest Lab tab beside
    `Collect Signals` and `Validate Signals`. Render all OPEN positions
    immediately. Filter by ticker and state; default to OPEN and hide CLOSED.
    Combine themed and no-theme positions equally and order oldest first by
    open time. Use an explicit Refresh button that reloads saved positions plus
    latest prices and recalculated P&L. Each position shows ticker, BUY price,
    SELL price or `-`,
    percentage profit, profit, open time, closed time, and signal set.
    OPEN positions also show latest trading-day price and its resulting
    unrealized profit/%. P&L is per-share price difference with no fees or
    taxes. Manual BUY/SELL forms keep user-editable actual price fields. An
    optional quantity multiplies absolute P&L; without it, profit remains the
    simple per-share price difference. Quantity and BUY/SELL prices remain
    editable after recording, overwrite only their current values, and never
    change the position open or closed time. OPEN positions show SELL price and
    closed time as `-`.
  - Keep BUY and SELL recording in `Validate Signals`: show a BUY or `Close
    position` action beside each applicable suggestion. Use individual action
    forms per eligible item; do not provide a batch selection/shared form.
    Current Positions is the saved-position list/filter/edit view for saved
    quantity and BUY/SELL price values. Its explicit `Refresh positions` action
    reloads saved records, latest closes, and P&L without creating a record.
  - No replay, strategy, price scaling, artifact, database, or risk/holding
    logic changed. No commit made.
- **Spike and Build Validate Signals Advice and Position Monitoring (completed 2026-08-09):**
  - Turn Backtest Lab's static Validate Signals tab into a read-only check of
    already-certified signal sets. The theme checkbox mirrors Collect Signals:
    unchecked checks no-theme only; checked reports no-theme and VN-Index AND
    variants independently.
  - Matching is capped `current_score / threshold_score_buy * 100`. A required
    unconfirmed VN-Index theme is ineligible. `<70%` advises Observe,
    `70%–<85%` is Nearly match, and `>=85%` is Closely match.
  - A no-position eligible set advises BUY. Users may confirm one or more sets;
    each creates a separate `(ticker, theme_variant, metric)` record with UI
    `k VND` price converted to raw integer storage. Open records pin strategy
    and risk values against later signal-artifact replacement.
  - Open positions display matching plus stored ATR SL/TP/timeout state. SELL
    remains manual and becomes allowed after `>60%` native max-hold or price is
    within/beyond 5% of stored SL/TP. Swing remains daily; Mid-term remains
    weekly. Phase 0 must prove buy-date/weekly-bar mapping before code.
  - Plan: `docs/superpowers/plans/2026-08-07-validate-signals-position-monitoring.md`.
  - **Task 0 completed (2026-08-09):** The read-only spike confirms current
    FPT signal files are empty while temporary non-empty artifacts round-trip
    correctly. The focused Docker contract gate passes 28/28. Existing replay
    reloads FPT once per metric and lacks current score/ATR/latest-close/as-of
    output; Task 1 will close that measured gap. A Mid-term mid-week fixture
    proves `W-SUN` is only a period label: no future source row was read. The
    frozen contract uses raw source max as as-of, counts native daily/weekly
    periods only, and never adds daily Mid-term exits. The current malformed
    running `DATABASE_URL` is documented as a Task 6 live-validation
    precondition, not a test failure. Report:
    `docs/superpowers/reports/2026-08-07-validate-signals-spike.md`.
  - **Task 1 completed (2026-08-09):** Replay now returns current score, raw
    latest close/ATR, and raw-source as-of date even without a crossing. It
    validates document/set ticker-theme-horizon metadata and reuses one
    validated ticker frame (and one VN-Index confirmation frame when needed)
    for all metrics in a coherent artifact. The read-only advice primitive
    applies the exact capped match bands and reports unavailable artifacts or
    null metrics explicitly. The focused Docker gate passes 18/18; container
    compilation passes; a mocked success path proves it does not run jobs,
    pipeline, certification, or signal persistence. Await Task 2 signal.
  - **Task 2 completed (2026-08-09):** UI `k VND` prices convert with exact
    `Decimal` arithmetic to positive raw BIGINT values, rejecting invalid or
    more-than-three-decimal inputs. Each `(ticker, theme_variant, metric)` now
    has a schema-validated append-only atomic JSON history with one open record
    maximum. A record freezes JSON-safe certified, entry, and caller-supplied
    risk snapshots; explicit manual SELL updates only the named open record,
    retains closed history, and permits a new open record. The focused Docker
    gate passes 9/9; compilation and whitespace checks pass. Await Task 3
    signal.
  - **Task 3 in progress:** Add RED native-clock monitor coverage before
    calculating holding time, proximity, or manual SELL eligibility.
  - **Task 3 completed (2026-08-09):** The read-only monitor validates raw
    OHLCV, slices at as-of before any calculation, counts Swing daily bars and
    Mid-term weekly periods only, and blocks same-week Mid-term exits. It
    allows manual SELL only after the native minimum and the approved >60% or
    SL/TP-proximity condition; timeout remains informational. The native plus
    existing lifecycle Docker gate passes 17/17.
  - **Task 4 complete — advice composition:** Existing saved artifacts now
    render per metric and theme as unavailable, Observe, BUY eligible, or
    pinned open-position monitor state. Theme variants are independent: a
    malformed position file makes only its own variant unavailable. Validation
    neither submits a job nor writes signal or position data. Docker replay,
    advice, store, and monitor gate passes 30/30. Task 5 adds the manual page
    orchestration.
  - **Task 5 complete — manual Validate Signals UI:** `backtest_lab.py` now
    validates only after a user click, keeps result identity tied to ticker and
    theme selection, renders independent variants/metrics, and shows clear
    unavailable states. Multi-selected eligible tuples use one user-entered
    `k VND` BUY price but a BUY date locked to each common validation as-of;
    the page converts price in Python and freezes as-of ATR 1.5x/2.5x exits.
    Open positions show pinned risk, native holding, current match, and SELL
    reasons; SELL remains explicit/manual. No validation action submits a job,
    refreshes status, trades, or auto-closes. Docker page/job/replay/advice
    gate passes 47/47. Task 6 records full verification evidence.
  - **Task 6 complete — evidence and review:** Final explicit Backtest Docker
    gate passes 105 tests with one expected diagnostics skip because top-level
    `scripts` are not mounted. Compile and whitespace checks pass. A real FPT
    live-safe run used only temporary artifacts/positions: no-theme and
    VN-Index AND replayed, two no-theme tuples shared locked as-of date
    `2026-08-07`, raw/UI price round-trip was exact, manual close retained
    history, and temporary data was removed. Self-review fixed Ho Chi Minh
    SELL date default and preflights all selected BUY tuples before any write.
    Evidence: `docs/superpowers/reports/2026-08-07-validate-signals-verification.md`.
- **Diagnose Empty FPT Backtest Signal Sets (completed archive):**
  - The 15-year Swing FPT no-theme job `24bac55bd995444eaf4dc6a9118f5758`
    and VN-Index `AND` job `6086db3928344074b0046a7a4234c9ef` both completed
    at progress `1.0` without an error and wrote their expected output paths.
    Both current JSON artifacts contain `empty: true` with `win_rate`,
    `profit`, and `sharpe` all `null`; this proves that the symptom is an empty
    certification result, not a failed job or missing artifact.
  - Source-level triage identifies a high-confidence score-input contract
    mismatch: `build_indicator_frame()` produces numerical columns such as
    `RSI_14`, `%K`, `ATR_14`, and `BBM_20_2`, but `score_combo()` looks for the
    indicator names `MA`, `MA cross`, `RSI`, `Stochastic`, `OBV`, `ATR`, and
    `Bollinger`. Only numeric `OBV` matches; it is not a trend key and falls
    back to the neutral value `2`, producing a 50 score below threshold 60.
  - Before a repair, execute the approved test-first debug plan at
    `docs/superpowers/plans/2026-08-04-backtest-zero-signal-investigation.md`.
    It will produce a read-only FPT funnel report covering data quality,
    per-dimension score contributions, score range, crossings, trade exits,
    theme filtering, and certification rejections. It explicitly tests the
    score-input contract, ADX semantics, and warm-up hypotheses without
    weakening certification rules. Before any downstream full-grid measurement,
    it also requires the Swing long-only lifecycle repair: each Phase 1
    TradeEvent is an implicit equal-unit BUY/SELL pair, `VNINDEX` stays
    confirmation-only, and Swing SL/TP/timeout exits cannot occur before entry
    plus three daily bars.
  - The current incident is scoped to FPT Swing over 15 years. The plan first
    preserves the existing JSON artifact/status evidence, then proves the
    earliest failing stage. A positive crossing count is not by itself a
    healthy-score verdict: if the first unexplained failure is insufficient
    crossings/trades for `MIN_N`, the plan returns to score coverage before
    accepting a statistical-gate explanation. The approved Mid-term repair is
    all-weekly: ticker indicators, ATR, crossings, execution, and
    `MAX_HOLD_MIDTERM_BARS = 16` remain weekly; exits first become eligible on
    the next weekly bar and timeout closes at inclusive bar 16. Task 7 must
    prove this contract without a daily execution path. Downstream DSR
    conclusions require an unannualized/Pearson conformance check, while
    overlapping-window duplicates are reported without changing approved
    validation input.
  - **Task 0 completed (2026-08-06):** both terminal job sidecars and their
    current empty artifacts were re-read and SHA-256 baselined; the focused
    `test_backtest_signal_combos` and `test_backtest_validation` Docker gate
    passed 9/9. Source conformance confirms hard-ADX per-row normalization and
    unannualized/Pearson DSR. It also confirms the separate current Mid-term
    daily-ticker/weekly-VN-Index mismatch; the approved all-weekly repair is
    reserved for Task 7.
  - **Task 1 completed (2026-08-06):** after the live runtime URL was
    corrected, the exact FPT Swing/60/soft-ADX read-only probe used one
    all-dimension combo and returned 3,736 scores, all equal to the neutral
    fallback `50`. Only raw `OBV` matched the seven requested trend-label
    inputs; there were zero threshold hits and zero BUY crossings. This is a
    valid measurement that selects **Task 2: repair the score-input contract**.
    The earlier empty-port Compose blocker and the exact probe output are
    retained in the triage report. No job, artifact, status sidecar, database
    write, production change, or commit was made.
  - **Task 2 completed (2026-08-06):** the approved canonical MA sources are
    Swing `5/10` and Mid-term `4/12`. `build_indicator_frame()` now adds seven
    causal `backtest_signal_*` label columns while preserving raw numeric
    indicators; `score_combo()` reads the mapped labels and retains bare-name
    fallback only for legacy synthetic tests. The RED gate produced the
    expected missing-contract/numeric-OBV failures; the focused adapter,
    scorer, pipeline, early-warning, and trade gate passed 27/27. The
    read-only FPT rerun resolved all seven inputs, reached the threshold on
    1,358 rows, and produced 228 BUY crossings. This selects **Task 5:
     Swing-only minimum-hold lifecycle**; Tasks 3 and 4 are not selected. No
     job, artifact, status sidecar, database write, or commit was made.
  - **Task 5 completed (2026-08-06):** the RED lifecycle gate proved that
    historical and replay Swing execution could close at entry and accepted a
    three-bar custom hold. `MIN_EXIT_OFFSET_SWING_BARS = 3` now supplies one
    shared eligibility boundary to both paths: SL/TP may resolve only from
    entry + 3 daily bars, stop-first ordering is retained, and an inclusive
    custom Swing hold below four bars is rejected. The focused Docker trade,
    rolling-window, and early-warning gate passed 17/17. Mid-term execution,
    SQL, BIGINT values, scoring, crossings, jobs, artifacts, status sidecars,
    database state, and commits were untouched. **Task 6** is next for
    read-only downstream trade and certification measurement; Tasks 3 and 4
    remain unselected.
  - **Task 6 completed (2026-08-06):** the DSR conformance gate passed 5/5,
    confirming the approved unannualized/Pearson/observed-trial-variance and
    DSR-before-permutation convention. The new read-only collector records
    production-path funnel counts, raw versus unique overlap events, and
    validation outcomes per canonical combo key without calling the pipeline,
    certification, persistence, or job runner. Full 15-year FPT Swing reports
    show no first insufficient stage: no-theme has 123 qualified of 270 combos
    in 1,373.494 seconds, while VN-Index `AND` has 43 in 1,242.933 seconds;
    every combo exceeds `MIN_N`. The old empty artifacts are therefore not
    reproduced by the current repaired Swing path. Duplicate-event rates are
    80.86% and 80.98%; validation intentionally retains the approved raw event
    sequence, and any deduplication or `MIN_N` change needs a separate
    statistical-design decision. The two per-combo JSON reports are under
    `docs/superpowers/reports/`. Tasks 3 and 4 remain unselected. No job,
    signal artifact, status sidecar, database write, or commit was made.
  - **Task 7 completed (2026-08-07):** the former Mid-term daily-ticker versus
    weekly-VN-Index mismatch is repaired by one shared `to_weekly_ohlcv()`
    adapter. Mid-term ticker indicators, ATR, crossings, execution input, and
    VN-Index confirmation now share weekly bars; Swing stays daily. The named
    `MAX_HOLD_MIDTERM_BARS = 16` timeout is inclusive (entry bar 1 through
    timeout bar 16), and SL/TP begins at the next weekly bar. The all-weekly
    Docker conformance gate passed 42/42 and the unchanged Swing lifecycle
    regression passed 20/20. A read-only FPT 15-year Mid-term probe found 775
    weekly scores from 3,736 daily rows, 410 scores at or above 60, and 41 BUY
    crossings. No job, artifact, status sidecar, database write, SQL, BIGINT,
    or commit change was made. **Task 8** (final verification and
    documentation) is next; do not start it without user signal.
  - **Task 8 completed (2026-08-07):** the explicit Backtest Docker gate
    passed 60/60 after a stale mocked diagnostics-CLI payload was aligned with
    the existing summary contract; no production source changed. Host
    compilation and `git diff --check` passed. Generic Docker discovery is not
    a valid final gate because `tests/` is not an importable package for
    worker-factory fixtures and `scripts/` is not mounted; that pre-existing
    test-layout limitation remains documented separately. The FPT zero-signal
    investigation plan is complete; Tasks 3 and 4 were never selected by its
    evidence. No job, artifact, status sidecar, database write, SQL, BIGINT,
    Docker, credential, dependency, or commit change was made.
- **Implement Comprehensive Unit Testing (Priority 2 — paused):**
  - Expand `unittest` coverage for all project functions while preserving
    existing behavior and protected boundaries; the function inventory is
    complete.
  - Start module-by-module with `app/commons/`, using a test-first plan and a
    focused validation gate for each completed module.
  - Export tests are already included; do not add dependencies or refactor
    production behavior unless a separately approved failing test proves a
    defect.
- **Build Per-Ticker Signal-Set Backtest Engine (Completed baseline):**
  Phase 0 contracts, Phase 1 data-quality/raw-history/indicator adapters,
  Phase 2 combo generation/scoring, Phase 3 rolling/trade execution, and
  Phase 4 VN-Index theme alignment, Phase 5 statistical validation and
  certification, Phase 6 early-warning replay, Phase 7 offline job
  runner/status polling, Phase 8 standalone Backtest page, and Phase 9
  profiling/verification/documentation handoff are complete. Cumulative
  backtest and Technical Analyze focused tests pass 69/69 in Docker;
  protected boundaries are unchanged.
  Phase 5 uses unannualized per-trade PSR/Deflated-Sharpe math from
  `BACKTEST_ENGINE.md` §3.3, exact trial-count variance, min-n gating, and
  shortlist-only centered moving-block permutation. Certification selects one
  qualified set per metric and atomically overwrites only the selected
  ticker/theme JSON file. Phase 6 replays persisted scoring, ATR exits, and
  saved VN-Index conditions against fresh bounded data, with explicit current
  states, timeout resolution, theme suppression/OR behavior, certification
  age, and certified-vs-current diff. The shipped baseline remains long-only
  BUY with ATR TP/SL/timeout exits; the active zero-signal plan now adds the
  approved three-session minimum before any such SELL closure may execute.
  The 2026-08-04 worker repair replaces the original
  spawned job pool with an isolated `python -m backtest_engine.worker`
  subprocess: the parent atomically writes a JSON request, no callable crosses
  the process boundary, and terminal JSON status is retained for worker errors.
  Phase 8 is wired into legacy navigation, submits the environment-backed
  pipeline, automatically repolls queued/running/unreadable statuses each
  second without a Refresh button, renders three metric sections/empty state,
  and downloads JSON or Markdown artifacts. Phase 9 recorded the 15-year SSI baseline profile,
  focused Docker verification, the full-discovery exception, boundary checks,
  and documentation in
  `docs/superpowers/reports/2026-08-02-backtest-engine-verification.md`.
  The full Docker discovery result is 194/195 because the container does not
  mount the pre-existing top-level `scripts` helper package; this is outside
  the feature implementation. Every implemented phase passed its RED/GREEN
  gate before advancement.
  Standalone page: `app/pages/backtest_lab.py`; engine package:
  `app/backtest_engine/`. Plan:
  `docs/superpowers/plans/2026-08-02-per-ticker-backtest-engine.md`.
  Worker/autostatus repair plan and verification:
  `docs/superpowers/plans/2026-08-04-backtest-worker-autostatus.md` and
  `docs/superpowers/reports/2026-08-04-backtest-worker-autostatus-verification.md`.
  Runtime guard and two-tab follow-up plan and verification:
  `docs/superpowers/plans/2026-08-04-backtest-runtime-guard-and-tabs.md` and
  `docs/superpowers/reports/2026-08-04-backtest-runtime-guard-and-tabs-verification.md`.
  Compose must receive root `.env` via `--env-file .env` during interpolation;
  the `env_file` declaration alone is insufficient for constructing
  `DATABASE_URL`.
## 4. Known Issues & Technical Debt
- Full Docker `unittest discover -s tests` remains noncanonical and currently
  fails before Multi-Group paths run: `backtest_engine.diagnostics` imports
  deleted pipeline helper `_default_dates` and calls stale `_theme_signal`
  arguments; discovery-only job-worker fixtures resolve as top-level modules
  instead of `tests.*`; and `scripts` is not mounted for
  `test_trend_classification_probe`. The current focused Backtest Docker gate
  passes 108/108. Treat test topology/diagnostics repair as a separate task;
  do not weaken the focused Backtest gate. Evidence:
  `docs/superpowers/reports/2026-08-14-backtest-multi-group-membership-verification.md`.
- Historical technical context still reads the full ticker history without a
  date bound. This is retained for exact prefix/as-of semantics; score processing
  is now precomputed in linear history time. A future SQL bound requires a
  separately verified as-of design.
- Full Docker unittest discovery remains noncanonical: `discover -s tests`
  loads worker fixtures as top-level modules and cannot import unmounted
  `scripts`, while `-t .` rejects the non-package `tests/` directory. Use
  explicit module gates until a separately approved test-topology repair.

## 5. Next Steps & Priorities
1.  **Comprehensive Unit Testing:** Implement `unittest` suites for all modules, starting with `commons/`; include export tests when the feature is added.
2.  **Build Per-Ticker Signal-Set Backtest Engine:** Complete; maintain the shipped engine and address only separately approved follow-up work. Preserve offline execution, no look-ahead, multiple-testing control, and overwrite-only current signal files.
3.  **Technical Indicator empirical validation:** Broader 64-ticker sample is measured; extend only with separately approved datasets and recalibrate only from measured results.
4.  **Technical Indicator Enhancement — Phase 1:** Deferred until high-effort `pandas_ta` tech debt is separately approved.
5.  **Legacy indicator backlog:** Bollinger visualization is covered by the UI integration plan; Ichimoku is intentionally removed from scope.
6.  **Define explanation of Final Advice:** Keep as a later documentation refinement after the UI workflow plan.

---
*Last Updated: 2026-08-26 (Flexible Rulebook Core Plan Task 2 complete: isolated
history quality/fingerprint/anchor/split adapter, combined Docker gate 36/36,
compilation pass; Task 3 FeatureStore/lazy-mask slice passes 7/7 while catalog
settings and primitive cache remain blocked. The amended design/ordered plans lock 75%
training-overlap Top-3 distinctness, fresh-source per-primitive cache reuse,
FeaturePlan/receipt-verified frozen Continue, under-five-hour maximal-slot
budgeting, parity-gated fast execution, and UI contract. Horizon Rulebook Signal Redesign schema-4 replacement and Validate
Positions Phase B are complete. Original V2 deletion remains unapproved.)*
