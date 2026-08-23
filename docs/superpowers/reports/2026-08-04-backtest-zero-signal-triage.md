# Backtest Zero-Signal Triage

## VCB Mid-term VN-Index `AND` 15-Year Fresh Capture — 2026-08-09

The current signal-file contract is overwrite-only per ticker/theme. A later
VCB five-year themed run had replaced the former 15-year payload, so the exact
15-year themed request was submitted again before any further five-year run.
The rerun used the existing configuration unchanged: `2011-08-09` through
`2026-08-09`, `midterm`, VN-Index `AND`, long-only, 16 inclusive weekly bars,
`min_n: 30`, DSR cutoff `0.95`, and 1,000 seeded moving-block permutations.

| Job ID | State / progress | Output path | SHA-256 |
|---|---|---|---|
| `70b21d806b1c47ec8657793bede51297` | `done` / `1.0`; `error_text: null` | `ticker-signals/VCB/VCB_signals_background-theme.json` | `48b82c4b86425b21fa52c9f1a725c646a65e16275334d01f79a75afcfff01d2d` |

Captured verbatim immediately after terminal completion:

```json
{
  "certified_at": "2026-08-09T18:21:51.055867+07:00",
  "empty": true,
  "schema_version": 1,
  "signal_sets": {
    "profit": null,
    "sharpe": null,
    "win_rate": null
  },
  "theme_variant": "background-theme",
  "ticker": "VCB"
}
```

This proves the fresh 15-year themed result is an empty certification payload,
not a job failure, missing artifact, or partial write. The VCB no-theme
artifact and no five-year request were not changed by this capture.

### VCB-Adapted Task 1 Read-Only Mid-term AND Funnel Probe — 2026-08-10

The Task 1 baseline was adapted to the reproduced VCB incident without
submitting a job or writing any signal/status artifact. It read VCB and
VN-Index from `2011-08-09` through `2026-08-09`, built one shared weekly VCB
frame, selected the all-dimension / `60` / soft-ADX / Mid-term / VN-Index
`AND` combination, and applied the production theme alignment path.

```text
raw_rows: 3737
weekly_rows: 774
weekly_frame_dates: 2011-08-21 through 2026-08-09
required_label_columns:
  MA: backtest_signal_ma
  MA cross: backtest_signal_ma_cross
  RSI: backtest_signal_rsi
  Stochastic: backtest_signal_stochastic
  OBV: backtest_signal_obv
  ATR: backtest_signal_atr
  Bollinger: backtest_signal_bollinger
resolved_labels: all seven
score: count=774, mean=51.7906169250646, std=20.1113521841326,
       min=18.75, p25=31.25, p50=53.125, p75=71.875, max=87.5, NaN=0
score value counts:
  18.75:20, 20.3125:1, 21.875:37, 23.4375:7, 25.0:46, 26.5625:7,
  28.125:52, 29.6875:5, 31.25:26, 32.8125:8, 34.375:14, 35.9375:5,
  37.5:17, 39.0625:8, 40.625:19, 42.1875:11, 43.75:18, 45.3125:18,
  46.875:16, 48.4375:17, 50.0:16, 51.5625:10, 53.125:25, 54.6875:13,
  56.25:8, 57.8125:8, 59.375:29, 60.9375:10, 62.5:44, 64.0625:6,
  65.625:27, 67.1875:5, 68.75:23, 71.875:53, 75.0:50, 78.125:43,
  81.25:24, 84.375:22, 87.5:6
at_or_above_60: 313
ticker_crossing_count: 50
VN-Index daily rows: 3738
weekly aligned theme true / false: 494 / 280
themed_crossing_count: 37
themed_crossing_dates:
  2012-02-12, 2013-06-23, 2013-10-13, 2014-02-23, 2014-06-29,
  2014-07-20, 2014-08-24, 2014-10-05, 2015-04-19, 2015-10-18,
  2016-04-24, 2016-07-17, 2017-01-29, 2017-02-12, 2017-06-18,
  2017-10-08, 2018-09-16, 2019-07-07, 2019-09-29, 2020-05-24,
  2020-09-27, 2020-11-22, 2021-06-27, 2021-11-28, 2021-12-12,
  2022-01-02, 2022-09-04, 2023-05-21, 2023-09-03, 2024-01-21,
  2024-03-03, 2024-09-29, 2024-10-20, 2025-03-09, 2025-07-13,
  2026-01-11, 2026-05-24
```

**Route selected:** The current score-input contract is resolved, score is not
flat, and the production AND path still yields 37 crossings. The score and
theme stages cannot explain the empty artifact. The existing lifecycle work is
already complete; proceed to the VCB-adapted Task 6 production trade and
statistical-certification funnel measurement. Do not change indicators, price
data, or gate values from this evidence.

## Reported Outcome

A 15-year FPT Swing Backtest returned no certified signal sets for both the
no-theme and VN-Index `AND` variants.

## Read-Only Artifact Evidence

| Variant | Job ID | State | Progress | Artifact result |
|---|---|---:|---:|---|
| No theme | `24bac55bd995444eaf4dc6a9118f5758` | done | 1.0 | `empty: true`; all three metric sets are `null` |
| VN-Index AND | `6086db3928344074b0046a7a4234c9ef` | done | 1.0 | `empty: true`; all three metric sets are `null` |

Both jobs cover 2011-08-04 through 2026-08-04 and have `min_n: 30`. Their
status documents contain no error and each names its expected signal-artifact
path. The failure is therefore inside the signal-to-certification funnel, not
the UI, worker, database-URL, or artifact-persistence path. Because the
no-theme variant is also empty, VN-Index `AND` filtering cannot be the sole
cause.

### Task 0 fresh capture — 2026-08-06

| Variant | Job ID | State / progress | Output path | `empty` | Metric keys | SHA-256 |
|---|---|---|---|---:|---|---|
| No theme | `24bac55bd995444eaf4dc6a9118f5758` | `done` / `1.0` | `ticker-signals/FPT/FPT_signals_no-background-theme.json` | `true` | `profit`, `sharpe`, `win_rate` — all `null` | `53846c9c3a67b823ddde94018b86b8970297bf0f32e8826f81f5e1bfd3bfdd0b` |
| VN-Index `AND` | `6086db3928344074b0046a7a4234c9ef` | `done` / `1.0` | `ticker-signals/FPT/FPT_signals_background-theme.json` | `true` | `profit`, `sharpe`, `win_rate` — all `null` | `847dd27d5197e061fba092dc850f2989fbb856a5a0ee1b655f42ac85eefbabac` |

Both status documents had `error_text: null`; the captured paths existed at
read time. These hashes freeze the Task 0 comparison baseline. No job,
database record, status sidecar, or signal artifact was written by this capture.

## Source-Level Trace

```text
pipeline.run_backtest_pipeline()
  -> indicators.build_indicator_frame()
     returns numeric columns: RSI_14, %K, %D, SMA_*, cross_*, ATR_14,
     OBV, BBM_20_2/BBU_20_2/BBL_20_2/BBB_20_2/BBP_20_2, ADX_14
  -> signal_combos.score_combo()
     searches for: MA, MA cross, RSI, Stochastic, OBV, ATR, Bollinger
  -> rolling_window.detect_buy_crossings()
  -> validation.validate_candidates()
  -> certify.certify_top_sets()
```

The two contracts do not match. `OBV` is the only overlapping column name, but
it contains a numeric cumulative-volume value rather than one of the trend
labels used by `score_indicator_value()`. Unmapped numeric values receive the
neutral fallback score `2`. All other dimensions are absent, so the source contract
predicts an effective `(2 / 4) * 100 = 50`, below the minimum threshold of 60.
This is a strong source-level explanation, not yet a live FPT measurement.
The required Step 0 probe must record the actual score distribution before any
repair is chosen.

## Task 0 Source-Conformance Gate — 2026-08-06

`docker exec stock_app python -m unittest tests.test_backtest_signal_combos
tests.test_backtest_validation -v` passed **9/9** in 0.031 seconds.

- Hard ADX uses the per-row `ADX_14 < 20` mask, subtracts only the
  `trend_direction` weighted contribution and its remaining denominator, and
  retains the fixed `/ 4 * 100` score scale. This is characterization evidence,
  not a formula-repair decision.
- `calculate_deflated_sharpe()` uses unannualized returns and a manual Pearson
  kurtosis calculation. The passing validation suite also confirms the
  permutation path is not reached for a Deflated-Sharpe rejection.
- At Task 0, the ticker Mid-term indicator and execution paths did not
  resample, while VN-Index confirmation aggregated weekly OHLCV. This was the
  former daily-ticker versus weekly-VN-Index mismatch. Task 7 now replaces it
  with one shared all-weekly contract.

## Task 1 Blocker — 2026-08-06

The mandatory read-only FPT Swing/60/soft-ADX probe stopped before opening its
first database connection. `backtest_engine.pipeline._database_url()` raised
`RuntimeError: DATABASE_URL has an invalid port`; its underlying URL parse
failed on an empty explicit port (`ValueError: invalid literal for int() with
base 10: ''`).

A credential-safe runtime inspection found a present PostgreSQL URL with host
`db` but an unset port, while `POSTGRES_HOST` is `db` and `POSTGRES_PORT` is
`5432`. This is the known Compose-time interpolation failure: the container's
preconstructed `DATABASE_URL` contains `@db:` before `env_file` injects the
runtime `POSTGRES_PORT`. `_database_url()` correctly refuses to bypass that
malformed explicit URL.

No FPT history query, score calculation, crossing detection, worker job,
database write, status-sidecar write, or signal-artifact write occurred.
Therefore there is no valid Step 0 measurement and no Task 2–6 route can be
selected.

Required external recovery (recreates only the application container using
root `.env` interpolation):

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --force-recreate app
```

After that recreation, repeat the unchanged Task 1 read-only probe and record
its score distribution before selecting exactly one next route. Do not build a
manual URL or otherwise bypass `_database_url()`.

## Task 1 Result — 2026-08-06

After the live runtime configuration was corrected, the required read-only
probe selected exactly one no-theme Swing combination with all four voting
dimensions, threshold `60`, and soft ADX. Its exact diagnostic output was:

```text
{'preflight': {'scheme': 'postgresql', 'host': 'db', 'port': 5432}}
{'raw_rows': 3736, 'indicator_rows': 3736, 'required_inputs': ('MA', 'MA cross', 'RSI', 'Stochastic', 'OBV', 'ATR', 'Bollinger'), 'input_matches': ['OBV'], 'describe': {'count': 3736.0, 'mean': 50.0, 'std': 0.0, 'min': 50.0, '25%': 50.0, '50%': 50.0, '75%': 50.0, 'max': 50.0}, 'value_counts': {50.0: 3736}, 'nan_count': 0, 'at_or_above_60': 0, 'crossing_count': 0}
```

The command also emitted existing non-fatal Streamlit `SyntaxWarning` messages
and pandas' DBAPI-connectable warning after producing the successful result.
Neither changes the score frame or the recorded metrics.

**Selected route: Task 2 — repair the score-input contract first.** All
required trend-label inputs except `OBV` are absent, and the entire score
series is the neutral fallback value `50`, below the BUY threshold. No worker,
job, artifact, status sidecar, or database write was created by this probe.

## Task 2 Result — 2026-08-06

The approved canonical MA sources are the first existing pair for each horizon:
Swing `5/10` and Mid-term `4/12`. `build_indicator_frame()` now creates seven
causal `backtest_signal_*` label columns without replacing raw numeric
indicators. `score_combo()` prefers those mapped columns and retains bare-name
fallback only for existing synthetic fixtures.

The RED gate failed exactly as intended: two tests proved the missing label
contract, and one proved that numeric `OBV` still scored as the neutral `50`.
The post-repair focused gate passed **27/27**, including canonical-label,
no-look-ahead, pipeline-composition, and early-warning replay fixtures.

The required post-repair FPT probe completed without writing any job, artifact,
status sidecar, or database record. Compared with Task 1's flat 50 baseline:

| Metric | Before Task 2 | After Task 2 |
|---|---:|---:|
| Raw / indicator rows | 3,736 / 3,736 | 3,736 / 3,736 |
| Resolved score inputs | raw `OBV` only | all 7 canonical labels |
| Score range | 50.0–50.0 | 12.5–90.625 |
| Mean score | 50.0 | 51.0916 |
| Scores at or above 60 | 0 | 1,358 |
| BUY crossings | 0 | 228 |
| Score-frame probe time | not separately recorded | 9.365 seconds |

The score series has no `NaN` values. It now varies across the expected
point-scale values; the original bare-column intersection remains `OBV` only
because the scorer resolves the other six requested indicator names through
`BACKTEST_SIGNAL_COLUMNS`.

**Selected route: Task 5 — apply the Swing-only three-daily-bar minimum-hold
policy.** Task 3 is not selected because scores reach the threshold; Task 4 is
not selected because BUY crossings exist. No score formula, threshold,
validation, SQL, BIGINT, or artifact-persistence rule changed.

## Task 5 Result — 2026-08-06

The Task 5 RED gate failed as predicted: both the historical runner and replay
could close a Swing position on its entry bar, and a custom three-bar Swing hold
was accepted. The repair adds `MIN_EXIT_OFFSET_SWING_BARS = 3` and applies one
shared exit-eligibility slice to both paths. An entry at daily row `i` can now
use SL or TP only from row `i + 3`; the existing stop-first result remains in
force when both levels hit on that eligible row.

The inclusive hold window remains unchanged. Therefore, a custom Swing hold
must be at least four bars, so its timeout can occur no earlier than row
`i + 3`; the default 15-bar hold is unchanged. Mid-term execution is untouched
and remains reserved for its all-weekly Task 7 repair.

The focused Docker gate passed 17/17:
`test_backtest_trade_execution`, `test_backtest_rolling_window`, and
`test_backtest_early_warning`. This task made no SQL, BIGINT, score, crossing,
job, artifact, status-sidecar, database, or persistence change. The next
selected task is Task 6: read-only downstream trade and certification
measurement.

## Task 6 Result — 2026-08-06

The DSR conformance gate passed 5/5 before the live measurements. It confirms
the existing path uses unannualized per-trade returns, manual Pearson
non-excess kurtosis, variance from the observed trial-Sharpe set, and runs the
permutation gate only after Deflated Sharpe passes. The new read-only collector
uses the production loader, indicator adapter, score/crossing path,
`run_combo_window()`, and `validate_candidates()`; it never invokes the
pipeline, certification, persistence, or job runner.

The collector reports every combo in two JSON files:

- `2026-08-06-fpt-swing-no-theme-funnel.json`: 270 combos × 176 windows in
  1,373.494 seconds. All combos exceeded `MIN_N`; 123 qualified, and 147 were
  rejected by Deflated Sharpe. It measured 296,801 ticker/theme crossings,
  260,647 raw completed events, and 49,893 unique `(combo_key, signal_date)`
  events.
- `2026-08-06-fpt-swing-vnindex-and-funnel.json`: 270 combos × 176 windows in
  1,242.933 seconds. VN-Index `AND` reduced theme-confirmed crossings to
  229,145 (from 296,801 ticker crossings), but every combo still exceeded
  `MIN_N`; 43 qualified, and 227 were rejected by Deflated Sharpe. It measured
  201,766 raw completed events and 38,376 unique events.

Neither report has a first insufficient funnel stage. Therefore, under the
current repaired Swing engine, FPT's historical empty artifacts are not
reproduced by score coverage, BUY crossings, execution, `MIN_N`, or the
approved certification gates. Those old artifacts predate the Task 2
score-input repair; Task 6 intentionally did not overwrite them.

Overlapping windows produce material duplicates: 210,754/260,647 (80.86%)
no-theme and 163,390/201,766 (80.98%) `AND`. The counts and rates are now
recorded, but validation still receives the approved raw event sequence. A
separate statistical-design decision is required before any deduplication or
`MIN_N` change. The same full-grid sequential execution requires about
20–23 minutes per 270-combo variant; optimization is outside this diagnostic
task and needs separate approval.

## Task 7 Result — 2026-08-07

Task 7 replaces the prior mixed-clock Mid-term path with one shared
`to_weekly_ohlcv()` adapter: `open:first`, `high:max`, `low:min`,
`close:last`, and `volume:sum`, dropping weeks without required OHLC values.
It copies and sorts its input, so daily history is unchanged. Both
`build_indicator_frame(..., "midterm")` and VN-Index confirmation now use this
adapter before calculating indicators, ATR, crossings, or execution inputs;
Swing remains daily.

`MAX_HOLD_MIDTERM_BARS = 16` makes the timeout meaning explicit: entry is bar
1 and timeout closes at bar 16. Mid-term SL/TP becomes eligible at weekly bar
2 only, while Swing retains its independent entry-plus-three-daily-bar rule.
Both historical and replay execution call the same horizon-specific boundary.

The RED gate produced the expected missing-adapter and old-entry-week-exit
failures. The final all-weekly Docker conformance gate passed **42/42**,
including weekly aggregation, daily-input immutability, Mid-term-only
pre-indicator resampling, shared ticker/VN-Index dates, next-week SL/TP,
inclusive 16-bar timeout, invalid sub-two-bar holds, future daily mutations
leaving completed-week labels and scores unchanged, and a future Mid-term week
leaving its bounded prior exit unchanged.

The required Task 5 Swing regression gate also passed **20/20**, retaining the
daily entry-plus-three exit dates and stop-first behavior.

The bounded FPT baseline is a read-only 2011-08-04 through 2026-08-04 probe
using the exact all-dimension, threshold-60, soft-ADX, no-theme Mid-term combo:

| Metric | Result |
|---|---:|
| Raw daily rows / weekly score rows | 3,736 / 775 |
| Resolved score inputs | 7 canonical labels |
| Score min / Q1 / median / Q3 / max | 12.5 / 39.0625 / 62.5 / 75.0 / 87.5 |
| Mean score / NaN count | 57.3347 / 0 |
| Scores at or above 60 | 410 |
| BUY crossings | 41 |

The direct bare-column intersection remains raw `OBV` only by design; the
other six score inputs resolve through `BACKTEST_SIGNAL_COLUMNS`. This is not a
new score-input defect. The probe called only the history loader, indicator
adapter, scorer, and crossing detector; it submitted no job and made no
artifact, status-sidecar, database, SQL, BIGINT, or persistence change.

## Task 8 Result — 2026-08-07

The final explicit Backtest Docker suite passed **60/60** across contracts,
indicators, signal combinations, execution, rolling windows, pipeline,
early-warning replay, validation, VN-Index confirmation, and diagnostics.
Docker normally omits the top-level `scripts/` directory, so the diagnostics
CLI test would otherwise skip. Its existing script was copied temporarily into
the running container only for this verification and removed immediately after.

That enabled test exposed a stale fixture, not a production defect: the mock
report supplied only `ticker` and `combos`, while the CLI correctly prints the
always-present diagnostics summary fields `theme_mode`, `combo_count`,
`window_count`, and `elapsed_seconds`. The fixture now supplies the complete
report contract; the focused mocked CLI regression and the full 60-test gate
pass. No production source changed.

`python -m compileall -q app/backtest_engine
scripts/debug_backtest_zero_signal.py` exited successfully. `git diff --check`
also exited successfully. The pre-existing dirty worktree still includes
protected `app/main.py` and `app/pages/data_preparation.py` changes; Task 8 did
not edit either file. No Backtest job, signal artifact, status sidecar,
database record, SQL, BIGINT rule, Docker configuration, credential,
dependency, or commit changed.

Full generic Docker discovery is not a valid final gate in this repository.
`unittest discover -s tests` imports fixtures as top-level modules, which makes
the isolated worker unable to import its serialized `tests.*` factory; it also
cannot import the unmounted `scripts` package. Adding `-t .` instead fails
before execution because `tests/` is not a classic importable package. This
pre-existing test-layout limitation remains separate from the explicit
Backtest evidence and requires a separately approved test-topology change.

The incident is therefore resolved and measured: the initial FPT Swing probe
had 3,736 flat `50` scores with zero BUY crossings; the repaired score-label
contract yielded 1,358 threshold hits and 228 BUY crossings. The downstream
15-year Swing funnel has 123 qualified no-theme and 43 qualified VN-Index
`AND` combinations, with every combination above `MIN_N`; overlapping-window
duplicates remain approximately 81% and intentionally are not deduplicated.
The separately repaired Mid-term probe has 775 weekly scores, 410 threshold
hits, and 41 BUY crossings. Tasks 3 and 4 remain unselected because the
evidence never selected their hypotheses.

## Hypothesis Status

| Hypothesis from `DEBUG_BACKTEST.md` | Status | Evidence |
|---|---|---|
| Missing score-label contract | First live pre-check | Static inspection predicts only numeric `OBV` reaches the scorer. Step 0 records actual input-column matches and score metrics. |
| Volatility semantics dilute bullish scores | Do not change yet | ATR/Bollinger meanings differ, but their trend columns currently do not reach the scorer. Evaluate this only after the score-label contract is live-proven. |
| Hard ADX fails to renormalize | Unlikely for soft baseline; verify separately | The Step 0 probe uses soft ADX. Source code calculates a data-dependent hard-mode denominator, but a post-contract test must prove it. |
| NaN warm-up suppresses crossings | Open | Step 0 must measure score NaNs, first valid index, threshold reaches, and crossings before changing crossing semantics. |
| Crossings exist but certification rejects them | Not yet measurable | Do not inspect significance gates until Step 0 proves crossings exist. |

## Confidence

**8.5 / 10 — high enough to prioritize, not yet conclusive.** The
input-column mismatch is visible in the exact producer and consumer source
contracts and is consistent with both successful jobs persisting empty results.
The Step 0 read-only FPT probe is required to measure the real score
distribution and select exactly one repair route.

## Non-Changes

No Backtest job was submitted, no ticker artifact was overwritten, no database
write occurred, and no SQL, BIGINT, Docker, credential, dependency, or commit
change was made during this triage.
