"""Concrete, receipt-first services for Flexible Rulebook campaigns."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from collections.abc import Mapping, Sequence
from decimal import Decimal
import time
from typing import Callable, Literal
import json

import pytz

from .campaigns import (
    CampaignItem,
    CampaignManifest,
    CampaignRequest,
    build_campaign_selection_snapshot,
    create_manifest,
    read_campaign_chain,
    transition,
    write_campaign_item,
    write_campaign_selection_snapshot,
)
from .cap_benchmark import SlotPhaseTiming, WindowPhaseTiming
from .catalog import catalog_revision_1
from .contracts import (
    EvaluationSplit,
    ExecutionContract,
    FeatureBuildContract,
    FeaturePlan,
    FeatureProfile,
    FeatureResolutionReceipt,
    PartitionMetrics,
    PredicateSpec,
    PrimitiveSpec,
    RulebookDefinition,
    RulebookEvaluation,
    canonical_json,
    rulebook_id,
)
from .history import HistorySnapshot
from .history import load_flexible_history, make_evaluation_split
from .features import (
    CacheOffer,
    FeaturePreflight,
    FeatureResolution,
    compose_entry_mask,
    compose_technical_exit_mask,
    current_feature_build_contract,
    inspect_primitive_cache,
    resolve_feature_store,
)
from .execution import ExecutionInterrupted, execute_rulebook
from .execution import CompletedTrade
from .storage import (
    append_ledger_chunk,
    write_campaign_selection_membership,
    write_feature_resolution_receipt,
    write_rulebook_definition,
    write_signal_set,
    iter_signal_set_paths,
    read_signal_set,
    selection_memberships_by_evaluation,
)
from .search import (
    CandidateSpace,
    DiscoveryResult,
    FrontierAssignment,
    discover_and_evaluate,
    scheduled_candidates,
)
from .metrics import qualifies
from .scope_expansion import ProgressEvent


_HCM = pytz.timezone("Asia/Ho_Chi_Minh")


def _now_hcm(value: datetime | None) -> datetime:
    timestamp = datetime.now(_HCM) if value is None else value
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("service time must be timezone-aware")
    return timestamp.astimezone(_HCM)


def _definition_primitives(definition: RulebookDefinition) -> tuple[PrimitiveSpec, ...]:
    if not isinstance(definition, RulebookDefinition):
        raise ValueError("definitions must contain RulebookDefinition values")
    candidates = [
        predicate.primitive
        for predicate in (
            *definition.buy_predicates,
            *definition.gates,
            *definition.filters,
            *definition.exits,
        )
    ]
    if definition.atr_primitive is not None:
        candidates.append(definition.atr_primitive)
    unique: dict[str, PrimitiveSpec] = {}
    for primitive in candidates:
        unique[canonical_json(primitive.to_dict())] = primitive
    return tuple(unique[key] for key in sorted(unique))


def _union_profile(definitions: Sequence[RulebookDefinition]) -> FeatureProfile:
    if isinstance(definitions, (str, bytes)):
        raise ValueError("definitions must be a sequence")
    values = tuple(definitions)
    if not values:
        raise ValueError("at least one rulebook definition is required")
    primitives: dict[str, PrimitiveSpec] = {}
    for definition in values:
        for primitive in _definition_primitives(definition):
            primitives[canonical_json(primitive.to_dict())] = primitive
    return FeatureProfile(tuple(primitives[key] for key in sorted(primitives)))


def _history_matches_snapshot(
    history: HistorySnapshot,
    expected: object,
) -> bool:
    """Compare every frozen source identity field, not just the latest date."""

    return (
        getattr(expected, "ticker", None) == history.ticker
        and getattr(expected, "raw_history_fingerprint", None) == history.fingerprint
        and getattr(expected, "requested_start", None) == history.requested_start
        and getattr(expected, "requested_as_of", None) == history.requested_as_of
        and getattr(expected, "first_date", None) == history.first_date
        and getattr(expected, "as_of_date", None) == history.as_of_date
        and getattr(expected, "quality_state", None) == history.quality_state
    )


def preflight_feature_components(
    engine: object,
    ticker: str,
    profiles: Sequence[FeatureProfile],
    contracts: Sequence[FeatureBuildContract],
    root: Path,
    now: datetime,
) -> tuple[FeaturePreflight, ...]:
    """Fresh-load one ticker, then inspect every requested profile/cache offer."""

    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible service root must be absolute")
    profile_values = tuple(profiles)
    contract_values = tuple(contracts)
    if not profile_values or len(profile_values) != len(contract_values):
        raise ValueError("profiles and contracts must have equal non-empty lengths")
    if any(not isinstance(profile, FeatureProfile) for profile in profile_values):
        raise ValueError("profiles must contain FeatureProfile values")
    if any(not isinstance(contract, FeatureBuildContract) for contract in contract_values):
        raise ValueError("contracts must contain FeatureBuildContract values")
    timestamp = _now_hcm(now)
    snapshot = load_flexible_history(engine, ticker)
    if snapshot.quality_state == "invalid":
        raise ValueError("data_ineligible")
    from .features import feature_snapshot_for_history

    feature_snapshot = feature_snapshot_for_history(snapshot)
    result: list[FeaturePreflight] = []
    for profile, contract in zip(profile_values, contract_values):
        plan = FeaturePlan(feature_snapshot, contract, profile)
        offer = inspect_primitive_cache(snapshot, contract, profile, root, timestamp)
        result.append(FeaturePreflight(snapshot, contract, plan, offer))
    return tuple(result)


def preflight_group_feature_components(
    engine: object,
    group: object,
    definitions: Sequence[RulebookDefinition],
    root: Path,
    now: datetime,
    *,
    progress_fn: Callable[[ProgressEvent], None] | None = None,
) -> Mapping[tuple[str, str], FeaturePreflight]:
    """Fresh-load all frozen members before inspecting any member cache."""

    from .group_adapter import FrozenGroup

    if not isinstance(group, FrozenGroup):
        raise ValueError("group must be a FrozenGroup")
    profile = _union_profile(definitions)
    contract = current_feature_build_contract()
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible service root must be absolute")
    timestamp = _now_hcm(now)
    # Source reads happen as a complete first phase.  This makes the cache
    # decision one batch operation rather than a serial prompt per member.
    def emit(event: ProgressEvent) -> None:
        if callable(progress_fn):
            try:
                progress_fn(event)
            except Exception:
                pass

    snapshots: list[HistorySnapshot] = []
    for index, ticker in enumerate(group.members, 1):
        snapshots.append(load_flexible_history(engine, ticker))
        emit(ProgressEvent("source", index, len(group.members), f"loaded {ticker}"))
    if any(snapshot.quality_state == "invalid" for snapshot in snapshots):
        raise ValueError("data_ineligible")
    from .features import feature_snapshot_for_history

    result: dict[tuple[str, str], FeaturePreflight] = {}
    for index, snapshot in enumerate(snapshots, 1):
        plan = FeaturePlan(feature_snapshot_for_history(snapshot), contract, profile)
        offer = inspect_primitive_cache(snapshot, contract, profile, root, timestamp)
        preflight = FeaturePreflight(snapshot, contract, plan, offer)
        result[preflight.key] = preflight
        emit(ProgressEvent("cache", index, len(snapshots), f"inspected {snapshot.ticker}"))
    return result


def resolve_frozen_feature_bundle(
    snapshot: HistorySnapshot,
    contract: FeatureBuildContract,
    profile: FeatureProfile,
    root: Path,
    *,
    cache_choice: str | None = None,
    now: datetime | None = None,
) -> FeatureResolution:
    """Resolve a verified source under an explicit operational cache choice."""

    if cache_choice is None:
        raise ValueError("cache_choice must be explicitly reuse or rebuild")
    return resolve_feature_store(
        snapshot,
        contract,
        profile,
        root,
        choice=cache_choice,
        now=_now_hcm(now),
    )


def _evaluate_definition(
    definition: RulebookDefinition,
    features: FeatureResolution,
    *,
    split: object,
    execution_contract: ExecutionContract,
    catalog_hash: str,
    should_stop: Callable[[], bool] | None = None,
) -> RulebookEvaluation:
    """Evaluate one portable definition against one already-resolved bundle."""

    if not isinstance(split, EvaluationSplit):
        raise ValueError("split must be an EvaluationSplit")
    entry_mask = compose_entry_mask(features.store, definition)
    technical_mask = compose_technical_exit_mask(features.store, definition)
    stop = (lambda: False) if should_stop is None else should_stop
    training = execute_rulebook(
        features.store,
        entry_mask,
        technical_mask,
        definition,
        split.training,
        receipt_digest=features.receipt.receipt_id,
        should_stop=stop,
    )
    if isinstance(training, ExecutionInterrupted):
        raise TimeoutError("qualification execution interrupted")
    testing = execute_rulebook(
        features.store,
        entry_mask,
        technical_mask,
        definition,
        split.test,
        receipt_digest=features.receipt.receipt_id,
        should_stop=stop,
    )
    if isinstance(testing, ExecutionInterrupted):
        raise TimeoutError("qualification execution interrupted")
    from .metrics import partition_metrics

    train_metrics = partition_metrics(training)
    test_metrics = partition_metrics(testing)
    state = "qualified" if qualifies(train_metrics, test_metrics) else "not_qualified"
    if features.store.snapshot.quality_state != "eligible":
        state = "display_only"
    return RulebookEvaluation(
        definition,
        features.store.snapshot.ticker,
        features.plan.snapshot,
        catalog_hash,
        split,
        execution_contract,
        features.plan.build_contract,
        features.plan.profile,
        features.receipt,
        train_metrics,
        test_metrics,
        state=state,
        training_trades=tuple(training),
        test_trades=tuple(testing),
    )


def qualify_rulebook_for_ticker(
    engine: object,
    definition: RulebookDefinition,
    ticker: str,
    preflight: FeaturePreflight,
    root: Path,
    *,
    cache_choice: str | None = None,
    execution_contract: ExecutionContract | None = None,
    split: object | None = None,
    feature_resolution: FeatureResolution | None = None,
) -> RulebookEvaluation:
    """Qualify one definition independently; failures never delete its ID."""

    if not isinstance(definition, RulebookDefinition):
        raise ValueError("definition must be a RulebookDefinition")
    if not isinstance(preflight, FeaturePreflight):
        raise ValueError("preflight must be a FeaturePreflight")
    if preflight.snapshot.ticker != str(ticker).strip().upper():
        raise ValueError("ticker does not match preflight source")
    if cache_choice not in {"reuse", "rebuild"}:
        raise ValueError("cache_choice must be explicitly reuse or rebuild")
    if feature_resolution is None:
        feature_resolution = resolve_frozen_feature_bundle(
            preflight.snapshot,
            preflight.build_contract,
            preflight.feature_plan.profile,
            root,
            cache_choice=cache_choice,
        )
    if feature_resolution.plan != preflight.feature_plan:
        raise ValueError("feature resolution does not match preflight plan")
    chosen_split = make_evaluation_split(preflight.snapshot) if split is None else split
    chosen_contract = ExecutionContract() if execution_contract is None else execution_contract
    if not isinstance(chosen_contract, ExecutionContract):
        raise ValueError("execution_contract must be an ExecutionContract")
    return _evaluate_definition(
        definition,
        feature_resolution,
        split=chosen_split,
        execution_contract=chosen_contract,
        catalog_hash=catalog_revision_1().catalog_hash,
    )


def _decode_json_value(value: object) -> object:
    if isinstance(value, list):
        return [_decode_json_value(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"$decimal"} and isinstance(value["$decimal"], str):
            return Decimal(value["$decimal"])
        return {key: _decode_json_value(item) for key, item in value.items()}
    return value


def _predicate_from_dict(value: object, *, default_role: str | None = None) -> PredicateSpec:
    if not isinstance(value, dict):
        raise ValueError("predicate document is invalid")
    primitive_payload = value.get("primitive")
    if not isinstance(primitive_payload, dict):
        raise ValueError("predicate primitive is invalid")
    primitive = PrimitiveSpec(
        primitive_payload.get("family"),
        primitive_payload.get("family_revision"),
        tuple(primitive_payload.get("settings", {}).items()),
    )
    role = value.get("role", default_role)
    if not isinstance(role, str):
        raise ValueError("predicate role is missing")
    condition = value.get("condition", {})
    if not isinstance(condition, dict):
        raise ValueError("predicate condition is invalid")
    return PredicateSpec(role, primitive, tuple(condition.items()))


def _definition_from_semantic(value: object) -> RulebookDefinition:
    payload = _decode_json_value(value)
    if not isinstance(payload, dict):
        raise ValueError("rulebook definition is invalid")
    buys = tuple(_predicate_from_dict(item, default_role="buy") for item in payload.get("buy_predicates", ()))
    entry_filters = tuple(_predicate_from_dict(item, default_role="gate") for item in payload.get("entry_filters", ()))
    exits = tuple(_predicate_from_dict(item, default_role="technical_sell") for item in payload.get("technical_sell_predicates", ()))
    atr_payload = payload.get("atr_primitive")
    atr = None
    if atr_payload is not None:
        if not isinstance(atr_payload, dict):
            raise ValueError("ATR primitive is invalid")
        atr = PrimitiveSpec(
            atr_payload.get("family"),
            atr_payload.get("family_revision"),
            tuple(atr_payload.get("settings", {}).items()),
        )
    price_exits = payload.get("atr_price_exits", {})
    if not isinstance(price_exits, dict):
        raise ValueError("ATR price exits are invalid")
    return RulebookDefinition(
        buy_predicates=buys,
        gates=entry_filters,
        exits=exits,
        atr_primitive=atr,
        atr_stop_multiplier=price_exits.get("stop_multiplier"),
        atr_target_multiplier=price_exits.get("target_multiplier"),
        atr_trailing_multiplier=price_exits.get("trailing_multiplier"),
        min_hold_bars=payload.get("min_hold_bars", 3),
        max_hold_bars=payload.get("max_hold_bars", 64),
        definition_revision=payload.get("definition_revision", "flexible-rulebook-definition-v1"),
    )


def _decode_evidence_value(value: object) -> object:
    """Decode the canonical scalar wrappers used in immutable evidence JSON."""

    if isinstance(value, list):
        return [_decode_evidence_value(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"$date"} and isinstance(value["$date"], str):
            return date.fromisoformat(value["$date"])
        if set(value) == {"$decimal"} and isinstance(value["$decimal"], str):
            return Decimal(value["$decimal"])
        if set(value) == {"$float"} and isinstance(value["$float"], str):
            return float(value["$float"])
        return {key: _decode_evidence_value(item) for key, item in value.items()}
    return value


def _evaluation_from_signal_set(path: Path) -> RulebookEvaluation:
    """Rehydrate one typed qualified evaluation for chain-wide selection."""

    payload = read_signal_set(path)
    if payload.get("persistence_reason") != "qualified":
        raise ValueError("signal set is not qualified evidence")
    decoded = _decode_evidence_value(payload)
    if not isinstance(decoded, dict):
        raise ValueError("signal set evidence is invalid")
    definition = _definition_from_semantic(decoded["definition"])
    source = __import__("flexible_rulebook.contracts", fromlist=["FeatureSnapshot"]).FeatureSnapshot(**decoded["source_snapshot"])
    contract = FeatureBuildContract(**decoded["feature_build_contract"])
    profile_payload = decoded["feature_profile"]
    if not isinstance(profile_payload, dict):
        raise ValueError("signal set feature profile is invalid")
    profile = FeatureProfile(tuple(PrimitiveSpec(**item) for item in profile_payload["primitive_specs"]))
    plan = FeaturePlan(source, contract, profile)
    receipt_payload = decoded["feature_receipt"]
    if not isinstance(receipt_payload, dict):
        raise ValueError("signal set feature receipt is invalid")
    receipt = FeatureResolutionReceipt(
        plan,
        tuple(tuple(item) for item in receipt_payload["resolved_components"]),
    )
    if receipt_payload.get("feature_plan_hash") != plan.feature_plan_hash or receipt_payload.get("receipt_id") != receipt.receipt_id:
        raise ValueError("signal set feature receipt identity mismatch")
    split_payload = decoded["split"]
    split = EvaluationSplit(
        split_payload["method"],
        split_payload.get("requested_test_cutoff"),
        __import__("flexible_rulebook.contracts", fromlist=["EvaluationPartition"]).EvaluationPartition(**split_payload["training"]),
        __import__("flexible_rulebook.contracts", fromlist=["EvaluationPartition"]).EvaluationPartition(**split_payload["test"]),
    )
    execution_contract = ExecutionContract(**decoded["execution_contract"])
    metrics = {
        "training": PartitionMetrics(**decoded["training_metrics"]),
        "test": PartitionMetrics(**decoded["test_metrics"]),
    }
    trades_payload = decoded["completed_trades"]
    training_trades = tuple(CompletedTrade(**item) for item in trades_payload["training"])
    test_trades = tuple(CompletedTrade(**item) for item in trades_payload["test"])
    evaluation = RulebookEvaluation(
        definition,
        decoded["ticker"],
        source,
        decoded["catalog_hash"],
        split,
        execution_contract,
        contract,
        profile,
        receipt,
        metrics["training"],
        metrics["test"],
        qualification_revision=decoded["qualification_revision"],
        state="qualified",
        training_trades=training_trades,
        test_trades=test_trades,
    )
    if decoded.get("evaluation_id") != evaluation.evaluation_id:
        raise ValueError("signal set evaluation identity mismatch")
    return evaluation


def _chain_evaluations(
    root: Path,
    chain: Sequence[CampaignManifest],
    current: Sequence[RulebookEvaluation],
) -> tuple[RulebookEvaluation, ...]:
    """Collect all qualified evidence committed by this campaign chain."""

    chain_ids = {manifest.campaign_id for manifest in chain}
    allowed_ids: set[str] = set()
    for evaluation_id, memberships in selection_memberships_by_evaluation(root).items():
        if any(item.get("campaign_id") in chain_ids for item in memberships):
            allowed_ids.add(evaluation_id)
    evaluations: dict[str, RulebookEvaluation] = {
        evaluation.evaluation_id: evaluation
        for evaluation in current
        if qualifies(evaluation.training_metrics, evaluation.test_metrics)
    }
    source = chain[-1].request.source_snapshots[0]
    for path in iter_signal_set_paths(root):
        if path.stem not in allowed_ids:
            continue
        try:
            evaluation = _evaluation_from_signal_set(path)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise ValueError("committed parent evaluation evidence is invalid") from error
        if (
            evaluation.ticker == source.ticker
            and evaluation.source_snapshot.raw_history_fingerprint == source.raw_history_fingerprint
            and evaluation.split == chain[-1].request.split
            and evaluation.execution_contract == chain[-1].request.execution_contract
            and evaluation.feature_build_contract.feature_build_contract_hash in chain[-1].request.feature_build_contract_hashes
        ):
            evaluations[evaluation.evaluation_id] = evaluation
    return tuple(evaluations[key] for key in sorted(evaluations))


def _chain_ledger_rows(root: Path, chain: Sequence[CampaignManifest], current_rows: Sequence[dict[str, object]]) -> tuple[dict[str, object], ...]:
    """Read immutable ledger chunks for parent windows plus current rows."""

    rows = list(current_rows)
    for manifest in chain[:-1]:
        directory = root / "campaigns" / manifest.campaign_id / "ledger" / manifest.request.source_snapshots[0].ticker
        for path in sorted(directory.glob("*.json")):
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError("parent discovery ledger is unreadable") from error
            if (
                not isinstance(document, dict)
                or document.get("schema_version") != 1
                or document.get("artifact_kind") != "flexible_discovery_ledger_chunk"
                or document.get("campaign_id") != manifest.campaign_id
                or document.get("ticker") != manifest.request.source_snapshots[0].ticker
                or not isinstance(document.get("rows"), list)
            ):
                raise ValueError("parent discovery ledger is invalid")
            rows.extend(item for item in document["rows"] if isinstance(item, dict))
    return tuple(rows)


def reusable_rulebooks(root: Path) -> tuple[RulebookDefinition, ...]:
    """Load immutable portable definitions; never read signal-set/cache data."""

    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible service root must be absolute")
    definitions: list[tuple[str, RulebookDefinition]] = []
    directory = root / "rulebooks"
    if not directory.is_dir():
        return ()
    for path in sorted(directory.glob("frb_*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            definition = _definition_from_semantic(document["definition"])
            identifier = document.get("rulebook_id")
            if identifier != rulebook_id(definition) or path.stem != identifier:
                raise ValueError("rulebook definition identity mismatch")
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("rulebook definition document is invalid") from error
        definitions.append((identifier, definition))
    return tuple(definition for _, definition in definitions)


def qualify_rulebooks_for_group(
    engine: object,
    rulebook_ids: Sequence[str],
    group: object,
    request: CampaignRequest,
    *,
    root: Path | None = None,
    cache_choice: str | None = None,
    now: datetime | None = None,
    progress_fn: Callable[[ProgressEvent], None] | None = None,
) -> CampaignManifest:
    """Evaluate frozen portable definitions independently for each group member."""

    from .group_adapter import FrozenGroup
    from .storage import resolve_flexible_root

    if not isinstance(group, FrozenGroup):
        raise ValueError("group must be a FrozenGroup")
    if not isinstance(request, CampaignRequest) or request.operation != "qualify":
        raise ValueError("qualification requires a qualify CampaignRequest")
    if request.frozen_members != group.members:
        raise ValueError("request members must equal the frozen group members")
    identifiers = tuple(rulebook_ids)
    if (
        not identifiers
        or any(not isinstance(identifier, str) or not identifier for identifier in identifiers)
        or len(set(identifiers)) != len(identifiers)
        or set(identifiers) != set(request.rulebook_ids)
    ):
        raise ValueError("rulebook IDs must match the frozen request")
    if cache_choice not in {"reuse", "rebuild"}:
        raise ValueError("cache_choice must be explicitly reuse or rebuild")
    base = resolve_flexible_root() if root is None else root
    if not isinstance(base, Path) or not base.is_absolute():
        raise ValueError("Flexible service root must be absolute")
    definitions_by_id = {
        rulebook_id(definition): definition for definition in reusable_rulebooks(base)
    }
    try:
        definitions = tuple(definitions_by_id[identifier] for identifier in identifiers)
    except KeyError as error:
        raise ValueError("requested rulebook definition is unavailable") from error
    contract = current_feature_build_contract()
    if contract.feature_build_contract_hash not in request.feature_build_contract_hashes:
        raise ValueError("request does not declare the current feature build contract")
    profile = _union_profile(definitions)
    timestamp = _now_hcm(now)
    manifest = transition(create_manifest(request), "running")

    def emit(event: ProgressEvent) -> None:
        if callable(progress_fn):
            try:
                progress_fn(event)
            except Exception:
                pass

    # All target sources are fetched before any component inspection/evaluation.
    fresh_snapshots: list[HistorySnapshot | None] = []
    for ticker in group.members:
        try:
            fresh_snapshots.append(load_flexible_history(engine, ticker))
        except (ConnectionError, OSError, ValueError, TypeError):
            # Preserve target independence: one unavailable source must not
            # prevent other frozen members from being evaluated.
            fresh_snapshots.append(None)
        emit(ProgressEvent("source", len(fresh_snapshots), len(group.members), f"loaded {ticker}"))
    items: list[CampaignItem] = []
    receipt_ids: list[str] = []
    for expected, snapshot in zip(request.source_snapshots, fresh_snapshots):
        if snapshot is None:
            items.append(CampaignItem(expected.ticker, "failed"))
            continue
        if not _history_matches_snapshot(snapshot, expected):
            items.append(CampaignItem(snapshot.ticker, "source_changed"))
            continue
        if snapshot.quality_state == "invalid":
            items.append(CampaignItem(snapshot.ticker, "data_ineligible"))
            continue
        # One cache offer and one resolution per target/build contract; every
        # definition in the union reuses this immutable bundle.
        feature_snapshot = __import__(
            "flexible_rulebook.features", fromlist=["feature_snapshot_for_history"]
        ).feature_snapshot_for_history(snapshot)
        plan = FeaturePlan(feature_snapshot, contract, profile)
        if plan.feature_plan_hash not in request.feature_plan_hashes:
            items.append(CampaignItem(snapshot.ticker, "failed"))
            continue
        offer = inspect_primitive_cache(snapshot, contract, profile, base, timestamp)
        preflight = FeaturePreflight(snapshot, contract, plan, offer)
        try:
            features = resolve_frozen_feature_bundle(
                snapshot,
                contract,
                profile,
                base,
                cache_choice=cache_choice,
                now=timestamp,
            )
            receipt_ids.append(features.receipt.receipt_id)
            write_feature_resolution_receipt(
                base,
                manifest.campaign_id,
                snapshot.ticker,
                features.receipt,
            )
            # Qualification requests freeze one split before execution.
            split = request.split
            qualified_artifact: str | None = None
            has_qualified = False
            has_display_only = False
            for definition_index, definition in enumerate(definitions, 1):
                write_rulebook_definition(base, definition)
                evaluation = _evaluate_definition(
                    definition,
                    features,
                    split=split,
                    execution_contract=request.execution_contract,
                    catalog_hash=catalog_revision_1().catalog_hash,
                )
                if evaluation.state == "display_only":
                    has_display_only = True
                if evaluation.state == "qualified":
                    artifact = write_signal_set(base, evaluation)
                    qualified_artifact = qualified_artifact or artifact.stem
                    has_qualified = True
                completed = (group.members.index(snapshot.ticker) * len(definitions)) + definition_index
                emit(ProgressEvent("evaluation", completed, len(group.members) * len(definitions), f"{snapshot.ticker} definition {definition_index}"))
        except (ConnectionError, OSError, ValueError, TypeError, RuntimeError):
            items.append(CampaignItem(snapshot.ticker, "failed"))
            continue
        if has_qualified:
            items.append(CampaignItem(snapshot.ticker, "qualified", qualified_artifact))
        elif has_display_only:
            items.append(CampaignItem(snapshot.ticker, "data_ineligible"))
        else:
            items.append(CampaignItem(snapshot.ticker, "no_qualified_candidate_within_budget"))

    manifest = replace(
        manifest,
        items=tuple(items),
        feature_receipt_ids=tuple(dict.fromkeys(receipt_ids)),
    )
    all_qualified = all(item.state == "qualified" for item in items)
    return transition(manifest, "completed" if all_qualified else "completed_with_errors")


def discovery_ledger_rows(
    space: CandidateSpace,
    assignment: FrontierAssignment,
    result: DiscoveryResult,
    *,
    feature_receipt_id: str,
) -> tuple[dict[str, object], ...]:
    """Turn committed frozen discovery outcomes into compact immutable ledger rows."""

    if not isinstance(space, CandidateSpace) or not isinstance(assignment, FrontierAssignment) or not isinstance(result, DiscoveryResult):
        raise ValueError("ledger conversion requires frozen discovery inputs")
    scheduled = tuple(scheduled_candidates(space, assignment))
    outcomes = dict(result.outcomes)
    rows: list[dict[str, object]] = []
    strata = {item.stratum_id: item for item in assignment.strata}
    seen_per_stratum: dict[str, int] = {}
    for slot, stratum_id, canonical, _definition in scheduled:
        if slot not in outcomes:
            continue
        stratum_slot = seen_per_stratum.get(stratum_id, 0)
        seen_per_stratum[stratum_id] = stratum_slot + 1
        stratum = strata[stratum_id]
        rows.append({"candidate_space_hash": space.candidate_space_hash, "candidate_space_size": space.size, "candidate_space_algorithm_version": space.candidate_space_algorithm_version, "canonical_index": canonical, "global_slot": slot, "stratum_id": stratum_id, "stratum_slot": stratum_slot, "assignment_hash": assignment.assignment_hash, "frontier_algorithm_version": assignment.algorithm_version, "stratification_revision": assignment.stratification_revision, "stratum_multiplier": assignment.stratum_multiplier, "stratum_offset": assignment.stratum_offset, "stratum_quota": stratum.quota, "seed_fingerprint": hashlib.sha256(assignment.frontier_seed.encode("utf-8")).hexdigest(), "feature_receipt_id": feature_receipt_id, "outcome": outcomes[slot], "unsearched_count": result.unsearched_count})
    return tuple(rows)


def persist_discovery_ledger(
    root: Path, *, campaign_id: str, ticker: str, rows: tuple[dict[str, object], ...]
) -> Path:
    """Persist only receipt-bound, frozen discovery rows as one immutable chunk."""

    return append_ledger_chunk(root, campaign_id, ticker, rows)


def checkpoint_campaign_item(
    root: Path, manifest: CampaignManifest, item: CampaignItem
) -> CampaignManifest:
    """Write the worker-owned item first, then return its coordinator checkpoint."""

    if not isinstance(manifest, CampaignManifest) or not isinstance(item, CampaignItem):
        raise ValueError("item checkpoint requires campaign manifest and item")
    write_campaign_item(root, manifest, item)
    items = tuple(item if current.ticker == item.ticker else current for current in manifest.items)
    return replace(manifest, items=items)


class ReceiptCheckpointService:
    """Persist exact feature bytes proof before any discovery slot can commit."""

    def __init__(
        self,
        root: Path,
        *,
        receipt_resolver: Callable[[HistorySnapshot], FeatureResolutionReceipt],
    ) -> None:
        if not isinstance(root, Path) or not root.is_absolute():
            raise ValueError("Flexible service root must be absolute")
        if not callable(receipt_resolver):
            raise ValueError("receipt_resolver must be callable")
        self._root = root
        self._receipt_resolver = receipt_resolver

    def run(
        self,
        manifest: CampaignManifest,
        *,
        verified_sources: tuple[HistorySnapshot, ...],
    ) -> CampaignManifest:
        if (
            not isinstance(manifest, CampaignManifest)
            or manifest.request.operation != "discover"
            or len(verified_sources) != 1
            or len(manifest.request.source_snapshots) != 1
        ):
            raise ValueError("receipt checkpoint requires one discovery source")
        receipt = self._receipt_resolver(verified_sources[0])
        if (
            not isinstance(receipt, FeatureResolutionReceipt)
            or receipt.plan.snapshot != manifest.request.source_snapshots[0]
            or receipt.plan.feature_plan_hash not in manifest.request.feature_plan_hashes
            or receipt.plan.build_contract.feature_build_contract_hash
            not in manifest.request.feature_build_contract_hashes
        ):
            raise ValueError("resolved receipt does not match frozen campaign request")
        if manifest.feature_receipt_ids and manifest.feature_receipt_ids != (receipt.receipt_id,):
            raise ValueError("resolved receipt differs from persisted campaign receipt")
        write_feature_resolution_receipt(
            self._root,
            manifest.campaign_id,
            verified_sources[0].ticker,
            receipt,
        )
        return replace(manifest, feature_receipt_ids=(receipt.receipt_id,))


class DiscoveryService:
    """Compose one frozen discovery window in receipt/ledger/item order.

    The coordinator owns only immutable inputs and checkpoints.  Evaluation is
    injected so the same service can run in the isolated worker and remain
    deterministic in unit tests.
    """

    def __init__(
        self,
        root: Path,
        *,
        candidate_space: CandidateSpace,
        feature_resolver: Callable[[HistorySnapshot], FeatureResolution],
        discovery_runner: Callable[..., DiscoveryResult] = discover_and_evaluate,
        monotonic: Callable[[], float] = lambda: 0.0,
        cancellation_probe: Callable[[], bool] = lambda: False,
        phase_observer: Callable[[SlotPhaseTiming | WindowPhaseTiming], None] = lambda _event: None,
    ) -> None:
        if not isinstance(root, Path) or not root.is_absolute():
            raise ValueError("Flexible service root must be absolute")
        if not isinstance(candidate_space, CandidateSpace):
            raise ValueError("candidate_space must be CandidateSpace")
        if (
            not callable(feature_resolver)
            or not callable(discovery_runner)
            or not callable(monotonic)
            or not callable(cancellation_probe)
            or not callable(phase_observer)
        ):
            raise ValueError("discovery service dependencies must be callable")
        self._root = root
        self._space = candidate_space
        self._feature_resolver = feature_resolver
        self._discovery_runner = discovery_runner
        self._monotonic = monotonic
        self._cancellation_probe = cancellation_probe
        self._phase_observer = phase_observer

    @staticmethod
    def _item_state(result: DiscoveryResult) -> str:
        if result.state in {
            "no_qualified_candidate_within_budget",
            "time_budget_exhausted",
            "frontier_exhausted_no_qualified_candidate",
        }:
            return result.state
        return "failed"

    def run(
        self,
        manifest: CampaignManifest,
        *,
        verified_sources: tuple[HistorySnapshot, ...],
    ) -> CampaignManifest:
        """Resolve receipt, evaluate frozen slots, then checkpoint evidence."""

        if (
            not isinstance(manifest, CampaignManifest)
            or manifest.state not in {"running", "cancelling"}
            or manifest.request.operation != "discover"
            or len(verified_sources) != 1
        ):
            raise ValueError("discovery service requires one running discovery manifest")
        if manifest.state == "cancelling" or self._cancellation_probe():
            cancelling = manifest if manifest.state == "cancelling" else transition(manifest, "cancelling")
            return transition(cancelling, "cancelled")
        source = verified_sources[0]
        if not isinstance(source, HistorySnapshot):
            raise ValueError("verified source must be HistorySnapshot")
        assignment = manifest.request.frontier_assignment
        if assignment is None or assignment.source_ticker != source.ticker:
            raise ValueError("discovery assignment does not match verified source")

        # Resolve exactly once: the receipt and arrays used for evaluation must
        # be the same bytes proven by the immutable feature checkpoint.
        features = self._feature_resolver(source)
        if not isinstance(features, FeatureResolution):
            raise ValueError("feature resolver must return FeatureResolution")
        checkpoint = ReceiptCheckpointService(
            self._root,
            receipt_resolver=lambda _source: features.receipt,
        ).run(manifest, verified_sources=verified_sources)

        result = self._discovery_runner(
            source,
            features,
            self._space,
            assignment,
            monotonic=self._monotonic,
            split=manifest.request.split,
            execution_contract=manifest.request.execution_contract,
            phase_observer=self._phase_observer,
        )
        if not isinstance(result, DiscoveryResult):
            raise ValueError("discovery runner must return DiscoveryResult")

        # Validate the worker result before creating any discovery evidence. A
        # malformed cursor must never leave a ledger or signal-set artifact.
        frontier_size = result.frontier_size
        next_slot = result.next_slot
        if (
            frontier_size != self._space.size
            or isinstance(frontier_size, bool)
            or not isinstance(frontier_size, int)
            or isinstance(next_slot, bool)
            or not isinstance(next_slot, int)
            or next_slot < assignment.start_slot
            or next_slot > frontier_size
            or result.unsearched_count != frontier_size - next_slot
            or result.chain_attempted_count != next_slot
            or (
                result.uncommitted_slot is not None
                and result.uncommitted_slot != next_slot
            )
        ):
            raise ValueError("discovery result cursor is not contiguous")

        write_started = time.monotonic()
        rows = discovery_ledger_rows(
            self._space,
            assignment,
            result,
            feature_receipt_id=features.receipt.receipt_id,
        )
        if rows:
            persist_discovery_ledger(
                self._root,
                campaign_id=manifest.campaign_id,
                ticker=source.ticker,
                rows=rows,
            )
        checkpoint = replace(
            checkpoint,
            next_slot=next_slot,
            chain_attempted_count=next_slot,
            unsearched_count=frontier_size - next_slot,
            uncommitted_slot=result.uncommitted_slot,
        )
        target = "completed_with_errors" if result.uncommitted_slot is not None else "completed"
        terminal = transition(checkpoint, target)
        selection = None
        if result.uncommitted_slot is None:
            selection_started = time.monotonic()
            if terminal.request.parent_campaign_id is not None:
                parent_chain = read_campaign_chain(
                    self._root,
                    terminal.request.parent_campaign_id,
                )
                selection_chain = (*parent_chain, terminal)
            else:
                selection_chain = (terminal,)
            selection_evaluations = _chain_evaluations(
                self._root,
                selection_chain,
                tuple(result.evaluations),
            )
            all_ledger_rows = _chain_ledger_rows(
                self._root,
                selection_chain,
                rows,
            )
            selection = build_campaign_selection_snapshot(
                selection_chain,
                selection_evaluations,
                ledger_digest=hashlib.sha256(canonical_json(list(all_ledger_rows)).encode("utf-8")).hexdigest(),
                evaluation_digest=hashlib.sha256(
                    canonical_json([item.to_identity_dict() for item in selection_evaluations]).encode("utf-8")
                ).hexdigest(),
            )
            self._phase_observer(
                WindowPhaseTiming(
                    "selection",
                    max(0.0, time.monotonic() - selection_started),
                )
            )

        artifact_ids: list[str] = []
        for evaluation in result.evaluations:
            if not qualifies(evaluation.training_metrics, evaluation.test_metrics):
                continue
            write_rulebook_definition(self._root, evaluation.definition)
            path = write_signal_set(self._root, evaluation)
            artifact_ids.append(path.stem)
            if selection is not None:
                write_campaign_selection_membership(
                    self._root,
                    manifest.campaign_id,
                    evaluation,
                    selection.selection_snapshot_id,
                )
        item = CampaignItem(
            source.ticker,
            self._item_state(result),
            artifact_ids[0] if artifact_ids else None,
        )
        checkpoint = checkpoint_campaign_item(self._root, checkpoint, item)
        # An uncommitted slot is deliberately incomplete work. It cannot be
        # represented as terminal Top-3 evidence and therefore gets no
        # selection snapshot until a later receipt-bound continuation closes it.
        terminal = transition(checkpoint, target)
        if selection is None:
            self._phase_observer(
                WindowPhaseTiming(
                    "write",
                    max(0.0, time.monotonic() - write_started),
                )
            )
            return terminal
        persisted = write_campaign_selection_snapshot(
            self._root,
            terminal,
            selection,
        )
        self._phase_observer(
            WindowPhaseTiming(
                "write",
                max(0.0, time.monotonic() - write_started),
            )
        )
        return persisted


__all__ = ["DiscoveryService", "ReceiptCheckpointService", "checkpoint_campaign_item", "discovery_ledger_rows", "persist_discovery_ledger"]
