# Backtest V4 Schema-5 Final Verification

**Verified:** 2026-09-02  
**Docker Server:** 24.0.6  
**Verdict:** PASS

## Outcome

Tasks 1–11 are implemented and verified. Schema 5 remains the only current
Backtest artifact/job contract. Runtime optimization preserves exact reference
semantics and materially improves both horizons. The controlled research
variants remain `research_only`; none passed every training gate and nothing
was promoted.

## Automated gates

| Gate | Result |
|---|---:|
| Runtime trace/numeric parity | 8/8 pass |
| Full Backtest discovery | 253/253 pass in 5.225s |
| Canonical project discovery | 773/773 pass in 25.715s |
| `compileall backtest_engine pages/backtest_lab.py` | pass |
| Profiler host compile and Docker `--help` | pass |

The expected synthetic job-failure traceback and existing third-party
Streamlit/pandas warnings appeared during tests; no test failed.

## Exact-parity runtime benchmark

Each process loaded ticker/VN-Index sources once, then ran five non-persisting
evaluations at 1,000 permutations. `trade_count` in profiler output is the
completed train-plus-test count of the first preferred Top-3 rulebook. All 16
reference/optimized payload digests matched exactly.

| Ticker | Horizon | Reference p95 (s) | Optimized p95 (s) | Reduction | Digest |
|---|---|---:|---:|---:|---|
| VCB | Swing | 5.091 | 1.182 | 76.8% | `42f95a8ec5834270a7321469d7d2aa20ce8f5dcd13c77339e50f24aa3ecb2490` |
| VCB | Mid-term | 1.322 | 0.437 | 66.9% | `e614f1b9f3ac82bf9f1dcb6681124f6c4accd852606a2329bae26bde65284a10` |
| DHC | Swing | 4.754 | 1.099 | 76.9% | `12fcd351b37aa4d12df8672fc3724ff920314764e5b6a9576697c1e38ec435dd` |
| DHC | Mid-term | 1.420 | 0.464 | 67.3% | `29f723f3ec5c91e1ae849c06c1aa8d19f600ecab86347df8f2ad11ed872e8a0f` |
| DSN | Swing | 4.930 | 1.128 | 77.1% | `9c67516a10a56c2d77baefacac6906ec1013f3678395791472f1b5dea9d60590` |
| DSN | Mid-term | 1.302 | 0.451 | 65.4% | `ad9884bbcba596865a1174ef8c0ffd3a9f388d8cf3079567f82e85ffe7ff022c` |
| ELC | Swing | 4.521 | 1.106 | 75.5% | `fd3ca92737ee19ca85232efe3ec5b711bfeabce7335af8b6fa731c21e402c629` |
| ELC | Mid-term | 1.250 | 0.441 | 64.7% | `aa0627edc40e572788bc49f7b6304687ca9ee21325532a98071ce20d3bcbc31b` |
| BVH | Swing | 4.724 | 1.074 | 77.3% | `6e7451fd2cd0deb6d9aece0d08ee6a99bed1656cf700b3f452775a2c2f29f098` |
| BVH | Mid-term | 1.082 | 0.392 | 63.7% | `05a9260a167b24896e428f32870804c9ce422ed611cccecf07190ec35b7aa5aa` |
| HAP | Swing | 4.560 | 1.120 | 75.4% | `d1d03ebe009a07f6312b6e42c90b0b4c60a3a17f4501acc4b2bb70d1b4966e01` |
| HAP | Mid-term | 1.157 | 0.405 | 65.0% | `0ed078aafb14fef5c9fc887151bc980ffede0e727cab83c67d26f8a89e122477` |
| DRC | Swing | 5.037 | 1.141 | 77.3% | `ebc7eded6333c887a40161032dd7aa25482a46d0e43dcdeba83a372f3e2ab2b9` |
| DRC | Mid-term | 1.239 | 0.435 | 64.9% | `e99caaf08d38168005156cd0742474b5b983ebbe7d3c02fef9847265698daf4e` |
| CSM | Swing | 5.130 | 1.115 | 78.3% | `c385bf43e16ccda7cdd1b82e410c002119360447137ff23b3a230e44b3198008` |
| CSM | Mid-term | 1.159 | 0.409 | 64.7% | `f49e17881609ca95687a18b90d06fffeab36e90189a61758ba3a0711b36af181` |

Reference peak RSS was 253.1–258.0 MB; optimized peak RSS was 254.7–258.4
MB. The small memory increase is accepted against the measured p95 reduction.
No ticker parallelism was enabled.

## Practical database verification

### Recent listing and sparse-history controls

- `LPS`: common-as-of `2026-08-28`, fingerprint
  `7d59ab8fdcfeae4d4056980bb0efffb5b3a2e136574f82eb1ac5bc77db81e9da`,
  100% effective-session coverage, eligible, zero candidates from nine bars.
- `VPL`: common-as-of `2026-08-28`, fingerprint
  `162a268c109441f181063d0a709b2ba932b159de46b29103c7c4ff16bacc3824`,
  ineligible for `coverage_ratio_below_0.95` and
  `max_gap_sessions_exceeds_20`, zero candidates.

### Actual 15-ticker batch service

The production sequential batch path ran in an auto-cleaned container temp
directory: 15/15 items reached `done` in 16.453s, peak RSS 259.52 MB, with one
union-wide common-as-of `2026-08-27` and VN-Index fingerprint
`d2ad83336a947b131196aaf39ffebe717b8cc5a80a4b43b2e1c1a3bffbbba9d3`.
It wrote no product artifact and made no database change.

Gate shorthand below is `A=ADX`, `J=joint trend`, `R=RSI upcross`, `V=volume`.

| Ticker | Source fingerprint | Coverage | Max gap | Evidence / BUY block | Split | Top 3 |
|---|---|---:|---:|---|---|---|
| VCB | `ee736aff7ed3ab46b1358114272d8000e5c1f515b17b6ad44c701f1b3cecf6f5` | 99.92% | 1 | eligible | 10y/5y | J+R; A+J+R; J+R+V |
| DHC | `46affd81c6ab1a2c3859d29e2c96eeb54df17ec5aba863d0e488a1f8e11d818b` | 96.82% | 6 | eligible | 10y/5y | A+R+V; R+V; A+J+R+V |
| DSN | `f91fab860eda8657b10160516d86fa696e817467524c548ca12c72329eff311d` | 98.85% | 2 | eligible | 10y/5y | A+J+R+V; J+R+V; A+R+V |
| ELC | `bc78477c69191763d31778967c45cf521e184fe70d9876c724dcc8f4270b4e79` | 97.06% | 5 | eligible | 10y/5y | A+J+R+V; A+J+V; A+V |
| BVH | `978e506c2a4012230f5cb8ddd1fd58265c0bb79567211b5f6a5997b50f81f3f1` | 99.89% | 1 | eligible | 10y/5y | A+J+R+V; J+R; A+R+V |
| HAP | `b43a5769d99a874b1556e4b646daaaa8d1e88359922b1ba99e0c68735cbc00cb` | 98.29% | 58 | blocked: `max_gap_sessions_exceeds_20` | 10y/5y | A+J+R; J+R+V; A+J+R+V |
| DRC | `998b5962748394eec77fcfc68b84289459843419aa2ecdf64ecf7875cd02535f` | 99.92% | 1 | eligible | 10y/5y | R+V; A+R+V; A+R |
| CSM | `bedaf5db4d4484d3a40b8aa1540d5b2bc00e6ad94b7e9d11873e52109d1f8284` | 99.71% | 1 | eligible | 10y/5y | A+J+R; A+J+R+V; J+R+V |
| FPT | `1fe6760167d447a917d306e1c1b9c8e2e4c362b42e2b9df8e8556b8079f53329` | 99.89% | 1 | blocked: `raw_audit_not_clean` | 10y/5y | A+J+R+V; A+R; J+R+V |
| REE | `a1d77c2d4280f978b83a1820e32f5ef00b0f0cd73d50346e962b151781ca3cf7` | 99.95% | 1 | blocked: `raw_audit_not_clean` | 10y/5y | A; A+J; V |
| HPG | `9995b0dbe56f1092760d9ca73fb1b6784b66b41cf5199ddcf51f953cc4e68564` | 99.89% | 1 | blocked: `raw_audit_not_clean` | 10y/5y | J+R; R+V; A+R+V |
| MSN | `d31b3b2485974db1902ad9906049039458f00b0551ed74b42620fde23e7d5bb6` | 99.95% | 1 | blocked: `raw_audit_not_clean` | 10y/5y | J+R; J+V; A+J+V |
| VPL | `cc74a99d3abb332b5184e500115ea3b77850dac12f2a1efe8ca95e9e9df3266e` | 10.78% | 3331 | blocked: coverage and max gap | 10y/5y | none |
| LPS | `574df3935b1f05b219dcf94bd0b946bdeb0e346e03d858d1d8fb923b897fac36` | 100% | 0 | eligible; empty | 65/35 | none |
| HHC | `744f75fe43794388cfc1b090d675de8b73fdbc0058f17aa846a4bb0747badab6` | 51.26% | 73 | blocked: coverage and max gap | 10y/5y | J+R+V; A+J+R+V; A+R+V |

Every document used `Exploratory — gross`, `in-sample`, and
`historical test — previously observed`. A computed Top 3 never overrides an
evidence block.

## Canonical artifact integrity

The frozen Task 7 canonical files remain unchanged after research and runtime
work:

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

## Boundary and self-review

- No change to protected SQL/CTEs, BIGINT scaling, credential loading,
  Docker files, database schema, or dependencies.
- Database access reuses `get_engine_with_retry`, bound existing loaders, and
  raw connections; the benchmark adds no SQL.
- Product paths do not import controlled research definitions, and current
  display/replay does not parse or migrate legacy artifacts.
- No Git action or product database mutation occurred.
- Logic review: PASS; SQL safety: PASS; performance: PASS.

## Honest limitations and promotion gate

- Metrics remain gross: no fee, tax, or slippage is applied.
- Training is in-sample; test is historical previously observed evidence, not
  live or walk-forward proof. P-values remain informational only.
- The runtime benchmark has five timed repetitions per pair and separates DB
  load time from evaluation time; RSS is process peak, not incremental memory.
- Recent-listing data eligibility does not imply enough observations to emit a
  candidate. Raw-audit and coverage blocks remain independent of computation.
- Ticker execution remains sequential; parallelism needs a separate measured
  decision.
- No controlled variant passed every frozen training gate. The promotion gate
  is closed, and no output may be called statistically certified, profitable,
  or tradable.

