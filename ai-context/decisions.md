# Architecture Decision Records (ADR) Log

This document records significant architectural and design decisions made during the development of the Stock Analysis App. Its purpose is to provide context, rationale, and consequences for key choices, preventing future AI tools from re-evaluating already settled matters.

---

## ADR 001: Database Choice - PostgreSQL

*   **Decision:** PostgreSQL was chosen as the primary relational database.
*   **Date:** 2023-10-27
*   **Context:** The application requires a robust, reliable, and scalable database to store historical stock trading data (OHLCV) for multiple tickers over extended periods. It needs to support complex SQL queries, including window functions and aggregate functions, for statistical analysis.
*   **Alternatives Considered:**
    *   **SQLite:** Evaluated for simplicity and embedded nature.
    *   **MySQL:** Considered as a popular open-source alternative.
*   **Reason:** PostgreSQL offers advanced SQL features (like `LAG`, `LEAD`, `ROW_NUMBER`, `PERCENTILE_CONT`, `FILTER` clause for aggregates) that are heavily utilized in the analytical queries. It provides strong data integrity, extensibility, and is well-suited for analytical workloads. Its Docker image is also mature and easy to integrate.
*   **Consequences:** Requires a separate database service (e.g., in Docker Compose), increasing deployment complexity slightly compared to an embedded database like SQLite. However, this is offset by its performance and feature set.

---

## ADR 002: Price Data Storage Format - BIGINT (Scaled by 1000)

*   **Decision:** All price-related data (Open, High, Low, Close) are stored as `BIGINT` integers in the database, after being multiplied by 1000 and rounded.
*   **Date:** 2023-10-27
*   **Context:** Financial calculations often involve floating-point numbers, which can lead to precision issues and unexpected rounding errors in databases. The Vietnamese Dong (VND) currency typically has large nominal values but no decimal places, making integer storage a natural fit after scaling.
*   **Alternatives Considered:**
    *   **FLOAT/DOUBLE PRECISION:** Standard floating-point types.
    *   **NUMERIC/DECIMAL:** Arbitrary precision numeric types.
*   **Reason:** Storing prices as scaled integers (`BIGINT`) completely eliminates floating-point precision issues inherent in `FLOAT` or `DOUBLE PRECISION` types. While `NUMERIC/DECIMAL` also offers precision, `BIGINT` is generally more performant for exact arithmetic and storage, especially given the nature of VND values. The scaling factor of 1000 provides sufficient precision for typical stock price movements.
*   **Consequences:** Requires explicit scaling (`* 1000`) during data ingestion and inverse scaling (`/ 1000`) or careful handling during display and calculation (though percentage deltas inherently handle this). This conversion logic must be consistently applied.

---

## ADR 003: User Interface Framework - Streamlit

*   **Decision:** Streamlit was chosen for building the interactive web-based user interface.
*   **Date:** 2023-10-27
*   **Context:** The project requires a rapid development environment for creating interactive data dashboards and analytical tools, primarily driven by Python. The focus is on quick prototyping and ease of data visualization.
*   **Alternatives Considered:**
    *   **Flask/Django with a frontend framework (e.g., React, Vue):** Traditional web development stack.
    *   **Dash by Plotly:** Another Python-based dashboarding framework.
*   **Reason:** Streamlit allows for extremely fast development of data applications directly in Python, minimizing the need for separate frontend development. Its component model is intuitive for data scientists and analysts. The project prioritizes rapid iteration and Python-centric development.
*   **Consequences:** Streamlit's flexibility for complex, highly customized UI/UX is limited compared to traditional web frameworks. Performance can sometimes be an issue with very large datasets or complex interactions, though this is mitigated by efficient data fetching and processing.

---

## ADR 004: Containerization - Docker and Docker Compose

*   **Decision:** The entire application (Streamlit app and PostgreSQL database) is containerized using Docker and orchestrated with Docker Compose.
*   **Date:** 2023-10-27
*   **Context:** To ensure consistent development, testing, and deployment environments, and to simplify dependency management for both the Python application and the database.
*   **Alternatives Considered:**
    *   **Manual installation of dependencies:** Installing Python, PostgreSQL, and libraries directly on the host machine.
    *   **Virtual Machines:** Using tools like Vagrant.
*   **Reason:** Docker provides isolated, reproducible environments, eliminating "it works on my machine" issues. Docker Compose simplifies the management of multi-container applications, making it easy to set up and tear down the entire stack with a single command. This is crucial for local development and potential future deployment.
*   **Consequences:** Adds a layer of abstraction and requires familiarity with Docker concepts. Initial setup might be slightly more involved than running a single Python script, but benefits outweigh this for a multi-service application.

---

## ADR 005: Centralized SQL CTEs in `common_queries.py`

*   **Decision:** Common SQL Common Table Expressions (CTEs) and filtering clauses are extracted into `common_queries.py`.
*   **Date:** 2023-10-27
*   **Context:** The core logic for calculating price deltas (`BASE_DELTA_CALC_CTE`) and common filtering conditions (`COMMON_DELTA_FILTER_WHERE_CLAUSE`) was duplicated across `analyze_visualization.py` and `suggestion_visualization.py`. This led to redundancy and increased maintenance effort.
*   **Alternatives Considered:**
    *   **Inline SQL:** Keeping the full SQL query string within each visualization file.
    *   **SQL files:** Storing SQL queries in separate `.sql` files and loading them.
*   **Reason:** Centralizing these components in `common_queries.py` promotes code reusability, improves maintainability (changes to core logic only need to be made in one place), and enhances readability of the visualization-specific query parts. It also makes the SQL easier to test and review.
*   **Consequences:** Introduces an additional Python module. Requires careful management of parameter names to ensure consistency between the Python code and the SQL templates. Modifications to `common_queries.py` have a broad impact and require thorough testing.

---

## ADR 006: Database Connection Retry Logic

*   **Decision:** A `get_engine_with_retry` function is implemented to establish database connections with multiple retries and delays.
*   **Date:** 2023-10-27
*   **Context:** In a Docker Compose setup, the application container might start before the database container is fully initialized and ready to accept connections. This can lead to connection errors on application startup.
*   **Alternatives Considered:**
    *   **Docker Compose `depends_on` with `condition: service_healthy`:** This is used, but `get_engine_with_retry` provides an additional layer of robustness for the application itself.
    *   **Simple `create_engine` without retries:** This would lead to application crashes if the DB isn't immediately available.
*   **Reason:** Ensures the application can gracefully handle transient database unavailability during startup, making the system more resilient and user-friendly. It prevents the Streamlit app from failing immediately if the DB takes a moment longer to spin up.
*   **Consequences:** Adds a slight delay to application startup if the database is not immediately available.

---

## ADR 007: Timezone-Aware Date Handling for Report Dates

*   **Decision:** `pytz.timezone('Asia/Ho_Chi_Minh')` is used to determine the current time and default report dates, specifically considering the 8 PM cutoff for the previous day's data.
*   **Date:** 2023-10-27
*   **Context:** The stock market data is specific to Vietnam, which operates in the GMT+7 timezone. The availability of daily data (e.g., for the "report date") is typically after market close, often around 8 PM local time. Using naive `datetime.now()` could lead to incorrect report dates depending on the server's timezone or the exact time of execution.
*   **Alternatives Considered:**
    *   **Using naive `datetime.now()`:** Simpler, but prone to timezone errors.
    *   **Hardcoding a UTC offset:** Less flexible if daylight saving rules change (though Vietnam doesn't observe it).
*   **Reason:** Ensures that the "last trading day" and "default report date" logic accurately reflects the Vietnamese market's operational hours and data availability, regardless of where the application server is physically located. This is critical for data freshness and correctness.
*   **Consequences:** Requires the `pytz` library as a dependency.

---

## ADR 008: Ticker Filtering for Market-Wide Analysis

*   **Decision:** Market-wide analysis (e.g., in `suggestion_visualization.py`) explicitly filters out 'VNINDEX', requires tickers to have recent trading activity (last year), and excludes tickers with low average volume or zero-volume days.
*   **Date:** 2023-10-27
*   **Context:** The "Suggestion Page" aims to provide reliable trading signals for actual stocks. Including indices or illiquid/restricted stocks would skew results and provide misleading advice to users.
*   **Alternatives Considered:**
    *   **No filtering:** Analyze all available tickers.
    *   **Simpler filtering:** Only exclude VNINDEX.
*   **Reason:**
    *   **Exclude 'VNINDEX':** VNINDEX is a market index, not a tradable stock, and its behavior is different from individual equities.
    *   **Recent activity:** Ensures only currently active and relevant stocks are considered, removing delisted or dormant ones.
    *   **Average volume filter:** Removes highly illiquid stocks that are prone to manipulation or have unreliable price movements, making statistical analysis less meaningful.
    *   **No zero-volume days:** Identifies stocks that might be under trading restrictions or facing delisting, which are high-risk and unreliable for statistical pattern recognition.
*   **Consequences:** Reduces the total number of tickers analyzed, potentially missing some niche opportunities but significantly improving the quality and reliability of the suggestions provided. The filtering logic adds complexity to the `get_all_tickers` SQL query.

---

## ADR 009: Dynamic Delta Calculation and Logic Centralization

*   **Decision:** Refactored the core analysis logic to be "context-aware" by dynamically calculating the current delta for each ticker instead of requiring a manual `delta_target` input. The shared analysis function `analyze_ticker` was moved to a new `app/common_functions.py` module.
*   **Date:** 2023-10-28 (Assumed date)
*   **Context:** The original workflow required users to guess a relevant `delta_target`. This was not user-friendly and disconnected the analysis from the stock's actual current situation. Furthermore, the logic to perform a high-level analysis was needed by both the "Suggestion" page and the new "Portfolio Analyze" feature.
*   **Alternatives Considered:**
    *   **Keeping manual input:** Retaining the old workflow.
    *   **Duplicating logic:** Copying the analysis function into `analyze_visualization.py` for the portfolio tab.
*   **Reason:**
    1.  **Dynamic Delta:** Makes the tool significantly more powerful and relevant by analyzing the *current* market signal automatically.
    2.  **Centralization:** Moving `analyze_ticker` to `common_functions.py` follows the DRY (Don't Repeat Yourself) principle, improving maintainability and ensuring consistent statistical output across different pages.
    2.  **Centralization:** Moving `analyze_ticker` to `common_functions.py` follows the DRY (Don't Repeat Yourself) principle. It is used by the "Suggestion" page, the "Portfolio Analyze" tab, and (as of a recent refactoring) the "Ticker Analyze" tab. This ensures consistent statistical output across all features.
*   **Consequences:** The `analyze_visualization.py` and `suggestion_visualization.py` modules now have a dependency on `common_functions.py`. The user-facing UI is simplified by removing an input field.
*   **Consequences:** The `analyze_visualization.py` and `suggestion_visualization.py` modules now have a dependency on `common_functions.py`. The user-facing UI is simplified. The full refactoring of the "Ticker Analyze" tab has eliminated duplicated helper functions (`get_latest_delta`, `create_analyzed_statistical_report`) and resolved the "Fragile String Parsing" technical debt by consuming numeric data directly.