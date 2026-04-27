﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿# Current Project Status

This document provides a snapshot of the project's current state, including finished tasks, ongoing work, known issues, and next steps.

## 1. Recently Completed Tasks
- **Implement API support functions:**
  - Implement API endpoint `POST /api/prepare-data` to support trigger Data preparation: default values: 
    . Select Report Date: latest trading date
    . Gaps of data (years): 1 (year)
- **FastAPI Integration:**
  - Implemented REST API endpoint `GET /api/analyze/{ticker}` to trigger full statistical and technical analysis.
  - Developed Pydantic schemas for structured JSON responses (`TickerAnalysisResponse`).
  - Integrated the API server as a background thread within the Streamlit application for unified service management.
  - **Fix:** Resolved a bug in `synthesize_all_advice` where `result_days` was hardcoded to 10; it now respects API query parameters.
  - **Refactor Technical Trend Context:** Refactored the historical technical context summary to analyze the trend of the result category with the highest statistical frequency (Up vs Down vs No Change).
- **API Data Management:**
  - Implemented `POST /api/prepare-data` endpoint to trigger historical data ingestion.
  - Integrated `BackgroundTasks` to handle long-running downloads without HTTP timeouts.
  - Added a global `threading.Lock` to ensure thread-safety between UI and API-triggered ingestion.
- **Environment & Performance Fixes:**
  - Resolved Numba `RuntimeError` in Docker by configuring `NUMBA_CACHE_DIR` and optimizing `load_dotenv()` placement.
  - Fixed `StreamlitAPIException` by ensuring `st.set_page_config` is the absolute first command in `main.py`.
- **Project Restructuring:**
  - Modularized the application into `apis/` (REST), `commons/` (Shared logic), and `pages/` (Streamlit UI).
  - Updated all internal absolute imports to support the new package structure.
  - Centralized business logic in `app/commons/common_functions.py` to ensure consistency between the UI and API.
- **Refactor Ticker Analyze Tab (Historical Technical Context):**
  - Added 'Technical score' column to 'Block Day and Delta Statistical Report' to calculate technical strength at historical signal points.
  - Implemented a technical trend summary below 'Statistical Advice' using specific thresholds (Up $\ge 53\%$, Down $< 48\%$).
  - Optimized performance by calculating scores only for historical rows matching the predicted outcome.
- **Implement Trend Classification & State Management:**
  - Refactored the "Technical Analyze" page to use `st.session_state`, caching indicator data to prevent re-calculation on UI toggles.
  - Implemented business logic in `technical_analysis.py` to classify the current trend for MA Cross (based on <2% price spread for "Sideways") and RSI (based on a 30-period lookback analysis).
  - Added "Current Trend" metrics to the MA and RSI tabs in the UI.
- **Implement RSI (14) Indicator:**
  - Added `calculate_rsi` function to `technical_analysis.py`.
  - Added a "Show RSI (14)" checkbox to the "Technical Analyze" page.
  - Implemented a dynamic 3-row chart layout to display the RSI indicator in a separate subplot below the price and volume charts.
  - Added overbought (70) and oversold (30) threshold lines to the RSI chart.
  - Populated the "RSI" data tab with the latest indicator values.
- **Finalize MA and MA Cross Indicator:**
 - **Implement Stochastic (10, 3, 3) Indicator:**
  - Implemented `calculate_stochastic` function to `technical_analysis.py`.
  - Added logic to display the Stochastic (10, 3, 3) indicator.
  - Added logic to determine trend classifications (Up/Down/Sideways) on Stochastic.
  - Populated the "Stochastic" data tab with the latest indicator values.
  - Implemented UI controls for MA/MA Cross on the "Technical Analyze" page.
  - **Refactor UI of technical visualization page to optimize space and display as much as possible.**
  - Added timeframe-aware MA pair selection (Day, Week, Month).
  - Visualized SMA lines and Golden/Death cross signals on the main price chart.
  - Collapsed the raw data table by default to improve layout.
- **Technical Analyzed Page Implementation:**
  - Created a new page named "Technical Analyzed Page" using `pandas-ta` and `plotly`.
  - Implemented UI with Ticker, Timeframe, and Lookback controls.
  - Implemented interactive Price (Candlestick) and Volume (Bar) charts.
  - Created placeholder structure for technical indicators.
  - **Fix:** Resolved `AttributeError` in `fetch_data` by using `engine.raw_connection()` to bypass pandas/SQLAlchemy compatibility issues.
- **Refactor Number Formatting in Analyze Page:**
  - Refactored all numbers in analyze page (Ticker and Portfolio tabs) to have 2 decimal numbers after floating point.
- **Refactoring Core SQL Logic:**
  - Extracted common SQL CTEs for delta calculation into `common_queries.py`.
  - Updated `analyze_visualization.py` and `suggestion_visualization.py` to use the shared queries, reducing code duplication.
- **AI Context Documentation:**
  - Created and populated the entire `/ai-context` folder with all required documentation files (`README.md`, `project-overview.md`, `architecture.md`, `conventions.md`, `business-logic.md`, `decisions.md`, `boundaries.md`, `glossary.md`, `workflows.md`, `current-status.md`).
- **Bug Fixes:**
  - Resolved `ImportError` related to relative imports after refactoring.
  - Corrected SQL syntax errors (`ProgrammingError`) in both the Analyze and Suggestion pages.
- **Refactoring Suggestion & Analyze Page Logic:**
  - Implemented dynamic delta calculation for both Suggestion and Analyze pages.
  - Centralized 'Up'/'Down' thresholds in `common_queries.py`.
  - Added error handling to `analyze_ticker`.
  - Updated Analyze page to display 'Current Delta' metric.
- **Portfolio Analysis UI Refinement:**
  - Implemented conditional formatting for delta columns in the Portfolio Analyze tab to improve readability.
- **Documentation Sync:**
  - Updated `project-overview.md`, `architecture.md`, `business-logic.md`, `decisions.md`, `glossary.md`, and `README.md` to reflect the new "Context-Aware" logic and the addition of the Portfolio Analyze tab.
- **UI & Logic Standardization:**
  - Standardized the "day range" logic across the application, where an input of `N` now consistently represents an `N`-trading-day window (implemented as a lag of `N-1`).
  - Updated the "Analyze Page" UI to display the specific start and end dates for the current signal being analyzed.
- **Refactor "Ticker Analyze" Tab:**
  - Refactored the "Ticker Analyze" tab to use the centralized `analyze_ticker` function from `common_functions.py`.
  - This eliminated redundant helper functions and resolved the long-standing "Fragile String Parsing" known issue.

- **UI Enhancement: Remove Chart Gaps on Non-Trading Days:**
  - Reviewed the "Technical Analyze" page and confirmed the Plotly chart implementation already uses `rangebreaks` to remove gaps for weekends and holidays, making the x-axis continuous for trading days. The task is complete.
- **Refactor Data Preparation Page UI:**
  - In Data page, when receiving data and manipulation in progress, show the loading progress icon beside the Page title.
  - After all progress is done, hide the loading progress icon, show a check icon beside the page title
- **Fix Bug: Technical Analysis Page Crash (KeyError):**
  - Resolved `KeyError: 'cross_5_10'` in `technical_visualization.py` by adding a defensive check ensuring the signal column exists before plotting markers.
- **Fix Bug: MA Cross Signal Calculation Logic:**
  - Fixed logic in `technical_analysis.py` where the signal column creation was skipped due to a premature existence check, causing "Not enough data" errors despite sufficient data.
- **Fix Bug: Analyze Page & Result Page DB Compatibility:**
  - Refactored `analyze_ticker`, `analyze_price_movement`, and `result_page` to use `engine.raw_connection()` and safe string replacement for SQL parameters.
  - This resolves pandas/SQLAlchemy compatibility issues that caused silent query failures (`psycopg2.errors.InvalidSchemaName: schema "np" does not exist`) and `TypeError: Query must be a string unless using sqlalchemy`.
- **Refactor Analyze Page UI:**
  - Added a "Technical Report" table displaying Stochastic, RSI, MA, and MA Cross indicators with trend direction.
  - Implemented dynamic timeframe selection for technical indicators (Day vs Week) based on the validation day range.
  - Organized the "Block Day and Delta Statistical Report" into a collapsed expander, while keeping the "Analyzed Statistical Report" visible by default.
  - **Fix Bug: Analyze Page Crash (ValueError):**
    - Resolved `ValueError: too many values to unpack` in `analyze_page` by updating `provide_advice` to return a tuple `(message, trend)`.
    - **Refactor:** Standardized emoji usage across advice functions using a global `TREND_EMOJIS` constant, eliminating fragile string parsing logic.
  - **Refactor Analyze Page UI Layout:**
    - Reordered the "Ticker Analyze" tab to follow a strict 1-5 display order (Signal -> Stats -> Tech -> Final -> Explanation).
    - Removed legacy placeholder logic for cleaner linear rendering.
  - **Refine Final Advice Logic:**
    - Implemented a decision matrix combining Statistical and Technical trends to generate the Final Advice.
    - Documented the logic in `business-logic.md`.
  - **Refactor Portfolio Analyze UI:**
    - Converted the Portfolio table to a lightweight version with columns: `No`, `ticker`, `statistical trend`, `possibility`, `delta`, `technical trend`, `score`, `final advice`.
    - Integrated technical analysis (Trend & Score) for batch processing.
    - Added emoji support for trend visualization.
  - **Update RSI Trend Logic:**
    - Refined RSI trend classification rules: Sideways range (40-55), 2-consecutive period check for trends, and adjusted Strong/Over/Under thresholds.
  - **Update MA Trend Logic:**
    - Added bullish and bearish reversal pattern detection to the `calculate_ma_trend` function based on 3 consecutive periods of MA movement and their gap.

  - **Fix Bug: Inconsistent Technical Advice between Analyze Tabs:**
    - **Root Cause:** The `calculate_ma_cross` function incorrectly coupled the trend logic for MA spread and MA cross events, leading to inconsistent trend assignments.
    - **Fix:** Refactored the logic into two separate functions: `calculate_ma_trend` (for spread/reversal) and `calculate_ma_cross_trend` (for events). Both "Ticker Analyze" and "Portfolio Analyze" were updated to call these distinct functions, ensuring consistent and correct trend calculation for each indicator.
- **Enhance logic of Suggestion Page**: Implemented the filtering and multi-tier sorting logic for the Suggestion Page, combining statistical probabilities with technical scores and exchange-based priorities (HSX > HNX > UPCOM).
## 2. Work In Progress (WIP)
- **Implement Suggestion API:** Create a new API endpoint to provide market-wide ticker suggestions.
  - Default parameters: `day_range=5`, `result_day_range=5`, `min_avg_volume=1000000`, `year_gap=1`.
  - Response requirements: Top 5 Tickers by Possibility of Up (ticker, possibility_up, total_signals) and Top 5 Tickers by Delta of Up (ticker, max_up_delta, total_signals).
- **Implement Remaining Technical Indicators:**
  - Implement Bollinger Bands logic and visualization.
  - Implement Ichimoku Cloud (9, 26, 52, 26, 26) logic and visualization.
## 3. Known Issues & Technical Debt
*No known issues at this time.*

## 4. Next Steps & Priorities
1.  **Implement Suggestion API:** Create a new FastAPI endpoint for market-wide high-probability ticker suggestions.
2.  **Implement Bollinger Bands:** Add calculation logic and visualization for Bollinger Bands (20, 2) to the Technical Analyze and Analyze pages.
3.  **Implement Ichimoku Cloud:** Add calculation logic and visualization for Ichimoku Cloud (9, 26, 52, 26, 26).
4.  **Define explanation of Final advice:** (Lowest Priority) Define the logic to generate a detailed explanation for the Final Advice (currently a placeholder).

---
*Last Updated: 2024-05-28 (Enhanced Suggestion Page logic)*