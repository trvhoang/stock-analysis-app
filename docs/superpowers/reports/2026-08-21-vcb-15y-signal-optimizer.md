# VCB 15-Year Signal Optimizer Research

> **in-sample research only.** This is not V3 certification, out-of-sample validation, trading advice, or a production signal.

## Scope and fixed method

- As of: 2026-08-21
- VCB source bounds: 2011-08-22 to 2026-08-21
- Raw rows: VCB 3742; VNINDEX 3743
- VCB audit: clean; errors: ()
- Candidate grid: 15 non-empty four-gate subsets × no-theme and VNIndex AND = 30 per horizon.
- Native V3 execution unchanged: next native open, ATR exits, stop-first, one flat-to-flat trade sequence, and horizon-owned timeout.
- Eligibility: n >= 5, PSR >= 0.95, DSR >= 0.95, moving-block permutation p <= 0.05.
- Permutation: 1,000 draws, seed 42, block size 20.
- DSR family: every same-horizon n >= 5 finite-Sharpe candidate before PSR, DSR, or permutation filtering.
- Ranking: exact unrounded win rate %, profit_pct as sum of per-trade returns, and unannualized Sharpe.
- No V3 artifact, job, DB row, configuration, or persistence path changed.

## Swing

Candidates: 30. Rejection funnel: dsr=16, psr=14

### Exact winners

| Won metric(s) | Candidate | n | Win rate % | Profit % | Sharpe |
|---|---|---:|---:|---:|---:|
| no eligible candidate | - | - | - | - |

### Candidate audit

| Candidate | State | Reason | n | Win rate % | Profit % | Sharpe | PSR | DSR | Permutation p | DSR trials |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| swing:no-background-theme:rsi_upcross | ineligible | dsr | 142 | 50.0 | 152.498 | 0.22735695743847495 | 0.997244722498349 | 0.8122053082608407 | - | 30 |
| swing:background-theme:rsi_upcross | ineligible | dsr | 93 | 53.76344086021505 | 104.4726 | 0.24541955355573042 | 0.9915609385989527 | 0.8112204603261904 | - | 30 |
| swing:no-background-theme:joint_trend | ineligible | dsr | 230 | 46.95652173913044 | 157.29749999999999 | 0.1421171422340196 | 0.9857990241837253 | 0.42277852366399304 | - | 30 |
| swing:background-theme:joint_trend | ineligible | dsr | 190 | 46.8421052631579 | 108.1034 | 0.12151607598286884 | 0.9549794894188621 | 0.32148302757227243 | - | 30 |
| swing:no-background-theme:volume | ineligible | dsr | 291 | 47.07903780068728 | 235.3684 | 0.16417294860109768 | 0.998034517631294 | 0.5657181290997216 | - | 30 |
| swing:background-theme:volume | ineligible | dsr | 198 | 47.474747474747474 | 118.8597 | 0.13363270361257262 | 0.9717524056134015 | 0.381578434927211 | - | 30 |
| swing:no-background-theme:adx | ineligible | dsr | 331 | 46.52567975830816 | 249.3109 | 0.14857784649254901 | 0.9972419124892222 | 0.45411527505346855 | - | 30 |
| swing:background-theme:adx | ineligible | dsr | 218 | 46.788990825688074 | 119.4014 | 0.11696469588161612 | 0.9603795046908896 | 0.2853901262235728 | - | 30 |
| swing:no-background-theme:rsi_upcross+joint_trend | ineligible | dsr | 54 | 53.70370370370371 | 85.4932 | 0.3361406662505029 | 0.993033309796135 | 0.9075835534879673 | - | 30 |
| swing:background-theme:rsi_upcross+joint_trend | ineligible | dsr | 42 | 52.38095238095239 | 55.4798 | 0.2886658538664518 | 0.9689569994721476 | 0.8064207648230977 | - | 30 |
| swing:no-background-theme:rsi_upcross+volume | ineligible | psr | 70 | 42.857142857142854 | 16.4133 | 0.05549759356807726 | 0.6797907496958471 | - | - | 30 |
| swing:background-theme:rsi_upcross+volume | ineligible | psr | 44 | 47.72727272727273 | 22.9982 | 0.12367028150228275 | 0.7957847972501964 | - | - | 30 |
| swing:no-background-theme:rsi_upcross+adx | ineligible | dsr | 102 | 48.03921568627451 | 99.0151 | 0.1978088743735463 | 0.9803324385705053 | 0.6730258029376682 | - | 30 |
| swing:background-theme:rsi_upcross+adx | ineligible | psr | 65 | 49.23076923076923 | 50.3721 | 0.1651457310202906 | 0.9131853188571986 | - | - | 30 |
| swing:no-background-theme:joint_trend+volume | ineligible | dsr | 157 | 47.77070063694268 | 145.5853 | 0.19298259405760257 | 0.9930164535756657 | 0.6868203829663776 | - | 30 |
| swing:background-theme:joint_trend+volume | ineligible | dsr | 131 | 46.56488549618321 | 89.8335 | 0.14531895092069802 | 0.9540746631586351 | 0.45645334321568465 | - | 30 |
| swing:no-background-theme:joint_trend+adx | ineligible | dsr | 190 | 45.78947368421053 | 130.4367 | 0.1381880230242947 | 0.9738662530996827 | 0.4080459060150561 | - | 30 |
| swing:background-theme:joint_trend+adx | ineligible | psr | 163 | 42.331288343558285 | 44.5138 | 0.056694226786438984 | 0.7673241180111303 | - | - | 30 |
| swing:no-background-theme:volume+adx | ineligible | dsr | 232 | 48.275862068965516 | 224.2392 | 0.1892484387499489 | 0.9984835053892174 | 0.705491551318038 | - | 30 |
| swing:background-theme:volume+adx | ineligible | psr | 150 | 47.333333333333336 | 92.4086 | 0.13120676481233456 | 0.9481219713269774 | - | - | 30 |
| swing:no-background-theme:rsi_upcross+joint_trend+volume | ineligible | psr | 14 | 50.0 | 17.8268 | 0.24249176983405676 | 0.8164200752833104 | - | - | 30 |
| swing:background-theme:rsi_upcross+joint_trend+volume | ineligible | psr | 11 | 45.45454545454545 | 5.555 | 0.09743044103014793 | 0.623909281512359 | - | - | 30 |
| swing:no-background-theme:rsi_upcross+joint_trend+adx | ineligible | psr | 35 | 48.57142857142857 | 46.8541 | 0.27019804759649924 | 0.9471368008845733 | - | - | 30 |
| swing:background-theme:rsi_upcross+joint_trend+adx | ineligible | psr | 26 | 46.15384615384615 | 28.9712 | 0.2253689274124468 | 0.8785581370218596 | - | - | 30 |
| swing:no-background-theme:rsi_upcross+volume+adx | ineligible | psr | 45 | 44.44444444444444 | 16.6168 | 0.08410973763460208 | 0.7152305286011534 | - | - | 30 |
| swing:background-theme:rsi_upcross+volume+adx | ineligible | psr | 25 | 48.0 | 6.888600000000001 | 0.06478764540338487 | 0.6262099921054173 | - | - | 30 |
| swing:no-background-theme:joint_trend+volume+adx | ineligible | dsr | 124 | 49.193548387096776 | 133.2156 | 0.2144108353602814 | 0.9920485123472371 | 0.7487973410813371 | - | 30 |
| swing:background-theme:joint_trend+volume+adx | ineligible | psr | 106 | 46.22641509433962 | 81.5911 | 0.15629580813523358 | 0.9484094049324525 | - | - | 30 |
| swing:no-background-theme:rsi_upcross+joint_trend+volume+adx | ineligible | psr | 8 | 50.0 | 15.697099999999999 | 0.3148126881907152 | 0.8002206296508974 | - | - | 30 |
| swing:background-theme:rsi_upcross+joint_trend+volume+adx | ineligible | psr | 5 | 40.0 | 3.4253000000000005 | 0.09922138540828156 | 0.5811797763780655 | - | - | 30 |

## Midterm

Candidates: 30. Rejection funnel: min_n=4, psr=25, psr_error=1

### Exact winners

| Won metric(s) | Candidate | n | Win rate % | Profit % | Sharpe |
|---|---|---:|---:|---:|---:|
| no eligible candidate | - | - | - | - |

### Candidate audit

| Candidate | State | Reason | n | Win rate % | Profit % | Sharpe | PSR | DSR | Permutation p | DSR trials |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| midterm:no-background-theme:rsi_upcross | ineligible | psr | 17 | 35.294117647058826 | -2.6195000000000004 | -0.015133018942994304 | 0.4759961451532015 | - | - | 26 |
| midterm:background-theme:rsi_upcross | ineligible | psr | 14 | 35.714285714285715 | -1.5690000000000017 | -0.010804233437448893 | 0.4845236440059262 | - | - | 26 |
| midterm:no-background-theme:joint_trend | ineligible | psr | 76 | 50.0 | 110.1777 | 0.14781289921247603 | 0.9030029924716493 | - | - | 26 |
| midterm:background-theme:joint_trend | ineligible | psr | 65 | 46.15384615384615 | 38.816700000000004 | 0.06107638090768691 | 0.6891011679548511 | - | - | 26 |
| midterm:no-background-theme:volume | ineligible | psr | 52 | 51.92307692307693 | 115.8639 | 0.2106522586923004 | 0.9371756827996528 | - | - | 26 |
| midterm:background-theme:volume | ineligible | psr | 37 | 54.054054054054056 | 89.5488 | 0.2425697767025926 | 0.9273001488076731 | - | - | 26 |
| midterm:no-background-theme:adx | ineligible | psr | 51 | 39.21568627450981 | 25.140100000000004 | 0.04278040415758114 | 0.6204014881397075 | - | - | 26 |
| midterm:background-theme:adx | ineligible | psr | 39 | 33.33333333333333 | -58.9145 | -0.15106475297613173 | 0.1883658425911237 | - | - | 26 |
| midterm:no-background-theme:rsi_upcross+joint_trend | ineligible | psr | 15 | 40.0 | 12.4647 | 0.08159054644862059 | 0.6222351353315958 | - | - | 26 |
| midterm:background-theme:rsi_upcross+joint_trend | ineligible | psr | 12 | 41.66666666666667 | 13.5152 | 0.10841921083827878 | 0.6435818776305038 | - | - | 26 |
| midterm:no-background-theme:rsi_upcross+volume | ineligible | psr | 8 | 12.5 | -34.662 | -0.48120066391578836 | 0.22644857284703862 | - | - | 26 |
| midterm:background-theme:rsi_upcross+volume | ineligible | psr | 6 | 16.666666666666664 | -20.776100000000003 | -0.33089515126767016 | 0.30055451022231017 | - | - | 26 |
| midterm:no-background-theme:rsi_upcross+adx | ineligible | psr | 11 | 36.36363636363637 | 5.633000000000001 | 0.04599605026480325 | 0.5586935826703514 | - | - | 26 |
| midterm:background-theme:rsi_upcross+adx | ineligible | psr | 8 | 37.5 | 6.6834999999999996 | 0.07073356963384217 | 0.5758921346283024 | - | - | 26 |
| midterm:no-background-theme:joint_trend+volume | ineligible | psr | 31 | 45.16129032258064 | 16.492800000000003 | 0.057650536453345745 | 0.6251055673921356 | - | - | 26 |
| midterm:background-theme:joint_trend+volume | ineligible | psr | 24 | 45.83333333333333 | 21.195800000000002 | 0.09155317412999446 | 0.6716554742255753 | - | - | 26 |
| midterm:no-background-theme:joint_trend+adx | ineligible | psr | 40 | 35.0 | -43.680299999999995 | -0.11063648504035126 | 0.2531605879514669 | - | - | 26 |
| midterm:background-theme:joint_trend+adx | ineligible | psr | 35 | 34.285714285714285 | -49.1996 | -0.14084572949672602 | 0.2180516093674174 | - | - | 26 |
| midterm:no-background-theme:volume+adx | ineligible | psr | 24 | 33.33333333333333 | -20.812599999999996 | -0.07925839220539177 | 0.35697625177439163 | - | - | 26 |
| midterm:background-theme:volume+adx | ineligible | psr | 15 | 40.0 | -4.5857 | -0.029891366949490555 | 0.4558442038095639 | - | - | 26 |
| midterm:no-background-theme:rsi_upcross+joint_trend+volume | ineligible | psr_error | 5 | 0.0 | -35.7392 | -6.8511589350544835 | - | - | - | 26 |
| midterm:background-theme:rsi_upcross+joint_trend+volume | ineligible | min_n | 3 | 0.0 | -21.8533 | -6.633395631436298 | - | - | - | 26 |
| midterm:no-background-theme:rsi_upcross+joint_trend+adx | ineligible | psr | 10 | 40.0 | 13.453300000000002 | 0.12279415844689863 | 0.647691292569442 | - | - | 26 |
| midterm:background-theme:rsi_upcross+joint_trend+adx | ineligible | psr | 7 | 42.857142857142854 | 14.503800000000002 | 0.1785436273014481 | 0.674217909736912 | - | - | 26 |
| midterm:no-background-theme:rsi_upcross+volume+adx | ineligible | psr | 5 | 20.0 | -9.4997 | -0.17231249704802773 | 0.3866860672845211 | - | - | 26 |
| midterm:background-theme:rsi_upcross+volume+adx | ineligible | min_n | 3 | 33.33333333333333 | 4.386199999999999 | 0.10341904167658664 | - | - | - | 26 |
| midterm:no-background-theme:joint_trend+volume+adx | ineligible | psr | 16 | 25.0 | -47.2104 | -0.3478698435896486 | 0.1388937315445844 | - | - | 26 |
| midterm:background-theme:joint_trend+volume+adx | ineligible | psr | 12 | 33.33333333333333 | -19.7446 | -0.17123244104225976 | 0.29945568142726525 | - | - | 26 |
| midterm:no-background-theme:rsi_upcross+joint_trend+volume+adx | ineligible | min_n | 4 | 0.0 | -27.2792 | -7.9606880303114576 | - | - | - | 26 |
| midterm:background-theme:rsi_upcross+joint_trend+volume+adx | ineligible | min_n | 2 | 0.0 | -13.3933 | -11.503089095670825 | - | - | - | 26 |
