"""Persistent lifecycle contracts for user-authored Flexible Rulebook v2."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

import pytz

from flexible_rulebook.v2.contracts import (
    AtrExitV2,
    EvaluationResult,
    PredicateV2,
    PublishedRulebook,
    RulebookDefinitionV2,
    RulebookDraft,
)
from flexible_rulebook.v2.storage import (
    discard_draft,
    list_drafts,
    list_published_rulebooks,
    read_draft,
    read_evaluation,
    retire_rulebook,
    unretire_rulebook,
    write_draft,
    write_evaluation,
    write_published_rulebook,
)


HCM = pytz.timezone("Asia/Ho_Chi_Minh")
NOW = HCM.localize(datetime(2026, 9, 16, 9, 0, 0))


def _definition(*, threshold: int = 52) -> RulebookDefinitionV2:
    return RulebookDefinitionV2(
        horizon="swing",
        entry_operator="all",
        buy_predicates=(
            PredicateV2(
                role="buy",
                family="rsi",
                family_revision="rsi-wilder-sma-seeded-v1",
                settings={"period": 9},
                operator="upcross",
                condition={"threshold": threshold},
            ),
        ),
        atr_exit=AtrExitV2(stop_multiplier=Decimal("1.5")),
        max_hold_bars=22,
    )


def _evaluation(definition: RulebookDefinitionV2, *, ticker: str = "VCB") -> EvaluationResult:
    return EvaluationResult.completed(
        semantic_digest=definition.semantic_digest,
        ticker=ticker,
        source={"start": "2011-01-01", "end": "2026-09-16", "fingerprint": "a" * 64},
        split={"training": {"n": 0}, "test": {"n": 0}, "ratio": Decimal("0.65")},
        metrics={"training": {"n": 0}, "test": {"n": 0}},
        trades=(),
        warnings=("No completed trade is still completed evidence.",),
    )


class FlexibleRulebookV2StorageTests(unittest.TestCase):
    def test_draft_write_round_trips_from_v2_only_canonical_path(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            legacy = root / "rulebooks" / "legacy.json"
            legacy.parent.mkdir()
            legacy.write_text('{"legacy":true}', encoding="utf-8")
            draft = RulebookDraft.new(name="RSI turn", definition=_definition(), now=NOW)

            path = write_draft(root, draft, expected_revision=0)
            restored = read_draft(root, draft.draft_id)

            self.assertEqual(path, root / "v2" / "drafts" / f"{draft.draft_id}.json")
            self.assertEqual(restored, draft)
            self.assertEqual(legacy.read_text(encoding="utf-8"), '{"legacy":true}')
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["artifact_kind"], "flexible_rulebook_v2_draft")
            self.assertFalse(tuple(path.parent.glob("*.tmp")))

    def test_stale_draft_revision_fails_without_overwriting_newer_document(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            original = RulebookDraft.new(name="Original", definition=_definition(), now=NOW)
            write_draft(root, original, expected_revision=0)
            edited = original.with_changes(
                name="Edited",
                definition=_definition(threshold=55),
                now=HCM.localize(datetime(2026, 9, 16, 10, 0, 0)),
            )
            write_draft(root, edited, expected_revision=1)

            with self.assertRaisesRegex(ValueError, "stale draft revision"):
                write_draft(root, original, expected_revision=1)

            self.assertEqual(read_draft(root, original.draft_id), edited)

    def test_draft_library_lists_only_valid_v2_drafts_in_stable_order(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            alpha = RulebookDraft.new(name="Alpha", definition=_definition(), now=NOW)
            beta = RulebookDraft.new(name="Beta", definition=_definition(threshold=55), now=NOW)
            write_draft(root, beta, expected_revision=0)
            write_draft(root, alpha, expected_revision=0)
            malformed = root / "v2" / "drafts" / "00000000-0000-0000-0000-000000000000.json"
            malformed.write_text("not-json", encoding="utf-8")

            self.assertEqual(tuple(item.name for item in list_drafts(root)), ("Alpha", "Beta"))

    def test_evaluation_reader_rejects_document_whose_content_no_longer_matches_its_id(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            definition = _definition()
            rulebook_id = PublishedRulebook.publish(definition, published_at=NOW).rulebook_id
            path = write_evaluation(root, rulebook_id, _evaluation(definition))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["evaluation"]["metrics"]["training"]["n"] = 99
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "identity"):
                read_evaluation(root, path)

    def test_published_definition_and_zero_trade_evaluation_are_immutable(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            definition = _definition()
            published = PublishedRulebook.publish(definition, published_at=NOW)
            evaluation = _evaluation(definition)

            definition_path = write_published_rulebook(root, published)
            evaluation_path = write_evaluation(root, published.rulebook_id, evaluation)
            self.assertEqual(write_published_rulebook(root, published), definition_path)
            self.assertEqual(write_evaluation(root, published.rulebook_id, evaluation), evaluation_path)

            stored_rulebook_id, restored = read_evaluation(root, evaluation_path)
            self.assertEqual(stored_rulebook_id, published.rulebook_id)
            self.assertTrue(restored.is_completed)
            self.assertEqual(restored.metrics["training"]["n"], 0)
            self.assertEqual(definition_path.parent, root / "v2" / "definitions")
            self.assertEqual(evaluation_path.parents[2], root / "v2" / "evaluations")

            conflicting = _evaluation(_definition(threshold=55))
            with self.assertRaisesRegex(ValueError, "semantic digest"):
                write_evaluation(root, published.rulebook_id, conflicting)

    def test_corrupt_or_unsupported_documents_are_safe_errors_and_retirement_preserves_reference(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            draft = RulebookDraft.new(name="Corrupt", definition=_definition(), now=NOW)
            path = write_draft(root, draft, expected_revision=0)
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unreadable"):
                read_draft(root, draft.draft_id)
            path.write_text('{"schema_version":999,"artifact_kind":"unknown"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported schema"):
                read_draft(root, draft.draft_id)

            published = PublishedRulebook.publish(_definition(), published_at=NOW)
            write_published_rulebook(root, published)
            evidence_path = write_evaluation(root, published.rulebook_id, _evaluation(published.definition))
            retirement = retire_rulebook(
                root,
                published.rulebook_id,
                retired_at=HCM.localize(datetime(2026, 9, 16, 11, 0, 0)),
            )
            self.assertTrue(retirement.is_file())
            library = list_published_rulebooks(root)
            self.assertEqual(library, (published.retire(retired_at=HCM.localize(datetime(2026, 9, 16, 11, 0, 0))),))
            unretire_rulebook(
                root,
                published.rulebook_id,
                unretired_at=HCM.localize(datetime(2026, 9, 16, 12, 0, 0)),
            )
            self.assertEqual(list_published_rulebooks(root, include_retired=False), (published,))
            self.assertEqual(read_evaluation(root, evidence_path)[1].ticker, "VCB")

            with self.assertRaisesRegex(ValueError, "confirmation"):
                discard_draft(root, draft.draft_id, confirmed=False)
            self.assertTrue(discard_draft(root, draft.draft_id, confirmed=True))


if __name__ == "__main__":
    unittest.main()
