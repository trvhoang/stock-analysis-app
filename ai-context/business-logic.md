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

### Trend Classification
The application determines the current trend for indicators based on the following rules:

#### Moving Average (MA) Trend
*   **Condition:** Compares the spread between the short-term and long-term MAs against the current price, and checks for reversal patterns.
*   **Sideways:** The absolute difference between the fast and slow MA is less than **2%** of the asset's closing price. `(abs(FastMA - SlowMA) / Price) < 0.02`. This check is performed first.
*   **Up:** The trend is "Up" if either of these is true:
    1.  **Default:** The fast MA is above the slow MA.
    2.  **Bullish Reversal:** The fast MA is *below* the slow MA, but both MAs have been rising for 3 consecutive periods AND the gap between them has been shrinking for 3 consecutive periods.
*   **Down:** The trend is "Down" if either of these is true:
    1.  **Default:** The fast MA is below the slow MA.
    2.  **Bearish Reversal:** The fast MA is *above* the slow MA, but both MAs have been falling for 3 consecutive periods AND the gap between them has been shrinking for 3 consecutive periods.

#### MA Cross Trend
*   **Condition:** Assesses the trend based on the last 3 significant cross events (Golden or Death crosses).
*   **Up:** If 2 or more of the last 3 crosses were Golden Crosses.
*   **Down:** If 2 or more of the last 3 crosses were Death Crosses.
*   **Sideways:** If there are mixed signals (e.g., Golden, Death, Golden).
*   **Unknown:** If there are fewer than 2 recent cross events to analyze.

#### Relative Strength Index (RSI) Trend
*   **Condition:** Assessed by analyzing the RSI's behavior over the last 30 periods (or fewer if less data is available).
*   **Sideways:** The trend is classified as "Sideways" if either of these is true:
    1.  The RSI value has been between 40 and 55 for more than 70% of the lookback period.
    2.  The total range of the RSI (max - min) over the last 20 periods is less than or equal to 15 points.
*   **Up (Bullish):**
    *   Current RSI is between 40 and 80.
    *   RSI is rising for 2 consecutive periods.
    *   Current RSI value is > 55.
    *   **Strong Up:** All "Up" conditions met, PLUS RSI has exceeded 65 at any point in the lookback window.
*   **Down (Bearish):**
    *   Current RSI is between 20 and 60.
    *   RSI is falling for 2 consecutive periods.
    *   Current RSI value is < 40.
    *   **Strong Down:** All "Down" conditions met, PLUS RSI has dropped below 30 at any point in the lookback window.
*   **Other:**
    *   **Overbought (Up):** RSI > 80.
    *   **Oversold (Down):** RSI < 20.
    *   **Unknown:** If none of the above conditions are met.

#### Stochastic Trend
*   **Condition:** Assessed by analyzing the position and crossover of the %K and %D lines.
*   **Up:** The trend is classified as "Up" if both %K and %D are above 70, or if %K has crossed above %D while both are above 50.
*   **Down:** The trend is classified as "Down" if both %K and %D are below 30, or if %K has crossed below %D while both are below 50.
*   **Sideways:** The trend is classified as "Sideways" if the lines are crossing frequently around the 50 level (indicating a "chop" zone) or if no clear up/down trend is established.

## 7. Analyze Page - Technical Report

The "Analyze Page" includes a "Technical Report" table that provides a snapshot of key technical indicators for the selected ticker. The logic for this report is dynamic and adapts based on the user's `Validation Day Range` input.

### 7.1. Dynamic Timeframe and MA Pair Selection

The core of the report's logic is the selection of an appropriate timeframe and Moving Average (MA) pair to match the user's analysis window:

-   **If `Validation Day Range` is less than or equal to 5 days:**
    -   **Timeframe:** `Day`
    -   **MA Pair:** SMA 5 and SMA 10
    -   **Rationale:** This is considered a short-term analysis, so daily data with fast-reacting MAs is most relevant.

-   **If `Validation Day Range` is greater than 5 days:**
    -   **Timeframe:** `Week`
    -   **MA Pair:** SMA 4 and SMA 12
    -   **Rationale:** For longer analysis windows, weekly data provides a clearer view of the medium-term trend, and the 4/12-week MAs (approximating 1 and 3 months) are standard for this timeframe.

### 7.2. Indicator Calculation

All indicators are calculated using a lookback period of **100 periods** (e.g., 100 days or 100 weeks) to ensure sufficient historical data for accuracy.

-   **Stochastic (10, 3, 3):** Calculated using `calculate_stochastic`. The trend is determined by `calculate_stochastic_trend`.
-   **RSI (14):** Calculated using `calculate_rsi`. The trend is determined by `calculate_rsi_trend`.
-   **Moving Average (MA):** The latest values for the dynamically selected SMA pair are displayed. The trend is determined by `calculate_ma_trend`.
-   **MA Cross:** The last three cross events (Golden or Death) are displayed. The trend is the same as the MA trend.

## 8. Final Advice Logic

The "Final Advice" on the Analyze Page is generated by combining the **Statistical Trend** (from historical probability) and the **Technical Trend** (from indicators) using a decision matrix.

### Decision Matrix

| Statistical \ Technical | Strong Up | Up | Sideways | Down | Strong Down |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Strong Up** | Strong Up | Strong Up | Up | Unknown | Unknown |
| **Up** | Up | Up | Sideways | Unknown | Unknown |
| **Sideways** | Up | Sideways | Unknown | Down | Down |
| **Down** | Unknown | Unknown | Unknown | Down | Strong Down |
| **Strong Down** | Unknown | Unknown | Unknown | Strong Down | Strong Down |

### Outcome Explanations

-   **Strong Up:** Both statistical and technical analyses are strongly bullish.
-   **Up:** Both analyses point towards a bullish outlook.
-   **Sideways:** The analyses show mixed signals, suggesting a sideways movement.
-   **Down:** Both analyses point towards a bearish outlook.
-   **Strong Down:** Both statistical and technical analyses are strongly bearish.
-   **Unknown:** The statistical and technical signals are conflicting, leading to an uncertain outlook.