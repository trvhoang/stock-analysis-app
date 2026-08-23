# View Signals Ticker Filter Design

## Scope

Add one visible-text-hidden-label input at the top of the View Signals
popover. Its placeholder is exactly `ticker name`.

## Behavior

- Text is trimmed and auto-capitalized with the existing ticker-widget helper.
- The text is a case-insensitive partial ticker filter.
- The filter applies to whichever result tab the user is viewing: All, Valid,
  or Invalid. Empty text preserves every row.
- The control is read-only with respect to artifacts, positions, jobs, replay,
  database state, SQL, and prices.

## UI and tests

- Use a label-hidden Streamlit text input so the UI contains no label while
  screen-reader/test identity remains stable.
- The input appears before warnings and result tabs. It adds no action button.
- AppTest covers the exact placeholder, visible automatic capitalization, and
  an All-tab result narrowed to the matching ticker.
