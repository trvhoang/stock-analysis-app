"""Flexible-only immutable schema-1 document storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import hashlib
from collections.abc import Sequence

from .contracts import FeatureResolutionReceipt, RulebookDefinition, RulebookEvaluation, animal_alias, canonical_json, rulebook_id
from .metrics import qualifies


_LEDGER_PROVENANCE_FIELDS = frozenset({
    "candidate_space_hash", "candidate_space_size", "candidate_space_algorithm_version",
    "canonical_index", "global_slot", "stratum_id", "stratum_slot", "assignment_hash",
    "frontier_algorithm_version", "stratification_revision", "stratum_multiplier",
    "stratum_offset", "stratum_quota", "seed_fingerprint", "feature_receipt_id", "outcome",
})


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _path_component(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError(f"{name} must be a contained path component")
    return value


def _validate_selection_snapshot(snapshot: dict[str, object]) -> None:
    required = {"input_ledger_digest", "input_evaluation_digest", "selection_scope", "selection_policy_revision", "pairing_algorithm_revision", "ranked_rulebook_ids", "selected_rulebook_ids", "blocker_relations"}
    if not required <= set(snapshot) or not _is_digest(snapshot.get("input_ledger_digest")) or not _is_digest(snapshot.get("input_evaluation_digest")):
        raise ValueError("selection snapshot lacks immutable chain evidence")
    ranked, selected, blockers = snapshot["ranked_rulebook_ids"], snapshot["selected_rulebook_ids"], snapshot["blocker_relations"]
    if not isinstance(snapshot["selection_scope"], str) or not snapshot["selection_scope"] or not all(isinstance(item, str) for item in ranked) or not all(isinstance(item, str) for item in selected) or not isinstance(blockers, list):
        raise ValueError("selection snapshot is malformed")
    if len(selected) > 3 or len(set(ranked)) != len(ranked) or len(set(selected)) != len(selected) or not set(selected) <= set(ranked):
        raise ValueError("selection snapshot rank or Top 3 is invalid")
    for relation in blockers:
        if not isinstance(relation, dict) or not {"blocked_rulebook_id", "representative_rulebook_id", "overlap_numerator", "overlap_denominator"} <= set(relation):
            raise ValueError("selection snapshot blocker relation is incomplete")
        numerator, denominator = relation["overlap_numerator"], relation["overlap_denominator"]
        if isinstance(numerator, bool) or isinstance(denominator, bool) or not isinstance(numerator, int) or not isinstance(denominator, int) or not 0 <= numerator <= denominator or denominator == 0:
            raise ValueError("selection snapshot overlap evidence must be exact integers")


def resolve_flexible_root() -> Path:
    """Return package-relative development root; never depend on process CWD."""

    return (Path(__file__).resolve().parents[1] / "Flexible-Rulebook").resolve()


def _contained_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible storage root must be absolute")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _write_immutable(path: Path, payload: dict[str, object]) -> Path:
    material = canonical_json(payload)
    if path.exists():
        if path.read_text(encoding="utf-8") != material:
            raise ValueError("immutable Flexible document already differs")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name); stream.write(material); stream.flush(); os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != material:
            raise ValueError("immutable Flexible document already differs")
    finally:
        if temporary.exists(): temporary.unlink()
    return path


def write_rulebook_definition(root: Path, definition: RulebookDefinition) -> Path:
    """Persist one portable definition once, without mutable rank/result state."""

    if not isinstance(definition, RulebookDefinition):
        raise ValueError("definition must be RulebookDefinition")
    base = _contained_root(root)
    identifier = rulebook_id(definition)
    path = (base / "rulebooks" / f"{identifier}.json").resolve()
    if base not in path.parents:
        raise ValueError("definition path escapes Flexible root")
    return _write_immutable(path, {"schema_version": 1, "artifact_kind": "flexible_rulebook_definition", "rulebook_id": identifier, "animal_alias": animal_alias(identifier), "definition": definition.to_semantic_dict()})


def _trade_payload(trade: object) -> dict[str, object]:
    return {
        "trade_id": trade.trade_id, "signal_date": trade.signal_date.isoformat(),
        "entry_date": trade.entry_date.isoformat(), "exit_date": trade.exit_date.isoformat(),
        "signal_bar_ordinal": trade.signal_bar_ordinal, "entry_bar_ordinal": trade.entry_bar_ordinal,
        "exit_bar_ordinal": trade.exit_bar_ordinal, "entry_price": trade.entry_price,
        "exit_price": trade.exit_price, "exit_reason": trade.exit_reason, "return_pct": trade.return_pct,
    }


def write_signal_set(root: Path, evaluation: RulebookEvaluation, *, explicitly_saved: bool = False, discovery_provenance: dict[str, object] | None = None) -> Path:
    """Write one self-contained immutable evidence document per evaluation."""

    if not isinstance(evaluation, RulebookEvaluation):
        raise ValueError("evaluation must be RulebookEvaluation")
    if not isinstance(explicitly_saved, bool):
        raise ValueError("explicitly_saved must be bool")
    qualified = qualifies(evaluation.training_metrics, evaluation.test_metrics)
    if not qualified and not explicitly_saved:
        raise ValueError("signal set must be qualified or explicitly saved")
    base = _contained_root(root); identifier = evaluation.evaluation_id
    path = (base / "signal-sets" / evaluation.rulebook_id / evaluation.ticker / f"{identifier}.json").resolve()
    if base not in path.parents: raise ValueError("signal-set path escapes Flexible root")
    snapshot = evaluation.source_snapshot
    if discovery_provenance is not None and (not isinstance(discovery_provenance, dict) or not (_LEDGER_PROVENANCE_FIELDS - {"outcome"}) <= set(discovery_provenance)):
        raise ValueError("signal-set discovery provenance is incomplete")
    payload = {
        "schema_version": 1, "artifact_kind": "flexible_rulebook_signal_set", "evaluation_id": identifier,
        "rulebook_id": evaluation.rulebook_id, "animal_alias": animal_alias(evaluation.rulebook_id),
        "ticker": evaluation.ticker, "catalog_hash": evaluation.catalog_hash,
        "qualification_revision": evaluation.qualification_revision, "definition": evaluation.definition.to_semantic_dict(),
        "source_snapshot": snapshot.to_identity_dict(), "feature_build_contract": evaluation.feature_build_contract.to_identity_dict(),
        "feature_profile": evaluation.feature_profile.to_identity_dict(), "feature_receipt": evaluation.feature_receipt.to_identity_dict(),
        "split": evaluation.split.to_identity_dict(), "execution_contract": evaluation.execution_contract.to_identity_dict(),
        "training_metrics": evaluation.training_metrics.to_dict(), "test_metrics": evaluation.test_metrics.to_dict(),
        "persistence_reason": "qualified" if qualified else "explicitly_saved",
        "completed_trades": {"training": [_trade_payload(item) for item in evaluation.training_trades], "test": [_trade_payload(item) for item in evaluation.test_trades]},
        "evidence_source_anchor": {"ticker": snapshot.ticker, "first_date": snapshot.first_date.isoformat(), "as_of_date": snapshot.as_of_date.isoformat(), "prefix_fingerprint": snapshot.raw_history_fingerprint},
    }
    if discovery_provenance is not None:
        payload["discovery_provenance"] = discovery_provenance
    return _write_immutable(path, payload)


def read_signal_set(path: Path) -> dict[str, object]:
    """Read only a valid immutable schema-1 Flexible signal-set document."""

    try: payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise ValueError("signal-set document is unreadable") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("artifact_kind") != "flexible_rulebook_signal_set":
        raise ValueError("document is not a schema-1 Flexible signal set")
    required = {"definition", "completed_trades", "feature_build_contract", "evidence_source_anchor"}
    if not required <= set(payload): raise ValueError("signal-set document is incomplete")
    return payload


def iter_signal_set_paths(root: Path) -> tuple[Path, ...]:
    """Return only persisted signal-set evidence; never expose cache files."""

    signals_root = _contained_root(root) / "signal-sets"
    if not signals_root.is_dir():
        return ()
    return tuple(sorted(path for path in signals_root.rglob("*.json") if path.is_file()))


def write_feature_resolution_receipt(root: Path, campaign_id: str, ticker: str, receipt: FeatureResolutionReceipt) -> Path:
    """Persist immutable feature bytes proof before any campaign ledger slot."""

    campaign_id = _path_component(campaign_id, "campaign_id")
    ticker = _path_component(ticker, "ticker").upper()
    if not isinstance(receipt, FeatureResolutionReceipt): raise ValueError("receipt must be FeatureResolutionReceipt")
    base = _contained_root(root); path = (base / "campaigns" / campaign_id / "features" / f"{ticker}-{receipt.plan.feature_plan_hash}.json").resolve()
    if base not in path.parents: raise ValueError("receipt path escapes Flexible root")
    return _write_immutable(path, {"schema_version": 1, "artifact_kind": "flexible_feature_receipt", "receipt_id": receipt.receipt_id, "receipt": receipt.to_identity_dict()})


def append_ledger_chunk(root: Path, campaign_id: str, ticker: str, rows: Sequence[dict[str, object]]) -> Path:
    """Write immutable compact attempt rows; no mutable campaign document exists."""

    campaign_id = _path_component(campaign_id, "campaign_id")
    ticker = _path_component(ticker, "ticker").upper()
    if isinstance(rows, (str, bytes)) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("ledger rows must be mapping documents")
    normalized = tuple(rows)
    for row in normalized:
        if not _LEDGER_PROVENANCE_FIELDS <= set(row):
            raise ValueError("ledger row lacks frozen slot outcome provenance")
        if row.get("outcome") != "qualified" and "completed_trades" in row:
            raise ValueError("rejected ledger row must stay compact")
        if "unsearched_candidate_ids" in row:
            raise ValueError("ledger must record counts, never materialized unsearched IDs")
    digest = hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()
    base = _contained_root(root)
    receipt_ids = {str(row["feature_receipt_id"]) for row in normalized}
    persisted_receipts: set[object] = set()
    for receipt_path in (base / "campaigns" / campaign_id / "features").glob(f"{ticker}-*.json"):
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("artifact_kind") == "flexible_feature_receipt":
            persisted_receipts.add(payload.get("receipt_id"))
    if not receipt_ids <= persisted_receipts:
        raise ValueError("feature receipt must be immutable before ledger outcome")
    path = (base / "campaigns" / campaign_id / "ledger" / ticker / f"{digest}.json").resolve()
    if base not in path.parents: raise ValueError("ledger path escapes Flexible root")
    return _write_immutable(path, {"schema_version": 1, "artifact_kind": "flexible_discovery_ledger_chunk", "campaign_id": campaign_id, "ticker": ticker.upper(), "rows": list(normalized)})


def write_selection_snapshot(root: Path, campaign_id: str, snapshot: dict[str, object]) -> Path:
    """Persist immutable campaign-chain selection, never mutate signal sets."""

    campaign_id = _path_component(campaign_id, "campaign_id")
    if not isinstance(snapshot, dict):
        raise ValueError("campaign_id and selection snapshot are required")
    truth = snapshot.get("searched_window_truth")
    if truth not in ("partial_window", "complete_assigned_window", "frontier_exhausted"):
        raise ValueError("selection snapshot requires searched-window truth")
    if snapshot.get("global_exhaustion") is True and truth != "frontier_exhausted":
        raise ValueError("only frontier_exhausted may claim global exhaustion")
    _validate_selection_snapshot(snapshot)
    base = _contained_root(root)
    parent_id = snapshot.get("parent_selection_snapshot_id")
    if parent_id is not None:
        parent_path = (base / "campaigns" / campaign_id / "selections" / f"{parent_id}.json").resolve()
        if not _is_digest(parent_id) or base not in parent_path.parents:
            raise ValueError("selection snapshot parent ID is invalid")
        try:
            parent_payload = json.loads(parent_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("selection snapshot parent is unavailable") from error
        if not isinstance(parent_payload, dict) or parent_payload.get("artifact_kind") != "flexible_selection_snapshot" or parent_payload.get("selection_snapshot_id") != parent_id:
            raise ValueError("selection snapshot parent is invalid")
    digest = hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()
    path = (base / "campaigns" / campaign_id / "selections" / f"{digest}.json").resolve()
    if base not in path.parents: raise ValueError("selection path escapes Flexible root")
    return _write_immutable(path, {"schema_version": 1, "artifact_kind": "flexible_selection_snapshot", "selection_snapshot_id": digest, "snapshot": snapshot})


__all__ = ["append_ledger_chunk", "iter_signal_set_paths", "read_signal_set", "resolve_flexible_root", "write_feature_resolution_receipt", "write_rulebook_definition", "write_selection_snapshot", "write_signal_set"]
