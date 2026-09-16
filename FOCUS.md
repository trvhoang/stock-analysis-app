# FOCUS.md
# Updated: 2026-09-17

## Current Task

**UI enhancement revamp (2026-09-17; UI_AUDIT complete, awaiting review):**
The governed UI process is at `UI_AUDIT`; implementation remains prohibited.
The evidence-based audit is saved at
`docs/superpowers/features/ui-enhancement-guides-revised/artifacts/2026-09-17-current-ui-audit.md`.
It confirms a native Streamlit foundation with flat top navigation, shared icon
and dataframe helpers, but finds inconsistent page/action hierarchy, feedback,
and table conventions. The highest-impact dedicated slices are Backtest density
and Analyze/Suggestion result/run-state clarity. Runtime keyboard, contrast,
and narrow-screen evidence remains unknown. No application code or behavior was
changed. Review/approval of the audit is required before `UI_ARCHITECTURE`.

**Flexible Rulebook user-authored selective replacement (2026-09-15; complete):**
Tasks 0–9 are complete. The app now uses only the `flexible_rulebook.v2`
runtime: Rulebook Builder, Rulebook Backtest, and Rulebook Library replace the
retired automated-discovery workflow. Backtest Collect defaults to Standard;
published Flexible rules are isolated in their own artifact schema and display
only a short `Flexible · FR-…` identity. Standard schema-5 behavior remains
unchanged. Flexible Position references retain the full immutable ID backstage;
they deliberately have no fabricated Baseline V5 risk snapshot.

Final Docker evidence: v2 regression **77/77** and full discovery **696/696**
passed on 2026-09-17. A temporary live VCB collection/reload smoke succeeded
for both Swing (4,005 daily bars, 283 current events) and Mid-term (830
completed W-FRI bars, 59 current events), with a 65% chronological split and
the actual session bounds persisted. A Decimal serialization defect discovered
by that smoke is fixed: immutable definition/evaluation Decimal values now use
the v2 tagged canonical form in Flexible artifacts, with focused adapter
regression **9/9**. The legacy audit reports zero retired runtime modules and
zero retired behavior tests; both preserved legacy artifact roots remain empty
with SHA-256 `e3b0c442…b855`. No project signal artifact, live rulebook,
position, or database row was created by the smoke.

The implementation plan is complete:
`docs/superpowers/plans/2026-09-15-flexible-rulebook-user-authored-redesign.md`.
Known limitation: Flexible risk advice is intentionally unavailable for an
open Flexible position until a definition-owned risk contract is explicitly
designed; this avoids inventing Standard ATR stop/timeout semantics.

## Historical implementation detail

**Flexible Rulebook user-authored selective replacement (2026-09-15; Tasks 0–5
complete, Task 6 complete, Task 7 in progress):** The existing
automatic Discover/benchmark/activation/campaign/scope-expansion/qualification
runtime is now inventory-frozen—correctness fixes only, with no new discovery
features—and will be retired only after replacement verification. Task 0 added
a read-only legacy audit plus the final cutover contract. The production
inventory records 26 v1 runtime modules, 26 v1 tests, one benchmark-policy
reference, no Backtest/Position package reference, and two present but empty
artifact roots (`/app/Flexible-Rulebook`, `/data/flexible-benchmark`) with the
empty-tree SHA-256 digest. Before the new cutover contract, the focused
Flexible suite passed 327/327 in 22.755s and the full suite passed 925/925 in
46.332s. The new contract is intentionally RED on exactly three future-cutover
assertions; its read-only inventory assertion passes. No v1 runtime or artifact
was modified. The post-contract focused run executed 331 tests in 23.161s:
328 passed and exactly the three expected cutover assertions remained RED.
Task 7 has begun with a strict `backtest_engine.flexible_adapter`: one atomic
Flexible artifact per ticker/horizon/full rulebook ID in a sibling result root,
never schema-5. Its read-only catalog projection shows `Flexible · FR-…` while
retaining full rulebook/evaluation identities only in private fields. Published
collection now retains all causal entry events and loads each ticker raw source
once across selected definitions; Collect Signals has a Standard-default source
selector, filters active published rules by horizon, and runs Flexible chunks
sequentially. Fresh Docker adapter/service/catalog verification passes **13/13**
and Backtest page/helper regression passes **115/115**. Flexible validation,
position-reference, and removal integration remain pending.
Task 1 adds an isolated `flexible_rulebook.v2` contract/registry slice: one
immutable Daily Swing or completed-W-FRI Mid-term semantic rulebook; typed
BUY/gate/technical-SELL predicates; optional bounded ATR exits; fixed 3-bar
minimum hold; 4–64-bar timeout; draft revisions; evaluation identity;
immutable `frb2_` publication/retirement; and collision-safe short IDs. The
registry owns formula revision, native input series, roles, output series,
settings bounds, warm-up, supported predicates, and support projection for the
12 approved families, including Bollinger and Supertrend. Host Task 1 tests
pass **15/15** in **0.003s** and v2 modules compile. Docker was unavailable
after one retry, so no Docker-specific Task 1 result is claimed.
The approved v2 design provides Rulebook Builder, Rulebook Backtest, and
Rulebook Library workspaces; Daily Swing or completed W-FRI Mid-term per
rulebook; ALL/ANY BUY, ALL gates, ANY SELL; editable validated settings for the
project indicators plus Bollinger Bands and Supertrend; database Lifetime
history; adjustable 50–80% chronological training; mutable drafts; immutable
publication without a performance gate; and final Backtest integration with
Standard as default. UI identities are `Standard` or a collision-safe Flexible
short ID while full hashes stay backstage. Flexible classification is Closely
Match `>85%`, Nearly Match `65%..85%`, and No Match `<65%` or
Weakening/Invalidated; raw Standard `weak` remains unchanged in artifacts but
projects as No Match so the UI has exactly three filters. V1 artifacts remain
read-only and are not migrated, moved, or deleted. Task 2 now adds
`commons.causal_indicators` as the authoritative source for SMA/EMA,
SMA-seeded Wilder RSI/ATR/ADX/DMI, HL2 Alligator, Stochastic, prior-only
relative volume/breakout extrema, OBV, Bollinger, and versioned HL2/Wilder
Supertrend. The v2 FeatureStore has math-only component cache keys, all twelve
registry family builders, exact event/support masks, explicit warm-up
diagnostics, and prefix-invariance coverage. Standard Backtest and Technical
Analysis call compatibility wrappers around those primitives. Host verification
passed 41 focused v2/causal/Backtest tests; direct isolated Technical wrapper
parity also passed. The initial finite Supertrend bar is confirmed bullish
(`+1`) and uses the final lower band. Fresh Docker verification then passed
**100/100** across v2 contracts/registry, causal primitives, FeatureStore
masks, Backtest indicators, and Technical Analysis parity. Task 2 is complete;
Task 3 now adds `v2.history` and `v2.cache`: Lifetime/explicit bounded source
loading through the established retry/DBAPI path; live Listed-only skips;
raw-integer OHLCV and VN-Index calendar/source identities; Daily and completed
W-FRI native bars with actual session dates; all approved native-bar splits;
and contained atomic computed-component cache persistence. Cache identity binds
source, calendar, formula build, and math settings while corrupt/mismatched/
locked entries safely miss; timestamps normalize to `Asia/Ho_Chi_Minh`. Fresh
Docker Task 3 verification passed **15/15** in **0.268s**. Task 4 now adds a
linear native-bar reference executor, gross metrics, and Boolean validation:
ALL/ANY BUY, ALL gates, SELL-OR, causal next-open fills, frozen signal ATR,
prior-high-water trailing, stop-first gaps/collisions, timeout, actual W-FRI
sessions, no overlapping trades, and the three approved monitoring classes.
Fresh Docker Task 4 verification passed **14/14** in **0.009s**. Task 5 now
adds contained v2 lifecycle storage, atomic revision-checked drafts, immutable
definition/evaluation/retirement events, and collision-safe library IDs.
Evaluations are sequential and preserve completed items when later tickers
fail; source, feature, execution, metric, and persistence progress is emitted
at the actual phase boundary. The opt-in primitive cache binds raw source,
calendar, timeframe/build, and formula settings, while cache failures remain
safe in-memory work. A draft is Evaluated only by matching completed train/test
evidence; publishing remains explicit and has no performance threshold.
Evaluation results retain native numeric values in memory and canonicalize only
at persistence. Fresh host and Docker verification passed **21/21** across
v2 contracts/storage/service. A read-only Docker VCB smoke evaluation in a
temporary artifact root completed 4,005 Swing bars (2010-08-17 through
2026-09-15). Task 6—the three-workspace Flexible Rulebook page—is complete:
the Builder has registry-driven typed settings/conditions, a causal summary,
revision-safe editing, ATR exits, and reset/clone actions; Backtest supports
draft/published evaluation with cache/progress/trades/diagnostics; and Library
projects collision-safe IDs, evidence history, and lifecycle actions without
full hashes in primary UI. A saved VCB RSI smoke rule evaluated 4,005 Swing
bars and 114 trades, then published and reread from a temporary v2 root. Fresh
Docker verification passed 74/74 non-cutover v2/page/entrypoint tests. Task 7
is now in progress; frozen v1 runtime/artifacts remain untouched.
No v1
runtime/artifact, SQL schema, price scaling, dependency, Docker configuration,
or Git change has been made.
Design and plan:
`docs/superpowers/specs/2026-09-15-flexible-rulebook-user-authored-redesign-design.md`
and
`docs/superpowers/plans/2026-09-15-flexible-rulebook-user-authored-redesign.md`.

**Current Positions ineligible saved-set dates (2026-09-11; complete):** When
the New Position form finds saved signal sets but none is BUY-eligible, the
info message now lists every set on its own Markdown line with its horizon,
rulebook, theme, and signal date. A single result retains the concise summary
date; missing/malformed dates display `—`. Eligibility, signal selection,
positions, artifacts, SQL, price scaling, dependencies, Docker configuration,
and Git remain unchanged. Docker Backtest page regression passes **102/102**.

**Validate Positions P&L Trend triangle (2026-09-11; complete):** The result
table now projects `Ticker | Trend | Profit % | Profit | Risk | Result`.
Trend is display-only and uses raw as-of Profit direction: green `▲` for
positive, red `▼` for negative, yellow `▶` for zero, and unstyled `-` when
P&L is unavailable. The CSS targets only the Trend cell; Profit and Profit %
remain plain values, with Profit formatted to two decimal k-VND places. Risk
calculation, P&L calculation, persistence, SQL,
BIGINT storage, artifacts, dependencies, Docker configuration, and Git are
unchanged. Docker Backtest page regression passes **101/101**.

**Backtest duplicate tab headings removed (2026-09-10; complete):** The six
tab renderers no longer repeat their tab label inside the body—Collect Signals,
View Signals, Validate Signals, Current Positions, Validate Positions, and
Group Manager. The shared `Backtest Lab` page title, tab strip, and contextual
result headings such as `As of` remain. This is display-only; controls, data,
SQL, artifacts, position risk, dependencies, Docker configuration, and Git
are unchanged. Docker Backtest page regression passes **98/98**.

**Validate Positions as-of P&L result columns (2026-09-10; complete):**
The result table now projects exactly `Ticker | Profit % | Profit | Risk |
Result`; Evaluation is removed. The risk engine snapshots Profit % and raw
Profit from the same shared common As of close used for that validation run,
using the existing BUY-to-close × volume formula. Raw Profit is converted only
at the UI boundary to k VND; no-common-as-of, Delisted, or failed rows render
`-` rather than a misleading value. Current Positions and Validate Positions
share one P&L helper, while risk scoring, persistence, SQL, price storage,
artifacts, dependencies, Docker configuration, and Git remain unchanged.
Docker focused Backtest page, position-risk, and position-overview regression
passes **122/122**.

**Validate Positions risk legend and cell markers (2026-09-10; complete):**
Every rendered Validate Positions result table shows a compact color legend
immediately above it: 🟢 Low, 🟡 Medium, 🟠 High, and 🔴 Very. Each native
Swing/Mid-term risk level in the Risk cell now carries its corresponding
circle, so mixed-horizon rows preserve both colors. It is display-only and
uses one shared fixed mapping; no scoring, result data, artifact, SQL,
dependency, Docker, or Git behavior changed. Docker Backtest page regression
passes **97/97**.

**Collect Both default and silent Delisted Validate skip (2026-09-09;
complete):** Collect Signals now defaults Horizon to **Both** and turns one
selection into sequential Swing batches followed by Mid-term batches; each
worker request remains a single valid native horizon. Before Validate Signals
creates its progress bar or replays evidence, it makes one live status lookup
for the selected tickers, omits Delisted members silently, and uses only
Listed members in the total and replay. An all-Delisted selection reports only
that no Listed ticker is available. No rulebook, artifact, price, SQL,
dependency, Docker, or Git change. Docker changed-scope regression passes
**117/117**.

**Live Delisted status and Group Manager (2026-09-09; complete):** A ticker is now live **Delisted** when its
latest stored trading session differs from VN-Index's latest session; it
automatically returns to Listed when the dates again match. Collect preflights
the full selection, skips Delisted tickers before Lifetime/common-as-of work,
and writes no artifact for them. Validate and Flexible Rulebook return a
clear unavailable result without replay; new positions are blocked while
existing positions remain visible and risk validation reports unavailable.
The Backtest Group Manager tab lists live Listed/Delisted members, filters by
Group/Ticker/Status, and atomically creates, updates, renames, or deletes
Group sidecars without touching signals or positions. Collect renders a
Delisted skip as a deliberate outcome. A short-lived Current Positions
signature mismatch and minimal job-status compatibility regression were
repaired. Group Manager Status now follows the shared compact
popover-and-pills control pattern. Docker changed-scope regression passes
**172/172**; focused Group Manager UI tests pass **3/3**. Design and ordered plan:
`docs/superpowers/{specs,plans}/2026-09-08-live-delisted-status-and-group-manager*`.
No SQL schema, prices, artifacts, dependencies, Docker configuration, or Git
change.

**HSG batch-as-of validation conflict (2026-09-09; resolved by live
eligibility):** LTG's stale 19/06/2026 session can no longer participate in a
Lifetime batch whose VN-Index latest session is newer. It is skipped before
the shared range is resolved, so it cannot truncate HSG's evidence. Existing
HSG `requires_regeneration` documents remain historical terminal documents;
run Collect again after the live-data preflight reports its selection Listed.

**Flexible Rulebook active-policy storage missing (2026-09-08; investigated —
operator decision required):** The mounted `/data/flexible-benchmark` directory
is empty, including the previously recorded VCB direct-cap report, immutable
policy, and `active-policy.json` pointer. Scope Expansion is intentionally
additive: it requires a valid active policy for the fixed cap, seed scope, and
historical anchors, so its refusal is correct and no policy can be rebuilt from
the documented digest alone. Restore requires a fresh initial 100-cold-window
direct-cap benchmark and explicit activation, or a separately designed initial
bootstrap workflow; do not bypass the evidence gate. No code, data, SQL,
artifact, dependency, Docker, or Git change has been made.

**Current Positions available-ticker filter (2026-09-08; complete):** The
free-text `Ticker filter` control is now a `Ticker` dropdown containing `ALL`
and only sorted ticker codes present in the loaded position overview. `ALL`
preserves the unfiltered view; the existing State and sort controls continue
to apply independently. A stale prior text-filter value safely resets to
`ALL` before Streamlit renders the dropdown. No position data, SQL, artifact,
price, dependency, Docker, or Git change. Docker Backtest page regression
passes **90/90**.

**Validate Signals progressive signal state (2026-09-07; complete):** Fresh
schema-5 replay now derives an ephemeral candidate-specific state—Fresh,
On-going, Weakening, or Invalidated—from the latest observed entry event to
the latest valid native bar. It uses only the selected gate sources, original
theme where applicable, and signal-close/ATR-normalised price progression.
Age increases continuation proof requirements but never invalidates alone;
`max_hold_bars` does not cap a current BUY. Fresh/On-going retain `can BUY`;
Weakening/Invalidated become `expired BUY` without changing any artifact,
rank, treatment, or historical metric. Validate Signals displays the trend
state beside Monitoring and records the facts in collapsed JSON. The DPM supplied
case now assesses as Weakening at 03/09/2026 + two sessions (`-1.8152` signal
ATR). Docker focused Backtest regression passes **100/100**. No SQL, schema,
data, artifact, dependency, Docker, or Git change.

**Validate Signals trend filter (2026-09-07; complete):** The cached-result
filter row now has a multi-select **Trend** popover between Position actions
and Horizon. It defaults to Fresh, On-going, Weakening, and Invalidated; like
Class it re-filters the latest successful run without replay. Trend predicates
apply before profit bands and global win-rate sorting. No advice, artifacts,
metrics, schema, SQL, data, dependency, Docker, or Git change. Docker
Backtest page regression passes **85/85**.

**Validate Signals position-action counts (2026-09-07; complete):** The
Position actions selector now displays a count for ALL, can BUY, expired BUY,
can SELL, and HOLD from the latest valid cached candidates after Class, Trend,
Horizon, and both Profit filters. Its own selection is excluded from those
counts, so alternate actions remain visible. No validation replay, advice,
artifact, metric, schema, SQL, data, dependency, Docker, or Git change.
Docker Backtest page regression passes **86/86**.

**DPM Trend-toggle diagnosis (2026-09-08; verified):** The live DPM replay
has six available candidates: five `Invalidated` and one `Weakening`. The
shared predicate and Streamlit interaction regression both return six with
all states, one with Invalidated excluded, and five with Invalidated alone.
No server-side filter defect was reproduced; the regression preserves this
exact sequence. Docker Backtest page regression passes **87/87**.

**Validate Signals flat candidates (2026-09-08; complete):** Results no
longer render under ticker subheadings. Every candidate expander now uses
`Ticker — Rulebook — Theme`; Horizon remains an input filter only. Unavailable
and historical-position messages retain their ticker prefix. No validation
replay, advice, artifact, metric, schema, SQL, data, dependency, Docker, or
Git change. Docker Backtest page regression passes **88/88**.

**Validate Signals result-ticker filter (2026-09-08; complete):** A result-
gated **Ticker** dropdown now follows Test Profit %. It lists only tickers
with at least one available candidate plus `ALL`; selection filters cached
results and the other count labels without a replay. It resets to `ALL` when
the cached result is cleared or replaced without that ticker. No advice,
artifact, metric, schema, SQL, data, dependency, Docker, or Git change.
Docker Backtest page regression passes **89/89**.

**Collect/Validate tab-exit reset (2026-09-06; complete):** Native Backtest
tabs now track selection and rerun on a switch. Leaving Collect restores Group
to `N/A`, clears Tickers and completed output; leaving Validate restores Ticker
group to `-`, clears Tickers, and discards the displayed cached validation
result. Group-specific ticker widget state and unsaved group drafts are also
cleared. A Collect queue still in progress is deliberately retained so its
external job is not orphaned; it remains visible when returning to Collect.
All other controls and tabs are unchanged. Docker Backtest page regression
passes **83/83**. No SQL, schema, data, artifact, dependency, Docker, or Git
change.

**Validate Signals cross-ticker Win rate sort (2026-09-06; complete):**
`Training DESC` and `Test DESC` now flatten all visible eligible candidates
across tickers and rank the whole list by the selected preferred-treatment
metric, descending. Every sorted expander label starts with its ticker, so the
reported BANK run places VIB `57.7%`, VIB `55.6%`, then SHB `48.8%`. `None`
retains the established ticker-grouped stored order. Class, Position actions,
Horizon, and Train/Test Profit predicates apply before global ordering;
unavailable diagnostics and historical-position context remain visible. Docker
Backtest page regression passes **79/79**. No SQL, schema, data, artifact,
dependency, Docker, or Git change.

**Validate Signals result-gated filters (2026-09-06; complete):** Class, Win
rate, Position actions, Horizon, Train Profit %, and Test Profit % are disabled
until the latest cached validation contains at least one candidate whose
availability is `available`. They stay disabled for no cache, zero-candidate
runs, and unavailable-only diagnostics; diagnostics remain visible. Once an
available candidate exists, every filter and the existing preferred-treatment
profit labels, AND filtering, and Win rate ordering operate on the cached
result without replaying validation. Docker Backtest page regression passes
**77/77**. No SQL, schema, data, artifact, dependency, Docker, or Git change.

**Validate Signals first-row action layout (2026-09-06; complete):** Tickers,
Ticker group, and the Validate action now share the first row. The Group
control uses a wider native stretch column so long saved group names remain
readable; the existing Class, Win rate, Position actions, Horizon, Train
Profit %, and Test Profit % controls remain together on the second row in the
same order. Ticker-group resolution, validation execution, cached results,
filters, artifacts, and trading rules are unchanged. Docker targeted Backtest
page regression passes **3/3**. No SQL, schema, dependency, Docker, or Git
change.

**Validate Signals win-rate sort (2026-09-06; complete):** A single-select
`Win rate` control now sits immediately after Class with `None` (default),
`Training DESC`, and `Test DESC`. None keeps each ticker's stored visible
candidate order; either descending option now ranks all already-filtered
candidates across tickers by selected preferred-treatment win rate, highest
first, with ticker included in each label. Missing/non-finite values sort last;
exact ties use rulebook ID, treatment, then ticker for stable display. A new
widget key makes the neutral default take effect for existing sessions. Docker
Backtest page tests pass **79/79**. No SQL, schema, dependency, Docker, or Git
change.

**Validate Signals BANK profit-count audit (2026-09-06; resolved—no defect):**
The exact BANK / Closely Match / can BUY / Swing case contains four visible
candidates. Their preferred-treatment test profits are SHB ADX `18.46%`, SHB
ADX+joint-trend+RSI `-4.24%`, VIB ADX+RSI `-9.72%`, and VIB RSI+volume
`-27.86%`. The approved preferred-treatment-only Test Profit filter correctly
shows Profitable `1`, every other ≥5% band `0`, and All `4`. The Train bands
are independently Potential `2`, Profitable `1`, Attractive `1`, Outstanding
`0`. The apparently large gap from displayed win rates is correct: V3
`profit_pct` is the cumulative sum of completed trade returns, whereas win
rate is the count of positive returns divided by completed trades. Exact Test
pairs are SHB ADX `13/24`, `54.17%`, `+18.46%` total; SHB ADX+trend+RSI
`1/3`, `33.33%`, `-4.24%`; VIB ADX+RSI `3/10`, `30.00%`, `-9.72%`; and VIB
RSI+volume `2/13`, `15.38%`, `-27.86%`. A rendered Docker UI audit also proves
Class, Horizon, and Position action counts update from their shared filtered
cached set. No calculation, artifact, or data change was needed.

**Validate Signals stale profit-filter state (2026-09-06; complete):**
Validate Signals now converts a prior browser-session profit label such as
`Potential (5% - 15%) - 2` back to its stable internal key before calculating
counts, filtering results, or constructing either selectbox. Known counted
labels preserve the user's selected band; unknown malformed state safely
resets to `All`. This fixes Train Profit, Test Profit, and their AND
combination without replaying validation, changing artifacts, metrics, data,
or trading logic. Docker Backtest regression passes **317/317** and the page
compiles. No SQL, schema, dependency, Docker, or Git change.

**Validate Positions result reset and Risk display (2026-09-06; complete):**
After a completed validation, the completed result survives one rerun while
the position table is regenerated with every selection and `All` unchecked;
failed runs retain their selection for retry. The result-only Risk projection
now renders `Swing: risk% - Level | Mid-term: risk% - Level`, capitalizing
levels without changing stored risk text, formulas, or Current Positions.
Docker Backtest regression passes **316/316** and the page compiles. No SQL,
schema, dependency, Docker, or Git change.

**Validate Positions All selection and batched progress (2026-09-06;
complete):** `All` selects every currently eligible OPEN position in the
Validate Positions table. A single run now preflights one common latest
VN-Index/ticker bar across the full selection, then evaluates sequential
batches of five while reusing loaded VN-Index and ticker histories. Each batch
updates a native progress bar; the completed bar remains visible for three
seconds and then clears. Existing risk formulas, result wording, persistence,
and the single-batch service are unchanged. Docker Backtest regression passes
**315/315** and changed modules compile. No schema, dependency, Docker, or Git
change.

**Collect Signals Lifetime range (2026-09-06; complete):** Range now defaults
to `Lifetime`. Its queued Batch V5 request resolves once at execution time to
the first and last selected-ticker rows that share a VN-Index session, then
freezes those bounds for all ticker and theme loads in that batch. This avoids
a stale browser-date range and preserves the existing VN-Index calendar and
common-as-of rules; each artifact still records its own effective source range.
No prices, indicator math, rulebooks, artifacts, schema version, dependencies,
or Docker configuration changed. Docker Backtest regression passes **312/312**
and changed modules compile. A live read-only TCX check resolved
`2025-10-21` through `2026-09-04`.

**Popover labels above triggers (2026-09-06; complete):** `Class`, `State`,
and `Table` now render above their compact popover triggers in Validate
Signals, Current Positions, and View Signals respectively. The duplicate
in-popover pill label is visually collapsed while retained for accessibility.
Keys, defaults, values, filtering, data, and artifacts are unchanged. Docker
Backtest page/helper/store tests pass **80/80** and the page compiles. No SQL,
dependency, Docker, or Git change.

**Popover-pill label refinement (2026-09-06; complete):** The compact pill
labels are now `Class` in Validate Signals, `State` in Current Positions, and
`Table` in View Signals. Popover help remains descriptive; keys, values,
defaults, filter logic, data, and artifacts are unchanged. Docker Backtest
page/helper/store tests pass **80/80** and the page compiles. No SQL,
dependency, Docker, or Git change.

**Compact popover-pill filters (2026-09-06; complete):** Validate Signals
Monitoring classifications, Current Positions Position state, and View Signals
Columns now use native Streamlit popovers containing multi-select pills. This
is compatible with every existing fixed option list (4, 2, and 8 options
respectively) and retains their exact keys, defaults, list return values,
filtering, and table projection behavior. Validate's compact filter column
frees page width while the View and Position popovers retain their existing
native icon triggers. Docker Backtest page/helper/store tests pass **80/80**
and the page compiles. No SQL, data, artifact, dependency, Docker, or Git
change.

**Validate Signals preferred-treatment profit filters (2026-09-06;
complete):** Validate now adds `Train Profit %` and `Test Profit %` after
Horizon and before Validate. Both filter only the candidate's exact preferred
treatment in latest cached validation results—never the other treatment and
never a replay. Exact raw-profit bands are Potential `5–15`, Profitable
`>15–30`, Attractive `>30–50`, and Outstanding `>50`; missing, non-finite, or
below-5 values remain available only through All. Each option dynamically
counts candidates after Classification, Position action, Horizon, and the
opposite profit filter; both profit filters apply with AND semantics. A fully
successful validation reruns once to refresh count labels; a partial batch
retains its existing visible error. Exploratory-gross safeguards, advice,
artifacts, ranking, SQL, and market data stay unchanged. Docker Backtest
page/helper/store tests pass **80/80** and the page compiles. No dependency,
Docker, data, or Git change.

**Current Positions expander BUY/SELL summary (2026-09-06; complete):**
Position expander headings now show ticker, state, P&L, holding sessions,
displayed BUY price, and SELL value. OPEN uses the existing frozen sell
suggestion; CLOSED uses actual SELL price only, with all prices in k VND.
The heading and its static detail table reuse one display projection, so no
parallel sell-rule logic exists. Docker Backtest page/helper/store tests pass
**77/77** and the page compiles. No SQL, data, artifact, dependency, Docker,
or Git change.

**Current Positions detail-table content width (2026-09-06; complete):**
Current Positions detail table now uses Streamlit's native `width="content"`
mode instead of stretch width. Each column fits its longer header/cell with
native cell padding; values, table rows, and every other UI behavior are
unchanged. Docker Backtest page/helper/store tests pass **76/76** and the page
compiles. No SQL, data, artifact, dependency, Docker, or Git change.

**Current Positions Saved signal set semantic display (2026-09-06;
complete):** Current Positions replaces the superseded character-count wrap
with a two-line, display-only v5 projection: immutable rulebook ID first,
then `Theme: Included` or `Theme: Excluded`. Legacy/non-v5 labels remain
unchanged rather than inventing a treatment. Stored positions/signals and all
other table columns are unchanged. Docker Backtest page/helper/store tests
pass **76/76** and the page compiles. No SQL, data, artifact, dependency,
Docker, or Git change.

**Current Positions mutation feedback and readable details (2026-09-05;
complete):** Delete confirmation and Add Position now use callback-owned busy
states plus native spinners, preventing duplicate mutations while work runs.
Delete finishes by clearing its modal; successful Add resets New Position to
its native defaults before the next render, while a failed Add preserves the
entered values. Position expanders now show `Ticker — State — P&L % — holding
sessions`; their two-row detail view is a static wrapped table so long text is
not clipped. Docker Backtest page/helper/store tests pass **75/75** and the
page compiles. No SQL, data, artifact, dependency, Docker, or Git change.

**Collect Signals Edit Group Add-field reset (2026-09-05; complete):**
After a successful draft-member Add, the Edit Group `Add ticker` field now
clears before Streamlit rerenders. Native button callback updates only the
draft and its input state, avoiding forbidden post-render mutation of a widget
key. Empty or duplicate input remains unchanged; persisted Group members still
change only on Save Group. Docker page/helper/store tests pass **73/73** and
the page compiles. No SQL, data, artifact, dependency, Docker, or Git change.

**Collect Signals saved-Group Tickers refresh (2026-09-05; complete):**
`replace_group_tickers` already atomically persisted Group membership. The
disabled Tickers input retained Streamlit state because its key only contained
the Group name. After successful Save Group, a per-Group refresh generation
now changes that input key on rerun, rehydrating it from the saved resolver
members. Draft Add remains invisible in Collect Tickers until Save Group, as
the edit is atomic. Docker page/helper/store tests pass **72/72** and the page
compiles. No SQL, data, artifact, dependency, Docker, or Git change.

**Validate Signals signal date and win-rate projection (2026-09-05; complete):**
Fresh schema-5 replay now derives `signal_date` from its latest
calendar-filtered, observed false-to-true entry event. Validate Signals renders
`Monitoring: A% - classification | position action | signal date: DD/MM/YYYY |
win rate training / test: X% / Y%` from that replay and its selected preferred
treatment; unavailable values render `—`. New saved-signal positions show and
persist the same read-only date in `entry_context`, while manual BUY date stays
the actual execution date. Signal-backed Position risk uses the persisted date
for T+3; old position histories safely fall back to `as_of_date`. Rulebook
ranking, evidence eligibility, artifacts, SQL, prices, dependencies, Docker,
and current `can BUY` policy are unchanged. Training/test win rates now display
with exactly one Decimal `ROUND_HALF_UP` digit, while stored values and ranking
remain exact. Display/page tests pass **68/68**. Earlier signal-date focused
Docker Backtest passed **85/85**, complete Backtest discovery passed **299/299**,
and changed modules compile. Design:
`docs/superpowers/specs/2026-09-05-validate-signal-date-win-rate-design.md`;
plan: `docs/superpowers/plans/2026-09-05-validate-signal-date-win-rate.md`.
No Git action.

**Data Page latest-session Highlights (2026-09-04; complete):** After a
successful Get data transaction, Data Page makes one read-only aggregate query
and renders `VN-Index: Up to DD/MM/YYYY` plus `Ticker: Up to DD/MM/YYYY`.
Ticker means the latest non-VNINDEX stored session. A visible warning explains
that Backtest uses the latest shared VN-Index session whenever dates differ;
missing source data renders `—` without changing completed ingestion. Live
read-only verification currently returns VN-Index `03/09/2026` and Ticker
`04/09/2026`, so the intended warning will show. Docker Data Preparation
passes **14/14**. No market data, artifact, dependency, or Git change.

**Alligator HL2 formula migration (2026-09-05; complete):** Backtest and
Horizon Technical Analysis now calculate Bill Williams Alligator from
`HL2 = (high + low) / 2`, then the existing SMA-seeded recursive SMMA and
causal shifts. Swing uses `8/5/3` with `5/3/2` shifts; Mid-term uses `13/8/5`
with `8/5/3` shifts on completed weekly OHLCV. TCX's exact Swing HL2 values
now match the user calculation: 27/08 `39.964 / 40.141 / 40.401`, 28/08
`40.006 / 40.228 / 40.701`, 03/09 `40.149 / 40.442 / 40.942`, and 04/09
`40.202 / 40.639 / 40.945` for Jaw/Teeth/Lips in k VND. All previous
close-based evidence was invalidated: 96 canonical artifacts, 18 legacy
variants, and 128 job sidecars are valid `requires_regeneration` markers.
The four position records and all market data remain unchanged. Docker
Backtest passes **297/297** and shared Technical passes **17/17**.

**TCX Swing signal audit (2026-09-04; live root cause confirmed, no policy
change approved):** After the user added VNINDEX 04/09 data and regenerated,
TCX artifact and common-as-of correctly advance to `2026-09-04`; this is not a
cache issue. Baseline permits any non-empty gate subset, including
`joint_trend` alone. That Boolean checks only EMA and causal Alligator line
ordering, not their slopes: on 04/09 fast EMA `40352.03 > 40333.21` slow EMA
and Alligator lips `40944.68 > 40638.66 > 40202.23`, so it remains true even
when direction is weakening. Live replay calls that persistent true level
`literal_entry` rather than a fresh false-to-true event. Its last real entry
edge was 26/08, four valid bars earlier; RSI has no upcross, ADX is `15.41`
below 17 and falling, and volume gate is false. Yet the single-gate candidate
gets 100% Closely Match and can BUY. `validation_diagnostics` detects event
age, but live Validate Signals does not consume it. The preferred Top-3 test
evidence is also poor (0% wins, negative mean gross return in each themed test
treatment), so this artifact is exploratory, not reliable trading evidence.
Stochastic is not a Baseline Swing entry gate. Technical Analysis and Backtest
now share the corrected shifted HL2 Alligator values; from 28/08 to 04/09 they
rise slightly. A sensitivity design must explicitly choose which causal series
owns slope semantics. Formula migration invalidated stale artifacts, but made
no entry/validation policy change.

**VN-Index invalid-session ingestion cleanup (2026-09-04; implemented, awaits
next Get data):** A user-triggered Get data transaction now removes only the
acknowledged calendar-invalid dates `2023-08-26`, `2025-05-04`, `2025-05-11`,
`2026-02-07`, and `2026-03-08` after staging/finalizing source data and before
its only commit.
It then scans every persisted `trading_data` row for Saturday/Sunday dates.
Any remaining invalid date raises a detailed error with date, row count, and
ticker list and rolls back both the cleanup and the refreshed input. Targeted
test-first verification passes 4/4; Docker Data Preparation passes 13/13.
The complete five-date list was explicitly approved after the read-only scan;
no database mutation has been performed by this implementation. The next Get
data run performs the cleanup and records its empty all-table validity check.
Design/plan:
`docs/superpowers/specs/2026-09-03-project-wide-vnindex-trading-calendar-design.md`
and
`docs/superpowers/plans/2026-09-03-project-wide-vnindex-trading-calendar.md`.
No Git action.

**Flexible Rulebook runtime reset (2026-09-03; complete):** At the user's
request, cleared only current Flexible runtime evidence: `app/Flexible-Rulebook`
cache/campaign state and `data/flexible-benchmark` jobs, reports, policies, and
active-policy pointer. Both roots are now empty. Source code, Backtest
artifacts, positions, groups, PostgreSQL data, Docker configuration, and Git
state were not touched. A future Flexible run must benchmark and activate a
new discovery scope before Discover can run.

**Technical Analysis horizon-only UI (2026-09-02; complete):** Technical
Analysis now has main-page Ticker and Horizon (`Swing`, `Mid-term`) inputs
plus Analyze, with no sidebar control. Its isolated adapter fetches bounded
raw BIGINT OHLCV, builds up to 100 native schema-5 bars, uses exact horizon
MA/RSI/ADX/ATR and causal Alligator, then adds existing Stochastic, OBV, and
Bollinger output. The UI now has nine details including Alligator; prices
cross one k-VND display boundary and internal Backtest gate columns are absent.
The legacy eight-indicator Analyze/API snapshot remains unchanged. Approved design:
`docs/superpowers/specs/2026-09-02-technical-analysis-horizon-ui-design.md`.
Ordered implementation plan:
`docs/superpowers/plans/2026-09-02-technical-analysis-horizon-ui.md`.
Docker Technical regression passes **109/109**, shared consumer regression
passes **36/36**, a rendered Swing AppTest is green, and changed modules
compile. No Git action.

**Flexible Rulebook Discover operator identity default (2026-09-02; complete):**
Discover and Scope Expansion initialize editable operator identities once as
`admin DDMonYY <epoch-seconds>` using Ho Chi Minh time, for example `admin
02Sep26 1788341234`. A manual edit remains intact and a blank main-Discover
value disables Start. Each UI-submitted Discover campaign records identity as
durable runtime audit metadata without changing its idempotent semantic ID;
older manifests without it remain readable.
Docker Flexible regression passes **323/323** and changed modules compile. No
SQL, price scaling, dependency, Docker, runtime-data, or Git change.

**Backtest Collect/Validate Group `ALL` (2026-09-02; complete):** Collect
orders its Group choices as `N/A`, `New group…`, `ALL`, then named Groups.
`ALL` is a reserved virtual selection, resolving a deterministic de-duplicated
union of every named Group member and every saved-artifact ticker; it can never
be persisted as a named Group. Collect splits that union into ordered batches
of at most 15 and submits exactly one job at a time, continuing after failed
or requires-regeneration batches; it prevents a second Collect submission while
the queue is active. Validate exposes `-`, `N/A`, `ALL`, then named Groups;
its existing serial 15-ticker batching consumes the same resolver. `N/A` in
Validate remains saved-artifact tickers absent from all named Groups. The
session-local Collect queue advances while the Backtest page remains active;
a durable parent job is intentionally out of scope. Docker Backtest regression
passes **284/284** and changed modules compile. No SQL, price scaling,
artifact schema, dependency, Docker, runtime-data, or Git change.

**Backtest Group display refresh and Validate Horizon filter (2026-09-02;
complete):** Group-backed disabled Ticker inputs now carry Group-specific
Streamlit keys, so switching from one named Group to another always displays
the newly resolved members in both Collect Signals and Validate Signals.
Validate Signals now has a `Horizon` filter (`Both`, `Swing`, `Mid-term`)
between Position actions and Validate. It filters the cached latest validation
display only and does not replay, mutate artifacts, or alter advice. Docker
Backtest regression passes **284/284** and the page compiles. No SQL, price
scaling, artifact, dependency, Docker, runtime-data, or Git change.

**Current Positions delete confirmation dialog (2026-09-02; complete):** The
existing protected batch-delete confirmation now opens in native Streamlit
`st.dialog`, rather than inline page content. It keeps the exact selection and
display-context guard, summary, Confirm permanent delete action, Cancel action,
and underlying deletion service unchanged. Docker Backtest regression passes
**284/284** and the page compiles. No SQL, price scaling, artifact, dependency,
Docker, runtime-data, or Git change.

**Streamlit 1.62 app-wide UX implementation (2026-09-02; complete):** The
exact runtime set is active, the seven flat top-navigation routes replace the
sidebar, and the global `Stock Analysis App` title is removed to give page
content more space. Native icon utilities, popovers,
confirmation-before-Backtest-removal, and responsive tables are implemented
without altering trading, SQL, artifact, job, position, or risk logic. The
targeted Technical transition clears only `tech_*` session state. A Backtest
route-ownership regression and the live desktop/narrow visual checks prove it
does not render Flexible Rulebook Discover content. The complete affected
Docker gate passes **170/170**; dependency, compile, Streamlit-health,
FastAPI-docs, legacy-API audits, and the seven-page visual gate are green.
Live read-only AppTests now also execute Analyze through Final Advice and
Technical Analyze through a rendered Plotly chart with zero exceptions. A live
one-year FPT export payload returns 250 rows, expected columns, and its
deterministic filename without writing a file. An existing running Flexible
campaign retained its state across read-only Refresh, while unchanged default
Discover inputs correctly kept Preflight/Start disabled. Local headless Chrome
also confirmed Technical output clears after Backtest/Flexible navigation and
return, without a Streamlit exception. An isolated copy of the real BVH Swing
artifact verifies cancel preservation, exact one-candidate removal, and
reference-block preservation.
User then added a current ACB schema-5 signal-backed position; production
read-only guard preflight protects its exact `ACB / midterm /
midterm_rulebook_v5__joint_trend` identity. Calling the removal service itself
was approved and correctly blocked. Its artifact document is byte-equivalent
before/after and no transaction journal remains. Explicit approval also removed
unreferenced `ACB / midterm / midterm_rulebook_v5__adx`: the valid artifact
changed from seven to six candidates, with no journal. Fresh Backtest discovery
passes **272/272** plus compilation. No Git action.

**Saved-signal position fractional-ATR repair (2026-09-02; complete):** Exact
Wilder ATR is correctly fractional in raw-price units. New Position previously
sent it through the close-price integer validator and rejected valid saved
sets. The frozen schema-5 snapshot now rounds only finite positive ATR to the
nearest raw unit with Decimal half-up semantics; `latest_close` remains strict
raw integer. TCB's current Swing ATR `979.5087091830576` now freezes as `980`,
with valid levels `31930`/`35850`. Backtest Docker discovery passes **272/272**
and compilation passes. No SQL, BIGINT storage scaling, artifact, or Git change.
Verification:
`docs/superpowers/reports/2026-09-02-streamlit-1-62-app-wide-ux-verification.md`.
No Git action occurred.

**Backtest View Signals compact remove control follow-up (2026-09-02;
complete):** Replaced the View Signals text action with a compact `🗑️` button
beside `Select all visible`. It remains disabled with zero selected candidates;
its tooltip retains the explicit `Remove selected signals (N)` meaning. A
toolbar placeholder and selection-generation key keep its state current and
prevent a stale editor payload from restoring a cleared selection. Docker
Backtest-page tests pass (45/45); page compilation passes. No SQL, dependency,
or git change.

**Backtest removal-toolbar clarification (2026-09-02; complete):** Current
Positions now uses the same compact remove icon immediately beside `Select all
visible`, retaining its existing exact-locator, confirmation-before-delete
flow. View Signals uses the same adjacent toolbar layout and now explains that
the refreshed Top 3 can show a promoted stored candidate after a successful
removal. This is expected: every success artifact keeps all remaining
candidates and reranks its displayed Top 3, so a stable row count is not stale
data. Docker Backtest regression passes **272/272** and page compilation
passes. No SQL, data, artifact, dependency, or git change.

**Backtest View Signals pagination (2026-09-02; complete):** The filtered
signal list now paginates at 50 rows by default, with 100 and 150 alternatives.
Native previous/next controls show the current page and total filtered signals;
selection and `Select all visible` are strictly page-local and cannot carry a
pending deletion to another page. Signal-removal semantics remain unchanged.
Docker Backtest regression passes **276/276** and page compilation passes. No
SQL, data, artifact, dependency, or git change.

**Backtest View Signals filtering and bulk candidate management (2026-09-02;
complete):** Exact multi-ticker text filtering, configurable visible columns
with Evidence/Theme hidden by default, visible-row numbering, native
visible-only checkbox selection, and safe bulk removal are complete. Removal
preserves nonselected candidates, reranks Top 3, converts a final candidate to
a valid regeneratable schema-5 `empty` artifact, and blocks the entire request
if an OPEN or CLOSED saved position references any selection. A durable
before/after journal restores a coherent catalog after a mid-batch filesystem
failure; malformed journals fail closed. Docker compilation passed; focused
persistence/catalog/removal/page suites pass **68/68** and canonical discovery
passes **790/790**. No git action or dependency change was made. Design:
`docs/superpowers/specs/2026-09-02-backtest-view-signals-bulk-management-design.md`;
plan: `docs/superpowers/plans/2026-09-02-backtest-view-signals-bulk-management.md`.

**Backtest V4 schema-5 evidence integrity and enhancement (2026-09-01;
design and ordered plan approved, Tasks 1–11 complete):** Exact
SMA-seeded Wilder formulas, one explicit common-as-of/W-FRI clock, honest
partition exits, gap-safe stops, immutable source fingerprints, and the 95%
VN-Index-session/no-gap-over-20 eligibility gate are complete. Strict schema 5
now owns artifacts, requests, jobs, Top-3 baseline identities, evidence labels,
and current position references. Superseded schema-4 artifacts and job
sidecars are atomic `requires_regeneration` markers; older theme-only schema-2
files and schema-4/older positions remain ignored or frozen history.
Validate Signals recomputes ticker and VN-Index source identity before replay,
invalidates changed evidence, blocks ineligible BUY, and no longer treats a
consumed BUY trigger as SELL. Only explicit exit/deterioration or frozen price
conditions can return `can SELL`; no trade is executed. View/Validate expose
evidence and exact `in-sample` / `historical test — previously observed`
labels. The complete Backtest suite passes **224/224** and affected modules
compile. Task 7's frozen eight-ticker database diagnostic completed at one
`2026-08-28` common-as-of and exact 1,000 permutations; ordinary Collect
workers regenerated all 16 canonical artifacts as schema-5 success documents.
Seven tickers are evidence-eligible; HAP remains display-only/ineligible for a
58-session source gap. The verification and artifact hashes are in
`docs/superpowers/reports/2026-09-01-backtest-schema-5-baseline-verification.md`.
Task 8 now supplies only the two approved immutable research pairs, causal
setup/trigger masks, first-overlap timing, training diagnostics, and
training-only acceptance; its selection snapshot is test-blind and remains
`research_only`. Focused tests pass 14/14, the full Backtest suite passes
**238/238**, compilation passes, and product-import isolation is clean.
Task 9's read-only-by-default runner freezes training before historical test,
requires exact Mid-term baseline/W-FRI/source identity, and writes only
content-addressed non-canonical research evidence. The sample produced 14
complete runs and two HAP `not_run` records; no variant passed every training
gate, so the promotion gate remains closed. Research tests pass 21/21; the
full Backtest suite passes **245/245**. Report:
`docs/superpowers/reports/2026-09-01-backtest-schema-5-controlled-experiments.md`.
Task 10 now preserves byte-exact reference semantics across all 16 frozen
ticker/horizon benchmarks while reducing Swing p95 by about 75–78% and
Mid-term p95 by about 64–67%; peak RSS remains about 253–258 MB. Exact parity
tests pass 8/8 and the full Backtest gate passes **253/253**. Ticker execution
remains sequential. Task 11 passed the canonical **773/773** test gate,
compilation, practical LPS/VPL and 15-ticker batch checks, protected-boundary
review, architecture sync, and final handoff. Final report:
`docs/superpowers/reports/2026-09-01-backtest-schema-5-final-verification.md`.
Design:
`docs/superpowers/specs/2026-09-01-backtest-v4-schema-5-enhancement-design.md`;
plan:
`docs/superpowers/plans/2026-09-01-backtest-v4-schema-5-enhancement.md`.

**Backtest V4 enhancement review prompt (2026-09-01; complete):** Created
`ENHANCE-PROMPT.md` as a read-only, evidence-first audit and enhancement brief.
It requires dual verification of material claims, an adversarial second-pass
blind-spot register, separate trading-quality and runtime analysis, controlled
Swing/Mid-term experiments, recommendation falsification, and a mandatory
design self-critique/readiness gate before any implementation plan or code.

**Comprehensive Unit Testing — targeted public-boundary slices (2026-08-31;
complete):** Added
seven focused `price_utils` tests covering exact BIGINT conversion, precision
and invalid-value rejection, UI scaling, export preservation, and unsupported
output modes; eight `validation` tests covering classification boundaries,
score directions, split selection, and report eligibility/input gates; and
seventeen `technical_analysis` tests covering grouping, gates, dimensions,
correlation, ATR, OBV, Bollinger, ADX, moving-average, RSI, stochastic, trend,
formatting, and alias helpers; validation now includes one private-helper
contract test. Analyze-page coverage adds bounded movement and classifier tests;
data-preparation coverage adds trading-day, source, exchange, and progress
helper tests, plus BIGINT staging and transaction-safety tests. Docker focused
gates pass 7/7, 9/9, 17/17, 11/11, 10/10, and 10/10; the combined commons
regression gate passes 42/42. Backtest Lab coverage now tests input, batching,
status, display, saved-set, raw-price, selection, deletion, position-creation,
and overview-load helpers. It also fixes invalid price display: non-numeric raw
values now render `"-"`, not `NaN`. Result-page coverage now verifies bound
raw-connection queries, VNINDEX exclusion, responsive tables, and
close-on-failure. Suggestion-page coverage verifies its empty-universe warning
plus threaded four-ranking projection. Technical chart coverage verifies
selected overlays, cross markers, panel thresholds, and missing-column no-ops.
API route coverage adds five tests for ticker normalization/advice projection,
missing-data 404, bullish-only ranking, busy ingestion rejection, bad-date
rejection, and background-task scheduling. Entrypoint coverage adds three
isolated tests for API/database/bootstrap ownership, all seven page routes,
and state clearing when leaving Technical Analyze. Docker's canonical
`unittest discover -s tests -v` gate now passes **697/697** in 25.2 seconds.
Broader Analyze-page coverage exposed and repaired a Portfolio Analyze
classification mismatch: its final-advice key now reuses the same direct
up/down probability rule as Ticker Analyze, so low up probability is not
silently treated as bearish evidence. The regression covers `25%` up and
`60%` down evidence as `Down` (not `Strong Down`).
The prior `scripts` import gap is repaired by mounting the root scripts
directory read-only in development Compose; the app container was recreated
with explicit root `.env` interpolation, with no database or volume removal.
No production SQL, dependency, database, or git change was made. Current
unit-test task is complete for the targeted commons, utility, API-route, and
entrypoint slices; only broader optional coverage remains.

**Flexible Rulebook UI Scope Expansion and Progress (2026-08-30; complete):**
Tasks 1–6 are complete. The Discover workspace now accepts additive ticker and
seed scope with required operator identity and approval note, computes the
latest common completed bar across the full union (minimum latest eligible
ticker bar when member watermarks differ), submits one idempotent
benchmark job, and activates the union only after 100 cold windows per pair
pass. Durable sidecars expose pair/window progress and safe failures. Discover
campaigns, Qualification, and Current Group BUY Scan expose phase-aware
progress callbacks/bars. Operator identity now defaults once to `admin DDMonYY
<epoch-seconds>` in Ho Chi Minh time; the editable note defaults from normalized added
tickers and never overwrites manual wording. Active expansion progress now
polls its durable sidecar every three seconds and stops polling at terminal
states. Docker verification passes 321 Flexible tests and
affected modules compile. No V3, positions, protected SQL, Docker, dependency,
or git changes were made. Design:
`docs/superpowers/specs/2026-08-30-flexible-rulebook-ui-scope-expansion-progress-design.md`;
plan:
`docs/superpowers/plans/2026-08-30-flexible-rulebook-ui-scope-expansion-progress.md`;
verification:
`docs/superpowers/reports/2026-08-30-flexible-rulebook-ui-scope-expansion-progress-verification.md`.

**Flexible Rulebook Discover full-unlock activation plan (2026-08-30;
implementation is complete):** Tasks 1–6 are complete. Direct fixed-cap
evidence, the isolated cap runner, immutable activation policies, and the
activated campaign boundary now enforce one exact policy-bound runtime:
historical anchor/split validation precedes a fresh eligible source freeze;
worker services receive the complete request; and the persisted cache choice
is retained across an activated continuation. Source anchors include the full
quality revision. Task 5 adds the active-policy scoped Discover selectors,
explicit preflight/cache-choice start, safe state invalidation, campaign
Refresh/Cancel/Resume/Continue controls, and cache-offer recheck at submission.
The Task 5 Docker gate passes 113 tests and Flexible modules/pages compile.
Task 6 full verification passes **300** Flexible Docker tests, compilation,
and both non-writing CLI help checks. A real PostgreSQL cap corpus for VCB is
now recorded as 100/100 complete cold windows at fixed cap 8, one worker,
with no eligibility failures; immutable policy
`f5a304a583890c527e359477687b7bae9af66b21cd6bde267a2abb2a4ea014b6` is active
under `/data/flexible-benchmark`. Discover is unlocked only for VCB and
`frb-default-seed-v1`, still requiring its normal preflight and explicit cache
treatment. The evidence and operator sequence are in
`docs/superpowers/reports/2026-08-28-flexible-rulebook-discovery-activation-verification.md`.

**Flexible Rulebook production benchmark implementation (Task 5B, complete
2026-08-28):** the read-only Docker CLI, canonical evidence report, isolated
cold/warm cache roots, full worker path, phase telemetry, 4h55 ticker budget,
and cap-safety guard are implemented. Host Flexible verification passes **245
tests** (20 Streamlit-runtime skips) plus compilation and CLI help. Docker
server `24.0.6` passes the focused benchmark gate **29/29**; the later
production cap run and activation are recorded in the current runbook. See
`docs/superpowers/reports/2026-08-28-flexible-rulebook-production-benchmark-verification.md`.

**Flexible Rulebook UI selector amendment complete (2026-08-28):** Cross-ticker
Qualification now selects only available immutable rulebook IDs and valid named
Groups from read-only dropdown controls. Discover uses the active policy scope
and preflight/cache-choice gate (or remains safely disabled under the zero-
attempt policy when no policy exists), with explicit next-step guidance to
Library, Qualification, and Current Group BUY Scan. Library empty state now identifies
the configured Flexible root, missing artifacts, benchmark gate, and V3
isolation. Docker verification passes 226/226
Flexible tests plus compilation.

**Horizon Rulebook Signal Redesign and Validate Positions Risk — Phase B are
complete (2026-08-25).**

Horizon V3 remains complete through its schema-4 replacement. Validate
Positions Phase B is complete and verified by 68 focused Docker tests plus
container compilation. Evidence:
`docs/superpowers/reports/2026-08-25-validate-positions-phase-b-verification.md`.

**Historical work:** Flexible Rulebook Core Plan. Tasks 3 and 4 implementation is
complete (2026-08-27): catalog-v1, causal FeatureStore/lazy masks, individual
computed-component cache, receipt proof, reference execution, and inert
identity-bound event-plan parity guard exist. Cache accepts only matching
source/contract primitive keys; corrupt, partial, locked, low-space, and write
failures stay uncached without ticker failure. Task 4 fixtures cover next-open,
E+3, technical queue/discard, prior-high trailing, raw-open gaps, deadline
precedence, sparse/dense masks, cancellation, and source/receipt/mask/partition
event-plan rejection. Canonical Docker focused gate passes 73/73 plus
compilation. Tasks 3–4 are verified complete.

**Task 5 contract history (completed 2026-08-26):** its evidence contract is locked:
`RulebookEvaluation` will own typed immutable `training_trades` and
`test_trades` tuples, count-matched to each partition metric and excluded from
`rulebook_id`. Sensitivity reads these tuples only; no aggregate inference or
artifact lookup.

**Task 5 complete (2026-08-26):** metrics now validates a single selection
scope, pairs first inclusive trade-interval overlaps deterministically, records
exact integer overlap evidence, and greedily retains at most three training-time
distinct candidates under the fixed 75% rule. Focused Flexible Docker gate
passes 56/56 with compilation. **Task 6 complete:** catalog-v1 fixes ATR
stop `2.0×`, target `3.0×`, and no trailing. Its first lazy seed-free
CandidateSpace and ticker-seeded affine traversal tests pass in Docker (4/4).
Structural strata and discovery evaluation are complete: seeded stratum order,
continuation-safe affine slots, budget terminal truth, and frozen train/test
typed evidence. Core Docker gate passes 80/80 plus compilation. **Task 7 is
complete:** Flexible-only schema-1 storage writes immutable definitions,
qualified/explicitly-saved evidence, receipt-bound provenance ledgers, verified
Continue selection chains, and excludes `cache/` from signal-set traversal.
Full Flexible Docker gate passes 96/96 and all Flexible modules compile.
Campaign manifests/resume cursors begin only in the dependent Campaigns and
Current Scan plan.

**Correctness remediation complete (2026-08-28):** cache reuse no longer
recalculates already-valid primitive components; OHLC quality ratios exclude
volume; continuation deadline counters preserve the global cursor; qualification
requires an explicit valid cache choice plus frozen request split/plan hashes;
audit-only targets remain data-ineligible; and signal-set identity checks now
verify path, receipt, and source anchor. Continue selection now recomputes from
all committed qualified evidence in the verified parent chain. Regression and
full Flexible Docker verification passes **219/219** plus compilation.

**Historical Task 1 implementation note:** Flexible Campaigns and Current Scan
plan Task 1. Its isolated
campaign contract now freezes semantic request identity, ignores cache/runtime
diagnostics in request hashing, validates discovery-only frontier assignment,
enforces legal campaign and item states, and creates source-verified linked
Continue windows with contiguous cursor accounting. Continue now also requires
an exact, non-empty, freshly verified FeatureResolutionReceipt ID tuple before
it can create a child request. Campaign reconciliation also validates any
claimed immutable SelectionSnapshot schema, ID, and content digest; a missing
claim becomes a safe campaign failure. A terminal committed discovery now
writes its immutable SelectionSnapshot before atomically checkpointing its ID
into the manifest; nonterminal discovery is rejected. Focused Docker evidence
is 23/23 plus compilation. A linked child campaign writes its own immutable
higher-ranked snapshot; a parent checkpoint cannot be replaced. Durable
versioned manifest persistence now atomically
round-trips frozen request identity, validates the campaign ID against that
identity, and reconciles worker-owned item artifacts: verified orphans are
adopted while missing/corrupt claimed artifacts become item failures. Receipt-
bound Resume remains within Task 1. Selection recomputation now accepts typed
evaluation evidence only from the full committed parent chain and applies the
frozen training-only timing-distinct policy. A chain reader accepts only contiguous discovery
parents with preserved frozen semantics, terminal state, and verified immutable
SelectionSnapshots.

**Historical Task 2 milestones:** Flexible Campaigns Task 2 began with durable idempotent
submit/read APIs and legal cancellation state handling. A duplicate frozen
request attaches to its existing queued campaign; queued cancellation is
terminal before a worker claim, while a running campaign becomes cancelling.
The global one-worker lease is atomic, increments the claim epoch, blocks a
different campaign, and permits only the owner to release it. Focused Docker
runner evidence is 6/6; full Flexible evidence is 125/125 plus compilation.
Heartbeat is atomic and timezone-aware; stale recovery verifies the exact
campaign/epoch, marks it interrupted, and releases the worker. Explicit Resume
reuses the persisted request/assignment and obtains a new lease epoch only from
the documented recoverable states. Focused Docker runner evidence is 7/7; full
Flexible evidence is 126/126 plus compilation. The coordinator now accepts an
injected campaign service, persists only an identity/epoch-compatible returned
checkpoint, and releases the lease after terminal work. Focused Docker runner
evidence is 8/8; full Flexible evidence is 127/127 plus compilation. Isolated
subprocess wiring remains. Before any service execution, the runner now
fresh-loads and exactly verifies every frozen source and the active feature-build
contract, passes only those verified sources to the service, and safely blocks
on source change/unavailability or unavailable feature revision without cursor
advance; it then releases the lease. Focused Docker runner evidence is 12/12;
full Flexible evidence is 131/131 plus compilation. Receipt resolution/matching
and real isolated worker execution remain. Runner-level Continue now reads only
the persisted terminal parent, fresh-verifies its frozen source/contract, and
creates the linked queued window through the existing receipt-bound cursor
contract; corrected history creates no child and leaves the parent unchanged.
Focused Docker runner evidence is 14/14; full Flexible evidence is 133/133 plus
compilation.

**Campaign service prerequisite (2026-08-27):** discovery evaluation now accepts
and records a caller-supplied frozen `EvaluationSplit` and `ExecutionContract`,
rather than reconstructing their provenance when a campaign service invokes it.
Focused Docker search evidence is 8/8; full Flexible evidence is 134/134 plus
compilation. Concrete service/artifact checkpointing and isolated worker wiring
remain.

**Current checkpoint (authoritative, 2026-08-27):** Campaign Task 1 is complete.
Campaign Task 2 is complete through its Docker gate using the `desktop-linux`
context: receipt-first
`DiscoveryService`, serialized worker/watchdog boundary, source/contract and
receipt-bound Resume proof, cancellation, deterministic fault classes, one
transient retry, and safe incompatible-checkpoint failure with lease release.
The full Flexible campaign suite is **189/189 plus compilation**. Task 3 is
complete: the read-only group adapter, fresh all-member preflight, unioned
primitive profiles, explicit cache choice, independent target qualification,
source-change isolation, and receipt-backed group artifacts are implemented and
Docker-verified. **Campaign Task 4 is now complete:** common-as-of Current BUY
Scan enforces one latest bar for the frozen group, verifies source/evidence
anchors before cache work, groups primitive profiles by ticker/build contract,
persists all feature receipts before current-mask evaluation, and writes
current-scan result artifacts. Display-only, source/receipt/cache failures can
never become no-current-setup. **Campaign Task 5 is complete through its safe
policy and deterministic fixtures:** safe defaults remain 15 tickers, zero
discovery attempts, one worker; no production scale benchmark has been claimed
or enabled. The synthetic 20-ticker current-scan fixture measured 0.473677s
cold and 0.166481s warm in Docker. The FPT-shaped maximal-slot discovery
fixture completed 100 cold and 100 warm full train/test/selection/write samples
(cold p99 total 0.133270s; warm 0.110010s), but both fixtures exclude
production DB/source-load and resource telemetry. They neither create a
`BenchmarkRecord` nor expand policy. **Campaign Task 6 is complete
(2026-08-28):** the
standalone radio workspace and sidebar route are present; Discover stays
disabled under the zero-attempt policy; Library projects immutable definitions
and signal evidence with read-only filtering, pagination, artifact downloads,
and campaign-specific selection/75%-overlap status; Qualification and Current
Group BUY Scan preflight before execution. Discovery now validates a worker
cursor before persisting evidence and publishes a selection snapshot only for a
fully committed window. Campaign-specific selection membership is immutable and
separate from the campaign-independent signal-set identity. Current Scan now
verifies qualified evidence anchors before it can offer cached components.
The implementation review found no SQL/DB path, no V3 coupling, and no unsafe
artifact mutation. The canonical Docker focused gate passes **209/209**, and
the required Flexible modules compile. Evidence:
`docs/superpowers/reports/2026-08-28-flexible-rulebook-task6-verification.md`.

**Campaign receipt checkpoint (2026-08-27):** `ReceiptCheckpointService` now
requires one runner-verified discovery source, resolves only a receipt matching
the frozen source/FeaturePlan/FeatureBuildContract, writes that immutable receipt
before returning its checkpoint, and rejects a different persisted receipt.
Focused Docker runner evidence is 15/15; full Flexible evidence is 135/135 plus
compilation. Frozen-frontier candidate-to-ledger conversion now emits compact
receipt/assignment/stratum/outcome provenance only for committed slots; the full
Flexible Docker gate then passed 136/136 plus compilation. Receipt-bound ledger
chunk persistence is now exposed through the service boundary, and campaign-item
checkpointing writes the immutable worker-owned item artifact before returning
the coordinator's updated manifest checkpoint. `DiscoveryService` now composes
receipt resolution, frozen candidate evaluation, ledger persistence, qualified
definition/signal evidence, item checkpointing, and contiguous cursor/state
updates. The isolated `worker.py` boundary now accepts only an atomic JSON
request with validated top-level callable references; `start_campaign_worker`
and `watch_campaign_worker` launch one module subprocess and convert timeout or
dead-worker loss to resumable `interrupted` without forging success. Focused
worker/fault evidence is 7/7, discovery-service evidence is 3/3, and runner
evidence is 24/24; the local Flexible suite is 159/159 plus compilation.
Docker rerun used the `desktop-linux` context after the default client pipe was
stale. `runner.py`
now also provides deterministic safe `WorkerFault` classification for source,
shared-infrastructure, transient-item, invariant, and watchdog failures;
receipt-bound Resume proof happens before lease claim. Runner now retries an
explicit transient item failure once, blocks shared infrastructure failure,
fails invariant worker contracts, and cancels before source work when
cancellation is already requested. Deadline no-skip and receipt-mismatch fault
tests are covered locally. Task 2 Docker verification passes. Task 3 adds the
read-only `FrozenGroup` adapter, fresh all-member preflight, unioned primitive
profiles, explicit cache choice, independent target qualification, and
source-change isolation; focused group/service evidence is 6/6 plus the full
Flexible suite at 163/163.
Approved design:
`docs/superpowers/specs/2026-08-25-flexible-rulebook-design.md`. Execution
sequence remains `docs/superpowers/plans/2026-08-25-flexible-rulebook-core.md`
then `docs/superpowers/plans/2026-08-25-flexible-rulebook-campaigns-and-current-scan.md`.

**Flexible Rulebook planning amendment (2026-08-26):** approved review repair
now locks a lazy seeded structurally stratified CandidateSpace/FrontierAssignment
search, persisted continuation cursor, portable cross-ticker reuse, native-bar
split boundary, explicit technical/price exit precedence, and 75%-overlap
training timing distinctness for Top 3. It also defines fresh-source-validated
reusable per-primitive indicator components (with request-scoped bundles only),
the <=24-hour Reuse/Recalculate prompt, frozen-source Continue/Resume safety,
append-safe historical evidence anchors, immutable campaign-chain selection
snapshots, a 4h55 per-ticker normal terminal limit with 4h30 candidate admission
stop, benchmark-backed maximal-slot caps, and standalone radio-workspace UI
behavior. The amendment now adds FeaturePlan/FeatureResolutionReceipt digest
proof for cache eviction and continuation, a reference-executor oracle with an
exact-parity-gated event fast path, and an optional exact-prefix append extension
that remains disabled until its benchmark gate passes. Core Tasks 1–7 and
Campaigns Task 1 contract, durable persistence/reconciliation, and receipt-bound
Continue now exist; receipt-bound Resume reconciliation, runner, service,
benchmark, and UI remain
for ordered later tasks.

**Completed UI change:** Collect Signals now has named-Group Edit Group draft
editing: Add/Remove members in a popover and atomically Save, including an
empty Group. Layout is Tickers/Group/Edit Group, then Horizon/Range/Run.
Verification:
`docs/superpowers/reports/2026-08-23-collect-signals-edit-group-verification.md`.

**Completed UI change:** Validate Signals now has the local `Position actions`
dropdown (`ALL` default) ANDed with Monitoring classifications. Its first row
is Tickers plus Ticker group; second row is both filters plus Validate. It
filters the latest cached result without replay. Design:
`docs/superpowers/specs/2026-08-23-validate-signals-position-action-filter-design.md`.
Plan:
`docs/superpowers/plans/2026-08-23-validate-signals-position-action-filter.md`.
Verification:
`docs/superpowers/reports/2026-08-23-validate-signals-position-action-filter-verification.md`.

**Completed UI change:** New OPEN Position form now shows an empty SELL date.
Validate Signals shows sequential progress, an action in the top Monitoring
summary (`can BUY`, `expired BUY`, `can SELL`, or `HOLD`), and collapsed JSON
diagnostics. OPEN signal-backed actions use only the current replay and frozen
SL/TP; no action executes a trade. Design:
`docs/superpowers/specs/2026-08-23-current-positions-sell-default-and-validate-actions-design.md`.
Plan:
`docs/superpowers/plans/2026-08-23-current-positions-sell-default-and-validate-actions.md`.
Verification:
`docs/superpowers/reports/2026-08-23-current-positions-sell-default-and-validate-actions-verification.md`.

**Completed UI change:** View Signals now filters the existing read-only
schema-4 summary table by optional uppercase partial Ticker and by the
`Both`/`Swing`/`Mid-term` Horizon select box (default `Both`). The filters
intersect and do not mutate artifacts, jobs, catalog data, validation, or
positions. Design:
`docs/superpowers/specs/2026-08-23-view-signals-ticker-horizon-filter-design.md`.
Plan:
`docs/superpowers/plans/2026-08-23-view-signals-ticker-horizon-filter.md`.
Verification:
`docs/superpowers/reports/2026-08-23-view-signals-ticker-horizon-filter-verification.md`.

**Completed UI change:** a native shared `View Signals` tab with no View
Signals buttons/popovers, and group-driven batch Validate Signals are
specified in
`docs/superpowers/specs/2026-08-22-backtest-signal-tabs-and-batch-group-validation-design.md`.
Implementation plan:
`docs/superpowers/plans/2026-08-22-backtest-signal-tabs-and-batch-group-validation.md`.
Verification: `docs/superpowers/reports/2026-08-22-backtest-signal-tabs-and-batch-group-validation-verification.md`.
This work does not alter the Phase B risk contract.

**Completed UI change:** View Signals summary columns and terminal-row
suppression are specified in
`docs/superpowers/specs/2026-08-22-view-signals-summary-columns-design.md`.
Implementation plan is
`docs/superpowers/plans/2026-08-22-view-signals-summary-columns.md`.
Verification: `docs/superpowers/reports/2026-08-22-view-signals-summary-columns-verification.md`.

**Completed repair:** New Position now uppercases a committed ticker and
refreshes its saved signal-set choices through isolated current validation;
audit-ineligible or otherwise non-BUY-eligible sets remain manual-only with a
blocking explanation. Verification:
`docs/superpowers/reports/2026-08-22-new-position-saved-set-refresh-verification.md`.

**Completed UI change:** Collect Signals Group defaults to `N/A`, offers
existing groups plus `New group…`, locks Tickers to selected existing-group
members, and preserves existing atomic group creation only on Run Backtest.
Verification:
`docs/superpowers/reports/2026-08-22-collect-signals-group-selector-verification.md`.

**Completed UI change:** Collect Signals run artifacts render in stable output
order, four items per row; item content and downloads are unchanged.
Verification:
`docs/superpowers/reports/2026-08-22-collect-signals-result-grid-verification.md`.

**Completed repair:** Validate Signals Classifications now filter the latest
successful cached validation result without replaying; fresh sessions render no
result list. Verification:
`docs/superpowers/reports/2026-08-22-validate-signals-classification-refresh-verification.md`.

Phase A now provides the fifth non-actionable `Validate Positions` tab,
schema-4 BUY/SELL position groups, and existing position controls. `View
Signals` is the second shared read-only tab.
Verification: 41 focused Docker tests passed; compilation and whitespace checks
passed. The approved Phase B contract is isolated schema-4/no-signal risk
advice: T+3 signal-backed activation, raw-BIGINT scoring, no risk-created SELL
reason, and no legacy evaluation path.

Authoritative design and plan are
`docs/superpowers/specs/2026-08-16-validate-positions-risk-and-trade-rows-design.md`
and `docs/superpowers/plans/2026-08-16-validate-positions-risk-and-trade-rows.md`.
Phase B is governed by the approved
`docs/superpowers/specs/2026-08-22-validate-positions-risk-phase-b-design.md`
and executable plan
`docs/superpowers/plans/2026-08-22-validate-positions-risk-phase-b.md`.
Implementation is complete. Focused Docker verification passes 68 tests and
container compilation passes. Risk suggestion text renders each available
horizon on its own line with a one-decimal score. Its saved-set boundary is
current schema-4 V3 artifacts. Completion evidence:
`docs/superpowers/reports/2026-08-25-validate-positions-phase-b-verification.md`.
Verification is recorded in
`docs/superpowers/reports/2026-08-22-validate-positions-phase-a-verification.md`.

**Predecessor: Horizon Rulebook Signal Redesign — schema-4 exploratory
multi-rulebook replacement: complete and verified.**

Authoritative policy and implementation are
`docs/superpowers/specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`
and `docs/superpowers/plans/2026-08-22-horizon-v3-exploratory-multi-rulebook.md`.
Verification is recorded in
`docs/superpowers/reports/2026-08-22-horizon-v3-exploratory-multi-rulebook-verification.md`.
The implementation evaluates all 15 non-empty RSI/joint-trend/volume/ADX
subsets under both treatments, persists no-theme-training `n >= 5` candidates,
selects treatment only by training DSR, ranks Top 3 by training
win-rate/profit/Sharpe/lexical ID, and labels all evidence
`Exploratory — gross`.

V3 marker invalidation is complete: legacy V3 artifacts/job sidecars are now
schema-4 `requires_regeneration` markers. Fresh VCB Swing verification passed
with a clean audit, calendar 10y/5y split, 15 candidates, and Top 3 evidence.
Audit-ineligible rulebooks are display-only and blocked both in the UI and at
the schema-4 signal-backed position boundary.

**Stopping point:** Phase B is complete. Flexible Rulebook Core Plan Task 3's
generic FeatureStore/lazy-mask slice passes its focused gate. Catalog-v1 finite
settings and persistent primitive cache remain blocked. Task 4 needs a
definition-owned ATR primitive/period before it can freeze entry ATR. It must
not enumerate candidates or depend on cache resolution.
The text below is historical context only.

Replace the current three compact strategy IDs with one deterministic,
long-only rulebook per horizon. Swing is daily EMA(5/13), RSI(9) upcross 52,
short causal Alligator, a prior-10-session 1.3× volume gate, ADX(14) >=17,
and an inclusive 22-bar hold. Mid-term is weekly SMA(8/21), RSI(14) upcross
70, standard causal Alligator, a prior-8-week 1.5× volume gate, ADX(14) >=20,
and an inclusive 16-bar hold. Both require the shared MA/Alligator joint trend
predicate: each strict local point must be `Up` (`>=3`); there is no averaged
trend bucket. Swing historical entry uses joint trend plus RSI crossing only;
mid-term historical entry uses joint trend plus volume only. VN-Index AND is an
optional additional entry gate. The other calculated criteria remain
monitoring-only. Rulebook inputs are fresh Backtest-owned functions, never Analyze
helpers; missing/non-finite required input explicitly blocks entry. Mid-term
uses `W-FRI` bars and excludes the final labelled week until its Friday has
passed, including where Friday itself is a market holiday. Saturday and later
include that labelled row; there is no Monday-only block.

Validate's match percentage is a monitoring/near-miss readout only, never an
entry or certification score. It weights capped current-to-saved-rulebook
threshold ratios for RSI, volume, ADX, and (when themed) VN-Index. Trend is
binary: the same joint predicate contributes 100% or 0%, never an averaged
near-miss score. Swing uses 15% per ticker factor plus 40% theme; Mid-term
uses 20% each. No-theme redistributes to 25% per ticker factor with zero theme
share. The four exclusive classifications are: Swing themed `<=50`, `>50–<65`,
`>=65–<90`, `>=90`; Swing no-theme `<=50`, `>50–<65`, `>=65–<80`, `>=80`;
Mid-term themed `<=40`, `>40–<60`, `>=60–<85`, `>=85`; Mid-term no-theme
`<=40`, `>40–<60`, `>=60–<80`, `>=80` (No Match, Weak, Nearly, Closely).

Certification remains per ticker/horizon/theme with `n >=5` for both horizons.
Default no-theme execution runs only no-theme and uses
`min_n` plus deterministic permutation p-value; it has no PSR or DSR. A
VN-Index request runs both treatments and uses their exact two-Sharpe DSR family
for both rows, with Swing `DSR >=0.90` and Mid-term `DSR >=0.85`, then each
row's permutation p-value. A missing themed companion blocks no-theme
certification explicitly and never falls back to permutation-only. V3 audit
eligibility is freshly calculated from the run's raw DB history:
clean needs valid OHLCV, <=1% OHLC mismatch, and no >=15% close discontinuity;
indeterminate/ordering-only-invalid normal results remain available but
audit-ineligible, using the derived envelope only for ordering issues. A range
longer than retained history uses all available history and records its bounds.

V2 artifacts have no current reader, fallback, conversion, warning, or
maintenance path. After V3 tests and a manual nonempty V3 proof, an explicit
bulk backfill inventories legacy filenames only, runs every ticker across both
horizons with theme enabled, and writes no-theme and themed V3 documents.
Every requested treatment writes one terminal `success`, `empty`, or
`failed(reason)` document; a tracker, not a four-file atomicity claim, gates
cleanup. Empty certification records a controlled rejection reason, including
`missing required no-theme DSR companion`; unavailable date ranges use paired
null dates plus a reason. Failures do not retain V2 evidence. Only then may
the user review exact V2 paths and separately approve deletion.
Existing frozen position snapshots remain readable without artifact lookup.
V3-only cutover explicitly removes V2 job requests, root migration, compact
score replay, artifact/catalog readers, and UI/download paths. Existing pre-V3
positions are P&L/manual-management history only, never V3 signal evidence.

Current stopping point: **the approved gate/statistics amendment design and
executable plan are ready; implementation has not started.** It supersedes the
previous V3 gate/PSR policy, so all Task 7 evidence stated below is
pre-amendment history and the manual proof must be rerun after the amendment is
implemented and verified. Task 6 replaced score replay with horizon-isolated V3 rulebook replay,
added V3 saved-set position identity and risk snapshots, retained frozen
pre-V3 positions only for P&L/manual management, and restored those management
controls in Current Positions with k-VND display scaling. The full Docker
Backtest suite passes 132 tests. Task 7 published read-only VCB evidence:
both horizons are clean but remain below their locked `min_n`, without tuning.
The final read-only proof preflight also found every locked-roster no-theme
Swing result empty (`n=5--8`, below 22), so no locked ticker can clear the
manual nonempty-proof gate. The 2026-08-21 user-run Swing Collect job
`ef0412da7a504a76843fe3abb7657b95` for TCB, VCB, REE, FPT, HPG, and MSN
completed without errors and wrote all 12 requested V3 documents, but each is
an `empty` `min_n` result. No-theme completed exits were TCB 2, VCB 8, REE 5,
FPT 5, HPG 6, and MSN 8; themed exits were 2, 5, 5, 4, 5, and 6 respectively.
TCB and VCB were audit-clean; the remaining four are ordering-mismatch
audit-ineligible but remain normal results by design. The required manual
nonempty proof is therefore still unmet and no backfill may begin. Separate
VCB-only read-only signal-optimizer research has an approved design at
`docs/superpowers/specs/2026-08-21-vcb-read-only-signal-optimizer-design.md`
and execution plan at
`docs/superpowers/plans/2026-08-21-vcb-read-only-signal-optimizer.md`.
Its isolated `backtest_engine.research_optimizer` implementation and 15-year
VCB live run are complete. It evaluates all 60 candidates through native V3
frames/execution without V3 persistence or configuration changes; report:
`docs/superpowers/reports/2026-08-21-vcb-15y-signal-optimizer.md`.
Swing had 16 DSR and 14 PSR rejections; Mid-term had 25 PSR, four `min_n`,
and one PSR-computation rejection, so no candidate is fully eligible under the
approved search-wide contract. The focused Docker gate passed 39/39. V3 and
Task 7 remain untouched. Diagnostics
now use current pipeline date/theme helpers; immutable Swing/Mid-term
rulebooks own all values; causal Boolean entries execute one flat-to-flat
native trade sequence; and the permanent
read-only frozen-roster audit is at
`docs/superpowers/reports/2026-08-15-v3-price-audit.md`. All eight tickers
meet the independent Swing/Mid-term history floors; only VCB is price-audit
clean. Future V3 research excludes REE, FPT, SSI, VIC, PLX, DHG, and HPG while
normal UI availability remains unchanged. The temporary input—not the
report—is removed only after the whole plan and separately approved V2 cleanup.

Queued only after **every** Horizon Rulebook Signal Redesign task closes:
**Validate Positions Risk and Trade-row Presentation** has an approved
two-phase design. Do not start any Phase A task after V3-only cutover alone:
Tasks 0--9 must finish in order, including Task 7 manual V3 proof, Task 8
backfill/tracker, and Task 9 V2 cleanup after separate explicit deletion
approval. Phase A adds the fourth tab and collapsible BUY/SELL position groups
while retaining existing controls; Phase B was initially blocked pending a separately
approved deterministic risk formula, bands, and result-table contract. It uses
latest completed DB bars only, supports up to five sequential OPEN positions,
and never reads V2 artifacts.
Design: `docs/superpowers/specs/2026-08-16-validate-positions-risk-and-trade-rows-design.md`.
Plan: `docs/superpowers/plans/2026-08-16-validate-positions-risk-and-trade-rows.md`.

- [x] Study the existing rule logic and run read-only VCB/frozen-universe
  feasibility spikes.
- [x] Lock two rulebooks, entry gates, min-n values, AND-only theme, PSR/DSR
  trial semantics, fresh V3 audit eligibility, and bulk-backfill-before-delete.
- [x] Write the V3-only artifact cutover design and phased implementation plan.
- [x] Spike all three Backtest tabs and add the V2 job, migration, replay,
  horizon-identity, audit-metadata, and UI cutover gaps to the plan.
- [x] Lock the shared joint-trend gate/zero-strength monitoring behavior,
  treatment-specific match bands, and holiday-short-week `W-FRI` boundary
  fixture (Thursday/Friday exclude; Saturday/Monday include).
- [x] Design queued V3-only Validate Positions and grouped BUY/SELL position
  presentation; defer risk formula and bands to a separate Phase B contract.
- [x] Task 0: repair diagnostics and publish the locked-roster price-audit report.
- [x] Task 1: encode immutable horizon rulebooks.
- [x] Task 2: build causal rulebook inputs and entry gates.
- [x] Task 3: execute one flat-to-flat trade sequence per rulebook.
- [x] Task 4: original PSR/DSR implementation (superseded by the approved amendment).
- [x] Task 5: introduce V3 horizon-qualified terminal artifacts and remove V2 current-artifact support.
- [x] Task 6: V3 replay/UI and horizon-qualified saved-set position boundary.
- [x] Review the V3 gate/statistics amendment design and write its executable amendment plan.
- [x] Implement and verify the approved V3 schema-4 exploratory replacement.
- [x] Task 7: evidence/report complete under the replacement plan.
- [x] Task 8: replacement-plan terminal artifact/job transition complete.
- [x] Task 9: V3 plan closure complete; V2 deletion remains explicitly outside scope and unapproved.

Design:
`docs/superpowers/specs/2026-08-15-horizon-rulebook-signal-redesign-design.md`.

Superseded amendment design:
`docs/superpowers/specs/2026-08-21-horizon-rulebook-v3-gate-statistics-update-design.md`.

Active replacement design:
`docs/superpowers/specs/2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`.

Active replacement plan:
`docs/superpowers/plans/2026-08-22-horizon-v3-exploratory-multi-rulebook.md`.

Plan:
`docs/superpowers/plans/2026-08-15-horizon-rulebook-signal-redesign.md`.

## Latest Completed Task

**Collect Group Membership Independent of Backtest Results (2026-08-15).**

Named Collect Groups now atomically add all requested batch tickers before
theme preflight or ticker execution, regardless of empty, failed, or retried
backtest outcomes. Group-store failures abort before work starts. Validate
continues to skip no-signal Group tickers and validates eligible siblings.
Unordered uppercase unique Group JSON tickers are accepted and read in sorted
order; duplicate/non-uppercase values remain invalid. Docker focused Backtest
tests passed 108/108, compilation and Streamlit health `200` passed. No
artifact, position, replay, SQL, BIGINT-price, dependency, Docker, credential,
runtime-data, or commit change.

Verification:
`docs/superpowers/reports/2026-08-15-collect-group-membership-independent-of-results-verification.md`.

## Task

**Backtest Multi-Metric Certified Candidates and Sequential Batch (2026-08-14).**

- Persist one schema-v2 candidate for every metric group won by the exact same
  indicator combination; no V1 artifact read, conversion, or fallback remains.
- Collect Signals accepts one to five ordered unique tickers and submits one
  auto-polled sequential job. Theme runs one shared VN-Index preflight then
  writes each ticker's no-theme and VN-Index AND outputs in order; ticker
  failures retry once after first pass and remain recorded when terminal.
- Saved-set replay, catalog, validation, and position references preserve the
  full grouped metric list. Existing frozen legacy position snapshots remain
  readable only in position history.
- The final focused Docker gate passes 127/127. The six verified V1 FPT/TCB/VCB
  artifact files were deleted; no V2 artifact remains and signals will be
  regenerated later. No Backtest, database, position, job-status, dependency,
  Docker, credential, or commit change was made.

Design:
`docs/superpowers/specs/2026-08-14-backtest-v2-multi-metric-batch-design.md`.
Plan:
`docs/superpowers/plans/2026-08-14-backtest-v2-multi-metric-batch.md`.
Verification:
`docs/superpowers/reports/2026-08-14-backtest-v2-multi-metric-batch-verification.md`.

## Earlier Completed Task

## Task

**View Signals Current-Tab Ticker Filter.**

- Add one label-hidden filter at the top of View Signals with placeholder
  `ticker name`.
- Filter uses partial ticker matching and auto-capitalizes input; it affects
  the displayed All, Valid, or Invalid rows while leaving warnings and tab
  availability intact.
- The implementation is read-only: no artifact, position, job, replay, SQL,
  BIGINT-price, dependency, Docker, credential, or commit change.

Design:
`docs/superpowers/specs/2026-08-13-view-signals-ticker-filter-design.md`.
Plan:
`docs/superpowers/plans/2026-08-13-view-signals-current-tab-ticker-filter.md`.
Verification:
`docs/superpowers/reports/2026-08-13-view-signals-current-tab-ticker-filter-verification.md`.

## Earlier Completed Task

## Task

**View Current Signal Sets Popover.**

- Add native `View Signals` beside Collect Signals `Run backtest`; it scans
  every current ticker/theme JSON artifact read-only and has no action control.
- Show the approved nine fields. Invalid artifacts keep the same schema, use a
  red row, and show a separate warning; tabs are All/Valid/Invalid only when
  invalid data exists, otherwise All only.
- Preserve job submission, replay, persistence, SQL, BIGINT pricing,
  dependencies, Docker, credentials, and commit history.

Plan: `docs/superpowers/plans/2026-08-13-view-current-signal-sets.md`.
Verification:
`docs/superpowers/reports/2026-08-13-view-current-signal-sets-verification.md`.

## Earlier Completed Task

## Task

**Action Labels for Collect Signals and Data Page.**

- Add `Action` above Collect Signals `VN-Index theme` and Data Page `Get data`
  so each aligns with the input and dropdown boxes.
- Preserve checkbox label/default/disabled state, ingestion callback behavior,
  configuration variants, SQL, BIGINT pricing, dependencies, Docker, and
  commit history.

Verification:
`docs/superpowers/reports/2026-08-13-collect-signals-theme-alignment-verification.md`.

## Earlier Completed Task

## Task

**Data Page Phase-Progress UI.**

- Put `Up-to date`, `Year gaps`, and `Get data` on one first row; Year gaps
  defaults to `15`, with an `Action` label above the button for input-box
  alignment.
- Replace the spinner with truthful completed-phase progress: reset, schema,
  stock, VN-Index, and completion, from 0 to 100%.
- Keep existing detailed ingestion messages in an initially-expanded
  `Progress details` section.
- Preserve the existing synchronous ingestion path, API/background behavior,
  reset semantics, URLs, SQL, BIGINT `* 1000` price scaling, dependencies,
  Docker, and commit history.

Plan: `docs/superpowers/plans/2026-08-13-data-page-phase-progress.md`.
Verification:
`docs/superpowers/reports/2026-08-13-data-page-phase-progress-verification.md`.

## Earlier Completed Task

## Task

**Collect Signals Control-Row Layout.**

- Put Ticker, Time range, Horizon, and `VN-Index theme` on line 1.
- Default Time range to `15y`; use Horizon dropdown default `-` and preserve
  existing required-horizon validation.
- Keep Custom Start/End dates and Run backtest below; leave Validate Signals
  and Current Positions unchanged.

Plan: `docs/superpowers/plans/2026-08-13-collect-signals-control-row.md`.
Verification:
`docs/superpowers/reports/2026-08-13-collect-signals-control-row-verification.md`.

## Earlier Completed Task

## Task

**Current Positions Native New Position Popover Restoration.**

- Restore `st.popover("New position")` and remove panel-only session state,
  placeholder, and Close button.
- Preserve ticker capitalization, saved-signal lookup, OPEN/CLOSED validation,
  raw-price conversion, frozen risk snapshot, and persistence calls.
- Retain native click-outside/Escape dismissal; Streamlit 1.32 has no supported
  API for an internal Close control.
- Add `TODO(streamlit-upgrade)` beside the popover for future reevaluation.

Plan:
`docs/superpowers/plans/2026-08-13-current-positions-native-popover-restoration.md`.
Verification:
`docs/superpowers/reports/2026-08-13-current-positions-native-popover-restoration-verification.md`.

## Earlier Completed Task

## Task

**Current Positions UI Regression Fix — select-all and New Position Close.**

- Fix the stale state overwrite that prevented Select all visible from checking
  or unchecking the current filtered rows.
- Replace the Streamlit 1.32 popover (which lacks a programmatic close API)
  with a state-controlled New position panel and a Close button that writes no
  position data.
- Add RED/GREEN AppTest regression coverage for both paths.
- Leave SQL, schema, BIGINT price scaling, dependencies, Docker, credentials,
  and commit history unchanged.

Verification:
`docs/superpowers/reports/2026-08-12-current-positions-ui-regression-fix-verification.md`.

## Earlier Completed Task

## Task

**Validate Signals UI Revamp — Scope Definition.**

Improve the saved-signal validation flow without changing replay, signal
artifacts, or long-only execution rules. Extend position persistence only for
the approved optional quantity and editable actual BUY/SELL values.

Approved design:
`docs/superpowers/specs/2026-08-11-validate-signals-ui-revamp-design.md`.

Execution plan:
`docs/superpowers/plans/2026-08-11-validate-signals-ui-revamp.md`.

- show progress only while `Validate saved signals` is running; hide it after
  success or failure;
- show no-theme result first, then VN-Index AND result; each title owns its
  corresponding signal sets;
- place an expandable signal-set summary below those results. Show Identity
  (ticker and selected metric), Strategy (indicators and BUY threshold),
  Backtest performance, Current match, Current trade signal, and
  Existing-position state by default;
- show Backtest performance fields: `n`, win rate %, profit %, Sharpe,
  deflated Sharpe, p-value, and date range;
- show Current match fields: match %, classification, advice, and theme
  eligibility;
- show Current trade signal fields: signal date, entry, SL, TP, and projected
  exit;
- show Existing-position state fields: status, holding/suggested holding,
  SELL allowed/reasons, and pinned SL/TP;
- provide a column-visibility filter; all other available fields are hidden by
  default; visibility resets each browser session;
- reveal selected signal sets in expandable detail views; users may expand
  several detail panels at once; summary and detail panels start collapsed;
- support explicit, individual BUY/SELL decision recording for each eligible
  signal set or open position.
- keep BUY and SELL recording in `Validate Signals`: show BUY or `Close
  position` beside each applicable suggestion. `Current Positions` is the
  saved-position list, filter, and saved price/quantity edit view.
- add `Current Positions` as a third top-level Backtest Lab tab beside
  `Collect Signals` and `Validate Signals`.
- render all OPEN positions immediately; filter by ticker and state, with
  `OPEN` selected and `CLOSED` hidden by default.
- use an explicit `Refresh` button for Current Positions.
- treat themed and no-theme positions equally; order the combined list by
  position open time, oldest first.
- show ticker, actual BUY price, actual SELL price or `-`, percentage profit,
  profit, open time, closed time, and associated signal set for every position.
- for OPEN positions, show latest trading-day close as current price and use it
  to calculate unrealized profit and percentage profit; show SELL price and
  closed time as `-`.
- calculate displayed P&L without fees or taxes.
- display absolute P&L as per-share VND price difference. Manual BUY/SELL
  recording forms keep user-editable actual price fields. Saved quantity and
  BUY/SELL prices remain editable after recording.
- add optional position quantity. When present, absolute P&L equals price
  difference times quantity; when absent, show simple per-share price
  difference. Percentage P&L remains price-based. Quantity is user-entered
  optionally at any time; it is not fixed at BUY and remains editable after
  recording. Quantity/price edits overwrite their current values only and
  never change open or closed time.

## Current Phase — Complete

- [x] Confirm result ordering: No theme first, then VN-Index AND.
- [x] Confirm collapsible signal-set selection: several detail panels may be
  expanded simultaneously.
- [x] Confirm current-position tab placement: third top-level Backtest Lab tab.
- [x] Confirm current-position list/filter contract: render all OPEN positions;
  ticker and OPEN/CLOSED filters; CLOSED hidden by default.
- [x] Confirm position ordering principle: one theme-neutral combined list,
  ordered oldest first by open time.
- [x] Confirm current-position fields: ticker, BUY/SELL prices, percentage and
  absolute profit, open/closed times, and signal set.
- [x] Confirm OPEN placeholders: SELL price and closed time are `-`.
- [x] Confirm OPEN profit semantics: latest trading-day close is current price
  and drives unrealized profit/%.
- [x] Confirm P&L cost treatment: no fees or taxes.
- [x] Confirm manual-decision placement: BUY/Close position beside applicable
  Validate Signals advice; Current Positions is a list/filter/edit view.
- [x] Confirm decision interaction: individual action/form per eligible item;
  no batch selection or shared BUY/SELL form.
- [x] Confirm absolute-profit unit: per-share VND price difference; manual
  decision forms accept user-entered actual prices.
- [x] Confirm optional quantity/P&L contract: quantity multiplies absolute P&L;
  no quantity preserves simple per-share price difference.
- [x] Confirm quantity interaction: optional user entry at any time, not fixed
  at BUY, and editable after recording.
- [x] Confirm edit temporal rule: quantity/price edits never change open or
  closed time.
- [x] Confirm edit persistence: overwrite current quantity/price only; no
  correction history.
- [x] Confirm current-position refresh trigger: explicit Refresh button.
- [x] Confirm Current Positions Refresh scope: saved position records plus
  latest prices and recalculated P&L.
- [x] Confirm default signal-summary groups and fields: Identity/Strategy plus
  specified Backtest performance, Current match, Current trade signal, and
  Existing-position state fields.
- [x] Confirm column visibility: non-default fields start hidden and users can
  control their visibility.
- [x] Confirm column visibility lifetime: reset each browser session.
- [x] Retain current per-set detail content in this structural UI revamp.
- [x] Confirm saved price/quantity edit entry point: Current Positions.
- [x] Confirm default collapse state: signal-set summary and all detail panels
  start collapsed.
- [x] Write consolidated design and test-first implementation plan.
- [x] Task 1: position quantity and atomic manual edits. Host RED proved the
  missing interface; host GREEN passes 7/7 position-store tests.
- [x] Task 2: batched current-position overview. Host RED proved the missing
  module; host GREEN passes 12/12 store/overview tests.
- [x] Task 3: Validate Signals progress, hierarchy, and individual decisions.
  Docker RED exposed missing third tab; green AppTests prove progress cleanup,
  no-theme-first hierarchy, collapsed summaries/details, and individual manual
  actions.
- [x] Task 4: Current Positions tab/filter/edit flow. Docker AppTests prove
  OPEN default/filtering, per-record BUY/SELL edits, optional quantity removal,
  and recalculated frozen-ATR SL/TP after a BUY-price edit.
- [x] Task 5: verification, review, and documentation. See
  `docs/superpowers/reports/2026-08-11-validate-signals-ui-revamp-verification.md`.

Current stopping point: **Validate Signals UI Revamp complete. No commit made.**

## Prior Phase — Backtest Compact Strategy Revamp (complete)

Review the VCB zero-certification behavior without tuning to VCB. The approved
design replaces the generated indicator grid with three compact strategies,
adds causal Williams Alligator, removes rolling-window duplicate trade events,
and decouples statistical gate semantics after a database-only price audit.

Approved design:
`docs/superpowers/specs/2026-08-10-backtest-compact-strategy-revamp-design.md`.

Execution plan:
`docs/superpowers/plans/2026-08-10-backtest-compact-strategy-revamp.md`.

## Completion Evidence

- [x] Freeze no-forced-signal, per-ticker `n >= 30`, database-only audit,
  compact strategy, causal Alligator, and hard-ADX decisions.
- [x] Write and self-review the design specification.
- [x] User reviews and approves the specification.
- [x] Write and self-review the detailed implementation plan.
- [x] Task 0: record RED contract baseline; old 270/810 generated grid lacks
  compact `strategy_id` and fixed-rulebook behavior as expected.
- [x] Task 1: 14/14 Docker audit/universe tests pass. One bound raw-connection
  query loads candidates; exact 15% moves are indeterminate, material OHLC
  mismatches and coverage exclude candidates, and ticker-symbol ties are
  deterministic.
- [x] Task 2: 11/11 Docker indicator tests pass. Backtest-only Alligator uses
  causal 13/8/5 SMMA values with 8/5/3 lags; no live Technical behavior changed.
- [x] Task 3: 43/43 Docker compatibility gate passes. Generator emits only
  three strategy IDs per no-theme/AND variant at score 60 with hard `ADX >=20`.
  Old no-ID artifact replay remains supported.
- [x] Task 4: 28/28 Docker native-clock tests pass. One chronological sequence
  executes each signal once; partitions exclude boundary-crossing exits.
- [x] Task 5: 8/8 Docker validation/certification tests pass. Permutation alpha
  is explicit and independent from the DSR cutoff.
- [x] Task 6: 5/5 Docker pipeline/diagnostic tests pass (one expected unmounted
  CLI skip). Pipeline certifies sequence events, not rolling duplicates.
- [x] Task 7 deterministic gate: 60/60 Docker tests pass, one expected CLI skip;
  Backtest package compiles and whitespace check passes.
- [x] Refine the audit using current DB evidence: use the shared available
  history bounds, warn for `<=1%` OHLC mismatch, reject `>1%`, and create only
  a derived Backtest OHLC envelope. Raw DB values remain unchanged.
- [x] Task 7 live audit: 21 clean, 6 indeterminate, and 1,837 invalid
  candidates. VCB is clean (0.95% minor mismatch, no `>=15%` close move), and
  the deterministic frozen universe is `VCB, DHC, HJS, ELC, VPL, C47, HAP,
  CSM`.
- [x] Task 7: `collect_compact_strategy_diagnostics()` evaluates eight frozen
  tickers across Swing/Mid-term and no-theme/VN-Index AND variants (96 compact
  strategy results). It loads candidates once, loads VN-Index once, reuses raw
  frames, reports full-history certification plus reporting-only calibration
  and holdout metrics, preserves VCB trade traces, and declares no writes.
- [x] Final gate: Docker focused Backtest suite passes 66/66 with one expected
  unmounted CLI skip; `compileall backtest_engine pages/backtest_lab.py`,
  `git diff --check`, and changed-file whitespace checks pass.
- [x] Follow-up replay repair: persisted JSON sorts compact indicator dimensions
  alphabetically, while compact strategy identity requires rulebook order. The
  shared `IndicatorCombo` contract now validates indicator content independent
  of JSON key order, canonicalizes the approved order, and still rejects
  duplicate, missing, extra, or incorrect dimensions. RED/GREEN regression
  coverage passes; live VCB no-theme and VN-Index AND replay are both available.

Current outcome: **live read-only diagnostic used current DB history from
2011-08-10 through 2026-08-10; selected `VCB, DHC, HJS, ELC, VPL, C47, HAP,
CSM`; returned 27 qualified compact combinations. VCB Swing has five qualified
sets; VCB Mid-term has none because no-theme variants fail DSR and themed
variants fail `n >= 30`. This is a truthful certification outcome, not an OHLC
failure and not a reason to tune frozen gates. Runtime was 204.64 seconds. No
database data, job, current signal artifact, or commit changed. Evidence:
`docs/superpowers/reports/2026-08-10-backtest-compact-strategy-evidence.md`.**

## Prior Phase — Validate Signals Verification and Documentation (complete)

- [x] Inspect signal artifacts, replay context, price conversion, and position
  persistence boundaries without writing an artifact or database record.
- [x] Prove daily/weekly buy-date and as-of handling with a deterministic
  Mid-term mid-week fixture; no future source bar may be counted.
- [x] Record the selected native-bar contract before source code changes.

Phase 0 gate: PASS — see
`docs/superpowers/reports/2026-08-07-validate-signals-spike.md`.

Task 1 checklist:

- [x] Add and run RED coverage for raw replay context, artifact horizon
  consistency, one-frame-per-horizon replay, and matching boundaries.
- [x] Make the smallest replay and matching implementation that turns that
  coverage GREEN.
- [x] Verify the read-only boundary and compile the engine package.

Task 1 gate: PASS — the expected RED failures were recorded; the focused
Docker gate passes 18/18 and `backtest_engine` compiles in the container.

Task 2 checklist:

- [x] Add and run RED coverage for `k VND` input conversion and atomic
  per-tuple position histories.
- [x] Implement validated raw-price conversion and freeze caller-supplied
  signal, entry, and risk snapshots without deriving new trading values.
- [x] Verify focused Docker tests, snapshot immutability, whitespace, and
  protected-boundary scope.

Task 2 gate: PASS — expected missing-interface RED was recorded; the focused
Docker gate passes 9/9 and `backtest_engine` compiles in the container. The
store uses raw integers only, deep-copies validated snapshots, and atomically
replaces its per-tuple JSON file. The protected-path inspection showed a
pre-existing unrelated `app/main.py` diff; Task 2 did not modify it.

Task 3 checklist:

- [x] Add and run RED lifecycle coverage for native holding periods, SL/TP
  proximity, timeout, and no-look-ahead handling.
- [x] Implement the read-only daily/weekly monitor without an exit path.
- [x] Verify monitor and existing Swing/Mid-term lifecycle tests.

Task 3 gate: PASS — the focused native-monitor and existing Swing/Mid-term
lifecycle Docker gate passes 17/17. The monitor slices raw history at as-of
before calculation, counts daily/weekly native periods only, and never writes
or closes a position.

Task 4 checklist:

- [x] Add and run composition coverage for Observe, BUY eligibility, theme
  ineligibility, independent variants, and pinned open-position monitoring.
- [x] Isolate malformed position history to its own theme variant, retaining
  advice from the other variant.
- [x] Verify no persistence calls during validation and rerun replay coverage.

Task 4 gate: PASS — Docker validation-advice, position-store,
position-monitor, and early-warning gate passes 30/30. Validation remains
read-only; a corrupt themed position file now reports only that themed result
as unavailable and does not hide no-theme advice.

Task 5 checklist:

- [x] Add and run RED AppTests for explicit validation, independent theme
  rendering, unavailable artifacts, manual BUY, manual SELL, and no job
  submission.
- [x] Implement injected validation/store callbacks, selection identity
  protection, raw/UI price conversion, and manual forms only.
- [x] Lock each BUY date to its validation as-of date and calculate/freeze its
  raw ATR risk snapshot from that same context.
- [x] Verify page, job, replay, and advice regressions; prove stale selection
  guard fails when removed and passes when restored.

Task 5 gate: PASS — Docker page, job-runner, replay, and validation-advice
gate passes 47/47. The Validate tab has no job submission, refresh, auto-buy,
or auto-close path. Streamlit dependency `SyntaxWarning` output is external;
the test suite has no test failures or page exceptions.

Task 6 checklist:

- [x] Run explicit Backtest module gate: 105 passed; one expected Docker
  diagnostics skip for unmounted top-level `scripts`.
- [x] Compile `backtest_engine` and `pages`; inspect whitespace and protected
  boundaries without commits.
- [x] Replay real FPT history using temporary artifacts/positions; verify
  no-theme/themed reads, multi-BUY raw/UI conversion, manual SELL, retained
  history, and cleanup.
- [x] Complete implementation review, fix Ho Chi Minh SELL date default and
  multi-selection preflight, then rerun all verification.

Task 6 gate: PASS — full evidence in
`docs/superpowers/reports/2026-08-07-validate-signals-verification.md`.

## Active Locked Decisions

- Validation reads existing current signal files only. It never submits a job,
  re-certifies, or overwrites `ticker-signals`.
- Theme checkbox behavior mirrors Collect Signals: unchecked validates
  no-theme; checked shows no-theme and VN-Index AND separately.
- `match = min(100, current_score / threshold_score_buy * 100)`; a failed
  required theme makes the themed set ineligible. `<70` Observe, `70–<85`
  Nearly match, `>=85` Closely match.
- Eligible sets without an open position advise BUY. Users may select one or
  more, saved separately by ticker/theme/metric. BUY and SELL need explicit
  confirmation and never trade or auto-close.
- A manual BUY date is locked to its selected validation as-of date; this
  freezes that as-of raw ATR and engine-standard 1.5x/2.5x raw exit levels
  with the user's actual raw BUY price. Mixed-as-of selections must be saved
  separately.
- UI price is `k VND`; persistence is raw integer price. No SQL scaling,
  database BIGINT, export, dependency, Docker, or protected-boundary change.
- Each position pins its certified signal/risk snapshot. SELL is allowed only
  after `>60%` of pinned max-hold or within/beyond 5% of pinned SL/TP. Swing
  stays daily; Mid-term stays weekly.
- No commits. `IMPLEMENTED.md` remains excluded.
- Current Docker configuration supplied real FPT history to live-safe temporary
  validation. Existing signal artifacts and position histories were untouched.

## Active Phase Plan

1. Spike/freeze actual temporal contract.
2. Expose replay context and matching primitives.
3. Add raw-price position persistence.
4. Monitor pinned positions on native clocks.
5. Compose advice.
6. Implement Validate Signals tab.
7. Complete verification and document evidence. **Complete.**

Update this active section task-by-task only after each recorded test gate
passes. Current stopping point: **all approved Validate Signals plan tasks are
complete; no commit was made.**
The material below is retained solely as historical Backtest context.

## Archived Backtest Locked Decisions

- Engine package location: `app/backtest_engine/`; this keeps offline jobs and
  the standalone page available in the existing Docker image without changing
  Docker configuration.
- UI placement: standalone `app/pages/backtest_lab.py`.
- Phase 1 trade direction: long-only BUY entries; no short entries and no
  technical early exits. Each TradeEvent is one implicit unit BUY and one
  equal-volume SELL through SL, TP, or timeout; multi-fill support is not in
  the current schema and requires a separately approved model change.
- Combo score: reuse existing technical dimensions, 4/3/2/1/0 points, equal
  group weights, and existing ADX gate semantics.
- Signal trigger: one BUY on the upward crossing of the searched threshold,
  not one signal for every bar above threshold.
- Search: indicator subsets by dimension, BUY threshold grid `{60, 65, 70,
  75, 80}`, ADX gate modes `soft/hard`, horizon, and theme variant.
- Risk/holding defaults: ATR(14), SL `1.5x`, TP `2.5x`, Swing timeout 15
  daily bars with first exit at entry plus three daily bars; Mid-term timeout
  `MAX_HOLD_MIDTERM_BARS = 16` inclusive weekly bars with first exit on the
  next weekly bar. Same-bar SL wins only among eligible exit bars.
- Validation defaults: pooled `MIN_N=30`, six-month windows, one-month
  sliding stride, moving block permutation size 20, 1000 permutations, seed
  42, Deflated-Sharpe/PSR cutoff `0.95`.
- Certification math: unannualized per-trade returns, Pearson kurtosis,
  empirical variance across the exact observed trial Sharpe set, and DSR
  cutoff `0.95`; annualization is display-only.
- Early warning: replay persisted combo, ATR exit, and saved VN-Index
  condition against fresh bounded data; expose no-signal, active, open, and
  timeout-resolved states plus certification age and certified/current diff.
- Job runner: submit immediately through an isolated
  `python -m backtest_engine.worker` subprocess. It atomically persists a JSON
  request and queued/running/done/failed sidecars, keeps progress monotonic,
  serializes no callable, and never imports Streamlit or `main.py`. Database
  URL ports are validated before engine creation; terminal worker failures log
  a job-ID traceback without logging configuration values.
- Container startup: the Compose file is under `docker/`, so Compose must load
  the repository-root `.env` during interpolation, not only as `env_file`.
  Use `docker compose --env-file .env -f docker/docker-compose.yml up -d
  --force-recreate app`; `env_file` alone does not populate `${POSTGRES_PORT}`
  while Compose constructs `DATABASE_URL`.
- Backtest page: a required selected Horizon radio (`Swing` or `Mid-term`) and
  unchecked `INCLUDE_THEME_OPTION` produce one no-theme run or two sibling
  runs (no-theme plus fixed VN-Index `AND`). Request-defining controls and Run
  remain disabled while any submitted job is queued/running/unreadable;
  per-variant statuses/results render independently and update automatically
  every second without a Refresh button. All existing controls, status, and
  results are under `Collect Signals`; `Validate Signals` is intentionally a
  static deferred-work tab. Prices remain raw in engine artifacts.
- Theme: optional no-theme, AND, or OR; VN-Index confirmation uses SMA(50)
  daily for Swing and SMA(20) weekly for Mid-term, aligned as-of signal date.
- Persistence: JSON source of truth; exactly two current files per ticker,
  with-theme and without-theme; re-certification overwrites the selected file.
- Long-running work: background job only. The current isolated worker evaluates
  combos and windows sequentially; its parent uses one reaper thread only to
  wait for the worker process. Do not assume an executor or add concurrency
  diagnostics without separately approved parallelisation work.

## Global Do / Check / Act Workflow

For every task:

1. **DO:** write the smallest failing test first; run it and record the
   expected RED failure.
2. **CHECK:** implement the minimum behavior, run the focused GREEN tests,
   inspect logic/performance/SQL/side effects, and run the phase gate.
3. **ACT:** update this checklist and `current-status.md` only after the gate
   passes; then begin the next task.

No phase advances with a failing, skipped, or unrecorded test. No production
code is written until the plan is approved. No page integration occurs before
the engine and job contracts are proven.

## Archived Backtest Phase Tracker

### Phase 0 — Freeze Contracts and Test Fixtures

- [x] Task 0.1 — Define and test `BacktestConfig`, `IndicatorCombo`,
  `TradeEvent`, and `JobStatus`. Test: `tests.test_backtest_contracts`.
- [x] Task 0.2 — Verify RED for missing contracts. Test command is recorded in
  the implementation plan.
- [x] Task 0.3 — Implement named constants and validated dataclasses only.
- [x] Task 0.4 — Verify GREEN, serialization, invalid-input rejection, and
  contract self-review.

Phase gate: PASS — Docker `tests.test_backtest_contracts` 8/8, compile check
passed, and all Phase 0 schema decisions are frozen.

### Phase 1 — Data Quality, Raw History, and Indicator Adapter

- [x] Task 1.1 — Write RED data-quality tests for structure, prices, duplicate
  dates, >7% findings, gaps, and raw-value preservation.
- [x] Task 1.2 — Verify `tests.test_backtest_data_quality` fails for the
  expected missing implementation.
- [x] Task 1.3 — Implement `data_quality.py` and parameterized raw history
  loading; malformed data blocks indicators, warnings are explicit.
- [x] Task 1.4 — Verify data-quality GREEN and no raw BIGINT mutation.
- [x] Task 1.5 — Write RED indicator-adapter tests for all eight existing
  indicators and horizon parameter reuse.
- [x] Task 1.6 — Implement `indicators.py` as a narrow adapter over existing
  `commons.technical_analysis` functions.
- [x] Task 1.7 — Verify adapter GREEN, SQL safety, and storage-boundary review.

Phase gate: PASS — Docker focused Phase 1 tests pass 11/11; existing
Technical Analyze regressions pass 9/9; SQL, BIGINT, UI-import, and protected
boundary review passed.

### Phase 2 — Combo Generation and Exact Signal Score

- [x] Task 2.1 — Write RED tests for bounded subsets, fixed weights, soft/hard
  ADX gates, threshold grid, and upward crossing semantics.
- [x] Task 2.2 — Verify expected RED failure.
- [x] Task 2.3 — Implement deterministic `signal_combos.py` generation and
  score functions without duplicating live scoring constants.
- [x] Task 2.4 — Verify GREEN and deterministic combo ordering.
- [x] Task 2.5 — Self-review for no flat cross-product, no short signal, no
  weight search, and no level-trigger duplication.

Phase gate: PASS — Docker combo tests pass 4/4; cumulative backtest and
Technical regression gate passes 32/32; no short path, weight search, or
level-trigger duplication found.

### Phase 3 — Rolling Windows and Vectorized Long Trade Engine

- [x] Task 3.1 — Write RED full-coverage rolling-window tests.
- [x] Task 3.2 — Write RED trade fixtures for no look-ahead, next-open entry,
  SL/TP, same-bar SL priority, timeout, and crossing-only signals.
- [x] Task 3.3 — Verify both rolling/trade test files fail for expected missing
  implementation.
- [x] Task 3.4 — Implement vectorized `rolling_window.py` execution.
- [x] Task 3.5 — Verify GREEN on all synthetic fixtures.
- [x] Task 3.6 — Self-critique entry timing, ATR date, overlap, and process
  safety before validation work.

Phase gate: PASS — Docker rolling/trade tests pass 7/7; cumulative backtest
and Technical regression tests pass 39/39; vectorized future-bar scan,
no-look-ahead, next-open, SL-first, TP/SL level prices, and timeout checks
passed.

### Phase 4 — VN-Index Theme Alignment

- [x] Task 4.1 — Write RED no-theme/as-of/SMA/AND/OR tests.
- [x] Task 4.2 — Verify expected RED failure.
- [x] Task 4.3 — Implement `vnindex_theme.py` with backward/as-of alignment.
- [x] Task 4.4 — Verify GREEN and no-look-ahead review.

Phase gate: PASS — Docker theme tests pass 5/5; cumulative focused suite
passes 44/44; as-of, daily/weekly SMA, no-theme, AND/OR, compile, and
protected-boundary checks passed.

### Phase 5 — Statistical Validation and Certification

- [x] Task 5.1 — Write RED reference math, min-n, block-permutation, and
  deterministic-seed tests.
- [x] Task 5.2 — Verify expected RED failure.
- [x] Task 5.3 — Implement Deflated-Sharpe pre-filter and shortlist-only
  permutation validation.
- [x] Task 5.4 — Verify GREEN and rejected candidates never permute.
- [x] Task 5.5 — Write RED certification/persistence tests for pooled n,
  top-one-per-metric, empty state, two files, overwrite, atomicity, and
  round-trip schema fidelity.
- [x] Task 5.6 — Implement `certify.py` and JSON persistence.
- [x] Task 5.7 — Verify GREEN and review theme-file isolation.

Phase gate: PASS — Phase 5 tests pass 9/9; cumulative backtest and Technical
regression tests pass 53/53 in Docker; compile, atomic overwrite, empty-state,
round-trip, and protected-boundary checks passed.

### Phase 6 — Early Warning Replay and Diff

- [x] Task 6.1 — Write RED replay tests for both theme variants, data-quality
  failure, all current states, timeout resolution, staleness, and diff output.
- [x] Task 6.2 — Verify expected RED failure.
- [x] Task 6.3 — Implement `check_current_situation()` by composing the same
  indicator, score, theme, and trade functions.
- [x] Task 6.4 — Verify GREEN and exact replay-drift parity.

Phase gate: PASS — Phase 6 replay tests pass 7/7; cumulative backtest and
Technical regression tests pass 60/60 in Docker; fresh-data quality rejection,
all four ticker states, timeout parity, both theme modes, persisted-rule
validation, certification age, compile, and protected-boundary checks passed.

### Phase 7 — Offline Job Runner and Status Polling

- [x] Task 7.1 — Write RED job lifecycle tests for immediate submission,
  queued/running/done/failed status, monotonic progress, errors, and worker
  configuration.
- [x] Task 7.2 — Verify expected RED failure.
- [x] Task 7.3 — Implement `job_runner.py` with process workers and atomic JSON
  status sidecars, never blocking Streamlit.
- [x] Task 7.4 — Verify GREEN and process cleanup.

Phase gate: PASS — Phase 7 tests pass 3/3; cumulative backtest and Technical
regression tests pass 63/63 in Docker; queued/running/done/failed lifecycle,
monotonic progress, atomic sidecars, spawned worker pool, worker default,
compile, and protected-boundary checks passed. Superseded for current behavior
by the isolated module-worker repair below.

### Phase 8 — Standalone Backtest Page

- [x] Task 8.1 — Write RED page/AppTest tests for controls, submit-only
  behavior, polling, result sections, empty state, and downloads.
- [x] Task 8.2 — Verify expected RED failure.
- [x] Task 8.3 — Implement `app/pages/backtest_lab.py` and minimal `main.py`
  navigation integration; reuse Plotly and price-output conventions.
- [x] Task 8.4 — Verify GREEN with Docker AppTest/headless smoke and no page
  errors/warnings.

Phase gate: PASS — Phase 8 page/AppTest tests pass 5/5; pipeline composition
and cumulative backtest/Technical regression tests pass 69/69 in Docker;
navigation, submit-only behavior, status polling, three result sections,
empty-state, downloads, compile, and protected-boundary checks passed.

### Phase 9 — Profiling, Verification, and Documentation Handoff

- [x] Task 9.1 — Run the first full 15-year profile and record runtime, RSS,
  workers, combo/window counts, and quality exclusions.
- [x] Task 9.2 — Run full Docker unittest discovery; record exact count.
- [x] Task 9.3 — Run `git diff --check` and protected-boundary diff checks.
- [x] Task 9.4 — Load implementation-review skill and fix all self-critique
  findings.
- [x] Task 9.5 — Update FOCUS, current-status, architecture if needed, and
  the verification report; mark only evidenced phases complete.

Phase gate: PASS WITH DOCUMENTED EXCEPTION — profile evidence, focused 69/69
Docker gate, compile, boundaries, whitespace, and docs pass. Full Docker
discovery is 194/195 with one pre-existing `scripts` package import error
outside this feature.

### Phase 10 — Backtest Page Run Variants and Control Lock

- [x] Task 10.1 — Write RED tests for no-default Horizon radio, one/two exact
  config variants, fixed `AND`, and disabled request controls while busy.
- [x] Task 10.2 — Verify expected RED failures before production changes.
- [x] Task 10.3 — Implement page-only multi-job submission, labelled polling,
  per-variant results, and terminal-state unlock.
- [x] Task 10.4 — Verify GREEN in Docker AppTest and focused Backtest/Technical
  regression gates.
- [x] Task 10.5 — Self-review, profile the two-job request if needed, and
  synchronize context and verification evidence.

Phase gate: PASS — RED/GREEN evidence is recorded; Backtest page tests pass
9/9 and the focused Backtest/Technical Docker gate passes 124/124. Temporary
syntax compilation, protected-boundary, whitespace, and independent review
checks pass. No two-job live profile was needed because this page-only change
reuses the separately profiled existing worker contract.

### Phase 11 — Runtime Configuration Guard and Lab Tab Split

- [x] Task 11.1 — Write and verify RED/GREEN tests for empty explicit database
  URL ports and valid URL preservation.
- [x] Task 11.2 — Persist the existing UI-safe failure status and log one
  job-ID traceback for worker-factory exceptions.
- [x] Task 11.3 — Add native `Collect Signals` and `Validate Signals` tabs;
  retain every existing collection element and automatic polling in Collect.
- [x] Task 11.4 — Run the explicit-module Backtest Docker gate, compilation,
  whitespace, and non-writing live URL preflight.
- [x] Task 11.5 — Diagnose the live `DATABASE_URL` failure as Compose-time
  interpolation before `env_file` injection; user-confirm a successful
  Backtest run after the runtime configuration was corrected.

Phase gate: PASS — 75/75 Backtest Docker tests, compile, whitespace, and a
credential-safe live preflight (`postgresql`, `db`, `5432`) pass. No live job
was submitted during automated verification, so current signal artifacts were
not overwritten. The later user-confirmed live Backtest run completed without
the URL-port failure.

## Archived Backtest Stopping Point

Phase 11 Backtest work is complete and remains documented for reference.
Current task: diagnose empty FPT Backtest signal sets. Task 0 is complete:
both empty FPT artifacts are freshly hashed and the source-conformance Docker
gate passes 9/9. Task 1 is complete: after the live runtime URL was corrected,
its read-only FPT Swing probe selected one all-dimension/60/soft-ADX combo and
measured 3,736 scores, all `50`. Only raw `OBV` matched the seven requested
trend-label inputs; there were zero threshold hits and zero BUY crossings. This
conclusively selects Task 2: repair the score-input contract first. The
URL-port blocker, recovery, and exact output are retained in the triage report.
Task 2 is complete. The approved canonical MA sources are the first existing
pair for each horizon: Swing `5/10` and Mid-term `4/12`. The adapter now adds
seven causal label columns while preserving raw numeric values, and the scorer
uses those labels rather than numeric `OBV`. Its RED gate failed as expected;
the focused adapter/scorer/pipeline/replay/trade gate passes 27/27. The
read-only FPT rerun resolved all seven inputs, reached 60 on 1,358 rows, and
produced 228 BUY crossings. Task 5 is complete: its RED gate exposed entry-bar
historical/replay exits and an accepted three-bar custom hold; the shared
Swing-only `MIN_EXIT_OFFSET_SWING_BARS = 3` boundary now enforces closure from
entry + 3 daily bars, retains stop-first ordering, and rejects a custom hold
below four inclusive bars. Task 6 is complete: its DSR gate passed 5/5; the
read-only full 15-year FPT Swing grid produced 123 qualified no-theme and 43
qualified VN-Index `AND` combos, with no combo below `MIN_N`. The current
engine therefore does not reproduce the old empty artifacts; the detailed
per-combo funnel evidence is in the two dated JSON reports. Overlapping-window
duplicates are material (about 81%) and remain deliberately undeduplicated
pending a separate statistical-design decision. Tasks 3 and 4 remain
unselected. Task 7 is complete: one shared weekly OHLCV adapter now supplies
Mid-term ticker indicators and VN-Index confirmation; Mid-term SL/TP starts at
the next weekly bar and its inclusive timeout is bar 16. The all-weekly Docker
gate passes 42/42 and the preserved Swing lifecycle gate passes 20/20. The
read-only FPT Mid-term baseline transformed 3,736 daily rows into 775 weekly
scores, with 410 scores at or above 60 and 41 BUY crossings. Task 8 is
complete: its exact Backtest Docker suite passes 60/60, including the mocked
diagnostics CLI after its stale mock report was aligned with the existing
summary contract. Host compilation and `git diff --check` pass. Full generic
Docker discovery remains noncanonical because `tests/` is not an importable
package for worker fixtures and `scripts/` is not mounted; this pre-existing
test-layout limitation is recorded separately. The zero-signal investigation
plan is complete. Tasks 3 and 4 remain unselected. Next action: await a new
prioritized WIP item; do not resume the paused comprehensive-unit-test work
without a separate plan. No Task 8 job, signal artifact, status sidecar,
database record, or commit was created.
