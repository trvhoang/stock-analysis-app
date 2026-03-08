# AI Context: Stock Analysis App

## 1. Purpose
This folder (`/ai-context`) is the **Single Source of Truth** for any AI agent working on this project. It contains all the necessary information to understand the project's goals, architecture, business logic, and coding standards.

**Your Goal:** MUST read and internalize the contents of this folder before attempting any code modifications or answering complex queries. This ensures consistency, prevents regression, and aligns your output with the project's established patterns.

## 2. Reading Order (Strict)
Follow this sequence to build your understanding layer by layer:

1.  **`project-overview.md`**: Understand the "Why" and "What" of the application.
2.  **`architecture.md`**: Learn the system design, data flow, and tech stack.
3.  **`business-logic.md`**: Master the core rules, formulas, and domain knowledge.
4.  **`conventions.md`**: Memorize the coding standards and style guidelines.
5.  **`decisions.md`**: Review past architectural choices to understand the "How".
6.  **`boundaries.md`**: Know what is off-limits and where to exercise extreme caution. (Date: 2023-10-27)
7.  **`workflows.md`**: Understand how to build, test, and deploy features.
8.  **`glossary.md`**: Clarify project-specific terminology.
9.  **`current-status.md`**: Check the latest progress and immediate priorities.

## 3. Quick Start Summary
The Stock Analysis App is a Python-based web tool (Streamlit) that helps investors validate trading strategies on the Vietnamese stock market. It ingests daily OHLCV data from external ZIP files into a PostgreSQL database, storing prices as `BIGINT` (multiplied by 1000). Users define a "signal" (e.g., a 3% drop over 5 days) and the app scans historical data to report the statistical probability of subsequent price movements (Up/Down/No Change). The core logic relies on calculating percentage deltas over specific time windows (`validation_days` and `result_days`). The app is containerized using Docker and Docker Compose for easy deployment.
The core logic is "context-aware", meaning it automatically calculates a stock's current price change and uses that as the signal to find historical matches, rather than requiring a manual target from the user.

## 4. Critical Rules (DO NOT VIOLATE)
*   **DO NOT** modify the `common_queries.py` file without explicit instruction and thorough impact analysis, as it affects multiple visualization pages.
*   **DO NOT** change the data storage format (BIGINT for prices) or the VND conversion logic (`price * 1000`).
*   **DO NOT** introduce new external dependencies unless absolutely necessary and approved.
*   **DO NOT** hardcode sensitive credentials; always use environment variables.
*   **DO** always use the `get_engine_with_retry` function for database connections.
*   **DO** ensure all SQL queries use parameter binding to prevent injection.

## 5. Handling Unknowns
If you encounter a situation, error, or requirement that is not covered by the documentation in this folder:
1.  **Stop.** Do not make assumptions.
2.  **Ask** the user for clarification, referencing the specific gap in your knowledge.
3.  **Propose** a solution based on established patterns if possible, but wait for confirmation.

---

**Confirmation Protocol:**
If you have read all files in this folder, confirm by saying:
> "I have fully reviewed the ai-context folder and I am ready to work."