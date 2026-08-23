import unittest
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from datetime import date, timedelta
from io import StringIO
import inspect
from unittest.mock import Mock, patch

import pandas as pd

import backtest_engine.research_optimizer as optimizer
from backtest_engine.research_optimizer import (
    ResearchCandidate,
    ResearchResult,
    ResearchRun,
    apply_search_statistics,
    candidate_entry_signal,
    collect_research_from_histories,
    collect_vcb_research,
    enumerate_candidates,
    evaluate_horizon,
    main,
    rank_winners,
    render_markdown,
)
from backtest_engine.validation import PermutationResult


def _entry_frame() -> pd.DataFrame:
    """Return small causal-gate fixture with intentionally mixed rows."""

    return pd.DataFrame(
        {
            "rulebook_rsi_upcross": [True, True, True],
            "rulebook_joint_trend_pass": [False, True, True],
            "rulebook_volume_gate": [False, False, True],
            "rulebook_adx_gate": [False, False, True],
            "rulebook_missing_required_input": [False, True, False],
        },
        index=pd.date_range("2025-01-06", periods=3, freq="B"),
    )


def _events(
    count: int,
    *,
    start: date = date(2025, 1, 6),
    return_offset: float = 0.0,
):
    """Return completed native events with varied finite returns."""

    from backtest_engine.models import TradeEvent

    return tuple(
        TradeEvent(
            signal_date=start + timedelta(days=index * 3),
            entry_date=start + timedelta(days=index * 3 + 1),
            entry_price=100,
            atr=2,
            stop_loss=97,
            take_profit=105,
            exit_date=start + timedelta(days=index * 3 + 2),
            exit_price=101,
            exit_reason="timeout",
            return_pct=1.0 + return_offset + (index % 3) * 0.1,
            source_window=(start, start + timedelta(days=count * 3)),
        )
        for index in range(count)
    )


def _passing_permutation(*_args, **_kwargs) -> PermutationResult:
    return PermutationResult(
        observed_sharpe=1.0,
        p_value=0.01,
        null_sharpes=(0.0,),
        count=1000,
        seed=42,
        block_size=20,
    )


class ResearchCandidateTests(unittest.TestCase):
    def test_enumerates_each_nonempty_subset_in_both_v3_theme_variants(self):
        candidates = enumerate_candidates("swing")

        self.assertEqual(len(candidates), 30)
        self.assertEqual(
            sum(
                candidate.theme_variant == "no-background-theme"
                for candidate in candidates
            ),
            15,
        )
        self.assertEqual(
            sum(
                candidate.theme_variant == "background-theme"
                for candidate in candidates
            ),
            15,
        )
        self.assertEqual(
            candidates[0].identity,
            "swing:no-background-theme:rsi_upcross",
        )
        self.assertEqual(
            candidates[-1].identity,
            "swing:background-theme:rsi_upcross+joint_trend+volume+adx",
        )

    def test_rejects_empty_unknown_duplicate_or_reordered_gate_selection(self):
        invalid_selections = (
            (),
            ("unknown",),
            ("rsi_upcross", "rsi_upcross"),
            ("joint_trend", "rsi_upcross"),
        )

        for gates in invalid_selections:
            with self.subTest(gates=gates):
                with self.assertRaises(ValueError):
                    ResearchCandidate(
                        horizon="swing",
                        theme_variant="no-background-theme",
                        gates=gates,
                    )

    def test_selected_subset_and_missing_input_are_both_required(self):
        frame = _entry_frame()
        candidate = ResearchCandidate(
            horizon="swing",
            theme_variant="no-background-theme",
            gates=("rsi_upcross",),
        )

        actual = candidate_entry_signal(frame, candidate)

        pd.testing.assert_series_equal(
            actual,
            pd.Series([True, False, True], index=frame.index, dtype=bool),
        )

    def test_themed_candidate_requires_aligned_theme_and_never_weakens_price_entry(self):
        frame = _entry_frame()
        candidate = ResearchCandidate(
            horizon="swing",
            theme_variant="background-theme",
            gates=("rsi_upcross",),
        )
        theme = pd.Series([True, True, False], index=frame.index, dtype=bool)

        actual = candidate_entry_signal(frame, candidate, theme)

        pd.testing.assert_series_equal(
            actual,
            pd.Series([True, False, False], index=frame.index, dtype=bool),
        )
        with self.assertRaisesRegex(ValueError, "theme"):
            candidate_entry_signal(frame, candidate)
        with self.assertRaisesRegex(ValueError, "index"):
            candidate_entry_signal(
                frame,
                candidate,
                pd.Series([True, True, True], index=pd.RangeIndex(3), dtype=bool),
            )


class ResearchStatisticsTests(unittest.TestCase):
    def test_evaluates_all_candidates_through_registered_rulebook_execution(self):
        frame = _entry_frame().reset_index(names="date")
        frame["open"] = 100
        frame["high"] = 101
        frame["low"] = 99
        frame["close"] = 100
        frame["ATR_14"] = 2
        theme = pd.Series([True, True, True], index=frame.index, dtype=bool)

        with patch(
            "backtest_engine.research_optimizer.run_rulebook_trade_sequence",
            return_value=_events(5),
        ) as run_sequence, patch(
            "backtest_engine.research_optimizer.calculate_probabilistic_sharpe",
            return_value=1.0,
        ), patch(
            "backtest_engine.research_optimizer.calculate_deflated_sharpe",
            return_value=1.0,
        ), patch(
            "backtest_engine.research_optimizer.moving_block_permutation_test",
            side_effect=_passing_permutation,
        ):
            results = evaluate_horizon(frame, "swing", theme)

        self.assertEqual(len(results), 30)
        self.assertEqual(run_sequence.call_count, 30)
        for call in run_sequence.call_args_list:
            self.assertEqual(call.args[1].rulebook.horizon, "swing")
            self.assertIn(
                call.args[1].theme_variant,
                ("no-background-theme", "background-theme"),
            )

    def test_min_n_skips_every_statistical_primitive(self):
        result = ResearchResult.from_events(
            ResearchCandidate("swing", "no-background-theme", ("rsi_upcross",)),
            _events(4),
        )

        with patch(
            "backtest_engine.research_optimizer.calculate_probabilistic_sharpe"
        ) as psr, patch(
            "backtest_engine.research_optimizer.calculate_deflated_sharpe"
        ) as dsr, patch(
            "backtest_engine.research_optimizer.moving_block_permutation_test"
        ) as permutation:
            evaluated = apply_search_statistics((result,))

        self.assertEqual(evaluated[0].reason, "min_n")
        psr.assert_not_called()
        dsr.assert_not_called()
        permutation.assert_not_called()

    def test_dsr_family_keeps_pre_statistical_psr_failure(self):
        first = ResearchResult.from_events(
            ResearchCandidate("swing", "no-background-theme", ("rsi_upcross",)),
            _events(5),
        )
        second = ResearchResult.from_events(
            ResearchCandidate("swing", "background-theme", ("rsi_upcross",)),
            _events(5, return_offset=0.2),
        )

        with patch(
            "backtest_engine.research_optimizer.calculate_probabilistic_sharpe",
            side_effect=(0.5, 1.0),
        ), patch(
            "backtest_engine.research_optimizer.calculate_deflated_sharpe",
            return_value=1.0,
        ) as dsr, patch(
            "backtest_engine.research_optimizer.moving_block_permutation_test",
            side_effect=_passing_permutation,
        ):
            evaluated = apply_search_statistics((first, second))

        self.assertEqual(evaluated[0].reason, "psr")
        self.assertEqual(evaluated[1].state, "eligible")
        self.assertEqual(
            dsr.call_args.args[1],
            (first.sharpe, second.sharpe),
        )
        self.assertEqual(evaluated[1].trial_count, 2)

    def test_records_first_failed_statistical_gate(self):
        candidates = (
            ResearchResult.from_events(
                ResearchCandidate("swing", "no-background-theme", ("rsi_upcross",)),
                _events(5),
            ),
            ResearchResult.from_events(
                ResearchCandidate("swing", "background-theme", ("rsi_upcross",)),
                _events(5, return_offset=0.1),
            ),
            ResearchResult.from_events(
                ResearchCandidate(
                    "swing",
                    "no-background-theme",
                    ("joint_trend",),
                ),
                _events(5, return_offset=0.2),
            ),
        )
        failing_permutation = PermutationResult(
            observed_sharpe=1.0,
            p_value=0.06,
            null_sharpes=(0.0,),
            count=1000,
            seed=42,
            block_size=20,
        )

        with patch(
            "backtest_engine.research_optimizer.calculate_probabilistic_sharpe",
            side_effect=(0.5, 1.0, 1.0),
        ), patch(
            "backtest_engine.research_optimizer.calculate_deflated_sharpe",
            side_effect=(0.5, 1.0),
        ), patch(
            "backtest_engine.research_optimizer.moving_block_permutation_test",
            return_value=failing_permutation,
        ):
            evaluated = apply_search_statistics(candidates)

        self.assertEqual(
            tuple(result.reason for result in evaluated),
            ("psr", "dsr", "permutation"),
        )

    def test_ranking_retains_exact_ties_and_multiple_metric_labels(self):
        first = replace(
            ResearchResult.from_events(
                ResearchCandidate("swing", "no-background-theme", ("rsi_upcross",)),
                _events(5),
            ),
            state="eligible",
            reason=None,
        )
        second = replace(
            ResearchResult.from_events(
                ResearchCandidate("swing", "background-theme", ("rsi_upcross",)),
                _events(5),
            ),
            state="eligible",
            reason=None,
        )

        winners = rank_winners((first, second))

        self.assertEqual(winners["win_rate"], (first, second))
        self.assertEqual(winners["profit_pct"], (first, second))
        self.assertEqual(winners["sharpe"], (first, second))


class _Quality:
    is_valid = True
    errors = ()


class _Audit:
    status = "clean"
    errors = ()


def _raw_history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-02", periods=30, freq="B"),
            "open": [100] * 30,
            "high": [101] * 30,
            "low": [99] * 30,
            "close": [100] * 30,
            "volume": [1000] * 30,
        }
    )


def _eligible_result(horizon: str) -> ResearchResult:
    return replace(
        ResearchResult.from_events(
            ResearchCandidate(horizon, "no-background-theme", ("rsi_upcross",)),
            _events(5),
        ),
        psr=0.99,
        dsr=0.98,
        permutation_p_value=0.01,
        trial_count=30,
        state="eligible",
        reason=None,
    )


class ResearchRunnerTests(unittest.TestCase):
    def test_database_wrapper_loads_vcb_and_vnindex_once(self):
        expected = object()
        with patch(
            "backtest_engine.research_optimizer.load_ticker_history",
            side_effect=(_raw_history(), _raw_history()),
        ) as load_history, patch(
            "backtest_engine.research_optimizer.collect_research_from_histories",
            return_value=expected,
        ) as collect:
            actual = collect_vcb_research(object(), date(2026, 8, 21))

        self.assertIs(actual, expected)
        self.assertEqual(
            tuple(call.args[0] for call in load_history.call_args_list),
            ("VCB", "VNINDEX"),
        )
        self.assertEqual(load_history.call_count, 2)
        self.assertEqual(collect.call_count, 1)

    def test_in_memory_collection_builds_independent_horizon_frames_and_theme(self):
        raw = _raw_history()
        confirmation = pd.Series(
            [True] * len(raw),
            index=pd.DatetimeIndex(raw["date"]),
            dtype=bool,
        )
        frame = raw.assign(
            ATR_14=2,
            rulebook_rsi_upcross=True,
            rulebook_joint_trend_pass=True,
            rulebook_volume_gate=True,
            rulebook_adx_gate=True,
            rulebook_missing_required_input=False,
        )

        audit = _Audit()
        with patch(
            "backtest_engine.research_optimizer.validate_ohlcv",
            return_value=_Quality(),
        ) as validate, patch(
            "backtest_engine.research_optimizer.audit_history",
            return_value=audit,
        ), patch(
            "backtest_engine.research_optimizer.build_rulebook_frame",
            side_effect=(frame, frame.copy()),
        ) as build_frame, patch(
            "backtest_engine.research_optimizer.build_vnindex_confirmation",
            side_effect=(confirmation, confirmation),
        ) as build_confirmation, patch(
            "backtest_engine.research_optimizer.align_vnindex_asof",
            return_value=pd.DataFrame({"vnindex_close": [True] * len(frame)}),
        ) as align, patch(
            "backtest_engine.research_optimizer.evaluate_horizon",
            return_value=(),
        ) as evaluate:
            run = collect_research_from_histories(raw, raw, date(2026, 8, 21))

        self.assertEqual(validate.call_count, 2)
        self.assertEqual(build_frame.call_count, 2)
        self.assertEqual(
            tuple(call.args[1].horizon for call in build_frame.call_args_list),
            ("swing", "midterm"),
        )
        self.assertEqual(build_confirmation.call_count, 2)
        self.assertEqual(align.call_count, 2)
        self.assertEqual(
            tuple(call.args[1] for call in evaluate.call_args_list),
            ("swing", "midterm"),
        )
        self.assertEqual(run.vcb_rows, len(raw))
        self.assertEqual(run.vnindex_rows, len(raw))
        self.assertIs(run.vcb_audit, audit)

    def test_markdown_exposes_in_sample_contract_metrics_and_candidate_audit(self):
        run = ResearchRun(
            as_of=date(2026, 8, 21),
            source_start=date(2011, 8, 22),
            source_end=date(2026, 8, 21),
            vcb_rows=3742,
            vnindex_rows=3742,
            vcb_audit=_Audit(),
            swing_results=(_eligible_result("swing"),),
            midterm_results=(_eligible_result("midterm"),),
        )

        report = render_markdown(run)

        self.assertIn("in-sample", report)
        self.assertIn("n >= 5", report)
        self.assertIn("1,000", report)
        self.assertIn("block size 20", report)
        self.assertIn("same-horizon n >= 5", report)
        self.assertIn("## Swing", report)
        self.assertIn("## Midterm", report)
        self.assertIn("Candidate audit", report)
        self.assertIn(repr(_eligible_result("swing").sharpe), report)

    def test_optimizer_module_has_no_report_or_v3_persistence_write_path(self):
        source = inspect.getsource(optimizer)

        self.assertNotIn("save_rulebook_result", source)
        self.assertNotIn("write_text", source)
        self.assertNotIn("open(", source)

    def test_cli_writes_only_markdown_to_stdout_and_disposes_engine(self):
        run = ResearchRun(
            as_of=date(2026, 8, 21),
            source_start=date(2011, 8, 22),
            source_end=date(2026, 8, 21),
            vcb_rows=3742,
            vnindex_rows=3742,
            vcb_audit=_Audit(),
            swing_results=(_eligible_result("swing"),),
            midterm_results=(_eligible_result("midterm"),),
        )
        engine = Mock()
        output = StringIO()

        with patch(
            "pages.data_preparation.get_engine_with_retry",
            return_value=engine,
        ), patch(
            "backtest_engine.pipeline._database_url",
            return_value="postgresql://read-only",
        ), patch(
            "backtest_engine.research_optimizer.collect_vcb_research",
            return_value=run,
        ):
            with redirect_stdout(output):
                status = main(["--as-of", "2026-08-21"])

        self.assertEqual(status, 0)
        self.assertEqual(output.getvalue(), render_markdown(run))
        engine.dispose.assert_called_once_with()


class ResearchIsolationTests(unittest.TestCase):
    def test_full_grid_keeps_registered_rulebooks_immutable_and_horizons_separate(self):
        from backtest_engine.config import rulebook_for

        frame = _entry_frame().reset_index(names="date")
        frame["open"] = 100
        frame["high"] = 101
        frame["low"] = 99
        frame["close"] = 100
        frame["ATR_14"] = 2
        theme = pd.Series([True, True, True], index=frame.index, dtype=bool)
        before = {
            horizon: asdict(rulebook_for(horizon))
            for horizon in ("swing", "midterm")
        }

        with patch(
            "backtest_engine.research_optimizer.run_rulebook_trade_sequence",
            return_value=_events(5),
        ), patch(
            "backtest_engine.research_optimizer.calculate_probabilistic_sharpe",
            return_value=1.0,
        ), patch(
            "backtest_engine.research_optimizer.calculate_deflated_sharpe",
            return_value=1.0,
        ) as dsr, patch(
            "backtest_engine.research_optimizer.moving_block_permutation_test",
            side_effect=_passing_permutation,
        ):
            swing_results = evaluate_horizon(frame, "swing", theme)
            midterm_results = evaluate_horizon(frame, "midterm", theme)

        self.assertEqual(len(swing_results), 30)
        self.assertEqual(len(midterm_results), 30)
        self.assertTrue(all(result.trial_count == 30 for result in swing_results))
        self.assertTrue(all(result.trial_count == 30 for result in midterm_results))
        self.assertTrue(all(len(call.args[1]) == 30 for call in dsr.call_args_list))
        self.assertEqual(
            {
                horizon: asdict(rulebook_for(horizon))
                for horizon in ("swing", "midterm")
            },
            before,
        )


if __name__ == "__main__":
    unittest.main()
