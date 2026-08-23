# Collect Signals Result Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline test-driven execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render Collect Signals output artifacts four items per row.

**Architecture:** `_render_collect()` creates one four-column Streamlit row and
routes each status output path by its stable index modulo four. `_render_v4_artifact()` remains unchanged.

**Tech Stack:** Python 3.12, Streamlit 1.32, unittest.

## Global Constraints

- Preserve artifact order and all existing item content.
- No job, artifact, SQL, raw-BIGINT, dependency, Docker, or Git change.

---

### Task 1: Four-column artifact output

**Files:**
- Modify: `tests/test_backtest_page.py`
- Modify: `app/pages/backtest_lab.py`

**Interfaces:**
- Consumes: `status.output_paths` and `_render_v4_artifact(path)`.
- Produces: four-column visual grouping without changing output paths.

- [x] Add a page test expecting a four-column result container and modulo-four
  output routing in `_render_collect()`.
- [x] Run RED: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.
- [x] Add `result_columns = st.columns(4)` and render every output path within
  `result_columns[index % 4]`.
- [x] Run GREEN: `docker exec stock_app python -m unittest tests.test_backtest_page -v`.
- [x] Run compilation: `docker exec stock_app python -m compileall -q pages/backtest_lab.py tests/test_backtest_page.py`.
