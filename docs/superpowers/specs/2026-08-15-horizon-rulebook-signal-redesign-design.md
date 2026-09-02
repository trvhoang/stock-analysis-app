# Horizon Rulebook Signal Redesign

**Status:** Superseded historical design. The implemented schema-4 replacement
is `2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md`, verified on
2026-08-22. This document is not an active implementation contract.

## Goal

Replace the three compact strategy IDs with one deterministic, causal, long-only
rulebook for each horizon. Each rulebook uses a joint trend-confirmation gate, a momentum event,
and non-directional risk/volume/theme gates. It must produce trustworthy
current artifacts without allowing obsolete V2 certified signals to be read,
replayed, or maintained as current evidence.

## Decisions Locked by the User

- One rulebook per horizon replaces `ma_cross_rsi_obv`,
  `alligator_rsi_obv`, and `consensus_rsi_obv`.
- Volume is an eligibility gate, never a directional score vote.
- VN-Index remains `AND` only. No `OR` variant is generated, persisted, or
  replayed.
- All execution is long-only. A trade is one BUY followed by one SELL; a
  rulebook cannot create another BUY while its prior trade remains open.
- Swing remains daily. Minimum exit offset remains three completed daily
  sessions; timeout is inclusive at 22 daily bars.
- Mid-term remains weekly end-to-end. Exit eligibility begins on the next
  weekly bar; timeout is inclusive at bar 16.
- Certification minimums are independent by ticker, horizon, and theme
  variant: Swing `n >= 22`; Mid-term `n >= 20`.
- A no-theme run has one genuine statistical trial: no-theme only. It uses
  single-trial PSR semantics and records `trial_count: 1`; it never loads or
  evaluates VN-Index data merely to manufacture a second trial. A themed run
  evaluates no-theme and VN-Index `AND`; the themed result uses their exact
  two-treatment DSR family, while its no-theme companion remains a
  single-trial PSR result.
- V2 artifacts receive no reader, fallback, conversion, warning, or maintenance
  path. V3 tests must pass and a user-triggered V3 Backtest must produce at
  least one valid signal set before the user may start the bulk V3 backfill.
  Only its terminal report can precede a separate V2-deletion permission
  request. Existing position snapshots remain historical evidence and must not
  require a V2 artifact lookup.
- Task 0 is a hard gate: it repairs diagnostics, audits the literal roster
  `VCB`, `REE`, `FPT`, `SSI`, `VIC`, `PLX`, `DHG`, and `HPG` from the current
  database, and publishes its report before any rulebook/gate work. The roster
  lives first in one temporary work-item data file, not in a runtime
  "find eight clean tickers" selector. The permanent audit report repeats the
  locked list; only the temporary input is removed after the complete V3
  cutover and separately approved V2 cleanup.

## Rulebooks

### Shared entry contract

An entry is generated only on the closed native-timeframe bar where all
conditions are true:

Before those conditions are evaluated, the implementation creates a named
`required_input` frame for finite MA-pair, Alligator-line, RSI,
current-volume, prior-only-volume, ADX, and ATR values. It derives a named
row-wise `missing_required_input` predicate from null or non-finite cells. If
any required value is absent or invalid, entry is explicitly `False` before
the Boolean AND chain; a neutral label or pandas comparison must never make it
eligible accidentally.

1. `rsi_upcross` is true: current RSI is greater than or equal to the
   configured level and the immediately preceding native bar is below it.
2. `joint_trend_pass` is true: the rulebook-owned MA point is at least `3`
   **and** its Alligator point is at least `3`. This is one shared Boolean
   predicate; V3 does not average, normalize, or threshold the two points for
   entry. Volume has no score points.
3. `volume_gate` is true: current volume is at least the configured multiplier
   times the mean of the **preceding** configured number of native bars. The
   current bar is excluded from its own baseline.
4. `ADX_14` is at or above the configured hard minimum.
5. For the themed treatment only, the native bar is eligible under the
   existing causal VN-Index confirmation. This is an additional `AND`
   condition, not a directional signal.

The BUY fills at the next native-bar open. The current signal bar has no
future price, indicator, or volume data available to it.

Rulebook indicators are fresh pure functions in `backtest_engine/indicators.py`.
They do not import or reuse Analyze helpers. MA is `Up` when fast is strictly
above slow, `Sideways` when equal, and `Down` when below; Alligator uses the
corresponding strict lips/teeth/jaw ordering. V3 owns a strict local map of
`Down = 1`, `Sideways = 2`, and `Up = 3`; it deliberately does not inherit
Analyze's strong/weak labels or its 2% sideways rule. Only `Up` plus `Up`
satisfies `joint_trend_pass`, after the named required-input gate passes.

Mid-term resampling uses `W-FRI`. After resampling, drop its final labelled
bar whenever the current Asia/Ho_Chi_Minh date is on or before that row's
Friday label. This conservative rule still accepts a holiday-short week once
its labelled Friday has passed: the Friday label is the completeness boundary,
not a requirement that Friday itself had a trading session.

The weekly-boundary contract is deliberately date-label based. Its named
holiday-short-week fixture must show that a final `W-FRI` row whose actual last
trade was Wednesday is excluded on Thursday and Friday, then included on
Saturday and the following Monday. There is no Monday-only inclusion block.

The entry rulebook's joint trend gate deliberately requires trend agreement.
The RSI crossing is the time trigger; volume and ADX are gates. This prevents
directional double counting from volume and makes every entry reason
inspectable. The separate monitoring readout is defined below.

### Swing rulebook: `swing_rulebook_v3`

| Concern | Rule |
|---|---|
| Native frame | Daily OHLCV |
| MA trend | EMA 5 / 13 |
| Williams Alligator | SMMA 8 / 5 / 3, causal lags 5 / 3 / 2 |
| Momentum trigger | RSI(9) upward crossing 52 |
| Volume gate | Current volume >= 1.3 × prior 10-session mean volume |
| ADX gate | ADX(14) >= 20 |
| Trend gate | MA point >= 3 **and** Alligator point >= 3 (`Up` + `Up`) |
| Theme | VN-Index close > daily SMA(50), ticker entry AND theme |
| Exit timing | First SL/TP eligible after three completed daily sessions |
| Timeout | Inclusive at entry bar + 21 more daily bars (22 bars total) |
| Certification | `n >= 22`, existing DSR cutoff and permutation alpha |

### Mid-term rulebook: `midterm_rulebook_v3`

| Concern | Rule |
|---|---|
| Native frame | Weekly OHLCV only |
| MA trend | SMA 8 / 21 |
| Williams Alligator | SMMA 13 / 8 / 5, causal lags 8 / 5 / 3 |
| Momentum trigger | RSI(14) upward crossing 70 |
| Volume gate | Current volume >= 1.5 × prior 8-week mean volume |
| ADX gate | ADX(14) >= 25 |
| Trend gate | MA point >= 3 **and** Alligator point >= 3 (`Up` + `Up`) |
| Theme | VN-Index close > weekly SMA(20), ticker entry AND theme |
| Exit timing | First SL/TP eligible from the next completed weekly bar |
| Timeout | Inclusive at entry bar + 15 more weekly bars (16 bars total) |
| Certification | `n >= 20`, existing DSR cutoff and permutation alpha |

ATR keeps its existing raw-BIGINT ATR(14), 1.5× stop-loss, and 2.5×
take-profit calculations. UI-only price scaling remains outside all rulebook
math and SQL.

## Monitoring and Near-miss Match Readout

Validate Signals also calculates a current, as-of-native-bar **monitoring**
readout. It is not an entry score: it never creates or suppresses a historical
BUY, changes certification, changes DSR, or makes a position action eligible.
The literal rulebook gates remain the sole source of a treatment's entry
eligibility. This readout only makes the current contribution of the VN-Index
theme visible alongside near-misses.

The readout compares current numeric values with the saved V3 rulebook's
entry thresholds. RSI, volume, ADX, and theme are capped fractional strengths
in `[0.0, 1.0]`; trend is the joint-confirmation strength below:

| Factor | Strength before its treatment weight |
|---|---|
| RSI | `min(1.0, current_rsi / rulebook.rsi_upcross_level)` |
| Trend | `1.0 if joint_trend_pass else 0.0`, using the exact shared predicate from entry evaluation |
| Volume | `min(1.0, current_volume_ratio / rulebook.volume_multiplier)`, where `current_volume_ratio` remains current volume divided by its prior-only mean |
| ADX | `min(1.0, current_adx_14 / rulebook.adx_minimum)` |
| Theme, themed treatment only | `min(1.0, current_vnindex_close / current_vnindex_theme_sma)` |

The percentage is the weighted sum of these factor strengths. The actual RSI
upcross, trend, volume, ADX, and theme Boolean gates are still calculated and
shown as rulebook facts, but are not substituted into this relative-strength
readout. Missing/non-finite inputs, a negative factor input, or a non-positive
required baseline make the monitoring readout unavailable rather than
fabricating a score.

Because the numeric factors are threshold proximity and trend requires joint
confirmation, a 100% monitoring readout does not itself prove a current BUY:
for example, RSI may be at its level without a new upcross, or VN-Index close
may equal its SMA while the themed `>` gate is false. A failed joint trend
predicate contributes zero rather than a near-miss ratio; this intentionally
removes trend-disagreement granularity so the percentage and its classification
cannot overstate agreement. The Boolean entry contract above remains
authoritative.

| Treatment | RSI / trend / volume / ADX | VN-Index theme |
|---|---:|---:|
| Swing, themed | 15% each | 40% |
| Mid-term, themed | 20% each | 20% |
| Either horizon, no-theme | 25% each | 0% |

For a no-theme treatment, the theme share is zero and is redistributed equally
to the four ticker states. A no-theme result therefore does not lose score,
become theme-ineligible, or depend on a VN-Index condition that its rulebook
does not require.

Classification uses the following mutually exclusive bands. The themed and
no-theme `Closely` floors each sit five points above the largest possible
score when the joint trend contribution is zero:

| Treatment | No Match | Weak | Nearly | Closely |
|---|---:|---:|---:|---:|
| Swing, themed | `<= 50%` | `> 50%` and `< 65%` | `>= 65%` and `< 90%` | `>= 90%` |
| Swing, no-theme | `<= 50%` | `> 50%` and `< 65%` | `>= 65%` and `< 80%` | `>= 80%` |
| Mid-term, themed | `<= 40%` | `> 40%` and `< 60%` | `>= 60%` and `< 85%` | `>= 85%` |
| Mid-term, no-theme | `<= 40%` | `> 40%` and `< 60%` | `>= 60%` and `< 80%` | `>= 80%` |

The readout is stored and displayed as current gate facts, factor strengths,
match percentage, classification, and (for themed treatment only) theme
eligibility. It is not a replacement for the rulebook's Boolean
current-trade signal.

## Certification, PSR, and DSR

Trial count follows the requested treatment, not a hidden companion:

| Requested treatment | Executions | Result method | Trial count |
|---|---|---|---:|
| No-theme | no-theme only | PSR with expected maximum Sharpe of zero | 1 |
| VN-Index `AND` | no-theme and themed | no-theme: PSR; themed: DSR across both treatment Sharpes | 1 / 2 |

Every result still uses its own returns, horizon-specific `min_n`, and
moving-block permutation result. A no-theme PSR is a first-class statistical
result, not a DSR workaround: it applies no multiple-treatment correction.
Its exact score is:

```text
PSR = Phi((SR - 0) * sqrt(n - 1) /
          sqrt(1 - skew * SR + ((kurtosis - 1) / 4) * SR^2))
```

`SR` is the unannualized per-trade Sharpe and kurtosis is Pearson kurtosis.
PSR uses the same `0.95` cutoff and subsequent moving-block permutation step
as DSR; only its benchmark is zero because `trial_count == 1`. Themed DSR
requires both observed treatment Sharpes to be finite. If the no-theme
companion lacks enough returns, themed certification is rejected as
`missing required no-theme DSR companion`; zero is never substituted.
The V3 signal set must therefore serialize `significance_method` (`"psr"` or
`"dsr"`), `significance_score`, and `trial_count`; the UI labels the value by
its method rather than calling every result Deflated Sharpe.

For V3 Backtest, Validate Signals, and View Signals output, the prior fixed
`Deflated Sharpe` label is replaced by `PSR` or `DSR` from the artifact, with
the recorded trial count available in detail. Historical V2 labels remain only
in archived documentation, never in live V3 output.

The only DSR family is the themed result's no-theme/themed pair for the same
ticker and horizon. This never mixes daily and weekly returns. A missing or
invalid VN-Index source makes only the themed execution unavailable; it must
not trigger or block a no-theme PSR execution.

The existing numerical `deflated_sharpe_cutoff` also applies to PSR; only the
multiple-testing adjustment differs. Permutation alpha, per-ticker minimum,
and calibration/holdout diagnostics remain mandatory for their applicable
method.

The existing multi-metric shape is retained only as a compatibility group: a
qualified single rulebook is stored once with registry-ordered certification
metrics `["win_rate", "profit", "sharpe"]`. These are certification views of
one rulebook, not three independently selected strategies.

## Fresh V3 Audit Eligibility

`audit_eligibility` is generated afresh from the raw database history used by
each completed V3 data run; it is never copied from, inferred from, or
"preserved" from a V2 artifact. It records `source: "fresh_v3_raw_history"`,
status, effective date bounds, warnings, and reasons. A terminal `failed`
document created before data is available records
`source: "unavailable"` and `eligible: false` with its failure reason; it never
claims a fresh audit that did not occur.

| Status | Exact DB-only rule | Normal Backtest result |
|---|---|---|
| `clean` | Structurally valid OHLCV, every raw OHLC-ordering mismatch is at most 1%, and no adjacent close move is at least 15%. | Available and audit-eligible; a <=1% ordering mismatch remains a warning. |
| `indeterminate` | Structurally valid data with one or more absolute adjacent-close moves of at least 15%; the DB alone cannot prove adjustment status. | Available, but audit-ineligible. |
| `invalid` | Structural OHLCV validation fails, or a raw OHLC-ordering mismatch exceeds 1%. | Structural failure stops that run. Ordering-only failure uses the derived OHLC envelope for the normal result, but remains audit-ineligible. |

The derived envelope is Backtest-only; it never changes database values. A
requested range longer than the database's retained history uses all available
history, records its effective first/last dates, and is not an audit failure.
For the fixed research roster, `price_audit_clean` means only the table's
`clean` data-quality result. `study_history_sufficient` is a separate Boolean:
it is true only when the ticker has at least five years of daily Swing history
**and** at least eight years of closed `W-FRI` Mid-term history. The audit
report also records the two horizon-specific coverage values so this combined
Boolean never hides which threshold failed. A false value excludes that ticker
from aggregate research, never from normal Backtest UI availability; all
history longer than those floors remains eligible.

The permanent report must state: **"Roster was selected for long observed
histories and blue-chip liquidity; it is not evidence of edge or
generalization across thin or small-cap names."** This is a research-scope
disclaimer, not a substitute for the Task 0 audit.

## V3 Artifacts and V2 Cleanup Gate

V2 stores one current JSON document per ticker/theme. That path cannot hold
both horizon rulebooks without one overwriting the other. V3 uses an
horizon-qualified current path:

```text
app/backtest-result/ticker-signals/<TICKER>/
  <TICKER>_signals_<HORIZON>_<THEME_VARIANT>.json
```

Each V3 document has `schema_version: 3`, `ticker`, `horizon`,
`theme_variant`, `certified_at`, `terminal_state`, `failure_reason`,
`rejection_reason`, `empty`,
`rulebook`, `audit_eligibility`, `requested_date_range`,
`effective_data_range`, `trade_event_range`, and zero or one `signal_set`.
`terminal_state` is exactly `success`, `empty`, or `failed`; readers trust only
these terminal documents. `success` stores one signal set with `empty: false`;
`empty` stores none and a controlled `rejection_reason` when a completed run
does not certify; `failed` stores none plus a nonempty `failure_reason`.
`missing required no-theme DSR companion` is one such `empty` rejection, not a
fourth state or a failure substitute. The three date fields are always present
as `{start: date-or-null, end: date-or-null, reason: string-or-null}` objects:
requested configuration bounds, actual raw-bar bounds used, and first signal
through last exit respectively. An unavailable raw-data run therefore has null
effective/event pairs with their terminal reason; a completed empty run has
actual effective bounds and a null event pair with reason `no trades
generated`. The rulebook serializes
every locked parameter and the entry contract. Completed data runs use fresh
audit metadata; a pre-data terminal backfill failure uses explicit unavailable
audit metadata. Every requested treatment atomically replaces its own exact
horizon/theme path, so stale current evidence cannot survive a new run.

V3-only cutover rules:

- V2 documents are never migrated, converted, catalogued, replayed, warned
  about, or treated as malformed current evidence. Current product readers
  ignore them completely; there is no V2 compatibility or maintenance path.
- Before V2 deletion, a separately user-triggered bulk V3 backfill is the one
  cleanup-time exception to manual Collect Signals. It inventories only legacy
  V2 **filenames** to obtain unique ticker targets; it never reads V2 payloads
  as result data. For every target it runs Swing and Mid-term with theme
  enabled, writing no-theme and themed V3 documents. A failed target/treatment
  atomically receives `terminal_state: "failed", empty: true` with its
  failure reason, rather than retaining V2 as current evidence.
- A shared VN-Index preflight failure does not block the independently valid
  no-theme work: each ticker/horizon still writes its no-theme PSR outcome.
  After its one retry is exhausted, every affected themed ticker/horizon path
  receives an explicit `failed` empty document and the terminal report
  records the shared cause. No theme data is invented or reused as a trial.
- After the full V3 test suite passes, one user-triggered Backtest must prove a
  nonempty, valid V3 signal set for a ticker. That evidence gates the explicit
  bulk backfill. Once its terminal report shows every target/horizon/treatment
  received a V3 document, list exact V2 paths and ask the user for separate
  deletion permission. The backfill report is not permission to delete.
- V2 files remain untouched until this backfill completes and the user
  explicitly approves the exact one-off deletion. Cleanup is outside normal
  product behavior and must not add V2 reader, conversion, or compatibility
  code.
- Existing position histories use their already-frozen signal/risk snapshots
  without resolving any artifact. Pre-V3 positions remain visible for P&L and
  manual edit/close/delete only; they never enter Validate advice, rule replay,
  risk monitoring, saved-set choices, or new-position eligibility.
- Backfill is a separate admin CLI, never a Streamlit control. It calls the
  same named V3 single-run service for ticker × horizon × treatment. Each file
  is tmp-and-rename atomic, while
  `app/backtest-result/v3-backfill/<run-id>.json` tracks all four terminal
  paths per ticker. The cleanup gate reads that completed tracker. The existing
  Group move journal remains untouched.
- New signal-backed snapshots carry `schema_version: 3` and use
  `validate_v3_position_snapshot()`. `schema_version: 2` and absent-version
  V2-shaped snapshots route only to the retained read-only legacy validator;
  an unknown explicit version is rejected rather than silently falling back.
  Neither legacy branch participates in new writes or V3 artifact reading.

### V2 retirement boundary

V3 is the only valid Backtest result and signal source. The following boundary
is mandatory, including when V2 files remain on disk pending cleanup:

| Surface | V3 treatment | V2 treatment |
|---|---|---|
| Signal artifact | Read/write the horizon-qualified schema-3 document and calculate fresh `audit_eligibility` from a completed run's raw DB data. A pre-data failure is explicitly audit-unavailable; a normal non-audit-eligible result remains available with its warning. | Ignore completely; no parse, validation, invalid-row display, migration, conversion, or fallback. |
| Collect job | Serialize and accept only `backtest_single_v3` and `backtest_batch_v3`; single is internally batch-of-one, while logs preserve its honest request name. Render/download only schema-3 terminal output paths. | Historical status sidecars remain untouched, but missing/V2 requests are rejected and an old V2 output path is never rendered or downloaded. |
| Catalog, Group `N/A`, and saved-set options | Discover only readable nonempty V3 documents across both horizons. | Do not contribute tickers, rows, warnings, dropdown options, or Group membership decisions. |
| Validate Signals | Replay V3 rulebook data only. One ticker may render Swing and Mid-term independently under each theme treatment. | No replay, match level, BUY/SELL advice, or current-monitor state. |
| Current Positions | New signal-backed positions use one V3 `(ticker, horizon, theme, rulebook, metric-group)` identity and frozen V3 snapshot. | Existing frozen records are trade history only: P&L and explicit manual management remain available, but they are not signal evidence. |
| UI and downloads | Render rulebook/gate values, horizon-qualified labels, and V3 JSON/Markdown only; label statistical significance as PSR or DSR with its stored trial count. | No visible V2 result, strategy, schema, or download content; rename internal V2 session keys during the UI cutover. |
| Result-root service | Create/read V3 and Group directories without an artifact migration side effect. The one-off post-proof backfill may scan legacy filenames as a target manifest only. | Remove the V2 root-migration journal, recovery, and migration tests; leave physical V2 files untouched until the backfill report and explicit deletion approval. |
| Historical documentation | Keep completed records as historical context only. | Never treat archived V2 documentation as runtime behavior or active implementation guidance. |

## Explicit Non-goals

- No full parameter grid or post-hoc tuning.
- No short entries, automatic order execution, fees, tax, or position sizing.
- No change to DB price storage, raw-BIGINT calculations, SQL delta CTEs,
  Docker, credentials, or dependencies.
- No runtime V2 conversion, discovery, or compatibility support. The only
  exception is the explicit, post-proof bulk-backfill filename inventory used
  solely to construct its one-off target manifest.

## Acceptance Evidence

Before any V3 artifact is considered current:

1. Unit fixtures prove each EMA/SMA, RSI crossing, causal Alligator, prior-only
   volume baseline, ADX gate, and shared joint-trend predicate. They prove
   `Up + Sideways` and `Down + Up` both fail entry and contribute zero
   monitoring trend strength, while `Up + Up` passes the trend condition.
2. A named holiday-short-week `W-FRI` boundary fixture proves that a Wednesday
   final actual trade is excluded on Thursday and Friday, included on Saturday
   and the following Monday, and never subject to a Monday-only block.
3. Daily and weekly no-look-ahead tests mutate future rows and prove prior
   rule values and entries do not change.
4. Golden trade traces prove one-open-trade behavior, next-open entry,
   minimum-hold exits, conservative same-bar SL/TP handling, and inclusive
   timeouts for each horizon.
5. Statistical tests prove no-theme uses PSR with `trial_count: 1` and never
   loads a theme companion; themed certification alone uses its exact
   no-theme/AND DSR pair with `trial_count: 2`.
6. Monitoring fixtures prove all four treatment bands and that, with every
   non-trend factor at 100% and joint trend false, the four ceiling scores
   (`85`, `75`, `80`, `75`) classify below `Closely`.
7. Persistence, catalog, replay, group discovery, and position tests prove V3
   horizon isolation, V2 is ignored by all current readers, V3 empty markers,
   fresh `audit_eligibility` status/bounds, and frozen-position continuity without
   artifact lookup or V2-derived advice.
8. A read-only multi-ticker report uses a coverage-qualified universe, reports
   calibration and holdout separately, and never promotes VCB as the tuning
   target. It measures the joint-trend gate's candidate/trade counts and `n`
   independently per ticker/horizon before any certification conclusion;
   these measurements cannot silently retune a locked rule, band, or minimum.
   Histories too short for the study remain valid UI input but are excluded
   from research conclusions.
9. After all V3 tests pass, a user manually runs Collect Signals and produces
   at least one nonempty valid V3 document. Only then may the user trigger the
   bulk V3 backfill. Its terminal report proves every legacy target has both
   horizons and both treatments represented by V3 results or explicit empty
   failure markers before exact V2 paths are presented for deletion approval.
10. A valid or malformed V2 file and a retained V2 job-status output path prove
   that current catalog, Validate, Current Positions signal choices, and result
   rendering use neither as a result or source.
