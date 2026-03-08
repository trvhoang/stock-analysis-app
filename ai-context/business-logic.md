# Business Logic & Domain Rules

This document outlines the core business rules, formulas, and domain-specific logic that drive the Stock Analysis App.

## 1. Stock Data Handling

### Price Storage (BIGINT)
*   **What:** All price data (Open, High, Low, Close) is stored in the database as `BIGINT`, calculated as `ROUND(Price * 1000)`.
*   **Why:** The Vietnamese Dong (VND) has high nominal values and no decimal subdivisions in stock trading. Storing as integers eliminates floating-point precision errors during storage and retrieval, ensuring exact arithmetic.

### Ticker Filtering (Suggestion Page)
*   **What:** When scanning the market for suggestions, the app applies strict filters:
    1.  **Exclude 'VNINDEX':** The market index is removed.
    2.  **Active Status:** Tickers must have at least one record in the last 365 days.
    3.  **Volume Threshold:** Tickers must have an average volume $\ge$ `min_avg_volume` (user input).
    4.  **No Zero-Volume Days:** Tickers with *any* 0 volume trading days in the last year are excluded.
*   **Why:**
    *   VNINDEX is not a tradable stock.
    *   Low volume or zero-volume days indicate illiquidity, trading restrictions (e.g., suspended stocks), or high manipulation risk. Statistical analysis on such stocks is unreliable.

## 2. Delta Calculation Formulas

The core of the application is the "Delta" calculation, defined in `common_queries.py`.

### Trading Days & Ranking
*   **What:** Analysis is based on *trading days*, not calendar days. We use `ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date)` to rank days.
*   **Why:** Markets are closed on weekends and holidays. A "5-day change" refers to 5 trading sessions, regardless of how many calendar days pass.

### Exact Delta (The Signal)

**2.1 Day Range and Window Definition**
*   **What:** All user inputs for time periods (e.g., "Validation Day Range", "Day Range") refer to a window of `N` trading days.
*   **Logic:** A `day_range` of 5 means a 5-trading-day window (e.g., Monday to Friday). The delta is calculated between the close price of the first day and the last day in this window.
*   **Implementation:** This is achieved using a SQL `LAG` function with a value of `N-1`. For a 5-day range, the lag is 4. The minimum valid range is 2 (a lag of 1).

### Exact Delta (The Signal)
*   **Formula:** $\frac{\text{Close}_{\text{current}} - \text{Close}_{\text{prev}}}{\text{Close}_{\text{prev}}} \times 100$
*   **Context:** Calculated over a lookback period of `validation_days`.
*   **Logic:**
    *   `prev_close` is the closing price `validation_days` ago.
    *   The gap between the current day rank and previous day rank must equal `validation_days` to ensure data continuity.

### Result Delta (The Outcome)
*   **Formula:** $\frac{\text{Close}_{\text{next}} - \text{Close}_{\text{current}}}{\text{Close}_{\text{current}}} \times 100$
*   **Context:** Calculated over a lookforward period of `result_days`.
*   **Logic:**
    *   `next_close` is the closing price `result_days` into the future.
    *   Measures the profitability of the trade if entered on the signal date.

## 3. Statistical Classification

Outcomes (`result_delta`) are classified into three categories to generate probabilities.

### Thresholds
*   **Up:** `result_delta > 0.1%`
*   **Down:** `result_delta < -0.1%`
*   **No Change:** `-0.1% <= result_delta <= 0.1%`

### Probability Calculation
*   **What:** $\text{Possibility} = \frac{\text{Count of Specific Outcome}}{\text{Total Signals}} \times 100$
*   **Why:** Provides a percentage-based confidence level for each outcome (e.g., "70% chance of going Up").

## 4. Advice Generation Logic

### Predictive Advice
*   **What:** The app looks at the *latest* available block of `validation_days` for a ticker.
*   **Logic (Analyze Page):**
    1.  Calculate the `latest_delta` for the most recent `validation_days`.
    2.  Use this `latest_delta` as the target to find all similar historical events (within a `[latest_delta - 1, latest_delta + 1]` range).
    3.  Calculate historical probabilities based on those events.
    4.  **Advice:** "Based on historical data, after a [current delta] event, the stock is more likely to go **[Highest Probability Outcome]**."
*   **Why:** Connects past statistical patterns directly to the *current* market situation to aid decision-making, without requiring user guesswork for the signal.

## 5. Confirmed Business Rules

1.  **Dynamic Target Range Window:** The app automatically calculates the current delta for a ticker over `validation_days` and searches for historical events in the range `[current_delta - 1, current_delta + 1]`.
2.  **Timezone:** All "current date" logic for reports defaults to `Asia/Ho_Chi_Minh` (GMT+7).
3.  **Data Cutoff:** Daily reports are generated based on the assumption that data for the current day is available after 8:00 PM GMT+7.
4.  **Rounding:** All percentage deltas are rounded to 2 decimal places.

## 6. Technical Indicator Logic

### Timeframe Resampling (Weekly/Monthly)
*   **What:** To generate 'Week' or 'Month' data, the application fetches a larger-than-required set of daily data. It then uses pandas `resample()` to aggregate this daily data into the target timeframe.
*   **Logic:**
    *   **Aggregation:** `{'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}`.
    *   **Data Integrity:** Any resampled period with no trading data (e.g., a week full of holidays) is dropped using `dropna()` to ensure data continuity.

### Moving Average Cross (MA Cross)
*   **What:** The system identifies Golden Cross and Death Cross signals based on two Simple Moving Averages (SMAs).
*   **Logic:**
    *   **Golden Cross:** A bullish signal where the short-term SMA crosses *above* the long-term SMA. (`short_ma > long_ma` now, and `short_ma <= long_ma` in the previous period).
    *   **Death Cross:** A bearish signal where the short-term SMA crosses *below* the long-term SMA. (`short_ma < long_ma` now, and `short_ma >= long_ma` in the previous period).