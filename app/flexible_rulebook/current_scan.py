"""All-or-nothing current BUY scans for already-qualified Flexible evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
import os
from pathlib import Path
import tempfile
from typing import Callable, Literal, Mapping, Sequence

from .campaigns import CampaignItem, CampaignManifest, CampaignRequest, create_manifest, transition, write_campaign_item, write_campaign_manifest
from .contracts import FeatureBuildContract, FeaturePlan, FeatureProfile, FeatureResolutionReceipt, FeatureSnapshot, PredicateSpec, PrimitiveSpec, RulebookDefinition, animal_alias, canonical_json, rulebook_id
from .features import FeaturePreflight, compose_entry_mask, current_feature_build_contract, feature_snapshot_for_history, inspect_primitive_cache
from .history import EvidenceSourceAnchor, HistorySnapshot, load_flexible_history, verify_evidence_source_anchor
from .service import _definition_from_semantic, resolve_frozen_feature_bundle
from .storage import iter_signal_set_paths, read_signal_set, write_feature_resolution_receipt
from .scope_expansion import ProgressEvent


CurrentScanState = Literal[
    "ready",
    "current_setup_found",
    "no_current_setup",
    "no_historically_qualified_rulebook",
    "blocked_common_as_of",
    "source_changed",
    "data_stale",
    "data_invalid",
    "current_evaluation_failed",
    "not_evaluated",
]


@dataclass(frozen=True)
class CommonAsOfPreflight:
    """Fresh all-member source load and common completed-bar decision."""

    members: tuple[str, ...]
    snapshots: tuple[HistorySnapshot, ...]
    state: CurrentScanState = "ready"
    common_as_of: date | None = None
    lagging_tickers: tuple[str, ...] = ()
    invalid_tickers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        members = tuple(item.strip().upper() for item in self.members)
        if not members or any(not item for item in members) or len(set(members)) != len(members):
            raise ValueError("common-as-of members must be unique non-empty tickers")
        snapshots = tuple(self.snapshots)
        if len(snapshots) != len(members) or tuple(item.ticker for item in snapshots) != members:
            raise ValueError("common-as-of snapshots must match frozen member order")
        if any(not isinstance(item, HistorySnapshot) for item in snapshots):
            raise ValueError("common-as-of snapshots must be HistorySnapshot values")
        if self.state not in {"ready", "blocked_common_as_of", "data_invalid"}:
            raise ValueError("invalid common-as-of state")
        if self.state == "ready" and (self.common_as_of is None or self.lagging_tickers or self.invalid_tickers):
            raise ValueError("ready common-as-of preflight must have one date and no blockers")
        if self.state == "blocked_common_as_of" and (self.common_as_of is None or not self.lagging_tickers):
            raise ValueError("blocked common-as-of preflight must list laggards")
        if self.state == "data_invalid" and not self.invalid_tickers:
            raise ValueError("invalid common-as-of preflight must list invalid tickers")
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "snapshots", snapshots)
        object.__setattr__(self, "lagging_tickers", tuple(self.lagging_tickers))
        object.__setattr__(self, "invalid_tickers", tuple(self.invalid_tickers))

    @property
    def snapshots_by_ticker(self) -> Mapping[str, HistorySnapshot]:
        return {snapshot.ticker: snapshot for snapshot in self.snapshots}

    @property
    def latest_dates(self) -> Mapping[str, date | None]:
        """Expose the exact per-member watermark used by the common gate."""

        return {snapshot.ticker: snapshot.as_of_date for snapshot in self.snapshots}


@dataclass(frozen=True)
class QualifiedCurrentPair:
    """Minimal immutable registry view needed by a current scan."""

    definition: RulebookDefinition
    ticker: str
    source_snapshot: FeatureSnapshot
    feature_build_contract: FeatureBuildContract
    feature_profile: FeatureProfile
    feature_receipt: FeatureResolutionReceipt | None = None
    evidence_anchor: EvidenceSourceAnchor | None = None


@dataclass(frozen=True)
class CurrentScanCachePreflight:
    """Verified qualified evidence and one cache offer per current-scan bundle."""

    state: Literal["ready", "source_changed", "no_historically_qualified_rulebook"]
    feature_preflights: Mapping[tuple[str, str], FeaturePreflight]
    no_qualified_tickers: tuple[str, ...] = ()
    changed_tickers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in {"ready", "source_changed", "no_historically_qualified_rulebook"}:
            raise ValueError("current cache preflight state is invalid")
        if any(not isinstance(key, tuple) or len(key) != 2 or not isinstance(value, FeaturePreflight) for key, value in self.feature_preflights.items()):
            raise ValueError("current cache preflight feature map is invalid")
        if self.state == "ready" and not self.feature_preflights:
            raise ValueError("ready current cache preflight requires feature bundles")
        if self.state == "source_changed" and not self.changed_tickers:
            raise ValueError("source-changed current cache preflight requires tickers")


def _normalize_members(members: Sequence[str]) -> tuple[str, ...]:
    if isinstance(members, (str, bytes)):
        raise ValueError("members must be a ticker sequence")
    result = tuple(str(item).strip().upper() for item in members)
    if not result or any(not item for item in result) or len(set(result)) != len(result):
        raise ValueError("members must be unique non-empty tickers")
    return result


def preflight_common_as_of(
    engine: object,
    members: tuple[str, ...],
    *,
    snapshots: Mapping[str, HistorySnapshot] | None = None,
) -> CommonAsOfPreflight:
    """Load every member first, then enforce one exact latest completed bar."""

    normalized = _normalize_members(members)
    if snapshots is None:
        loaded = tuple(load_flexible_history(engine, ticker) for ticker in normalized)
    else:
        if set(snapshots) != set(normalized):
            raise ValueError("snapshot map must exactly match members")
        loaded = tuple(snapshots[ticker] for ticker in normalized)
    invalid = tuple(snapshot.ticker for snapshot in loaded if snapshot.quality_state == "invalid")
    if invalid:
        return CommonAsOfPreflight(normalized, loaded, "data_invalid", invalid_tickers=invalid)
    latest = max(snapshot.as_of_date for snapshot in loaded if snapshot.as_of_date is not None)
    lagging = tuple(snapshot.ticker for snapshot in loaded if snapshot.as_of_date != latest)
    if lagging:
        return CommonAsOfPreflight(normalized, loaded, "blocked_common_as_of", latest, lagging)
    return CommonAsOfPreflight(normalized, loaded, "ready", latest)


def _union_profile(definitions: Sequence[RulebookDefinition]) -> FeatureProfile:
    if not definitions:
        raise ValueError("at least one qualified definition is required")
    primitives: dict[str, PrimitiveSpec] = {}
    from .contracts import canonical_json

    for definition in definitions:
        for predicate in (*definition.buy_predicates, *definition.gates, *definition.filters, *definition.exits):
            primitives[canonical_json(predicate.primitive.to_dict())] = predicate.primitive
        if definition.atr_primitive is not None:
            primitives[canonical_json(definition.atr_primitive.to_dict())] = definition.atr_primitive
    return FeatureProfile(tuple(primitives[key] for key in sorted(primitives)))


def _pair_fields(pair: object) -> tuple[RulebookDefinition, str, FeatureBuildContract, FeatureProfile, EvidenceSourceAnchor | None]:
    definition = getattr(pair, "definition", None)
    ticker = str(getattr(pair, "ticker", "")).strip().upper()
    contract = getattr(pair, "feature_build_contract", None)
    profile = getattr(pair, "feature_profile", None)
    anchor = getattr(pair, "evidence_anchor", None)
    if not isinstance(definition, RulebookDefinition) or not ticker or not isinstance(contract, FeatureBuildContract) or not isinstance(profile, FeatureProfile):
        raise ValueError("qualified current pair is incomplete")
    if anchor is not None and not isinstance(anchor, EvidenceSourceAnchor):
        raise ValueError("qualified current evidence anchor is invalid")
    return definition, ticker, contract, profile, anchor


def preflight_current_scan_features(
    engine: object,
    preflight: CommonAsOfPreflight,
    qualified: Sequence[object],
    root: Path,
    now: datetime,
    *,
    definitions: Sequence[RulebookDefinition] | None = None,
) -> Mapping[tuple[str, str], FeaturePreflight]:
    """Group qualified definitions by ticker/build contract and inspect cache once."""

    if not isinstance(preflight, CommonAsOfPreflight):
        raise ValueError("preflight must be CommonAsOfPreflight")
    if preflight.state != "ready":
        raise ValueError("current feature preflight is blocked")
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible current-scan root must be absolute")
    pairs = tuple(qualified)
    if not pairs and definitions is not None:
        # Test and embedding convenience: definitions are applied to every ready
        # member, while production uses the persisted qualified pair registry.
        pairs = tuple(
            QualifiedCurrentPair(
                definition,
                ticker,
                feature_snapshot_for_history(preflight.snapshots_by_ticker[ticker]),
                FeatureBuildContract(),
                _union_profile((definition,)),
            )
            for ticker in preflight.members
            for definition in definitions
        )
    grouped: dict[tuple[str, str], list[RulebookDefinition]] = {}
    contracts: dict[tuple[str, str], FeatureBuildContract] = {}
    snapshots = preflight.snapshots_by_ticker
    for pair in pairs:
        definition, ticker, contract, _profile, _anchor = _pair_fields(pair)
        if ticker not in snapshots:
            raise ValueError("qualified pair is outside frozen members")
        key = (ticker, contract.feature_build_contract_hash)
        grouped.setdefault(key, []).append(definition)
        contracts[key] = contract
    result: dict[tuple[str, str], FeaturePreflight] = {}
    for key, definitions_for_target in grouped.items():
        ticker, _contract_hash = key
        snapshot = snapshots[ticker]
        contract = contracts[key]
        profile = _union_profile(definitions_for_target)
        plan = FeaturePlan(feature_snapshot_for_history(snapshot), contract, profile)
        offer = inspect_primitive_cache(snapshot, contract, profile, root, now)
        result[key] = FeaturePreflight(snapshot, contract, plan, offer)
    return result


def _anchor_for_source(source: FeatureSnapshot) -> EvidenceSourceAnchor:
    return EvidenceSourceAnchor(
        ticker=source.ticker,
        requested_start=source.requested_start,
        requested_as_of=source.requested_as_of,
        first_date=source.first_date,
        as_of_date=source.as_of_date,
        prefix_fingerprint=source.raw_history_fingerprint,
    )


def _source_status(engine: object, expected: FeatureSnapshot, current: HistorySnapshot) -> Literal["match", "append_safe", "changed", "invalid", "stale"]:
    if current.quality_state == "invalid":
        return "invalid"
    if current.quality_state != "eligible":
        return "stale"
    if (
        current.ticker == expected.ticker
        and current.fingerprint == expected.raw_history_fingerprint
        and current.requested_start == expected.requested_start
        and current.requested_as_of == expected.requested_as_of
        and current.first_date == expected.first_date
        and current.as_of_date == expected.as_of_date
    ):
        return "match" if expected.quality_state == "eligible" else "stale"
    if (
        current.ticker == expected.ticker
        and current.as_of_date is not None
        and current.as_of_date > expected.as_of_date
        and current.first_date == expected.first_date
    ):
        proof = verify_evidence_source_anchor(engine, _anchor_for_source(expected))
        return "append_safe" if proof == "match" else "changed"
    return "changed"


def _decode(value: object) -> object:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"$date"}:
            return date.fromisoformat(str(value["$date"]))
        if set(value) == {"$decimal"}:
            from decimal import Decimal

            return Decimal(str(value["$decimal"]))
        if set(value) == {"$float"}:
            return float(value["$float"])
        return {key: _decode(item) for key, item in value.items()}
    return value


def _qualified_from_signal_set(path: Path) -> QualifiedCurrentPair | None:
    payload = read_signal_set(path)
    if payload.get("persistence_reason") != "qualified":
        return None
    try:
        if not isinstance(payload.get("evaluation_id"), str) or path.stem != payload["evaluation_id"]:
            raise ValueError("signal-set path/evaluation identity mismatch")
        definition = _definition_from_semantic(_decode(payload["definition"]))
        source = FeatureSnapshot(**_decode(payload["source_snapshot"]))
        if source.quality_state != "eligible":
            return None
        contract = FeatureBuildContract(**_decode(payload["feature_build_contract"]))
        profile_payload = _decode(payload["feature_profile"])
        profile = FeatureProfile(tuple(PrimitiveSpec(**item) for item in profile_payload["primitive_specs"]))
        receipt_payload = _decode(payload["feature_receipt"])
        plan = FeaturePlan(source, contract, profile)
        if payload.get("rulebook_id") != rulebook_id(definition):
            raise ValueError("signal-set rulebook identity mismatch")
        if payload.get("ticker") != source.ticker:
            raise ValueError("signal-set ticker/source mismatch")
        if path.parent.name != source.ticker or path.parent.parent.name != rulebook_id(definition):
            raise ValueError("signal-set path identity mismatch")
        if not isinstance(receipt_payload, Mapping):
            raise ValueError("signal-set feature receipt is invalid")
        if set(receipt_payload) != {"feature_plan_hash", "resolved_components", "receipt_id"}:
            raise ValueError("signal-set feature receipt is incomplete")
        if receipt_payload.get("feature_plan_hash") != plan.feature_plan_hash:
            raise ValueError("signal-set feature plan identity mismatch")
        receipt = FeatureResolutionReceipt(plan, tuple(tuple(item) for item in receipt_payload["resolved_components"]))
        if receipt_payload.get("receipt_id") != receipt.receipt_id:
            raise ValueError("signal-set feature receipt identity mismatch")
        anchor_payload = _decode(payload.get("evidence_source_anchor"))
        if not isinstance(anchor_payload, Mapping):
            raise ValueError("signal-set evidence anchor is invalid")
        expected_anchor_keys = {
            "ticker", "requested_start", "requested_as_of", "first_date",
            "as_of_date", "prefix_fingerprint",
        }
        if set(anchor_payload) != expected_anchor_keys:
            raise ValueError("signal-set evidence anchor is incomplete")
        anchor = EvidenceSourceAnchor(
            ticker=anchor_payload["ticker"],
            requested_start=anchor_payload["requested_start"],
            requested_as_of=anchor_payload["requested_as_of"],
            first_date=anchor_payload["first_date"],
            as_of_date=anchor_payload["as_of_date"],
            prefix_fingerprint=anchor_payload["prefix_fingerprint"],
        )
        if (
            anchor.ticker != source.ticker
            or anchor.requested_start != source.requested_start
            or anchor.requested_as_of != source.requested_as_of
            or anchor.first_date != source.first_date
            or anchor.as_of_date != source.as_of_date
            or anchor.prefix_fingerprint != source.raw_history_fingerprint
        ):
            raise ValueError("signal-set evidence anchor identity mismatch")
        return QualifiedCurrentPair(definition, str(payload["ticker"]).upper(), source, contract, profile, receipt, anchor)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise ValueError("qualified signal-set registry entry is invalid") from error


def _load_qualified(root: Path, members: tuple[str, ...]) -> tuple[QualifiedCurrentPair, ...]:
    result: list[QualifiedCurrentPair] = []
    for path in iter_signal_set_paths(root):
        try:
            pair = _qualified_from_signal_set(path)
        except ValueError:
            # One corrupt/old evidence file must not abort an otherwise valid
            # current scan; it is simply unavailable for BUY evaluation.
            continue
        if pair is not None and pair.ticker in members:
            result.append(pair)
    return tuple(result)


def _validated_current_pairs(
    engine: object,
    common: CommonAsOfPreflight,
    pairs: Sequence[object],
) -> tuple[dict[str, list[object]], tuple[str, ...]]:
    """Keep only current-contract, evidence-anchor-verified qualified pairs."""

    pairs_by_ticker: dict[str, list[object]] = {ticker: [] for ticker in common.members}
    compatible_contract_hash = current_feature_build_contract().feature_build_contract_hash
    anchor_results: dict[EvidenceSourceAnchor, str] = {}
    changed: set[str] = set()
    for pair in pairs:
        _definition, ticker, contract, _profile, anchor = _pair_fields(pair)
        if ticker not in pairs_by_ticker:
            raise ValueError("qualified pair is outside frozen members")
        source_snapshot = getattr(pair, "source_snapshot", None)
        if isinstance(source_snapshot, FeatureSnapshot) and source_snapshot.quality_state != "eligible":
            continue
        if contract.feature_build_contract_hash != compatible_contract_hash:
            continue
        if anchor is not None:
            if anchor not in anchor_results:
                anchor_results[anchor] = verify_evidence_source_anchor(engine, anchor)
            if anchor_results[anchor] != "match":
                changed.add(ticker)
        elif source_snapshot is None:
            changed.add(ticker)
        pairs_by_ticker[ticker].append(pair)
    return pairs_by_ticker, tuple(sorted(changed))


def preflight_current_scan_cache(
    engine: object,
    common: CommonAsOfPreflight,
    root: Path,
    *,
    now: datetime,
    qualified: Sequence[object] | None = None,
    progress_fn: Callable[[ProgressEvent], None] | None = None,
) -> CurrentScanCachePreflight:
    """Verify evidence anchors, then inspect one cache offer per valid bundle."""

    if not isinstance(common, CommonAsOfPreflight) or common.state != "ready":
        raise ValueError("current cache preflight requires ready common-as-of evidence")
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible current-scan root must be absolute")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("current cache preflight time must be timezone-aware")
    def emit(event: ProgressEvent) -> None:
        if callable(progress_fn):
            try:
                progress_fn(event)
            except Exception:
                pass

    emit(ProgressEvent("common-as-of", 1, 1, "common completed bar verified"))
    pairs = tuple(_load_qualified(root, common.members) if qualified is None else qualified)
    pairs_by_ticker, changed = _validated_current_pairs(engine, common, pairs)
    if changed:
        return CurrentScanCachePreflight("source_changed", {}, changed_tickers=changed)
    no_qualified = tuple(ticker for ticker, values in pairs_by_ticker.items() if not values)
    if len(no_qualified) == len(common.members):
        return CurrentScanCachePreflight(
            "no_historically_qualified_rulebook",
            {},
            no_qualified_tickers=no_qualified,
        )
    features = preflight_current_scan_features(
        engine,
        common,
        tuple(pair for values in pairs_by_ticker.values() for pair in values),
        root,
        now,
    )
    emit(ProgressEvent("cache", len(features), max(1, len(features)), "feature cache offers inspected"))
    return CurrentScanCachePreflight("ready", features, no_qualified_tickers=no_qualified)


def _blocked_manifest(request: CampaignRequest, state: CurrentScanState, message: str, *, invalid: tuple[str, ...] = ()) -> CampaignManifest:
    manifest = transition(create_manifest(request), "running")
    items = tuple(
        CampaignItem(
            ticker,
            state if state == "blocked_common_as_of" or ticker in invalid else "not_evaluated",
        )
        for ticker in request.frozen_members
    )
    terminal = replace(manifest, items=items, safe_error_code=f"CURRENT.{state.upper()}", safe_error_message=message)
    return transition(terminal, "completed_with_errors")


def _write_current_scan_artifact(
    root: Path,
    manifest: CampaignManifest,
    item: CampaignItem,
    *,
    common_as_of: date | None,
    evidence: Sequence[Mapping[str, object]] = (),
) -> Path:
    """Write the detailed current result separately from the campaign item."""

    ordinal = manifest.request.frozen_members.index(item.ticker)
    path = (root / "current-scans" / manifest.campaign_id / f"{ordinal:04d}-{item.ticker}.json").resolve()
    if root.resolve() not in path.parents:
        raise ValueError("current-scan artifact path escapes Flexible root")
    payload = {
        "schema_version": 1,
        "artifact_kind": "flexible_current_scan_item",
        "campaign_id": manifest.campaign_id,
        "ticker": item.ticker,
        "state": item.state,
        "common_as_of": common_as_of,
        "evidence": [dict(row) for row in evidence],
    }
    material = canonical_json(payload)
    if path.exists():
        if path.read_text(encoding="utf-8") != material:
            raise ValueError("immutable current-scan artifact already differs")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_text(encoding="utf-8") != material:
                raise ValueError("immutable current-scan artifact already differs")
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def _persist_terminal(
    root: Path,
    manifest: CampaignManifest,
    *,
    common_as_of: date | None = None,
    evidence: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
) -> CampaignManifest:
    """Durably write item artifacts before the terminal manifest."""

    details = {} if evidence is None else evidence
    for item in manifest.items:
        _write_current_scan_artifact(root, manifest, item, common_as_of=common_as_of, evidence=details.get(item.ticker, ()))
    for item in manifest.items:
        write_campaign_item(root, manifest, item)
    write_campaign_manifest(root, manifest)
    return manifest


def scan_current_setup(
    engine: object,
    request: CampaignRequest,
    root: Path,
    *,
    qualified: Sequence[object] | None = None,
    now: datetime | None = None,
    progress_fn: Callable[[ProgressEvent], None] | None = None,
) -> CampaignManifest:
    """Evaluate latest causal BUY masks without re-running historical trades."""

    if not isinstance(request, CampaignRequest) or request.operation != "current_scan":
        raise ValueError("current scan requires a current_scan CampaignRequest")
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("Flexible current-scan root must be absolute")
    timestamp = now
    if timestamp is None:
        from pytz import timezone

        timestamp = datetime.now(timezone("Asia/Ho_Chi_Minh"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("current scan time must be timezone-aware")
    def emit(event: ProgressEvent) -> None:
        if callable(progress_fn):
            try:
                progress_fn(event)
            except Exception:
                pass

    common = preflight_common_as_of(engine, request.frozen_members)
    emit(ProgressEvent("common-as-of", 1, 1, "common completed bar verified"))
    if common.state == "blocked_common_as_of":
        return _persist_terminal(root, _blocked_manifest(request, "blocked_common_as_of", f"latest completed bar mismatch; laggards={','.join(common.lagging_tickers)}", invalid=common.lagging_tickers), common_as_of=common.common_as_of)
    if common.state == "data_invalid":
        return _persist_terminal(root, _blocked_manifest(request, "data_invalid", f"invalid history={','.join(common.invalid_tickers)}", invalid=common.invalid_tickers), common_as_of=common.common_as_of)

    current_by_ticker = common.snapshots_by_ticker
    statuses = {
        ticker: _source_status(engine, expected, current_by_ticker[ticker])
        for ticker, expected in zip(request.frozen_members, request.source_snapshots)
    }
    changed = tuple(ticker for ticker, status in statuses.items() if status in {"changed", "invalid", "stale"})
    if changed:
        items = tuple(
            CampaignItem(
                ticker,
                "source_changed" if statuses[ticker] == "changed" else "data_invalid" if statuses[ticker] == "invalid" else "data_stale",
            ) if ticker in changed else CampaignItem(ticker, "not_evaluated")
            for ticker in request.frozen_members
        )
        return _persist_terminal(
            root,
            transition(
                replace(
                    transition(create_manifest(request), "running"),
                    items=items,
                    safe_error_code="CURRENT.SOURCE_CHANGED",
                    safe_error_message=f"source recheck failed={','.join(changed)}",
                ),
                "completed_with_errors",
            ),
            common_as_of=common.common_as_of,
        )

    pairs = tuple(_load_qualified(root, request.frozen_members) if qualified is None else qualified)
    pairs_by_ticker, changed = _validated_current_pairs(engine, common, pairs)
    if changed:
        items = tuple(CampaignItem(ticker, "source_changed") if ticker in changed else CampaignItem(ticker, "not_evaluated") for ticker in request.frozen_members)
        return _persist_terminal(root, transition(replace(transition(create_manifest(request), "running"), items=items, safe_error_code="CURRENT.EVIDENCE_ANCHOR_CHANGED", safe_error_message=f"evidence anchor failed={','.join(changed)}"), "completed_with_errors"), common_as_of=common.common_as_of)

    no_qualified = tuple(ticker for ticker, values in pairs_by_ticker.items() if not values)
    if all(not values for values in pairs_by_ticker.values()):
        items = tuple(CampaignItem(ticker, "no_historically_qualified_rulebook") for ticker in request.frozen_members)
        return _persist_terminal(root, transition(replace(transition(create_manifest(request), "running"), items=items), "completed"), common_as_of=common.common_as_of)

    # Cache policy is operational input, but it must be explicit; silently
    # choosing reuse would bypass the <=24-hour user decision contract.
    if request.cache_choice not in {"reuse", "rebuild"}:
        items = tuple(CampaignItem(ticker, "current_evaluation_failed" if ticker not in no_qualified else "no_historically_qualified_rulebook") for ticker in request.frozen_members)
        return _persist_terminal(root, transition(replace(transition(create_manifest(request), "running"), items=items, safe_error_code="CURRENT.CACHE_CHOICE_REQUIRED", safe_error_message="cache_choice must be reuse or rebuild"), "completed_with_errors"))
    features = preflight_current_scan_features(engine, common, tuple(pair for values in pairs_by_ticker.values() for pair in values), root, timestamp)
    choice = request.cache_choice
    resolutions = {}
    receipt_ids: list[str] = []
    try:
        for key, preflight in features.items():
            resolution = resolve_frozen_feature_bundle(preflight.snapshot, preflight.build_contract, preflight.feature_plan.profile, root, cache_choice=choice, now=timestamp)
            resolution_plan = getattr(resolution, "plan", None)
            receipt_plan = getattr(getattr(resolution, "receipt", None), "plan", None)
            if (resolution_plan is not None and resolution_plan != preflight.feature_plan) or (receipt_plan is not None and receipt_plan != preflight.feature_plan):
                raise ValueError("feature receipt differs from preflight plan")
            resolutions[key] = resolution
            receipt_ids.append(resolution.receipt.receipt_id)
            emit(ProgressEvent("feature-resolution", len(resolutions), max(1, len(features)), f"resolved {key[0]}"))
        manifest = transition(create_manifest(request), "running")
        # Receipt durability is a hard ordering boundary: no current mask is
        # composed until every target/build contract receipt is persisted.
        for key, resolution in resolutions.items():
            write_feature_resolution_receipt(root, manifest.campaign_id, key[0], resolution.receipt)
    except (OSError, ValueError, RuntimeError) as error:
        manifest = transition(create_manifest(request), "running")
        blocked = "receipt differs from preflight plan" in str(error)
        items = tuple(
            CampaignItem(
                ticker,
                "not_evaluated" if blocked and ticker not in no_qualified else "current_evaluation_failed" if ticker not in no_qualified else "no_historically_qualified_rulebook",
            )
            for ticker in request.frozen_members
        )
        return _persist_terminal(
            root,
            transition(
                replace(
                    manifest,
                    items=items,
                    safe_error_code="CURRENT.RECEIPT_MISMATCH" if blocked else "CURRENT.FEATURE_RESOLUTION_FAILED",
                    safe_error_message=str(error),
                ),
                "completed_with_errors",
            ),
            common_as_of=common.common_as_of,
        )

    items: list[CampaignItem] = []
    evidence: dict[str, list[Mapping[str, object]]] = {ticker: [] for ticker in request.frozen_members}
    for ticker_index, ticker in enumerate(request.frozen_members, 1):
        if ticker in no_qualified:
            items.append(CampaignItem(ticker, "no_historically_qualified_rulebook"))
            continue
        triggered = False
        try:
            for pair in pairs_by_ticker[ticker]:
                definition, _ticker, contract, _profile, _anchor = _pair_fields(pair)
                resolution = resolutions[(ticker, contract.feature_build_contract_hash)]
                mask = compose_entry_mask(resolution.store, definition)
                if mask.shape != (len(resolution.store.dates),):
                    raise ValueError("current BUY mask has invalid shape")
                pair_triggered = bool(mask[-1])
                triggered = triggered or pair_triggered
                source_snapshot = getattr(pair, "source_snapshot", None)
                qualified_through = getattr(source_snapshot, "as_of_date", None)
                age_days = None if qualified_through is None or common.common_as_of is None else (common.common_as_of - qualified_through).days
                evidence[ticker].append({
                    "rulebook_id": rulebook_id(definition),
                    "animal_alias": animal_alias(rulebook_id(definition)),
                    "qualified_through": qualified_through,
                    "evidence_age_days": age_days,
                    "triggered": pair_triggered,
                })
        except Exception as error:
            items.append(CampaignItem(ticker, "current_evaluation_failed"))
            continue
        items.append(CampaignItem(ticker, "current_setup_found" if triggered else "no_current_setup"))
        emit(ProgressEvent("evaluation", ticker_index, len(request.frozen_members), f"evaluated {ticker}"))

    manifest = replace(transition(create_manifest(request), "running"), items=tuple(items), feature_receipt_ids=tuple(dict.fromkeys(receipt_ids)))
    final_state = "completed" if all(item.state in {"current_setup_found", "no_current_setup", "no_historically_qualified_rulebook"} for item in manifest.items) else "completed_with_errors"
    final = transition(manifest, final_state)
    return _persist_terminal(root, final, common_as_of=common.common_as_of, evidence=evidence)


__all__ = ["CommonAsOfPreflight", "CurrentScanCachePreflight", "CurrentScanState", "QualifiedCurrentPair", "preflight_common_as_of", "preflight_current_scan_cache", "preflight_current_scan_features", "scan_current_setup"]
