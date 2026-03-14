# Project Boundaries & Sensitive Areas

This document defines areas of the codebase that are either off-limits for modification or require extreme caution and explicit user approval before any changes are made. Its purpose is to prevent regressions, security vulnerabilities, and breaking changes to core functionality.

## 1. Critical Boundaries (DO NOT MODIFY)

These areas are fundamental to the application's architecture and business logic. Unauthorized changes will break the system. (Date: 2024-05-25 - Date updated)

### Core Delta Calculation Logic
*   **File(s):** `app/common_queries.py`
*   **What:** The SQL strings `BASE_DELTA_CALC_CTE` and `COMMON_DELTA_FILTER_WHERE_CLAUSE`.
*   **Why:** This is the centralized, single source of truth for the application's primary analytical function. It has been refactored to prevent duplication and ensure consistency across the "Analyze" and "Suggestion" pages.
*   **Consequences of Violation:** Any change will have a cascading effect on all analytical outputs, potentially corrupting statistical results and providing incorrect advice to the user.

### Price Data Storage Format
*   **File(s):** `app/data_preparation.py` (ingestion), `trading_data` table schema.
*   **What:** The logic that scales prices by 1000 and stores them as `BIGINT` in the database.
*   **Why:** This was an explicit architectural decision (see `decisions.md` - ADR 002) to avoid floating-point precision errors with financial data. All calculations and data handling assume this format.
*   **Consequences of Violation:** Changing this will lead to data corruption, incorrect delta calculations, and will break the entire application from data ingestion to final analysis.

### Database Credentials and Environment Loading
*   **File(s):** `.env`, `app/main.py`
*   **What:** The `.env` file containing secrets and the `load_dotenv()` and `os.getenv()` logic used to load the `DATABASE_URL`.
*   **Why:** This is a critical security boundary. Hardcoding credentials or altering how they are loaded can expose sensitive information.
*   **Consequences of Violation:** High risk of security vulnerabilities, including exposing database credentials in source control.

## 2. Sensitive Areas (Modify with Extreme Caution)

Changes to these areas are possible but require a deep understanding of their impact and explicit user confirmation.

### Data Ingestion Pipeline
*   **File(s):** `app/data_preparation.py`
*   **What:** The functions responsible for downloading ZIP files from the external URL (`cafef1.mediacdn.vn`), unzipping them, and inserting data into the database.
*   **Why:** This logic is tightly coupled to an external data source and its specific file format. The URL is a fixed dependency.
*   **Consequences of Modification:** Incorrectly modifying the download or parsing logic can lead to incomplete data, data corruption, or complete failure of the data update process.

### Docker Environment Configuration
*   **File(s):** `docker-compose.yml`, `Dockerfile`
*   **What:** The configuration that defines the application services, network, volumes, and dependencies.
*   **Why:** This setup ensures a reproducible and consistent environment for development and deployment.
*   **Consequences of Modification:** Uninformed changes can break the local development environment, cause services to fail to start, or lead to data loss (e.g., by misconfiguring the database volume).

### Database Connection Retry Logic
*   **File(s):** `app/data_preparation.py`
*   **What:** The `get_engine_with_retry()` function.
*   **Why:** This function provides resilience during application startup, especially in a containerized environment where the app may start before the database is ready.
*   **Consequences of Modification:** Removing or altering this logic can make the application fragile and prone to crashing on startup if the database connection is not immediately available.