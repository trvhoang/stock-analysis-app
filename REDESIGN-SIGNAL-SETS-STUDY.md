# Indicator Design: Swing vs Mid-term Signal Sets

**Status:** Standalone design study. Every number below is a candidate to
test, not a locked config. Ticker-agnostic — applies to any equity, any
dataset. No dependency on any other document, prior investigation, or
existing implementation.

**Two sets, opposite personality:**

| | Swing | Mid-term |
|---|---|---|
| Candle | Daily (trading session) | Weekly |
| Min hold | 3 sessions | 5 sessions (= 1 weekly bar) |
| Max hold | 22 sessions (~1 month) | 16 weeks (~4 months) |
| Character | Sensitive, catch early | Lag OK, wait for confirmed trend |
| Market-index theme | Highly impacted | Loosely dependent |

---

## 1. Design Principles

1. **Reuse purpose, not numbers.** Same period count means different real
   time span on daily vs weekly bars. Every indicator gets its own config
   per set — never copy swing's number onto midterm assuming it still means
   the same thing.
2. **Every parameter here is a decision to approve, not a default.** This
   is a first-pass design study — nothing below should reach production
   without explicit sign-off and a passing test.
3. **Don't add grid dimensions casually.** Each new sweepable parameter
   multiplies the combo search space and makes any statistical
   significance gate harder to clear. Prefer a single locked value per set
   over a sweep range unless there's a specific reason to search.
4. **Overlap between trend indicators is not automatically a bug.** Two
   indicators voting on the same trend direction is noise risk on a fast,
   sensitive set, and a feature on a slow, confirmation-seeking set. Judge
   the same structural overlap differently per set — see §5.

---

## 2. Swing Set — Sensitive, Early-Catch

| Indicator | Setting | Rationale |
|---|---|---|
| RSI | Period 9, signal = midline cross (>50 bullish) | Shorter period + midline cross both catch momentum shift earlier than a default longer period/overbought(70) read. Two separate early-catch levers stacked — test each in isolation before combining (see §7). |
| MA cross | EMA, fast pair (e.g. 5/13 — candidate, needs testing) | EMA weights recent bars heavier than SMA — same period count, faster reaction, no new grid dimension. Preferred over shortening SMA periods. |
| William Alligator | Shorter SMMA set (e.g. 8/5/3, causal lag 5/3/2 — candidate) | A slower default set is midterm-appropriate, too slow for swing's ~1-month max hold. Needs its own regression test since shrinking periods is a genuine new parameter, not a formula swap. |
| Volume | Shorter avg window (e.g. 10-session), lower surge multiplier (e.g. 1.3x) | Catches smaller upticks early. Note: volume has no bull/bear direction of its own — it's a magnitude confirm, not a standalone directional vote. Keep it out of any directional group score. |
| Trend-strength gate | Hard eligibility filter (e.g. ADX ≥ 20) | Quick trend confirm, consistent with sensitivity goal — a single pass/fail gate rather than a soft-damping mode keeps the formula simple and testable. |
| Market-index confirmation | Strict combine (AND), daily long-window moving-average confirmation | "Highly impacted" = ticker signal must agree with broader market direction — AND is the strict combine, matches this requirement directly. |
| Min/max hold | 3 / 22 sessions | Deliberately short horizon to match the sensitivity goal — needs explicit approval before implementation, see §6. |

---

## 3. Mid-term Set — Lagging, Confirmed-Trend

| Indicator | Setting | Rationale |
|---|---|---|
| RSI | Longer period (e.g. 14), signal = overbought/oversold (70/30) | Midline cross would whipsaw a multi-week hold in and out. Classic extremes wait for a stronger, more confirmed momentum read — matches "lag OK" requirement. |
| MA cross | SMA or EMA, longer pair (e.g. 10/30 weekly — candidate) | 1 weekly bar already carries several sessions of smoothing. Don't stack extra reactivity (EMA) on top without also lengthening the period — test both SMA and EMA at the longer pair before choosing. |
| William Alligator | Standard/default periods (e.g. 13/8/5, causal lag 8/5/3) | Don't shrink on weekly bars — a longer window is already a meaningful trend read at weekly resolution. Shrinking here works against the "wait for clear trend" goal. |
| Volume | Longer avg window, higher surge multiplier | Look for sustained volume trend, not single-week spikes. Same magnitude-only caveat as swing — not a directional vote. |
| Trend-strength gate | Consider a stricter threshold than swing (e.g. ADX ≥ 25 — candidate) | Weekly trend-strength reads are naturally smoother than daily; a multi-month hold justifies demanding stronger confirmation before entry. |
| Market-index confirmation | Permissive combine (OR), weekly long-window moving-average confirmation | "Loosely dependent" = ticker signal alone can qualify — OR is the permissive combine, matches this requirement directly. |
| Min/max hold | 5 sessions (1 weekly bar) / 16 weeks | 5-session min-hold naturally resolves to "can't exit the same weekly bar it entered on" — the correct behavior at this candle size, and internally consistent without needing a separate daily-vs-weekly conversion. |

---

## 4. Group Score Dimension Mapping — Open Decision

Both sets use 4 indicators, but the group-score dimension count isn't
automatically 4:

- If the two trend indicators (Alligator + MA-cross) feed a single "trend"
  bucket, dimensions become: trend (2 indicators averaged), momentum
  (RSI), volume (Volume) — **3 buckets**, weights must sum to 1 across 3.
- If they stay separate votes, dimensions stay **4 buckets**, but trend
  gets double representation vs momentum/volume's single vote each — an
  intentional trend-weighted design, needs to be a stated choice, not a
  side effect.

**Weight renormalization is easy to get subtly wrong whenever the active
dimension count changes at runtime (e.g. a gate excluding one dimension on
some rows but not others). Resolve the bucket mapping explicitly, and
prove with a test fixture that weights sum to 1 for every dimension-count
scenario the design allows, before implementation.**

---

## 5. Trend-Indicator Overlap — Per-Set Treatment

| Set | Overlap is... | Action |
|---|---|---|
| Swing | Risk — two trend votes could drown out RSI/Volume's early-catch signal | Consider down-weighting one of the two in the group score, or keep them in separate dimensions with lower combined weight than momentum |
| Mid-term | Feature — two trend confirmations before a long hold is desirable | Fine to let both carry full weight, or even merge into one stronger "trend" bucket per §4 |

---

## 6. Design Decisions Requiring Explicit Sign-off

None of the values below are defaults — each is a first-pass proposal that
needs approval and a passing test before implementation:

- Swing max hold set to ~1 month (22 sessions) — a deliberately short
  horizon matched to the sensitivity goal.
- Mid-term gets its own minimum hold (5 sessions / 1 weekly bar),
  expressed in session terms but resolving cleanly to one bar at weekly
  resolution.
- Trend-strength gate threshold diverges between sets (looser for swing,
  stricter for mid-term) — the two sets no longer share one constant.
- Group-score dimension count/weighting per §4 — must be resolved and
  tested, not left to fall out of implementation order.

---

## 7. Testing Guardrails — Required Before Any Production Change

Per set, write regression tests covering:

1. **Indicator computation fixture test** — known input series → known
   output values, for each changed parameter (RSI period, Alligator
   periods, MA-cross type/periods, Volume window). Isolate one changed
   parameter per test.
2. **No-look-ahead test** — mutate rows after a given date, assert
   scores/labels through that date are unchanged, for both candle
   frequencies (daily and weekly).
3. **Group-score weight-sum test** — assert weights sum to 1 for whichever
   dimension mapping §4 resolves to, per set, including any row-level
   gating scenario that changes the active dimension count.
4. **Hold-time enforcement test** — assert no exit fires before min-hold,
   and no position exceeds max-hold, per set's own values from §2/§3.
5. **Market-index combine-mode test** — assert the strict (AND) combine
   correctly rejects a ticker-only signal, and the permissive (OR) combine
   correctly accepts one.
6. **Isolation test per §2 sensitivity change** — before combining RSI
   midline-cross + shorter period + EMA + shorter Alligator, test each
   swap independently: does crossing timing actually move earlier and
   still clear the statistical significance gate, or does it just add
   noise that gets rejected downstream? Only keep changes that pass both.

---

## 8. Explicitly Out of Scope Here

- Any specific ticker, dataset, or existing production defect. This is a
  general design study, applicable once adapted to a concrete
  implementation.
- Full-grid combo sweep across these new parameters. Lock single candidate
  values per §2/§3 first, test in isolation, sweep only if a specific
  parameter shows promise and needs range-tuning.
- Statistical significance gating itself (minimum sample size, risk-
  adjusted return thresholds, and any randomization-based validation).
  Those stay whatever they currently are regardless of indicator changes
  proposed here.