# Validate Signals Position-Action Filter Design

## Goal

Add a local Position actions dropdown to Validate Signals and arrange the
controls in the requested two rows.

## Layout

- Line 1: `Tickers`, `Ticker group`.
- Line 2: `Monitoring classifications`, `Position actions`, `Validate`.

## Position-action filter

- The `Position actions` select box options are exactly `ALL`, `can BUY`,
  `expired BUY`, `can SELL`, and `HOLD`; default is `ALL`.
- Monitoring classifications remains a multiselect with all values selected by
  default.
- Both filters use AND semantics.
- `ALL` includes every available action. Older session-cached rows that have no
  `position_action` are treated as `expired BUY`, matching the existing safe
  display fallback.

## Execution boundary

The filters only re-render the latest cached successful validation result.
Changing either filter never replays validation. A fresh session with no cache
continues to display no result list.

No action rule, validation execution, artifact/job or position schema, SQL,
price scaling, dependency, Docker, credential, or Git behavior changes.
