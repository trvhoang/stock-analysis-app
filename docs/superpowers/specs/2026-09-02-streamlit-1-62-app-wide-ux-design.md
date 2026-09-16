# Streamlit 1.62 and App-wide UX Design

**Date:** 2026-09-02  
**Status:** Design approved; implementation in progress.  
**Scope:** Upgrade the Streamlit runtime to 1.62.0 and make the seven-page
application consistent, legible, and safer to operate. This is a UI/runtime
change only; trading, data, artifact, position, and database semantics remain
unchanged.

## Purpose

The app has grown through several independent workflows. It currently uses a
custom sidebar page selector, inconsistent action controls, duplicated utility
actions, and old sizing APIs. The upgrade will use Streamlit's supported
navigation and native interaction primitives so the app is easier to scan,
works predictably across pages, and remains maintainable after the runtime
upgrade.

## Decisions

1. Upgrade the compatible runtime set together:

   - `streamlit==1.62.0`
   - `fastapi==0.141.1`
   - `uvicorn==0.52.4`
   - `numpy==2.2.6`
   - `pandas==3.0.5`
   - `pandas-ta==0.4.71b0`
   - `pytz==2025.2`

   Streamlit 1.62 requires newer Starlette and Uvicorn ranges than the current
   FastAPI 0.111 / Uvicorn 0.29 pair permits. No one-line Streamlit-only
   upgrade is allowed. The numerical/indicator pins are upgraded together
   because pandas-ta 0.4.71b0 requires NumPy at least 2.2.6 and pandas at least
   2.3.2, while its required Numba 0.61.2 caps NumPy below 2.3. `pytz` is a
   direct application import and is declared explicitly rather than relying on
   the dependency that pandas 2.x formerly supplied transitively. The final
   Docker image must pass `pip check`; resolved transitive versions are
   recorded in verification evidence.

2. Replace the legacy sidebar selector with one flat top navigation:

   ```python
   page = st.navigation(pages, position="top")
   page.run()
   ```

   The exact visible order is **Data**, **Result**, **Analyze**, **Suggestion**,
   **Technical Analyze**, **Backtest**, and **Flexible Rulebook**. There are no
   page groups, nested navigation, renamed workflows, or changed route intent.
   Each route receives a stable `url_path` and a Material icon. Existing shared
   startup (environment loading, cached engine, API bootstrap) remains in the
   entrypoint. Small no-argument route wrappers pass existing dependencies to
   the current page renderers. The redundant global `Stock Analysis App` title
   is removed so top navigation and page-local headings own the available
   vertical space.

3. Use Streamlit-native controls, not a custom visual system:

   - Primary workflow action: text plus a Material icon, one primary action in
     a local toolbar or form.
   - Secondary action: text plus icon when its meaning is not instantly
     obvious (for example, export).
   - Familiar utility: icon-only Material control with a specific `help`
     tooltip (remove, filter columns, edit, refresh, clear cache). The visible
     Material icon label is nonempty; no hidden CSS text or empty accessible
     label is used.
   - Lightweight temporary settings: `st.popover`.
   - Destructive or irreversible intent: `st.dialog` confirmation. The final
     confirm action remains text plus a destructive icon; the initial compact
     trigger is never itself destructive.
   - Successful short-lived confirmation: `st.toast`.
   - A warning, error, data-quality finding, job result, or action that needs
     acknowledgement: a titled persistent Streamlit alert in the relevant
     workflow section.

4. Use native table capability before bespoke controls. Read-only tables use
   `st.dataframe` with native sorting, column resize/reorder, stretch width,
   hidden index, and explicit column configuration. Checkbox-editing tables
   retain their stable deterministic row order because selection and removal
   must continue to address the exact rendered rows. A column-filter popover
   controls visibility where that improves dense operational views; it does not
   alter artifacts or calculations.

5. Do not add animation libraries, a new UI dependency, or decorative custom
   animation. Streamlit's native controls provide feedback. This is a
   professional data application: clarity, immediate response, and stable
   layout take priority over visual motion.

## Runtime compatibility and migration

### Dependency contract

`requirements.txt` receives the seven exact direct pins above. `pandas-ta`
remains imported as `pandas_ta`; the hyphenated project name is the correct pip
requirement and resolves to the normalized `pandas_ta` distribution artifact.
The image is rebuilt without dependency cache for the compatibility gate. A
resolver or clean build must prove that both the web stack and indicator stack
are consistent, and `python -m pip check` must be clean. Before the production
image gate, the exact numerical set must pass the focused technical-analysis
suite so dependency compatibility is demonstrated by indicator behavior, not
only by the package resolver.

The current image's Python 3.12 is supported. No Dockerfile or Compose change
is part of the original design. One compatibility-only Docker command flag,
`--browser.gatherUsageStats=false`, is required because Streamlit 1.62 writes a
machine ID during browser-session startup while the existing named Streamlit
cache volume is intentionally not writable by the non-root process. Disabling
telemetry skips that write without changing ownership, mounting, or container
privilege. Streamlit 1.62 also auto-discovers direct top-level FastAPI
constructors; the same API object is therefore created through a helper so the
dashboard remains the primary port-3501 app. The independent FastAPI process hosted on port 3500 and
the Streamlit process on port 3501 are both smoke-tested because Streamlit's
newer runtime also uses newer web-server dependencies.

### Required API migration

All `use_container_width=True` calls are audited.

- For Streamlit widgets and tables, replace it with `width="stretch"`.
- For `st.plotly_chart`, remove the obsolete argument and use the supported
  layout/container configuration for its current Streamlit API.
- No broad source replacement is permitted: each occurrence is reviewed so
  narrow controls do not become full-width accidentally.

The legacy sidebar navigation CSS and hidden auto-navigation CSS are removed.
Any remaining CSS is limited to stable layout or readability needs, not to
imitate native controls or hide semantic text.

## Navigation and shared UI boundaries

### Entry point

`app/main.py` owns navigation assembly and the shared startup lifecycle. It
must continue to initialize the engine and API exactly once per process/session
according to the current contract. Navigation state replaces the old selector
state without changing business-page session keys.

The existing intent to discard **Technical Analyze's temporary state** after
leaving that workflow is preserved explicitly and tested. The current global
`st.session_state.clear()` call is replaced with
`clear_technical_session_state()`: the Technical page owns a namespaced raw
history cache plus its four snapshot keys, and that helper removes only those
keys. This prevents leaving Technical Analyze from wiping a Backtest/Flexible
job display, another page's form input, or an unrelated pending dialog. It
does not change how a page starts its work.

### Lightweight shared helpers

A small common UI module will centralize only repeated presentation policy:

- semantic Material icon names;
- a utility icon-button helper that requires a tooltip and stable widget key;
- a common read-only dataframe configuration baseline;
- named feedback helpers for transient success and persistent operational
  notices.

It must not own page state, business wording, button callbacks, dialog state,
dataframes, or backtest/flexible persistence. Those remain local to their
current page modules. This boundary prevents a visual consistency task from
turning into a high-risk application-framework rewrite.

## Page behavior

### Data

Retain the existing retrieval inputs and sequential progress. Present the
retrieve action as the one labelled primary action; show durable progress and
completion/failure adjacent to the action rather than relying only on a toast.

### Result and Suggestion

Keep their queries and ranking rules intact. Apply the common table baseline,
meaningful number/date formats, native sort, explicit empty states, and a
consistent input/action row. Results remain read-only.

### Analyze

Analyze remains the labelled primary action. Export becomes a labelled
secondary text-plus-icon action and uses a compact popover for its existing
options; it does not change exported data or save behavior. Existing warnings
and classification evidence remain persistent in their local result sections.

### Technical Analyze

Retain its existing analysis controls and charts. There is one Clear Cache
utility control, not duplicate sidebar and page copies. It uses the shared
clear-cache icon and tooltip, while the confirmation/result message is local.
Plotly rendering is migrated for the Streamlit 1.62 API without changing
indicator or price calculations.

### Backtest

Retain the five-tab order and all schema-5, V3, and position safeguards.

- View Signals keeps visible-row selection and safe bulk removal. Its remove
  and column-filter controls use the shared Material icon conventions.
- A removal confirmation remains explicit. Blocked removal continues to state
  that a position's historical signal reference is protected.
- Long-running Collect/Validate work retains its progress bars, job summaries,
  terminal result areas, and actionable error messages. A toast may confirm
  submission, but never substitutes for durable status.
- Current Positions keeps its collapsible New Position section and existing
  BUY/SELL protections; utility controls are made visually consistent only.

### Flexible Rulebook

Retain approved discovery activation, source-freshness, benchmark, campaign,
qualification, and BUY-scan contracts. The page presents the lifecycle in a
consistent hierarchy: user inputs, one labelled primary action for the active
stage, durable progress/status, and results. Icon utilities are used only for
clear auxiliary actions; benchmark/campaign/qualification controls remain
labelled because their consequences are domain-specific. No change is made to
cap policy, campaign identity, cache semantics, artifact layouts, or worker
execution.

## Feedback, accessibility, and layout rules

- Every icon-only control has a precise tooltip which describes the action and
  affected scope, such as `Remove selected signals (3)`.
- Color never carries severity by itself. Alerts include a title and written
  outcome; destructive controls retain text in the final confirmation.
- Popovers contain small, reversible controls. They must not contain another
  popover or a long-running workflow.
- Dialogs are reserved for confirmation that prevents a material accidental
  write or removal. Closing a dialog performs no action.
- Buttons in dense toolbars use content width and do not wrap. Forms and
  primary workflow actions use stretch width only where that improves small
  viewport use.
- Tables render `—` for missing display data rather than `NaN`, blank numeric
  sentinels, or invented zeroes.
- No keyboard-triggered action is delayed by custom animation. Native controls
  and progress indicators are preferred over custom motion.

## Data and safety invariants

This work does **not** change:

- SQL, raw-connection usage, credential loading, BIGINT price scaling, or
  Delta CTEs;
- any indicator, trade, risk, schema-5 artifact, Flexible Rulebook, or
  position-validation calculation;
- job process ownership, sequencing, cancellation, cache, or persistence;
- group membership or user-entered backtest configuration;
- the existing seven workflow boundaries.

An upgrade failure or a page rendering error must fail visibly in its local UI
without silently resetting user configuration, replacing artifacts, or starting
a new job.

## Verification and acceptance criteria

### Automated

1. Dependency resolver/clean Docker build completes, `pip check` passes, and
   the container reports Streamlit 1.62.0 with the approved FastAPI/Uvicorn
   versions.
2. Compile all affected modules and run focused entrypoint, page, table, and
   Backtest/Flexible AppTest suites. Update assertions only where the approved
   presentation contract changes labels or topology.
3. Add focused tests for the flat seven-page top navigation, stable route
   definitions, page transition cleanup, icon-helper tooltip/key requirements,
   and no destructive callback before dialog confirmation.
4. Add regression coverage for View Signals selection/removal and Flexible
   lifecycle controls after the widget changes.
5. Search for obsolete Streamlit sizing calls and legacy sidebar-navigation CSS;
   any remaining occurrence must be documented as supported or removed.
6. Verify Docker health and the API smoke path on their existing ports after a
   clean rebuild.

### Manual visual gate

Check each of the seven pages at normal desktop width and a narrow browser
width. Confirm that top navigation is flat and usable, tooltips explain every
icon-only control, popovers fit their content, destructive dialog cancellation
does nothing, tables can sort where read-only, and no workflow action is hidden
or duplicated. The user-visible runtime must have no Streamlit warnings or
uncaught page exceptions.

## Rollout and rollback

The implementation is ordered as: runtime compatibility, shared conventions,
top navigation, simple read-only pages, analysis pages, Backtest, Flexible
Rulebook, and full regression/visual verification. Each stage has a focused
test gate before the next begins.

There is no data migration. If the runtime gate fails, retain the current
`requirements.txt` pins and do not merge partial widget/navigation changes.
If a later UX stage fails, revert only that stage's presentation changes; the
new runtime remains valid once its dedicated gate has passed.

## Explicit exclusions

- No redesign of the trading workflow or rulebooks.
- No new frontend framework, custom component, UI library, or animation
  dependency.
- No responsive layout overhaul beyond correcting controls that overflow or
  become unclear on a narrow view.
- No changes to artifacts, positions, database contents, or background-job
  protocol.
