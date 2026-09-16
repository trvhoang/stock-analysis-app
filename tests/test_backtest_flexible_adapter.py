"""Distinct Flexible signal-artifact contracts; Standard schema-5 stays separate."""

from __future__ import annotations

from datetime import date, datetime, timezone
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backtest_engine.flexible_adapter import (
    build_flexible_signal_artifact,
    collect_published_flexible_signals,
    flexible_signal_artifact_path,
    load_flexible_signal_artifact,
    replay_flexible_signal_artifact,
    write_flexible_signal_artifact,
)
from flexible_rulebook.v2.service import CurrentRulebookInspection, PublishedCollectionItem
from backtest_engine.persistence import signal_artifact_path
from backtest_engine.signal_removal import (
    SignalCandidateKey,
    SignalRemovalBlockedError,
    remove_saved_signal_candidates,
)
from backtest_engine.manual_position_store import create_manual_position
from backtest_engine.signal_catalog import list_current_signal_set_rows
from flexible_rulebook.v2.contracts import (
    AtrExitV2,
    EvaluationResult,
    PredicateV2,
    PublishedRulebook,
    RulebookDefinitionV2,
)
from flexible_rulebook.v2.storage import evaluation_id_for


def _published() -> PublishedRulebook:
    definition = RulebookDefinitionV2(
        horizon="swing",
        entry_operator="all",
        buy_predicates=(PredicateV2(
            role="buy",
            family="rsi",
            family_revision="rsi-wilder-sma-seeded-v1",
            settings={"period": 9},
            operator="upcross",
            condition={"threshold": 52},
        ),),
        max_hold_bars=22,
    )
    return PublishedRulebook.publish(
        definition,
        published_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )


def _evaluation(published: PublishedRulebook) -> EvaluationResult:
    return EvaluationResult.completed(
        semantic_digest=published.definition.semantic_digest,
        ticker="VCB",
        source={
            "source_fingerprint": "a" * 64,
            "calendar_fingerprint": "b" * 64,
            "snapshot_fingerprint": "c" * 64,
            "end_date": date(2026, 9, 15),
        },
        split={"training": {"start": "2016-01-01"}, "test": {"start": "2022-01-01"}},
        metrics={
            "training": {"n": 12, "win_rate": 60.0, "total_return_pct": 15.0, "sharpe": 1.0},
            "test": {"n": 5, "win_rate": 40.0, "total_return_pct": 2.0, "sharpe": 0.2},
        },
    )


class FlexibleSignalArtifactTests(unittest.TestCase):
    def test_decimal_definition_and_evaluation_evidence_round_trip(self) -> None:
        """Flexible artifacts preserve Decimal evidence using the v2 canonical form."""

        base = _published()
        definition = RulebookDefinitionV2(
            horizon="swing",
            entry_operator="all",
            buy_predicates=base.definition.buy_predicates,
            atr_exit=AtrExitV2(stop_multiplier=Decimal("1.5"), target_multiplier=Decimal("2.5")),
            max_hold_bars=22,
        )
        published = PublishedRulebook.publish(
            definition,
            published_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
        )
        evaluation = EvaluationResult.completed(
            semantic_digest=definition.semantic_digest,
            ticker="VCB",
            source={
                "source_fingerprint": "a" * 64,
                "calendar_fingerprint": "b" * 64,
                "snapshot_fingerprint": "c" * 64,
            },
            split={"training_ratio": Decimal("0.65")},
            metrics={"training": {"n": 12}, "test": {"n": 5}},
        )
        artifact = build_flexible_signal_artifact(
            published,
            evaluation,
            evaluation_id=evaluation_id_for(published.rulebook_id, evaluation),
            current_signal_events=(),
        )

        with TemporaryDirectory() as directory:
            restored = load_flexible_signal_artifact(
                write_flexible_signal_artifact(artifact, directory)
            )

        self.assertEqual({"$decimal": "1.5"}, restored["rulebook_definition"]["atr_exit"]["stop_multiplier"])
        self.assertEqual({"$decimal": "0.65"}, restored["evaluation"]["split"]["training_ratio"])

    def test_round_trip_is_distinct_from_schema5_and_keeps_full_identity_backstage(self) -> None:
        published = _published()
        evaluation = _evaluation(published)
        artifact = build_flexible_signal_artifact(
            published,
            evaluation,
            evaluation_id=evaluation_id_for(published.rulebook_id, evaluation),
            current_signal_events=({"signal_date": date(2026, 9, 15), "signal_bar_ordinal": 42},),
        )
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = write_flexible_signal_artifact(artifact, str(root))
            restored = load_flexible_signal_artifact(path)

            self.assertNotEqual(
                path,
                signal_artifact_path("VCB", "swing", str(root)),
            )

        self.assertEqual(1, restored["schema_version"])
        self.assertEqual("flexible_rulebook_signal_v1", restored["artifact_kind"])
        self.assertEqual(published.rulebook_id, restored["rulebook_id"])
        self.assertEqual(
            evaluation_id_for(published.rulebook_id, evaluation),
            restored["evaluation_reference"]["evaluation_id"],
        )
        self.assertEqual("2026-09-15", restored["current_signal_events"][0]["signal_date"])

    def test_rejects_an_evaluation_id_that_does_not_belong_to_the_evidence(self) -> None:
        published = _published()
        with self.assertRaisesRegex(ValueError, "evaluation_id"):
            build_flexible_signal_artifact(
                published,
                _evaluation(published),
                evaluation_id="frev2_" + "d" * 64,
                current_signal_events=(),
            )

    def test_paths_keep_each_published_rulebook_separate(self) -> None:
        first = _published()
        second_definition = RulebookDefinitionV2(
            horizon="swing",
            entry_operator="all",
            buy_predicates=(PredicateV2(
                role="buy",
                family="rsi",
                family_revision="rsi-wilder-sma-seeded-v1",
                settings={"period": 14},
                operator="upcross",
                condition={"threshold": 52},
            ),),
            max_hold_bars=22,
        )
        second = PublishedRulebook.publish(
            second_definition,
            published_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temporary:
            self.assertNotEqual(
                flexible_signal_artifact_path("VCB", "swing", first.rulebook_id, temporary),
                flexible_signal_artifact_path("VCB", "swing", second.rulebook_id, temporary),
            )

    def test_catalog_projects_flexible_evidence_without_schema5_coercion(self) -> None:
        published = _published()
        evaluation = _evaluation(published)
        artifact = build_flexible_signal_artifact(
            published,
            evaluation,
            evaluation_id=evaluation_id_for(published.rulebook_id, evaluation),
            current_signal_events=({"signal_date": "2026-09-15", "signal_bar_ordinal": 42},),
        )
        with TemporaryDirectory() as directory:
            write_flexible_signal_artifact(artifact, directory)
            catalog = list_current_signal_set_rows(directory)

        self.assertEqual(1, len(catalog["valid"]))
        row = catalog["valid"][0]
        self.assertEqual("flexible", row["_origin"])
        self.assertTrue(str(row["Rulebook"]).startswith("Flexible · FR-"))
        self.assertEqual(published.rulebook_id, row["_rulebook_id"])
        self.assertEqual("2026-09-15", row["_signal_date"])

    def test_collection_persists_one_distinct_artifact_per_completed_rulebook_ticker(self) -> None:
        published = _published()
        evaluation = _evaluation(published)

        def collect(*_args, **_kwargs):
            return (PublishedCollectionItem(
                rulebook_id=published.rulebook_id,
                ticker="VCB",
                terminal_state="completed",
                evaluation=evaluation,
                current_signal_events=({"signal_date": date(2026, 9, 15), "signal_bar_ordinal": 42},),
            ),)

        with TemporaryDirectory() as directory:
            outcome = collect_published_flexible_signals(
                (published,),
                tickers=("VCB",),
                signal_dir=directory,
                v2_root=Path(directory).resolve(),
                collection_fn=collect,
            )
            artifact = load_flexible_signal_artifact(outcome[0].artifact_path)

        self.assertEqual("completed", outcome[0].terminal_state)
        self.assertEqual(published.rulebook_id, artifact["rulebook_id"])

    def test_flexible_removal_writes_an_origin_specific_empty_artifact(self) -> None:
        published = _published()
        evaluation = _evaluation(published)
        artifact = build_flexible_signal_artifact(
            published,
            evaluation,
            evaluation_id=evaluation_id_for(published.rulebook_id, evaluation),
            current_signal_events=({"signal_date": "2026-09-15", "signal_bar_ordinal": 42},),
        )
        with TemporaryDirectory() as directory:
            write_flexible_signal_artifact(artifact, directory)
            removed = remove_saved_signal_candidates(
                [SignalCandidateKey("VCB", "swing", published.rulebook_id, "flexible")],
                signal_dir=directory,
                positions_dir=str(Path(directory) / "positions"),
            )
            restored = load_flexible_signal_artifact(
                flexible_signal_artifact_path("VCB", "swing", published.rulebook_id, directory)
            )
            catalog = list_current_signal_set_rows(directory)

        self.assertEqual("flexible", removed.removed[0].origin)
        self.assertEqual("empty", restored["terminal_state"])
        self.assertEqual([], restored["current_signal_events"])
        self.assertEqual([], catalog["valid"])
        self.assertEqual("flexible", catalog["terminal"][0]["origin"])

    def test_replay_requires_the_frozen_flexible_source_identity(self) -> None:
        published = _published()
        evaluation = _evaluation(published)
        artifact = build_flexible_signal_artifact(
            published,
            evaluation,
            evaluation_id=evaluation_id_for(published.rulebook_id, evaluation),
            current_signal_events=(),
        )
        inspection = CurrentRulebookInspection(
            ticker="VCB",
            horizon="swing",
            source={
                "source_fingerprint": "a" * 64,
                "calendar_fingerprint": "b" * 64,
                "snapshot_fingerprint": "c" * 64,
            },
            as_of_date=date(2026, 9, 15),
            latest_close=10_000.0,
            latest_atr=100.0,
            has_prior_event=False,
            signal_date=None,
            signal_state="Invalidated",
            age_native_bars=None,
            support_percentage=0.0,
            live_entry_support=False,
            all_gates_support=True,
            technical_exit=False,
            current_signal_events=(),
        )
        with patch("backtest_engine.flexible_adapter.inspect_current_definition", return_value=inspection):
            replay = replay_flexible_signal_artifact(artifact, engine=object())
        self.assertIs(replay["inspection"], inspection)
        mismatch = deepcopy(artifact)
        mismatch["evaluation_reference"]["source_fingerprint"] = "d" * 64
        mismatch["evaluation"]["source"]["source_fingerprint"] = "d" * 64
        with patch("backtest_engine.flexible_adapter.inspect_current_definition", return_value=inspection):
            with self.assertRaisesRegex(ValueError, "source_history_changed"):
                replay_flexible_signal_artifact(mismatch, engine=object())

    def test_flexible_removal_is_blocked_by_a_flexible_position_reference(self) -> None:
        published = _published()
        evaluation = _evaluation(published)
        artifact = build_flexible_signal_artifact(
            published,
            evaluation,
            evaluation_id=evaluation_id_for(published.rulebook_id, evaluation),
            current_signal_events=(),
        )
        reference = {
            "schema_version": 6,
            "contract_version": "flexible_rulebook_signal_v1",
            "origin": "flexible",
            "ticker": "VCB",
            "horizon": "swing",
            "rulebook_id": published.rulebook_id,
            "semantic_digest": published.definition.semantic_digest,
            "evaluation_id": artifact["evaluation_reference"]["evaluation_id"],
            "evaluation_label": "Exploratory — gross",
            "metrics": {
                "training": {"n": 12, "win_rate": 60.0, "profit_pct": 15.0, "sharpe": 1.0},
                "test": {"n": 5, "win_rate": 40.0, "profit_pct": 2.0, "sharpe": 0.2},
            },
        }
        with TemporaryDirectory() as directory:
            write_flexible_signal_artifact(artifact, directory)
            positions = Path(directory) / "positions"
            create_manual_position(
                "VCB", 50_000, "2026-09-15", signal_reference=reference,
                entry_context={"match_level": 100.0, "current_price": 50_000, "as_of_date": "2026-09-15"},
                risk_snapshot={"atr": 1000, "stop_loss": 48_500, "take_profit": 52_500, "max_hold_bars": 22},
                positions_dir=str(positions),
            )
            with self.assertRaises(SignalRemovalBlockedError):
                remove_saved_signal_candidates(
                    [SignalCandidateKey("VCB", "swing", published.rulebook_id, "flexible")],
                    signal_dir=directory,
                    positions_dir=str(positions),
                )


if __name__ == "__main__":
    unittest.main()
