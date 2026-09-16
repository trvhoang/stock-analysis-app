"""Evaluation and publication service contracts for Flexible Rulebook v2."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd
import pytz

from flexible_rulebook.v2.contracts import (
    EvaluationRequest,
    PredicateV2,
    PublishedRulebook,
    RulebookDefinitionV2,
    RulebookDraft,
)
from flexible_rulebook.v2.history import HistoryRange, HistorySnapshot
from flexible_rulebook.v2.service import (
    clone_draft,
    draft_is_evaluated,
    evaluate_draft,
    evaluate_published,
    evaluate_published_collection,
    inspect_current_definition,
    publish_draft,
)
from flexible_rulebook.v2.storage import list_evaluations, write_draft


HCM = pytz.timezone("Asia/Ho_Chi_Minh")
NOW = HCM.localize(datetime(2026, 9, 16, 9, 0, 0))


def _definition() -> RulebookDefinitionV2:
    return RulebookDefinitionV2(
        horizon="swing",
        entry_operator="all",
        buy_predicates=(
            PredicateV2(
                role="buy",
                family="ema",
                family_revision="ema-close-adjust-false-v1",
                settings={"fast_period": 3, "slow_period": 8},
                operator="bullish_cross",
            ),
        ),
        max_hold_bars=10,
    )


def _snapshot(ticker: str) -> HistorySnapshot:
    start = date(2026, 1, 2)
    dates = tuple(start + timedelta(days=index) for index in range(40))
    closes = [10_000 + (index % 7) * 80 - (index % 5) * 40 for index in range(40)]
    frame = pd.DataFrame(
        {
            "date": list(dates),
            "open": closes,
            "high": [value + 20 for value in closes],
            "low": [value - 20 for value in closes],
            "close": closes,
            "volume": [100 + index for index in range(40)],
        }
    )
    return HistorySnapshot(
        ticker=ticker,
        state="available",
        reason="",
        history_range=HistoryRange.lifetime(),
        start_date=dates[0],
        end_date=dates[-1],
        frame=frame,
        sessions=dates,
        excluded_sessions=(),
        source_fingerprint="a" * 64,
        calendar_fingerprint="b" * 64,
        fingerprint="c" * 64,
    )


class FlexibleRulebookV2ServiceTests(unittest.TestCase):
    def test_published_rulebook_evaluates_without_a_mutable_draft(self) -> None:
        definition = _definition()
        published = PublishedRulebook.publish(definition, published_at=NOW)
        request = EvaluationRequest(semantic_digest=definition.semantic_digest, tickers=("VCB",))
        with TemporaryDirectory() as temporary:
            result = evaluate_published(
                published,
                request,
                root=Path(temporary).resolve(),
                engine=object(),
                history_loader=lambda ticker, history_range, *, engine=None: _snapshot(ticker),
            )
        self.assertEqual("completed", result.items[0].terminal_state)
        self.assertTrue(result.items[0].current_signal_events or result.items[0].evaluation is not None)

    def test_published_collection_loads_each_ticker_once_for_multiple_definitions(self) -> None:
        first = PublishedRulebook.publish(_definition(), published_at=NOW)
        second = PublishedRulebook.publish(
            RulebookDefinitionV2(
                horizon="swing",
                entry_operator="all",
                buy_predicates=(PredicateV2(
                    role="buy", family="rsi", family_revision="rsi-wilder-sma-seeded-v1",
                    settings={"period": 9}, operator="upcross", condition={"threshold": 52},
                ),),
                max_hold_bars=10,
            ),
            published_at=NOW,
        )
        loaded: list[str] = []

        def history_loader(ticker: str, history_range: HistoryRange, *, engine: object | None = None) -> HistorySnapshot:
            loaded.append(ticker)
            return _snapshot(ticker)

        with TemporaryDirectory() as temporary:
            result = evaluate_published_collection(
                (first, second),
                tickers=("VCB",),
                root=Path(temporary).resolve(),
                engine=object(),
                history_loader=history_loader,
            )
        self.assertEqual(["VCB"], loaded)
        self.assertEqual(
            [(first.rulebook_id, "VCB", "completed"), (second.rulebook_id, "VCB", "completed")],
            [(item.rulebook_id, item.ticker, item.terminal_state) for item in result],
        )

    def test_evaluation_runs_tickers_sequentially_and_preserves_success_when_later_ticker_fails(self) -> None:
        definition = _definition()
        draft = RulebookDraft.new(name="EMA turn", definition=definition, now=NOW)
        request = EvaluationRequest(
            semantic_digest=definition.semantic_digest,
            tickers=("VCB", "FPT"),
            training_ratio=Decimal("0.65"),
        )
        progress: list[tuple[str, str, str | None]] = []

        def history_loader(ticker: str, history_range: HistoryRange, *, engine: object | None = None) -> HistorySnapshot:
            self.assertIsInstance(history_range, HistoryRange)
            if ticker == "FPT":
                raise RuntimeError("fixture source failure")
            return _snapshot(ticker)

        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            result = evaluate_draft(
                draft,
                request,
                root=root,
                engine=object(),
                history_loader=history_loader,
                on_progress=lambda item: progress.append((item.ticker, item.phase, item.terminal_state)),
            )

            self.assertEqual(tuple(item.ticker for item in result.items), ("VCB", "FPT"))
            self.assertEqual(tuple(item.terminal_state for item in result.items), ("completed", "failed"))
            self.assertIsNotNone(result.items[0].evaluation)
            self.assertIn("training", result.items[0].evaluation.metrics)
            self.assertIn("test", result.items[0].evaluation.metrics)
            self.assertIsInstance(result.items[0].evaluation.metrics["training"]["win_rate"], float)
            self.assertIsInstance(result.items[0].current_signal_events, tuple)
            self.assertTrue(all(
                set(event) == {"signal_date", "signal_bar_ordinal"}
                for event in result.items[0].current_signal_events
            ))
            self.assertEqual(len(list_evaluations(root, f"frb2_{definition.semantic_digest}")), 1)
            self.assertIn(("VCB", "persistence", "completed"), progress)
            self.assertIn(("FPT", "source", "failed"), progress)

    def test_publication_requires_explicit_intent_and_current_completed_evidence_without_metric_gate(self) -> None:
        definition = _definition()
        draft = RulebookDraft.new(name="Zero trade proof", definition=definition, now=NOW)
        request = EvaluationRequest(semantic_digest=definition.semantic_digest, tickers=("VCB",))

        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            write_draft(root, draft, expected_revision=0)
            evaluate_draft(
                draft,
                request,
                root=root,
                engine=object(),
                history_loader=lambda ticker, history_range, *, engine=None: _snapshot(ticker),
            )

            self.assertTrue(draft_is_evaluated(root, draft))
            with self.assertRaisesRegex(ValueError, "explicit"):
                publish_draft(root, draft, published_at=NOW, confirmed=False)

            published = publish_draft(root, draft, published_at=NOW, confirmed=True)
            self.assertEqual(published.definition, draft.definition)

            edited = draft.with_changes(
                definition=RulebookDefinitionV2(
                    horizon="swing",
                    entry_operator="all",
                    buy_predicates=(
                        PredicateV2(
                            role="buy",
                            family="ema",
                            family_revision="ema-close-adjust-false-v1",
                            settings={"fast_period": 5, "slow_period": 13},
                            operator="bullish_cross",
                        ),
                    ),
                    max_hold_bars=10,
                ),
                now=HCM.localize(datetime(2026, 9, 16, 10, 0, 0)),
            )
            self.assertFalse(draft_is_evaluated(root, edited))
            with self.assertRaisesRegex(ValueError, "completed train/test"):
                publish_draft(root, edited, published_at=NOW, confirmed=True)

            clone = clone_draft(root, draft, name="EMA copy", now=NOW)
            self.assertNotEqual(clone.draft_id, draft.draft_id)
            self.assertEqual(clone.definition, draft.definition)

    def test_request_digest_mismatch_fails_before_loading_history(self) -> None:
        draft = RulebookDraft.new(name="Mismatch", definition=_definition(), now=NOW)
        request = EvaluationRequest(semantic_digest="d" * 64, tickers=("VCB",))
        called = False

        def history_loader(ticker: str, history_range: HistoryRange, *, engine: object | None = None) -> HistorySnapshot:
            nonlocal called
            called = True
            return _snapshot(ticker)

        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "semantic digest"):
                evaluate_draft(
                    draft,
                    request,
                    root=Path(temporary).resolve(),
                    engine=object(),
                    history_loader=history_loader,
                )
        self.assertFalse(called)

    def test_cache_choice_never_changes_evidence_and_false_does_not_write_components(self) -> None:
        definition = _definition()
        draft = RulebookDraft.new(name="Cache proof", definition=definition, now=NOW)

        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            no_cache = evaluate_draft(
                draft,
                EvaluationRequest(
                    semantic_digest=definition.semantic_digest,
                    tickers=("VCB",),
                    use_cache=False,
                ),
                root=root,
                engine=object(),
                history_loader=lambda ticker, history_range, *, engine=None: _snapshot(ticker),
            )
            self.assertFalse((root / "v2" / "cache").exists())
            cached = evaluate_draft(
                draft,
                EvaluationRequest(
                    semantic_digest=definition.semantic_digest,
                    tickers=("VCB",),
                    use_cache=True,
                ),
                root=root,
                engine=object(),
                history_loader=lambda ticker, history_range, *, engine=None: _snapshot(ticker),
            )

            self.assertEqual(no_cache.items[0].evaluation.metrics, cached.items[0].evaluation.metrics)
            self.assertTrue((root / "v2" / "cache" / "primitives").is_dir())

    def test_current_inspection_is_read_only_and_keeps_causal_source_identity(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            inspection = inspect_current_definition(
                _definition(),
                "VCB",
                engine=object(),
                history_loader=lambda ticker, history_range, *, engine=None: _snapshot(ticker),
            )

            self.assertEqual("VCB", inspection.ticker)
            self.assertEqual("swing", inspection.horizon)
            self.assertEqual("a" * 64, inspection.source["source_fingerprint"])
            self.assertFalse((root / "v2").exists())
            self.assertIn(inspection.signal_state, {"Fresh", "On-going", "Weakening", "Invalidated"})


if __name__ == "__main__":
    unittest.main()
