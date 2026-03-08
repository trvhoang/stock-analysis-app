# Project Glossary

This document defines key terms, acronyms, and concepts specific to the Stock Analysis App to ensure consistent understanding.

## Core Concepts

*   **Ticker:** The unique 3-letter symbol representing a publicly traded company on the Vietnamese stock market (e.g., `FPT`, `VNM`).
*   **Signal:** A specific price movement pattern defined by the user (e.g., "price dropped 3% over 5 days") that triggers the statistical analysis.
*   **Validation Days:** The user-defined lookback period (in trading days) over which the initial price change (the signal) is measured.
*   **Result Days:** The user-defined lookforward period (in trading days) immediately following the signal, used to measure the outcome of the trade.
*   **Delta:** The percentage change in price between two points in time.
    *   **Exact Delta:** The actual percentage change that occurred during the `Validation Days`.
    *   **Result Delta:** The percentage change that occurred during the `Result Days`.
*   **Delta Target:** The user's desired percentage change for the signal (e.g., -3.0%). The app searches for events within a range of `[Target - 1, Target + 1]`.
*   **Delta Target:** A user-defined percentage change for a signal. **Note:** This is now only used in the underlying logic for the "Ticker Analyze" tab; the Suggestion and Portfolio pages calculate this dynamically based on the stock's current delta.

## Data & Technical Terms

*   **Trading Day:** A day where the stock market was open and trading occurred. This excludes weekends and public holidays. The app uses `day_rank` to sequence these days contiguously.
*   **Day Rank:** An integer assigned to each record for a ticker, representing its sequential order in time. Used to calculate deltas across gaps (weekends/holidays) correctly.
*   **BIGINT Price:** The format used to store stock prices in the database. It is the raw price multiplied by 1000 and rounded to the nearest integer (e.g., a price of 15.5 becomes 15500).
*   **OHLCV:** Standard financial data format: **O**pen, **H**igh, **L**ow, **C**lose, **V**olume.
*   **VNINDEX:** The benchmark index for the Ho Chi Minh City Stock Exchange. It is often excluded from stock-specific analysis in this app.

## Statistical Classifications

*   **Up:** An outcome where the `Result Delta` is strictly greater than 0.1%.
*   **Down:** An outcome where the `Result Delta` is strictly less than -0.1%.
*   **No Change:** An outcome where the `Result Delta` is between -0.1% and 0.1% (inclusive).
*   **Possibility (of Result):** The historical probability of a specific outcome (Up/Down/No Change) occurring after a signal, expressed as a percentage.

## Application Pages

*   **Data Page:** The interface for downloading external ZIP files and populating the database.
*   **Result Page:** A dashboard showing general market statistics (e.g., top volume tickers).
*   **Analyze Page:** A two-tab page. The "Ticker Analyze" tab provides a deep-dive into a single ticker's historical performance based on its current signal. The "Portfolio Analyze" tab provides a high-level statistical summary for a user-defined list of tickers.
*   **Suggestion Page:** The interface for scanning the *entire market* to find tickers with the highest probability of success, based on their own unique and current price signal.