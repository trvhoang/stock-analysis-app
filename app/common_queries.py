# common_queries.py

"""
This module contains common SQL query components used across different
analysis and visualization modules to promote reusability and maintainability.
"""

BASE_DELTA_CALC_CTE = """
    WITH trading_days AS (
        SELECT date, close,
               ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date) AS day_rank
        FROM trading_data
        WHERE ticker = :ticker
    ),
    ordered_data AS (
        SELECT date, close,
               LAG(close, :validation_days) OVER (ORDER BY date) AS prev_close,
               LEAD(close, :result_days) OVER (ORDER BY date) AS next_close,
               LAG(date, :validation_days) OVER (ORDER BY date) AS start_date,
               day_rank,
               LAG(day_rank, :validation_days) OVER (ORDER BY date) AS prev_day_rank,
               LEAD(day_rank, :result_days) OVER (ORDER BY date) AS next_day_rank
        FROM trading_days
    ),
    delta_calc AS (
        SELECT date,
               close,
               prev_close,
               next_close,
               start_date,
               CASE 
                   WHEN prev_close IS NOT NULL AND (day_rank - prev_day_rank) = :validation_days
                   THEN ROUND(((close - prev_close)::FLOAT / prev_close * 100)::NUMERIC, 2)
                   ELSE NULL 
               END AS exact_delta,
               CASE 
                   WHEN next_close IS NOT NULL AND (next_day_rank - day_rank) = :result_days
                   THEN ROUND(((next_close - close)::FLOAT / close * 100)::NUMERIC, 2)
                   ELSE NULL 
               END AS result_delta,
               CONCAT(TO_CHAR(start_date, 'DD/MM/YYYY'), ' - ', 
                      TO_CHAR(date, 'DD/MM/YYYY')) AS signal_date_range
        FROM ordered_data
    )
"""

COMMON_DELTA_FILTER_WHERE_CLAUSE = """
    WHERE exact_delta IS NOT NULL 
      AND exact_delta BETWEEN :delta_min AND :delta_max
      AND result_delta IS NOT NULL
      AND start_date IS NOT NULL
"""

# Centralized thresholds for classifying price movements (percentage)
DELTA_UP_THRESHOLD = 0.1
DELTA_DOWN_THRESHOLD = -0.1
