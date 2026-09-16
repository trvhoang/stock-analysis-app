# Current UI Audit — Stock Analysis App

**Phase:** `UI_AUDIT`  
**Date:** 2026-09-17  
**Code changes allowed:** No. This artifact is an audit only.  
**Evidence sources:** `app/main.py`, `app/commons/ui_controls.py`, the seven
page renderers, and focused UI tests. No fresh browser/mobile observation was
available, so those items are labelled `UNKNOWN`.

## 1. Executive summary

The app already has a sound Streamlit foundation: flat top navigation, wide
layout, native controls, Material icons, reusable responsive-dataframe options,
and several clear progress/error paths. The revamp should preserve those
workflows and focus first on a consistent visual hierarchy, action layout,
feedback language, and data-heavy Backtest ergonomics.

The main risk is treating this as cosmetic while changing trading workflows.
All proposed directions below preserve backend behavior, artifact formats,
positions, rulebook semantics, and data operations. Any change to a workflow,
default, filtering semantics, or background execution is a
`REQUIRES_DECISION` item.

## 2. UI and navigation map

| Route | Renderer | Current primary structure | Evidence |
|---|---|---|---|
| Data | `pages/data_preparation.py:data_page` | Three controls, ingestion progress/details, source-date highlights | `app/main.py:67`, `data_preparation.py:515` |
| Result | `pages/result_visualization.py:result_page` | Month input, two ranking tables | `main.py:73`, `result_visualization.py:8` |
| Analyze | `pages/analyze_visualization.py:analyze_page` | Ticker/Portfolio tabs; statistical, technical, and final-advice reports | `main.py:79`, `analyze_visualization.py:489` |
| Suggestion | `pages/suggestion_visualization.py:suggestion_page` | Four market-scan inputs and four result tables | `main.py:85`, `suggestion_visualization.py:12` |
| Technical Analyze | `pages/technical_visualization.py:technical_analysis_page` | Ticker/horizon action row, chart, indicator tabs and tables | `main.py:91`, `technical_visualization.py:290` |
| Backtest | `pages/backtest_lab.py:render_backtest_page` | Six workflow tabs for collect/view/validate/positions/groups | `main.py:97`, `backtest_lab.py:3485` |
| Flexible Rulebook | `pages/flexible_rulebook.py:render_flexible_rulebook_page` | Builder, Backtest, Library via horizontal radio | `main.py:106`, `flexible_rulebook.py:681` |

`CONFIRMED`: navigation is flat top navigation through `st.navigation(...,
position="top")`; no sidebar navigation is active.

## 3. Evidence-based findings

| Location | Evidence | Issue | User impact | Severity | Scope | Confidence | Direction |
|---|---|---|---|---|---|---|---|
| Shared shell, `app/main.py:119-133` | Inline CSS owns page width, paddings, and a broad dataframe selector | Shared presentation is embedded in the entrypoint, while reusable controls are elsewhere | Visual changes risk fragmented ownership and inconsistent page behavior | MEDIUM | SHARED | CONFIRMED | Create one small presentation layer with named tokens/helpers; keep CSS minimal and native-first |
| Shared pages | Headers vary between `Data Page`, `Result Page`, `Suggestion Page`, `Analyze Page`, `Technical Analysis`, `Backtest Lab` | Page naming and title hierarchy are inconsistent | Navigation label, page title, and task intent do not always reinforce each other | LOW | SHARED | CONFIRMED | Define a consistent page-header pattern and title vocabulary without renaming routes yet |
| Data, Analyze, Suggestion, Technical | Each has a different control-row composition and button placement | Primary-action placement is not consistently scanable | Users must relearn where to start each workflow | MEDIUM | SHARED | CONFIRMED | Adopt a reusable “inputs + primary action + optional utility action” layout contract |
| Suggestion page | `suggestion_page` runs a threaded market scan after a button click but gives only `st.write` text | Long-running work lacks a progress/status surface comparable to Data, Backtest, and Flexible Rulebook | User cannot distinguish working, slow, or stalled processing | HIGH | DEDICATED | CONFIRMED | Design a non-semantic progress/summary state; changing cancellation or execution model requires a separate decision |
| Backtest, `backtest_lab.py` | 138 KB renderer; Collect, Validate, View, Positions, and Group Manager use distinct dense layouts; Validate has eight filter columns | High-density workflows have no shared page-level visual structure | High cognitive load and greater risk of control/result separation on smaller screens | HIGH | DEDICATED | CONFIRMED | Plan Backtest as its own enhancement slice with a stable workflow header, result state, and responsive filter strategy |
| Backtest vs Flexible Rulebook | Backtest uses `st.tabs`; Flexible uses horizontal `st.radio` for conceptually related workspaces | Workspace navigation patterns differ | Users may not predict how adjacent research workflows behave | MEDIUM | SHARED | CONFIRMED | Choose one documented workspace-navigation rule based on task complexity; preserve state semantics |
| Tables across pages | `read_only_dataframe_kwargs()` standardizes stretch/hide-index, but direct `st.dataframe` and `st.data_editor` calls remain; pagination appears only in specific Backtest paths | No documented table contract for density, sorting, height, empty states, or action selection | Table-heavy pages feel inconsistent and can become hard to scan | MEDIUM | SHARED | CONFIRMED | Establish two explicit shared patterns: read-only result table and selectable/action table |
| Feedback states | `ui_controls.py` provides toast and titled notices, but pages still mix direct `st.success`, `st.write`, `st.info`, spinners, progress bars, and expanders | Success, pending, and outcome messages are not consistently prioritized | Important business completion/error states may be visually lost in dense pages | MEDIUM | SHARED | CONFIRMED | Define feedback-state hierarchy and migrate only repeated presentation paths |
| Icons and destructive actions | Shared `utility_icon_button()` provides Material icons and tooltip validation; some page controls still use plain `X` or text-only actions | Utility action affordance is partially standardized | Icon-only controls can be inconsistent or harder to discover | LOW | SHARED | CONFIRMED | Retain labelled destructive confirmations; standardize reusable icon actions with visible context and tooltips |
| Technical Analyze | Chart uses `width="stretch"`, but fixed 600/750 px height and data tables coexist below an indicator tab strip | Large analytical output is visually dominant without an explicit reading order | On constrained screens, controls and key summary may be displaced | MEDIUM | DEDICATED | CONFIRMED | Introduce a clear summary-to-chart-to-detail hierarchy; do not change indicator calculations |
| Analyze page | One successful run renders many sequential report sections, including a known future “Explanation” placeholder | Result narrative is long and mixes primary advice with supporting evidence | Users may miss the final decision or confuse historical evidence with current advice | HIGH | DEDICATED | CONFIRMED | Design progressive disclosure and a result summary hierarchy; explanation content itself is product scope and requires decision |
| All pages | No repository evidence of explicit keyboard traversal audit, narrow viewport test, or screen-reader review | Accessibility/runtime responsiveness are unverified | A visually appealing revamp could regress usability | MEDIUM | SHARED | UNKNOWN | Add manual keyboard, contrast, and narrow-width validation to the later implementation plan |

## 4. Repeated patterns and duplication

`CONFIRMED`

- `app/commons/ui_controls.py` is an existing stable base for utility icons,
  responsive read-only dataframes, toasts, and persistent notices.
- Primary action rows are implemented independently in Data, Analyze,
  Suggestion, Technical Analyze, Backtest, and Flexible Rulebook.
- Result tables repeat `st.subheader` + `st.dataframe` without a shared empty,
  caption, height, or selection convention.
- Native Streamlit tabs, popovers, expanders, dialogs, forms, and progress bars
  are already in use and should be preferred over a component-library rewrite.

`INFERRED`: the highest-value shared layer is small presentation helpers and
documented page composition—not a generic form/table abstraction with many
flags.

## 5. Accessibility and feedback-state gaps

| Area | Status | Evidence / limitation | Direction |
|---|---|---|---|
| Labels | CONFIRMED | Most visible inputs use labels; shared utility icon helper requires `help` text | Keep labels; verify icon actions retain accessible names |
| Destructive confirmation | CONFIRMED | Backtest uses dialogs for signal, position, and group deletion | Preserve confirmation dialogs and make destructive hierarchy consistent |
| Keyboard/focus | UNKNOWN | No browser/manual focus evidence was available | Add keyboard traversal and focus-visible checks to validation |
| Contrast/theme | UNKNOWN | The repository does not define a centralized theme token set; only limited inline CSS appears in `main.py` | Choose tokens and validate contrast before implementation |
| Loading and completion | CONFIRMED | Data/Backtest/Flexible use progress; Technical uses spinners; Suggestion does not expose progress | Define a clear pending/progress/success/error model per workload class |
| Responsive layout | UNKNOWN | `layout="wide"` and stretch tables are confirmed; narrow viewport behavior is not | Add defined breakpoints/compact fallback checks without fragile DOM selectors |

## 6. Confirmed constraints

- Preserve all business logic, database behavior, artifacts, positions, and
  workflows unless a behavior change is explicitly approved.
- Keep Streamlit and the existing flat top navigation.
- Prefer native Streamlit controls/layout/theming; use
  `streamlit-shadcn-ui` only for a verified unmet need.
- Keep custom CSS centralized, small, and free of fragile undocumented DOM
  dependencies.
- Preserve accessibility labels, keyboard operation, focus visibility, contrast,
  and clear feedback states.
- No implementation is permitted until the master-plan phase becomes
  `IMPLEMENTATION` with approved scope recorded.

## 7. Unknowns and decisions required

| Item | Status | Why it matters |
|---|---|---|
| Desired visual character: restrained professional research terminal, or a more expressive product identity | REQUIRES_DECISION | Determines typography, color intensity, density, and chart emphasis |
| Priority order across the seven pages | REQUIRES_DECISION | A whole-app revamp is too broad to implement safely in one slice |
| Real browser observations at desktop and narrow widths | UNKNOWN | Static code cannot prove spacing, overflow, focus, or visual contrast quality |
| Whether to improve Suggestion execution feedback only, or also its execution/cancellation behavior | REQUIRES_DECISION | The former is UI-only; the latter changes workflow behavior |
| Final Advice explanation content | REQUIRES_DECISION | A real explanation changes product content, not only presentation |

## 8. Highest-impact opportunities

1. **Shared shell and page hierarchy:** establish a restrained native Streamlit
   presentation foundation so each route begins with the same recognisable task
   framing and primary action zone.
2. **Backtest workflow clarity:** redesign the densest page as a separate,
   evidence-preserving slice; prioritize filters, progress, result state, and
   table scanability before decorative changes.
3. **Analyze/Suggestion output hierarchy:** surface the current conclusion and
   run state before supporting tables/details, without altering calculations.
4. **Feedback and table conventions:** build only the small shared helpers that
   are used by multiple routes and reduce duplicated one-off presentation code.
5. **Accessibility/responsive validation:** make these explicit acceptance
   criteria rather than visual afterthoughts.

## 9. Self-critique

- This audit does not claim a preferred visual style; no user brand direction
  or runtime screenshot evidence was supplied.
- The audit does not prescribe a React rewrite, a component-library dependency,
  or a global CSS overhaul because repository evidence does not justify them.
- The Backtest finding is systemic in density but intentionally stays scoped to
  presentation and interaction clarity; signal/position semantics are out of
  scope.
- The Suggestion progress finding is confirmed, but any asynchronous or
  cancellation change is explicitly deferred as a product decision.
- Narrow-screen, contrast, and keyboard conclusions remain `UNKNOWN` until a
  browser validation pass is performed.
