# Horizon Rulebook V3 — Gate and Statistics Update Design

**Date:** 2026-08-21  
**Status:** Superseded  
**Scope:** Amend the V3 entry-gate and certification policy only.

> Superseded on 2026-08-22 by
> [2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md](2026-08-22-horizon-v3-exploratory-multi-rulebook-design.md).
> Do not implement this binary-certification schema-3 design.

## Purpose and supersession

This amendment supersedes the entry-gate and PSR/DSR sections of
[`2026-08-15-horizon-rulebook-signal-redesign-design.md`](2026-08-15-horizon-rulebook-signal-redesign-design.md).
All other V3 decisions remain unchanged: completed-bar handling, weekly
completion clock, ATR exits, same-bar execution, raw-price storage, deterministic
permutation settings, artifact persistence, and UI treatment identity.

The separate read-only research optimizer remains out of scope and unchanged.

## Locked policy

### 1. Historical entry gates

Historical entry eligibility is an AND of only the gates listed below. A missing
required input makes the result false.

| Horizon | Required gates | Not entry gates |
|---|---|---|
| Swing | `joint_trend_pass` AND `rulebook_rsi_upcross` | volume, ADX |
| Midterm | `joint_trend_pass` AND `rulebook_volume_gate` | RSI, ADX |

`joint_trend_pass` remains the existing joint Alligator alignment plus MA-cross
trend predicate. When VN-Index mode is enabled, `vnindex_theme_pass` is an
additional AND gate for both horizons.

RSI, volume, and ADX columns continue to be calculated where current monitoring,
saved criteria, and replay readouts require them. Gates excluded above are
monitoring-only; they must not affect historical entry eligibility.

The retained ADX criterion thresholds are recalibrated to `ADX(14) >= 17` for
Swing and `ADX(14) >= 20` for Midterm. These values affect the calculated
criterion and monitoring/readout only; ADX remains excluded from historical
entry eligibility.

### 2. Execution modes

| UI choice | Evaluations | Certification statistics |
|---|---|---|
| VN-Index checkbox clear (default) | No-theme only. Do not load VN-Index. | Per-treatment `min_n` plus permutation p-value only. |
| VN-Index checkbox selected | No-theme and VN-Index-AND together. | Exact two-treatment DSR family, then each treatment's permutation p-value. |

No-theme default execution intentionally has no DSR: DSR requires a family of at
least two observed Sharpe ratios, while this mode evaluates one treatment only.

### 3. Horizon certification thresholds

| Horizon | `min_n` | DSR cutoff when VN-Index mode is selected |
|---|---:|---:|
| Swing | 5 completed exits | 0.90 |
| Midterm | 5 completed exits | 0.85 |

The existing permutation settings are unchanged: block length `20`, resamples
`1000`, seed `42`, two-sided p-value, and `p <= 0.05` acceptance.

### 4. PSR removal

V3 must not calculate, display, persist, or use probabilistic Sharpe ratio (PSR)
for certification. V3 uses only:

- `permutation` in default no-theme runs;
- `dsr` in paired no-theme plus VN-Index-AND runs.

The optimizer may retain its research-only PSR utility and output because it is a
separate experiment, not V3 certification.

## Statistical contract

### Default no-theme run

The single no-theme candidate passes when all conditions hold:

1. completed exits meet the horizon `min_n`;
2. the deterministic permutation test returns `p <= 0.05`.

Its persisted result is:

```text
significance_method = "permutation"
significance_score  = null
trial_count         = 0
```

`trial_count = 0` means no Sharpe-ratio family was used. The p-value remains the
only reported statistical score for this mode; it must not be copied into
`significance_score` under a misleading name.

### Paired VN-Index run

The pipeline first produces no-theme and VN-Index-AND returns. It forms one DSR
trial family from exactly their two unrounded sample Sharpe ratios, in treatment
order:

```text
(Sharpe(no-theme), Sharpe(VN-Index-AND))
```

Each treatment calculates its own DSR from its own return series and that shared
two-Sharpe family. It passes when all conditions hold:

1. its own completed exits meet the horizon `min_n`;
2. both treatments provide finite Sharpe ratios from at least two returns, so the
   two-Sharpe DSR family is defined;
3. the shared-family DSR meets that horizon's cutoff;
4. its own deterministic permutation p-value is `<= 0.05`.

Both persisted rows use:

```text
significance_method = "dsr"
significance_score  = <that treatment's DSR, unrounded>
trial_count         = 2
```

The DSR scores can differ because each treatment has its own return moments.
Qualification is treatment-specific because DSR, `min_n`, and permutation
p-value are evaluated per treatment.

### Paired-source failure

When the checkbox is selected, the caller explicitly requested paired DSR
validation. The pipeline must not silently fall back to no-theme permutation-only
certification if VN-Index data or the themed result is unavailable.

- The themed treatment records its concrete source/execution failure.
- The no-theme treatment records terminal `empty` with rejection
  `missing required themed DSR companion`.
- Neither treatment is certified.

This keeps checkbox-on results comparable and prevents mixed statistical methods
inside one requested run.

## Data-model and function changes

### Immutable rulebook policy

`RulebookSpec` owns the horizon-specific policy:

- historical entry gate names;
- DSR cutoff;
- existing indicator and exit parameters.

Request-level `deflated_sharpe_cutoff` overrides must be removed from V3 runtime
configuration. Callers cannot weaken or strengthen a locked rulebook through a
batch request.

### Signal composition

`rulebook_entry_signal` must select its required boolean columns from the active
`RulebookSpec`, AND them with non-null inputs, and optionally AND
`vnindex_theme_pass`. It must not hard-code all four ticker gates.

### Validation and artifacts

`ValidatedRulebookTreatment` must represent exactly these combinations:

| Method | `significance_score` | `trial_count` |
|---|---|---:|
| `permutation` | `null` | 0 |
| `dsr` | finite DSR | 2 |

Validation success requires a passing permutation result and, only for `dsr`, a
passing DSR score. PSR is not a valid V3 method.

Certification serialization, read-model validation, API/UI labels, and tests must
accept the nullable score for `permutation` and show it as **Permutation only**.
DSR rows continue to show their DSR score and two-trial basis.

## Existing V3 artifacts

Schema-3 validation already requires an artifact's embedded rulebook to equal the
active canonical horizon rulebook. Therefore artifacts written before this
amendment are intentionally no longer current evidence: their old `min_n`, ADX,
gate, or statistical-policy values fail canonical validation. Do not migrate,
rewrite, or fall back to them. A new Collect run replaces each requested
horizon/treatment path with an amended V3 terminal document.

## Acceptance tests

1. Swing entry is true only for joint-trend plus RSI, and ignores volume/ADX.
2. Midterm entry is true only for joint-trend plus volume, and ignores RSI/ADX.
3. Missing one required gate always rejects entry.
4. Default no-theme pipeline execution does not request VN-Index and can certify
   only through `min_n` plus permutation.
5. Checkbox-on execution evaluates both treatment variants and uses the exact
   two-Sharpe DSR family for each row.
6. Swing DSR `0.90` qualifies at equality; midterm DSR `0.85` qualifies at
   equality. Values below the relevant cutoff reject.
7. A missing/invalid themed companion in checkbox-on mode blocks no-theme
   certification with the stated rejection reason.
8. V3 artifact and UI output contain no PSR method, score, label, or override.
9. A pre-amendment V3 artifact is unavailable rather than silently treated as
   current evidence.
10. Existing raw-price scaling, completed-bar, ATR exit, same-bar, and
   deterministic-permutation regression tests still pass.

## Non-goals

- Do not change indicator calculations or raw criterion persistence merely because
  a criterion is no longer an entry gate.
- Do not alter `common_queries.py`, price scaling, database schema, Docker files,
  or the research optimizer.
- Do not introduce dependencies or change theme behavior beyond the paired DSR
  rule above.
