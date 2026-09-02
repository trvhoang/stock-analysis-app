# Backtest Schema 5 Baseline Verification

**Exploratory — gross, in-sample / historical test — previously observed.**

## Outcome

The non-writing schema-5 diagnostic completed for the frozen eight-ticker
sample, both horizons, both treatments, all 15 lexical non-empty gate subsets,
and exactly 1,000 permutations. The shared latest completed bar was
`2026-08-28`.

- Backtest gate before database work: **224/224 passed**.
- Diagnostic scope: `VCB,DHC,DSN,ELC,BVH,HAP,DRC,CSM`.
- Requested history: `2011-09-02` through `2026-09-02`.
- Runtime: **330.7544649820047 seconds** of measured evaluations;
  **336 seconds** wall time.
- Maximum traced peak memory: **24,326,881 bytes**.
- Write boundary: **no database, job, or canonical artifact writes**.
- Evidence: seven tickers eligible; `HAP` display-only/ineligible because its
  maximum source gap is 58 sessions, above the limit of 20.

This run establishes corrected baseline behavior. It does not establish that
schema 5 is better, profitable, tradable, or statistically certified.

## Frozen source evidence

All rows used the same VN-Index fingerprint:
`8a1f66049c8a1b69e4263681bae940a751458a10a3c0377a732814e110fb6a53`.

| Ticker | Ticker fingerprint | Coverage | Max gap | Evidence |
|---|---|---:|---:|---|
| VCB | `3f856e62656752d5d4d0a64a0466d779418f0c5c061361d834ee087258b67848` | 0.9991976464295266 | 1 | eligible |
| DHC | `1d6b2f08800c3923e140701160135bc926624eebadf7e6e00a8201cd2d276592` | 0.9681733083712223 | 6 | eligible |
| DSN | `32e5f4b2f3e37ef1a787c6daff760437ec8ff4419af455b457e19739d7d30d01` | 0.9884995988232148 | 2 | eligible |
| ELC | `25d41a0c17d414c1c82afa7503c799b8dee1b250ba7f8ec1f3cd4067100e4515` | 0.9705803690826424 | 5 | eligible |
| BVH | `6c89dbeacfa0cd84b46b52956ea7adc0983fd7cb5a38f04d03c524c5de362777` | 0.9989301952393688 | 1 | eligible |
| HAP | `3fb9444a47e3465ae4d5811d19bd77ec409ad462f68334ca5fa35f09a217e62d` | 0.9828831238299011 | 58 | ineligible: `max_gap_sessions_exceeds_20` |
| DRC | `4526adb1bad64b24d76ff6f8128888ecb4e40e902d10622b7fb9a99d0bc5d1cf` | 0.9991976464295266 | 1 | eligible |
| CSM | `fd69c27851ff1abf6bcfcde2d4ee340834c1172a58ea66515a2cc5bb8fb4a48b` | 0.9970580369082642 | 1 | eligible |

The normal split was daily training `2011-09-05..2021-09-01`, daily test
`2021-09-06..2026-08-28`, weekly training `2011-09-09..2021-08-27`, and
weekly test `2021-09-03..2026-08-28`. HAP's source gap changes its last
training bars to `2021-06-11` and first weekly test bar to `2021-09-10`;
the evidence gate therefore blocks its BUY eligibility.

## Primitive density

Values are causal gate passes over native frame rows. They are diagnostic
density, not trade counts.

| Ticker | Horizon | Rows | ADX | Joint trend | RSI upcross | Volume |
|---|---|---:|---:|---:|---:|---:|
| VCB | Swing | 3738 | 3058 (81.8%) | 1549 (41.4%) | 262 (7.0%) | 1131 (30.3%) |
| VCB | Mid-term | 774 | 430 (55.6%) | 407 (52.6%) | 27 (3.5%) | 186 (24.0%) |
| DHC | Swing | 3622 | 2811 (77.6%) | 1586 (43.8%) | 256 (7.1%) | 1152 (31.8%) |
| DHC | Mid-term | 773 | 606 (78.4%) | 419 (54.2%) | 30 (3.9%) | 211 (27.3%) |
| DSN | Swing | 3698 | 2823 (76.3%) | 1600 (43.3%) | 313 (8.5%) | 1183 (32.0%) |
| DSN | Mid-term | 774 | 623 (80.5%) | 410 (53.0%) | 38 (4.9%) | 199 (25.7%) |
| ELC | Swing | 3631 | 2695 (74.2%) | 1251 (34.5%) | 256 (7.1%) | 1141 (31.4%) |
| ELC | Mid-term | 773 | 513 (66.4%) | 308 (39.8%) | 33 (4.3%) | 220 (28.5%) |
| BVH | Swing | 3737 | 2971 (79.5%) | 1381 (37.0%) | 249 (6.7%) | 1090 (29.2%) |
| BVH | Mid-term | 774 | 395 (51.0%) | 253 (32.7%) | 20 (2.6%) | 183 (23.6%) |
| HAP | Swing | 3677 | 2777 (75.5%) | 1261 (34.3%) | 235 (6.4%) | 1148 (31.2%) |
| HAP | Mid-term | 762 | 559 (73.4%) | 285 (37.4%) | 23 (3.0%) | 203 (26.6%) |
| DRC | Swing | 3738 | 3008 (80.5%) | 1492 (39.9%) | 241 (6.4%) | 1150 (30.8%) |
| DRC | Mid-term | 774 | 466 (60.2%) | 316 (40.8%) | 21 (2.7%) | 208 (26.9%) |
| CSM | Swing | 3730 | 2626 (70.4%) | 1267 (34.0%) | 280 (7.5%) | 1166 (31.3%) |
| CSM | Mid-term | 774 | 462 (59.7%) | 275 (35.5%) | 24 (3.1%) | 215 (27.8%) |

## Candidate funnel and corrected Top 3

`A`, `J`, `R`, and `V` below mean ADX, joint trend, RSI upcross, and volume.
Candidate count is after the no-theme training `n >= 5` gate. Top 3 is exact
training rank order after DSR treatment selection.

| Ticker | Horizon | Candidates | Top 3 gate subsets | Runtime (s) | Peak bytes |
|---|---|---:|---|---:|---:|
| VCB | Swing | 15 | `J+R`; `A+J+R`; `J+R+V` | 36.210 | 24,326,881 |
| VCB | Mid-term | 13 | `J+R+V`; `J+R`; `A+J+R` | 8.514 | 2,806,011 |
| DHC | Swing | 15 | `A+R+V`; `R+V`; `A+J+R+V` | 33.387 | 10,298,951 |
| DHC | Mid-term | 15 | `R`; `A+R`; `V` | 9.413 | 2,998,460 |
| DSN | Swing | 15 | `A+J+R+V`; `J+R+V`; `A+R+V` | 33.026 | 10,017,020 |
| DSN | Mid-term | 15 | `A+V`; `V`; `A+R` | 9.052 | 2,833,785 |
| ELC | Swing | 15 | `A+J+R+V`; `A+J+V`; `A+V` | 31.094 | 9,528,938 |
| ELC | Mid-term | 15 | `A+J+R+V`; `J+R+V`; `A+R` | 8.563 | 2,626,620 |
| BVH | Swing | 15 | `A+J+R+V`; `J+R`; `A+R+V` | 32.336 | 10,380,022 |
| BVH | Mid-term | 12 | `V`; `A+V`; `A+J+V` | 6.881 | 2,444,342 |
| HAP | Swing | 15 | `A+J+R`; `J+R+V`; `A+J+R+V` | 31.797 | 10,014,815 |
| HAP | Mid-term | 15 | `A+J+R+V`; `J+R+V`; `A+V` | 7.645 | 2,741,643 |
| DRC | Swing | 15 | `R+V`; `A+R+V`; `A+R` | 34.810 | 11,048,171 |
| DRC | Mid-term | 15 | `R+V`; `R`; `J+R+V` | 8.213 | 2,564,374 |
| CSM | Swing | 15 | `A+J+R`; `A+J+R+V`; `J+R+V` | 32.145 | 10,102,501 |
| CSM | Mid-term | 15 | `A+R`; `A+R+V`; `A+J+R` | 7.668 | 2,673,603 |

HAP candidates are shown only to inspect the computation. They must not be
persisted as BUY-eligible evidence while the ticker remains audit-ineligible.

## Correctness-change comparison

The comparator reconstructs documented schema-4 EWM indicator, timeout, and
stop-fill behavior. Existing schema-4 artifacts were invalidated
content-blind and were not parsed or migrated. `Shared metrics` counts
same-rulebook treatment/partition cells available on both sides. Profit ranges
are schema-5 minus reconstructed schema-4 gross percentage points.

| Ticker | Horizon | Shared metrics | Changed n cells (range) | Changed profit cells (range) | Preferred treatment changes | Top-3 changed | Signal dates + / - |
|---|---|---:|---|---|---:|---|---:|
| VCB | Swing | 60 | 30 (0..2) | 60 (-69.97953157893102..-0.1517547106551156) | 1 | no | 35 / 4 |
| VCB | Mid-term | 52 | 30 (-3..2) | 43 (-15.378879384562126..38.74812909069644) | 0 | yes | 90 / 101 |
| DHC | Swing | 60 | 21 (0..2) | 52 (-86.38319038157226..0.0) | 0 | no | 30 / 0 |
| DHC | Mid-term | 60 | 29 (-3..2) | 52 (-58.89560558974415..25.854961541723043) | 4 | yes | 128 / 101 |
| DSN | Swing | 60 | 16 (-1..2) | 60 (-60.56622792859393..-0.000000000000001776) | 2 | no | 18 / 11 |
| DSN | Mid-term | 60 | 26 (-4..1) | 49 (-33.15332783805247..16.157910548489582) | 0 | yes | 117 / 135 |
| ELC | Swing | 60 | 24 (-1..2) | 59 (-104.17819835616471..0.000000000000014211) | 0 | no | 28 / 6 |
| ELC | Mid-term | 60 | 34 (-6..2) | 60 (-63.3328254777181..31.324304574217436) | 3 | yes | 138 / 123 |
| BVH | Swing | 60 | 20 (-3..2) | 56 (-133.0440367399755..4.1535607029643185) | 3 | yes | 24 / 12 |
| BVH | Mid-term | 48 | 19 (-2..2) | 46 (-41.945535623047796..36.26389197962615) | 0 | yes | 78 / 78 |
| HAP | Swing | 60 | 2 (-2..0) | 54 (-96.58823235461077..0.000000000000056843) | 0 | no | 4 / 7 |
| HAP | Mid-term | 60 | 38 (-1..7) | 60 (-63.07317646036729..30.173607608001298) | 1 | yes | 172 / 102 |
| DRC | Swing | 60 | 21 (-1..2) | 57 (-82.93413508350389..0.0) | 1 | yes | 60 / 36 |
| DRC | Mid-term | 56 | 34 (-2..4) | 44 (-16.90198883270119..37.840039582705074) | 2 | yes | 119 / 70 |
| CSM | Swing | 60 | 10 (0..2) | 60 (-73.20033195139042..-0.000000000000035527) | 1 | no | 12 / 1 |
| CSM | Mid-term | 60 | 26 (-2..4) | 52 (-39.68828405698973..46.57117158470214) | 6 | no | 91 / 75 |

The tiny near-zero floating differences shown above are numerical noise, not
economic changes. Mid-term schema-4 themed values are an invalid quality
comparator because the old W-SUN theme alignment is not equivalent to the
schema-5 completed W-FRI treatment.

## Exit and gap-fill evidence

Counts aggregate the 15 rulebooks, both treatments, and both partitions; they
are diagnostic executions, not a portfolio. Gap delta is the aggregate gross
return change from filling a stop gap at the next open rather than at the
unreachable stop price.

| Ticker | Horizon | Schema-5 exits | Reconstructed exits | Gap-below-stop exits | Aggregate gap delta (pp) |
|---|---|---:|---:|---:|---:|
| VCB | Swing | 4008 | 3977 | 512 | -809.5659776476631 |
| VCB | Mid-term | 839 | 850 | 29 | -67.89068783956496 |
| DHC | Swing | 3661 | 3631 | 543 | -1245.6105674376752 |
| DHC | Mid-term | 978 | 951 | 76 | -161.68594261078448 |
| DSN | Swing | 3471 | 3464 | 506 | -594.7991045025472 |
| DSN | Mid-term | 910 | 928 | 10 | -32.32496581002816 |
| ELC | Swing | 3334 | 3312 | 547 | -1473.6957927475655 |
| ELC | Mid-term | 820 | 805 | 34 | -58.915395953791176 |
| BVH | Swing | 3644 | 3632 | 491 | -931.1153668913811 |
| BVH | Mid-term | 709 | 709 | 59 | -128.93954305534692 |
| HAP | Swing | 3476 | 3479 | 529 | -1592.536430994325 |
| HAP | Mid-term | 859 | 789 | 48 | -294.0642580007212 |
| DRC | Swing | 3999 | 3975 | 612 | -1095.1287731388732 |
| DRC | Mid-term | 819 | 770 | 28 | -38.871441409884646 |
| CSM | Swing | 3506 | 3495 | 572 | -1199.4274882044976 |
| CSM | Mid-term | 817 | 801 | 46 | -262.1259105310486 |

## Gate decision

The diagnostic is suitable as the frozen pre-experiment baseline. Canonical
regeneration completed through the ordinary Collect Signals worker path:

- Swing job `87bc66b70ae346ae92e6cbfd87c06cbc`: schema-5 `done`, 8/8 tickers,
  one attempt each.
- Mid-term job `4377533cc10b41f8aaff12f824022b22`: schema-5 `done`, 8/8 tickers,
  one attempt each.
- Production-reader audit: 16/16 artifacts valid, schema set `{5}`, contract
  set `{backtest_schema5_v1}`, terminal-state set `{success}`, common-as-of set
  `{2026-08-28}`, and zero readable schema-4 documents in this scope.

| Ticker | Swing SHA-256 | Mid-term SHA-256 |
|---|---|---|
| VCB | `0ec3971533b28b9a7ab634e65b9b4210edd1abb02f33b15a25a961537d3e040f` | `5064e64dac8e51a5b92463041aebd0e79af0b4ef2f70c63285b1a697aa6a11f5` |
| DHC | `40031e4a75bea1ee94e73ee54b79a56e4c8a6e8eababcc435b627467c99a5b7f` | `bde813f6598653ed08d62ea52c55414834a1663c58940d566bcd3d74f2eb92f8` |
| DSN | `97605616dc2b827dd7bd0540b6286a9523aa7ddfbfd094170ed483d05435faf1` | `79feaa745b4c5547accefadb296c152a174560247f12b31876d3578f5f7a6dc0` |
| ELC | `b417144db29c61061076379b2f935a9979f1e5bd27d421ac1235d939c8b5f475` | `2208ab2dc3c01833335520c8a821982ff4287daab4ee3367a08ef68bcfe3fc79` |
| BVH | `69fe6641579f302a5ae0bcac46aa512ebf9da14f960dd59a7b4e8f48da2a86e0` | `7cd2a0618ae0a176b59383ae652b8d54db4a93a0697f51c0aadc64baabc81df7` |
| HAP | `07dafffee6500a7c197a8d294d0bb198d87c7b6eb5473e1988e380ad3eea9455` | `bbb91bf64429de5393f72e251768b285c8b7045735dda21cd115d81e5d053065` |
| DRC | `8e1893d15f7eadbe24fecfb35d0155168897245a9912f19068f53948a0752f3d` | `0c960efcc77f076fddf3b4740db6b432e8663bf7c379d6ca34f72e030b735585` |
| CSM | `cf331a6a2bcc31b7bd48118285e6d132908c8cbeda685a564cf2360032774e9f` | `ff1d63830dc60afae5a742fdce03c928159c79cb47b618dee3661ec090907a5c` |

HAP remains schema-5 display-only/ineligible and cannot become BUY eligible
unless corrected source history passes a fresh audit.
