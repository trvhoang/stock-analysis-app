# View Signals and New Position Layout Design

**Date:** 2026-08-22
**Status:** Approved design — implementation plan pending review

## View Signals

Keep current UI-only projection and raw data unchanged. `Win rate %`, `Profit
%`, and `Sharpe` pair values display one decimal place; `N/A` stays `N/A`.
`n` remains an unrounded integer pair.

Set View Signals dataframe height to approximately 20 displayed rows (720 px).
Native dataframe scrolling exposes rows beyond that height.

## New Position

Keep native popover, widget keys, labels, validation, and persistence unchanged.
Use live popover controls instead of a Streamlit form so Saved signal set
refreshes when Ticker changes.
Arrange fields as:

1. Ticker, Saved signal set, State
2. BUY price, BUY date, Volume
3. SELL price, SELL date
4. Add Position

No SQL, schema, BIGINT, signal, risk, SELL-advice, dependency, or Docker
behavior changes.

## Verification

Tests cover one-decimal metric display, preserved N/A/n output, dataframe
height, and three New Position field rows plus final submit row.
