import unittest
from datetime import date
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from unittest.mock import MagicMock, patch

import pandas as pd

try:
    from streamlit.testing.v1 import AppTest
except ModuleNotFoundError:
    AppTest = None
    sys.modules["streamlit"] = MagicMock()

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    sys.modules["requests"] = MagicMock()

try:
    import psycopg2.extras  # noqa: F401
except ModuleNotFoundError:
    psycopg2_module = ModuleType("psycopg2")
    extras_module = ModuleType("psycopg2.extras")
    extras_module.execute_values = MagicMock()
    psycopg2_module.extras = extras_module
    sys.modules["psycopg2"] = psycopg2_module
    sys.modules["psycopg2.extras"] = extras_module

import pages.data_preparation as data_preparation


class DataPreparationTests(unittest.TestCase):
    def test_trading_day_and_report_date_helpers_skip_weekend(self):
        self.assertEqual(data_preparation.get_last_trading_day(date(2026, 8, 15)), date(2026, 8, 14))
        self.assertEqual(data_preparation.get_last_trading_day(date(2026, 8, 16)), date(2026, 8, 14))
        self.assertEqual(data_preparation.get_last_trading_day(date(2026, 8, 17)), date(2026, 8, 17))

    def test_source_url_selects_stock_or_index_and_rejects_unknown_type(self):
        stock_url, stock_filter = data_preparation._source_url(date(2026, 8, 16), "stock")
        self.assertIn("20260814", stock_url)
        self.assertIn("14082026", stock_url)
        self.assertIsNone(stock_filter)
        index_url, index_filter = data_preparation._source_url(date(2026, 8, 16), "index")
        self.assertIn("CafeF.Index", index_url)
        self.assertEqual(index_filter, "VNINDEX")
        with self.assertRaisesRegex(ValueError, "Unknown data_type"):
            data_preparation._source_url(date(2026, 8, 16), "other")

    def test_exchange_detection_and_optional_progress_reporting_are_deterministic(self):
        self.assertEqual(data_preparation._exchange_for_file(Path("prices_HSX.csv")), "HSX")
        self.assertEqual(data_preparation._exchange_for_file(Path("prices_hnx.csv")), "HNX")
        self.assertEqual(data_preparation._exchange_for_file(Path("prices_UPCOM.csv")), "UPCOM")
        self.assertEqual(data_preparation._exchange_for_file(Path("prices.csv")), "Unknown")
        callback = MagicMock()
        data_preparation._report_phase(callback, 50, "halfway")
        callback.assert_called_once_with(50, "halfway")
        data_preparation._report_phase(None, 100, "done")

    @patch.object(data_preparation, "execute_values")
    def test_stage_chunk_preserves_bigint_price_scaling_and_deduplicates_rows(self, mock_execute_values):
        chunk = pd.DataFrame(
            {
                "ticker": ["FPT", "FPT"],
                "exchange": ["HSX", "HSX"],
                "date": [date(2026, 8, 14), date(2026, 8, 14)],
                "Open": [20.125, 20.125],
                "High": [21.250, 21.250],
                "Low": [19.875, 19.875],
                "Close": [20.500, 20.500],
                "Volume": [1234.6, 9999.0],
            }
        )
        staged_count = data_preparation._stage_chunk(MagicMock(), chunk)

        self.assertEqual(staged_count, 1)
        rows = mock_execute_values.call_args.args[2]
        self.assertEqual(rows, [["FPT", "HSX", date(2026, 8, 14), 20125, 21250, 19875, 20500, 1235]])
        self.assertEqual(chunk.loc[0, "Close"], 20.500)

    def test_init_db_commits_schema_and_rolls_back_on_schema_failure(self):
        engine = MagicMock()
        connection = engine.raw_connection.return_value
        cursor = connection.cursor.return_value
        with patch.object(data_preparation, "_ensure_schema") as ensure_schema:
            data_preparation.init_db(engine)
        ensure_schema.assert_called_once_with(cursor)
        connection.commit.assert_called_once_with()
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()

        engine = MagicMock()
        connection = engine.raw_connection.return_value
        with patch.object(data_preparation, "_ensure_schema", side_effect=ValueError("bad schema")):
            with self.assertRaisesRegex(ValueError, "bad schema"):
                data_preparation.init_db(engine)
        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_eligible_chunk_keeps_only_new_rows_without_historical_replacement(self):
        selector = getattr(data_preparation, "_eligible_chunk", None)
        self.assertTrue(callable(selector), "append-only eligibility selector is required")
        frame = pd.DataFrame(
            {
                "Ticker": ["FPT", "FPT", "VCB", "MBB"],
                "DTYYYYMMDD": pd.to_datetime(
                    ["2026-08-10", "2026-08-11", "2026-08-01", "2020-01-01"]
                ).date,
            }
        )

        eligible = selector(
            frame,
            {"FPT": date(2026, 8, 10)},
            date(2021, 8, 14),
            ticker_filter=None,
            exchange="HSX",
        )

        self.assertEqual(
            eligible[["ticker", "date"]].values.tolist(),
            [["FPT", date(2026, 8, 11)], ["VCB", date(2026, 8, 1)]],
        )

    def test_run_full_ingestion_downloads_both_sources_before_one_commit(self):
        source_type = getattr(data_preparation, "ExtractedSource", None)
        self.assertIsNotNone(source_type, "source-first ingestion contract is required")
        progress = []
        engine = MagicMock()
        connection = MagicMock()
        cursor = MagicMock()
        engine.raw_connection.return_value = connection
        connection.cursor.return_value = cursor

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stock = source_type("stock", root / "stock", None)
            index = source_type("index", root / "index", "VNINDEX")
            with patch.object(
                data_preparation, "_download_and_extract_source", side_effect=(stock, index)
            ) as download, patch.object(
                data_preparation, "_ensure_schema"
            ), patch.object(
                data_preparation, "_latest_dates", return_value={"FPT": date(2026, 8, 10)}
            ), patch.object(data_preparation, "_stage_source") as stage:
                result = data_preparation.run_full_ingestion(
                    date(2026, 8, 14),
                    15,
                    engine,
                    progress_callback=lambda value, label: progress.append((value, label)),
                )

        self.assertTrue(result)
        self.assertEqual(download.call_count, 2)
        self.assertEqual(connection.commit.call_count, 1)
        connection.rollback.assert_not_called()
        self.assertEqual(stage.call_count, 2)
        self.assertNotIn(
            "DROP TABLE",
            "\n".join(str(call_info) for call_info in cursor.execute.call_args_list).upper(),
        )
        self.assertEqual(progress[0][0], 0)
        self.assertEqual(progress[-1][0], 100)

    def test_run_full_ingestion_rolls_back_every_new_row_when_index_stage_fails(self):
        source_type = getattr(data_preparation, "ExtractedSource", None)
        self.assertIsNotNone(source_type, "source-first ingestion contract is required")
        engine = MagicMock()
        connection = MagicMock()
        cursor = MagicMock()
        engine.raw_connection.return_value = connection
        connection.cursor.return_value = cursor

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stock = source_type("stock", root / "stock", None)
            index = source_type("index", root / "index", "VNINDEX")
            with patch.object(
                data_preparation, "_download_and_extract_source", side_effect=(stock, index)
            ), patch.object(data_preparation, "_ensure_schema"), patch.object(
                data_preparation, "_latest_dates", return_value={}
            ), patch.object(
                data_preparation,
                "_stage_source",
                side_effect=(None, ValueError("index staging failed")),
            ):
                result = data_preparation.run_full_ingestion(date(2026, 8, 14), 15, engine)

        self.assertFalse(result)
        connection.commit.assert_not_called()
        self.assertEqual(connection.rollback.call_count, 1)

    def test_download_failure_never_opens_a_database_connection(self):
        engine = MagicMock()

        with patch.object(
            data_preparation,
            "_download_and_extract_source",
            side_effect=OSError("stock download failed"),
        ):
            result = data_preparation.run_full_ingestion(date(2026, 8, 14), 15, engine)

        self.assertFalse(result)
        engine.raw_connection.assert_not_called()

    @unittest.skipIf(AppTest is None, "host interpreter has no Streamlit runtime")
    def test_data_page_has_approved_control_row_and_progress_ui(self):
        """Catch a vertical control layout, spinner reuse, or missing phase display."""
        callback_received = []

        def run_ingestion(report_date, gaps_of_data, engine, progress_callback=None):
            callback_received.append(progress_callback)
            if progress_callback is not None:
                progress_callback(0, "Starting data ingestion...")
                progress_callback(100, "Data ingestion complete.")
            return True

        with patch.object(
            data_preparation, "run_full_ingestion", side_effect=run_ingestion
        ), patch.object(
            data_preparation.st,
            "spinner",
            side_effect=AssertionError("Data Page must use a progress bar, not a spinner."),
        ):
            app = AppTest.from_string(
                "from pages.data_preparation import data_page\n"
                "data_page(None)\n"
            ).run()

            self.assertEqual([widget.label for widget in app.date_input], ["Up-to date"])
            self.assertEqual([widget.label for widget in app.number_input], ["Year gaps"])
            self.assertEqual(app.number_input[0].value, 15)
            self.assertEqual([widget.label for widget in app.button], ["Get data"])
            self.assertEqual([item.value for item in app.caption], ["Action"])

            app.button[0].click().run()

        self.assertEqual(app.exception, [])
        self.assertEqual(len(app.get("progress")), 1)
        self.assertEqual(
            [(item.label, item.proto.expanded) for item in app.expander],
            [("Progress details", True)],
        )
        self.assertEqual(len(callback_received), 1)
        self.assertIsNotNone(callback_received[0])


if __name__ == "__main__":
    unittest.main()
