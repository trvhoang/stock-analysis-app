"""
Unit tests for app/commons/common_functions.py.

Focus:
1. Statistical classification logic (Up/Down/Strong).
2. Technical score aggregation.
3. SQL data processing with BIGINT price scaling.
"""
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import date
from commons.common_functions import (
    provide_advice, 
    generate_technical_advice, 
    generate_final_advice,
    analyze_ticker,
    get_all_tickers,
    synthesize_all_advice
)

class TestCommonFunctions(unittest.TestCase):
    def setUp(self):
        # Mock result dictionary representing historical database statistics
        self.sample_stats = {
            "ticker": "FPT",
            "current_delta": 3.50,  # Percentage format
            "total_signals": 10,
            "up_count": 7,
            "down_count": 2,
            "no_change_count": 1,
            "possibility_up": 70.0,
            "possibility_down": 20.0,
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 1, 5)
        }

    # --- SECTION 1: STATISTICAL & FINAL ADVICE LOGIC ---

    def test_provide_advice_classifies_strong_up_correctly(self):
        """Verify classification as 'Strong Up' when historical win rate > 70%."""
        stats = self.sample_stats.copy()
        stats["possibility_up"] = 75.0  # Above 70 threshold
        msg, trend = provide_advice(5, 5, stats)
        
        self.assertEqual(trend, "Strong Up", "Logic Error: 75% probability should trigger 'Strong Up' trend.")
        self.assertIn("3.50%", msg, "UI Error: Advice message must display the formatted 2-decimal current delta.")

    def test_provide_advice_handles_zero_signals_gracefully(self):
        """Ensure 'Unknown' trend is returned if no historical matches exist."""
        stats = {"ticker": "XYZ", "current_delta": 1.0, "total_signals": 0}
        msg, trend = provide_advice(5, 5, stats)
        
        self.assertEqual(trend, "Unknown", "Logic Error: Zero historical signals must result in an 'Unknown' trend.")
        self.assertIn("no historical data matches", msg.lower(), "UI Error: Message should inform user about lack of historical data.")

    # --- SECTION 2: TECHNICAL INDICATOR LOGIC ---

    def test_generate_technical_advice_calculates_correct_percentage_score(self):
        """Verify the 0-100% weighting: Strong Up(4), Up(3), Sideways(2), Down(1), Strong Down(0)."""
        # Test Case: [4, 3, 3, 2] -> Sum=12. Max potential (4 indicators * 4) = 16.
        # 12 / 16 = 0.75 (75%)
        tech_data = [
            [0, "Stoch", "", "Strong Up"],
            [1, "RSI", "", "Up"],
            [2, "MA", "", "Up"],
            [3, "Cross", "", "Sideways"]
        ]
        display, trend, score = generate_technical_advice(tech_data)
        
        self.assertEqual(score, 75.0, "Calculation Error: Technical score weighting (4,3,3,2) / 16 should be 75.0.")
        self.assertEqual(trend, "Strong Up", "Logic Error: 75% technical score must map to 'Strong Up' per business rules.")

    def test_generate_technical_advice_handles_empty_input(self):
        """Ensure technical advisor returns safe defaults for empty datasets."""
        display, trend, score = generate_technical_advice([])
        self.assertEqual(trend, "Unknown", "Logic Error: Empty indicator list should return 'Unknown' trend.")
        self.assertEqual(score, 0, "Logic Error: Empty indicator list should result in a 0 score.")

    def test_final_advice_matrix_handles_conflicts_and_alignments(self):
        """Verify matrix logic from business-logic.md Section 8."""
        # Alignment case
        self.assertIn("Strong Up", generate_final_advice("FPT", "Strong Up", "Strong Up"))
        # Conflict case
        self.assertIn("Unknown", generate_final_advice("FPT", "Strong Up", "Strong Down"))
        # Neutral case
        self.assertIn("Unknown", generate_final_advice("FPT", "Sideways", "Sideways"))

    # --- SECTION 3: DATA PROCESSING & SQL MOCKING ---

    @patch('commons.common_functions.fetch_data')
    @patch('pandas.read_sql')
    def test_analyze_ticker_calculates_correct_delta_from_scaled_bigint_prices(self, mock_read_sql, mock_fetch):
        """Verify price delta math: ((Current - Prev) / Prev) * 100 using BIGINT scale."""
        # Mock data: VND 110.0 and 100.0 stored as 110000 and 100000
        df_latest = pd.DataFrame({
            "date": [date(2024, 5, 20), date(2024, 5, 15)],
            "close": [110000, 100000], 
            "exchange": ["HSX", "HSX"]
        })
        
        df_hist = pd.DataFrame([{
            "up_count": 5, "down_count": 2, "no_change_count": 3, "total_signals": 10,
            "min_up_delta": 1.0, "median_up_delta": 2.0, "max_up_delta": 5.0,
            "min_down_delta": -1.0, "median_down_delta": -2.0, "max_down_delta": -5.0
        }])

        mock_read_sql.side_effect = [df_latest, df_hist]
        mock_fetch.return_value = pd.DataFrame()
        
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.raw_connection.return_value = mock_conn

        result = analyze_ticker("TCB", 2, 5, mock_engine)

        # Math check: (110000 - 100000) / 100000 = 0.1 -> 10.0%
        self.assertEqual(result["current_delta"], 10.0, "Math Error: Delta calculation failed to handle BIGINT scaling correctly.")
        self.assertEqual(result["total_signals"], 10, "Data Error: total_signals mismatch.")
        self.assertEqual(result["possibility_up"], 50.0, "Calculation Error: Up possibility mismatch.")

    @patch('commons.common_functions.fetch_data')
    @patch('pandas.read_sql')
    def test_analyze_ticker_returns_none_when_data_is_below_day_range_threshold(self, mock_read_sql, mock_fetch):
        """Verify the function returns None when the DB returns fewer rows than day_range."""
        df_insufficient = pd.DataFrame({
            "date": [date(2024, 5, 1), date(2024, 5, 2), date(2024, 5, 3)],
            "close": [100, 101, 102]
        })
        mock_read_sql.return_value = df_insufficient
        mock_engine = MagicMock()
        
        result = analyze_ticker("FPT", 5, 5, mock_engine)
        self.assertIsNone(result, "Logic Error: analyze_ticker must return None if insufficient price history is available.")

    @patch('pandas.read_sql')
    def test_get_all_tickers_extracts_list_correctly(self, mock_read_sql):
        """Verify that the SQL result set is converted to a clean Python list."""
        mock_read_sql.return_value = pd.DataFrame({"ticker": ["FPT", "TCB", "VNM"]})
        mock_engine = MagicMock()
        
        tickers = get_all_tickers(mock_engine, 1000000, 1)
        self.assertEqual(tickers, ["FPT", "TCB", "VNM"], "Data Error: Ticker list extraction from DataFrame failed.")
        self.assertEqual(len(tickers), 3, "Data Error: Ticker count mismatch.")

    @patch('commons.common_functions.fetch_data')
    def test_synthesize_all_advice_strips_markdown_for_api_consumers(self, mock_fetch):
        """Ensure double asterisks (**) are removed from advice for cleaner JSON responses."""
        mock_fetch.return_value = pd.DataFrame()
        mock_engine = MagicMock()
        
        result = synthesize_all_advice(self.sample_stats, 5, 5, mock_engine)
        
        self.assertTrue(all(k in result for k in ["statistical", "technical", "final"]), "Schema Error: API synthesis missing required keys.")
        self.assertNotIn("**", result['statistical'], "Formatting Error: Markdown asterisks not stripped from statistical advice.")
        self.assertNotIn("**", result['final'], "Formatting Error: Markdown asterisks not stripped from final advice.")

if __name__ == '__main__':
    unittest.main()