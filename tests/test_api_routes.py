"""Contract tests for the FastAPI routes without live database or ingestion work."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import BackgroundTasks, HTTPException

from apis import routes


def _request_with_engine() -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=object())))


class ApiRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_normalizes_ticker_and_projects_synthesized_advice(self) -> None:
        stats = {
            "start_date": datetime(2026, 1, 2),
            "end_date": datetime(2026, 1, 9),
            "current_delta": 2.75,
        }
        with (
            patch.object(routes, "analyze_ticker", return_value=stats) as analyze,
            patch.object(
                routes,
                "synthesize_all_advice",
                return_value={"statistical": "stat", "technical": "tech", "final": "final"},
            ) as synthesize,
        ):
            result = await routes.trigger_ticker_analyze("fpt", _request_with_engine(), 5, 10)

        self.assertEqual("FPT", result.ticker)
        self.assertEqual("Current 5-Day Delta: 2.75% (02/01/2026 - 09/01/2026)", result.signal)
        self.assertEqual(("stat", "tech", "final"), (result.statistical_advice, result.technical_advice, result.final_advice))
        analyze.assert_called_once_with("FPT", 5, 10, unittest.mock.ANY)
        synthesize.assert_called_once_with(stats, 5, 10, unittest.mock.ANY)

    async def test_analyze_returns_404_when_analysis_has_no_data(self) -> None:
        with patch.object(routes, "analyze_ticker", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                await routes.trigger_ticker_analyze("FPT", _request_with_engine())

        self.assertEqual(404, raised.exception.status_code)
        self.assertIn("FPT", raised.exception.detail)

    async def test_suggestions_rank_only_jointly_bullish_tickers(self) -> None:
        records = {
            "AAA": {
                "ticker": "AAA", "exchange": "HNX", "stat_trend": "Up", "tech_trend": "Up",
                "possibility_up": 70.0, "max_up_delta": 11.0, "total_signals": 4,
            },
            "BBB": {
                "ticker": "BBB", "exchange": "HSX", "stat_trend": "Strong Up", "tech_trend": "Strong Up",
                "possibility_up": 70.0, "max_up_delta": 14.0, "total_signals": 5,
            },
            "CCC": {
                "ticker": "CCC", "exchange": "HSX", "stat_trend": "Down", "tech_trend": "Strong Up",
                "possibility_up": 99.0, "max_up_delta": 99.0, "total_signals": 9,
            },
        }
        with (
            patch.object(routes, "get_all_tickers", return_value=list(records)),
            patch.object(routes, "analyze_ticker", side_effect=lambda ticker, *_: records[ticker]),
        ):
            result = await routes.get_suggestions(_request_with_engine())

        self.assertEqual(["BBB", "AAA"], [item.ticker for item in result.top_possibility_up])
        self.assertEqual(["BBB", "AAA"], [item.ticker for item in result.top_delta_up])

    async def test_prepare_data_returns_busy_without_scheduling_work(self) -> None:
        tasks = BackgroundTasks()
        with patch.object(routes, "data_prep_lock", Mock(locked=Mock(return_value=True))):
            result = await routes.trigger_data_preparation(tasks, _request_with_engine())

        self.assertEqual("busy", result.status)
        self.assertEqual([], tasks.tasks)

    async def test_prepare_data_rejects_bad_date_and_schedules_valid_request(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await routes.trigger_data_preparation(BackgroundTasks(), _request_with_engine(), report_date="09/01/2026")
        self.assertEqual(400, raised.exception.status_code)

        tasks = BackgroundTasks()
        with patch.object(routes, "data_prep_lock", Mock(locked=Mock(return_value=False))):
            result = await routes.trigger_data_preparation(
                tasks, _request_with_engine(), report_date="2026-01-09", years=3
            )

        self.assertEqual("accepted", result.status)
        self.assertEqual(date(2026, 1, 9), tasks.tasks[0].args[0])
        self.assertEqual(3, tasks.tasks[0].args[1])
        self.assertIs(tasks.tasks[0].func, routes.run_full_ingestion)


if __name__ == "__main__":
    unittest.main()
