# Coding Conventions & Standards

## 1. DO's (Must Follow)

### Database Interactions
*   **Rule:** Always use `sqlalchemy.text()` for SQL queries.
    *   **Reason:** Ensures compatibility with SQLAlchemy versions and proper handling of SQL statements.
    *   **Example:**
        ```python
        # Correct
        query = text("SELECT * FROM table WHERE id = :id")
        # Incorrect
        query = "SELECT * FROM table WHERE id = " + str(id)
        ```

*   **Rule:** Always use parameter binding (`params` dict) for dynamic values in SQL.
    *   **Reason:** Prevents SQL injection and handles data type conversion automatically.
    *   **Example:**
        ```python
        # Correct
        pd.read_sql(query, engine, params={"ticker": "FPT"})
        # Incorrect
        pd.read_sql(f"SELECT * FROM data WHERE ticker = '{ticker}'", engine)
        ```

*   **Rule:** Use `get_engine_with_retry()` for database connections.
    *   **Reason:** Handles transient connection failures, especially in Dockerized environments.

### Data Handling
*   **Rule:** Respect the `BIGINT` price format (Price * 1000).
    *   **Reason:** The database stores prices as integers to avoid floating-point errors.
    *   **Example:**
        ```python
        # Correct
        chunk["Close"] = (chunk["Close"] * 1000).round().astype('int64')
        ```

## 2. DON'Ts (Never Do)

*   **Rule:** Never hardcode database credentials or sensitive keys.
    *   **Reason:** Security risk. Use `os.getenv()` and `.env` files.
    *   **Example:**
        ```python
        # Correct
        user = os.getenv("POSTGRES_USER")
        # Incorrect
        user = "admin"
        ```

*   **Rule:** Do not duplicate the Delta Calculation Logic.
    *   **Reason:** The core logic for `exact_delta` and `result_delta` is centralized in `common_queries.py`.
    *   **Example:**
        ```python
        # Correct
        from commons.common_queries import BASE_DELTA_CALC_CTE
        query_str = BASE_DELTA_CALC_CTE + "SELECT ..."
        # Incorrect
        query_str = "WITH trading_days AS (SELECT ... ) ..." # Re-writing the CTE manually
        ```

## 3. Patterns (Standard Approaches)

### SQL Query Construction
*   **Pattern:** Construct complex queries by concatenating modular CTE strings from `common_queries.py`.
*   **Example:**
    ```python
    from commons.common_queries import BASE_DELTA_CALC_CTE, COMMON_DELTA_FILTER_WHERE_CLAUSE
    
    query_str = BASE_DELTA_CALC_CTE + """
        SELECT date, result_delta FROM delta_calc
    """ + COMMON_DELTA_FILTER_WHERE_CLAUSE
    
    query = text(query_str)
    ```

### Streamlit Data Display
*   **Pattern:** Use `use_container_width=True` for DataFrames to ensure responsive layout.
*   **Example:**
    ```python
    st.dataframe(df, use_container_width=True)
    ```

## 4. Anti-patterns (Avoid These)

### Ignoring Timezones
*   **Anti-pattern:** Using `datetime.now()` without timezone info for report dates.
*   **Correction:** Use `pytz.timezone('Asia/Ho_Chi_Minh')` to ensure alignment with the Vietnamese market close times.