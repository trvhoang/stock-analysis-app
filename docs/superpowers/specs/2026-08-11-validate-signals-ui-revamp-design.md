# Validate Signals UI Revamp Design

## Goal

Make saved-signal validation easier to read and let users maintain manual
positions without changing backtest replay, signal artifacts, or automated
trading behavior.

## Scope

Backtest Lab has three top-level tabs: Collect Signals, Validate Signals, and
Current Positions. All actions remain explicit and manual. No job submission,
re-certification, database write, auto-buy, or auto-close is added.

## Validate Signals

The page shows a progress bar only while `Validate saved signals` runs. It is
cleared after either a successful result or an error.

When theme validation is requested, display No theme first and VN-Index AND
second. Each theme is a group title containing only its own signal sets.

Each theme group contains a collapsed Signal-set summary and collapsed detail
expanders. Several signal-set detail expanders may be open simultaneously.
Detail content remains the current replay/advice content.

Default summary columns are:

- Identity: ticker, selected metric.
- Strategy: indicators, BUY threshold.
- Backtest performance: `n`, win rate, profit, Sharpe, deflated Sharpe,
  p-value, date range.
- Current match: match level, classification, advice, theme eligibility.
- Current trade signal: signal date, entry, SL, TP, projected exit.
- Existing-position state: status, holding/suggested holding, SELL
  allowed/reasons, pinned SL/TP.

Other already-available signal fields are initially hidden. A session-only
column picker controls visibility; it resets with the browser session and is
not stored in a file or database.

Eligible BUY advice and eligible Close position advice each show an individual
manual form beside that signal set. Batch selection and shared forms are
removed. BUY forms accept an optional positive whole-share quantity. Close
position remains an explicit manual SELL; it does not add a technical exit or
auto-close path.

## Current Positions

Current Positions is a third top-level tab. On first render it loads all saved
positions, gets latest prices for OPEN tickers in one bounded database query,
and renders OPEN positions immediately. Its Refresh button reloads both saved
position records and current prices/P&L. Cached tab state prevents unrelated
Streamlit reruns from repeatedly querying the database.

Ticker text and state filters shorten the list. State defaults to OPEN, so
CLOSED positions are hidden initially. The combined list treats No theme and
VN-Index AND equally and sorts by `opened_at`, oldest first.

Every row displays ticker, actual BUY price, actual SELL price or `-`, current
price for OPEN positions, percentage profit, absolute profit, open time,
closed time, and signal set. OPEN positions show `-` for SELL price and closed
time. OPEN P&L uses latest trading-day close; CLOSED P&L uses actual SELL.
P&L excludes fees/taxes. Percentage P&L is `(reference price / BUY price - 1)
* 100`. Absolute P&L is `reference price - BUY price` when quantity is absent,
or that difference multiplied by quantity when present.

Current Positions provides an individual Edit position form. Quantity is
optional, positive whole shares, and may be added, changed, or cleared after
BUY or SELL recording. BUY price is always editable; SELL price is editable
only for a CLOSED position. Edits overwrite current stored values, retain no
correction history, and never change `opened_at` or `closed_at`. Changing BUY
price recalculates pinned SL/TP from the already-frozen ATR, while retaining
the frozen ATR and max-hold bars.

## Data and Safety

Position files remain source of truth. Existing files without quantity load as
`quantity = null`. All position-file writes remain atomic. Malformed position
histories are isolated and reported without hiding valid records. The latest
price query uses `sqlalchemy.text()`, `engine.raw_connection()`, and bound
parameters. Raw price values remain BIGINT; UI formats only use shared price
conversion helpers.

## Verification

Tests cover backward-compatible quantity validation, price/quantity overwrite
behavior, frozen-ATR risk recalculation, timestamps preservation, batched
latest-price lookup, no N+1 current-position refresh, summary order/default
columns/collapse, individual BUY/SELL forms, and Current Positions filtering.
