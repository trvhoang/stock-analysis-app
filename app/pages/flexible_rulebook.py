"""Standalone, non-trading workspace for Flexible Rulebook research."""

from __future__ import annotations

from datetime import datetime
from inspect import signature
import json
from pathlib import Path
import time
from typing import Callable, Sequence
from collections.abc import Mapping
import uuid

import pytz
import streamlit as st

from flexible_rulebook.benchmark import safe_default_scale_policy
from flexible_rulebook.activation import active_policy_directory, load_active_policy
from flexible_rulebook.catalog import catalog_revision_1
from flexible_rulebook.campaigns import CampaignRequest
from flexible_rulebook.contracts import (
    ExecutionContract,
    FeatureBuildContract,
    RuntimeBudget,
    SelectionPolicy,
    animal_alias,
    canonical_json,
    rulebook_id,
)
from flexible_rulebook.current_scan import (
    preflight_common_as_of,
    preflight_current_scan_cache,
    scan_current_setup,
)
from flexible_rulebook.discovery_activation import (
    continue_activated_discovery,
    preflight_activated_discovery,
    resume_activated_discovery,
    submit_activated_discovery,
)
from flexible_rulebook.features import FeaturePreflight, feature_snapshot_for_history
from flexible_rulebook.group_adapter import (
    FrozenGroup,
    available_named_group_names,
    snapshot_named_group,
)
from flexible_rulebook.history import HistorySnapshot, make_evaluation_split
from flexible_rulebook.search import candidate_space
from flexible_rulebook.runner import read_campaign, request_cancel
from flexible_rulebook.scope_expansion import (
    ScopeExpansionStatus,
    build_scope_expansion_request,
    parse_scope_values,
    read_scope_status,
)
from flexible_rulebook.scope_expansion_runner import submit_scope_expansion
from flexible_rulebook.service import (
    preflight_group_feature_components,
    qualify_rulebooks_for_group,
    reusable_rulebooks,
)
from flexible_rulebook.storage import (
    iter_signal_set_paths,
    read_selection_snapshot,
    read_signal_set,
    resolve_flexible_root,
    selection_memberships_by_evaluation,
    selection_memberships_for_evaluation,
)


_WORKSPACES = (
    "Discover",
    "Rulebook Library",
    "Cross-ticker Qualification",
    "Current Group BUY Scan",
)
_HCM = pytz.timezone("Asia/Ho_Chi_Minh")
_DISCOVERY_PREFLIGHT_KEY = "flexible_discovery_preflight_v2"
_DISCOVERY_CAMPAIGN_KEY = "flexible_discovery_campaign_id_v2"
_CACHE_CHOICE_PLACEHOLDER = "— Select cache treatment —"
_SCOPE_EXPANSION_JOB_KEY = "flexible_scope_expansion_job_v1"
_SCOPE_TICKERS_KEY = "flexible_scope_additional_tickers_v1"
_SCOPE_OPERATOR_KEY = "flexible_scope_operator_v1"
_SCOPE_NOTE_KEY = "flexible_scope_note_v1"
_SCOPE_METADATA_INITIALIZED_KEY = "flexible_scope_metadata_initialized_v1"
_SCOPE_GENERATED_NOTE_KEY = "flexible_scope_generated_note_v1"
_SCOPE_POLL_SECONDS = 3.0


def build_current_scan_request(
    snapshots: Sequence[HistorySnapshot],
    *,
    cache_choice: str,
) -> CampaignRequest:
    """Freeze one ready common-as-of preflight for the current-scan service."""

    values = tuple(snapshots)
    if (
        not values
        or any(not isinstance(item, HistorySnapshot) or item.quality_state != "eligible" for item in values)
        or len({item.ticker for item in values}) != len(values)
        or len({item.as_of_date for item in values}) != 1
    ):
        raise ValueError("current scan requires eligible common-as-of snapshots")
    if cache_choice not in {"reuse", "rebuild"}:
        raise ValueError("current scan cache choice must be reuse or rebuild")
    contract = FeatureBuildContract()
    return CampaignRequest(
        operation="current_scan",
        frozen_members=tuple(item.ticker for item in values),
        source_snapshots=tuple(feature_snapshot_for_history(item) for item in values),
        catalog_hash=catalog_revision_1().catalog_hash,
        engine_revision="flexible-engine-v1",
        rulebook_ids=(),
        feature_build_contract_hashes=(contract.feature_build_contract_hash,),
        feature_plan_hashes=(),
        execution_contract=ExecutionContract(),
        split=make_evaluation_split(values[0]),
        runtime_budget=RuntimeBudget(),
        selection_policy=SelectionPolicy(),
        per_ticker_budget=1,
        cache_choice=cache_choice,
    )


def build_qualification_request(
    group: FrozenGroup,
    rulebook_ids: Sequence[str],
    preflights: dict[tuple[str, str], FeaturePreflight],
) -> CampaignRequest:
    """Freeze the exact group preflight before a qualification run may begin."""

    identifiers = tuple(rulebook_ids)
    if (
        not isinstance(group, FrozenGroup)
        or not group.members
        or not identifiers
        or len(set(identifiers)) != len(identifiers)
        or any(not isinstance(item, str) or not item.startswith("frb_") for item in identifiers)
    ):
        raise ValueError("qualification requires frozen members and immutable rulebook IDs")
    by_ticker: dict[str, FeaturePreflight] = {}
    for key, preflight in preflights.items():
        if not isinstance(key, tuple) or len(key) != 2 or not isinstance(preflight, FeaturePreflight):
            raise ValueError("qualification preflight map is invalid")
        ticker, contract_hash = key
        if ticker not in group.members or contract_hash != preflight.build_contract.feature_build_contract_hash:
            raise ValueError("qualification preflight is outside the frozen group")
        if ticker in by_ticker:
            raise ValueError("qualification requires one preflight per target/build contract")
        by_ticker[ticker] = preflight
    if set(by_ticker) != set(group.members):
        raise ValueError("qualification preflight must cover every frozen member")
    ordered = tuple(by_ticker[ticker] for ticker in group.members)
    contracts = {item.build_contract.feature_build_contract_hash for item in ordered}
    if len(contracts) != 1:
        raise ValueError("qualification requires one compatible build contract")
    return CampaignRequest(
        operation="qualify",
        frozen_members=group.members,
        source_snapshots=tuple(item.feature_plan.snapshot for item in ordered),
        catalog_hash=catalog_revision_1().catalog_hash,
        engine_revision="flexible-engine-v1",
        rulebook_ids=identifiers,
        feature_build_contract_hashes=tuple(contracts),
        feature_plan_hashes=tuple(dict.fromkeys(item.feature_plan.feature_plan_hash for item in ordered)),
        execution_contract=ExecutionContract(),
        split=make_evaluation_split(ordered[0].snapshot),
        runtime_budget=RuntimeBudget(),
        selection_policy=SelectionPolicy(),
        per_ticker_budget=1,
        group_snapshot=(group.group_id, group.group_name, group.source_updated_at, *group.members),
    )


def _preflight_policy_digest(preflight: object) -> str | None:
    """Return a preflight's immutable policy digest without trusting UI state."""

    policy = getattr(preflight, "policy", None)
    value = getattr(policy, "policy_digest", None)
    return value if isinstance(value, str) else None


def _policy_anchor_summary(policy: object) -> str:
    """Format immutable benchmark-as-of anchors for a read-only policy label."""

    entries = getattr(policy, "source_anchors", ())
    if not isinstance(entries, tuple):
        return "unavailable"
    labels: list[str] = []
    for entry in entries:
        if not isinstance(entry, tuple) or len(entry) != 2:
            return "unavailable"
        ticker, identity = entry
        if not isinstance(ticker, str) or not isinstance(identity, str):
            return "unavailable"
        try:
            payload = json.loads(identity)
        except json.JSONDecodeError:
            return "unavailable"
        as_of = payload.get("requested_as_of") if isinstance(payload, dict) else None
        if not isinstance(as_of, str):
            return "unavailable"
        labels.append(f"{ticker}: {as_of}")
    return "; ".join(labels) or "unavailable"


def _preflight_source_fingerprint(preflight: object) -> str | None:
    """Read the frozen current-source fingerprint for a Streamlit state key."""

    snapshot = getattr(preflight, "snapshot", None)
    for name in ("fingerprint", "raw_history_fingerprint"):
        value = getattr(snapshot, name, None)
        if isinstance(value, str) and value:
            return value
    return None


def _clear_discovery_preflight() -> None:
    """Discard an unsubmitted UI-only preflight; no durable work is changed."""

    st.session_state.pop(_DISCOVERY_PREFLIGHT_KEY, None)


def _safe_discovery_error(action: str, error: Exception) -> None:
    """Keep operational errors understandable without exposing internal details."""

    message = str(error).strip() or "an unexpected safe failure occurred"
    st.warning(f"{action} was not completed: {message}")


def _call_with_progress(function: Callable[..., object], *args: object, progress_fn: Callable[..., None], **kwargs: object) -> object:
    """Pass progress only to implementations that advertise the optional hook."""

    try:
        parameters = signature(function).parameters
        accepts = "progress_fn" in parameters or any(
            parameter.kind is parameter.VAR_KEYWORD for parameter in parameters.values()
        )
    except (TypeError, ValueError):
        accepts = False
    if accepts:
        kwargs["progress_fn"] = progress_fn
    return function(*args, **kwargs)


def _continuation_is_legal(manifest: object) -> bool:
    """Mirror the visible, cheap part of the activated continuation contract."""

    if getattr(manifest, "state", None) not in {"completed", "completed_with_errors"}:
        return False
    request = getattr(manifest, "request", None)
    assignment = getattr(request, "frontier_assignment", None)
    next_slot = getattr(manifest, "next_slot", None)
    budget = getattr(request, "per_ticker_budget", None)
    if (
        assignment is None
        or not isinstance(getattr(request, "activation_policy_digest", None), str)
        or not isinstance(next_slot, int)
        or not isinstance(budget, int)
        or getattr(manifest, "uncommitted_slot", None) is not None
        or getattr(manifest, "chain_attempted_count", None) != next_slot
    ):
        return False
    strata = getattr(assignment, "strata", ())
    size = sum(getattr(stratum, "size", 0) for stratum in strata)
    return size - next_slot >= budget


def _render_discovery_lifecycle(
    *,
    root: Path,
    campaign_reader_fn: Callable[[str, Path], object],
    cancel_campaign_fn: Callable[[str, Path], None],
    resume_discovery_fn: Callable[..., str],
    continue_discovery_fn: Callable[..., str],
    rerun_fn: Callable[[], None],
) -> None:
    """Show one persisted campaign and only actions legal for its visible state."""

    campaign_id = st.session_state.get(_DISCOVERY_CAMPAIGN_KEY)
    if not isinstance(campaign_id, str) or not campaign_id:
        return
    try:
        manifest = campaign_reader_fn(campaign_id, root)
    except (OSError, ValueError) as error:
        _safe_discovery_error("Campaign status refresh", error)
        return

    state = getattr(manifest, "state", "unknown")
    request = getattr(manifest, "request", None)
    assignment = getattr(request, "frontier_assignment", None)
    start_slot = getattr(assignment, "start_slot", None)
    attempt_count = getattr(assignment, "attempt_count", None)
    slot_label = "assigned slots unavailable"
    if isinstance(start_slot, int) and isinstance(attempt_count, int):
        slot_label = f"assigned slots {start_slot}–{start_slot + attempt_count - 1}"
    st.caption(f"Campaign `{campaign_id}` — **{state}**; {slot_label}.")
    if isinstance(start_slot, int) and isinstance(attempt_count, int) and attempt_count > 0:
        completed = max(0, min(attempt_count, (getattr(manifest, "next_slot", start_slot) or start_slot) - start_slot))
        st.progress(completed / attempt_count, text=f"frontier: {completed}/{attempt_count} assigned slots")
    code = getattr(manifest, "safe_error_code", None)
    safe_message = getattr(manifest, "safe_error_message", None)
    if isinstance(code, str) and code:
        suffix = f" {safe_message}" if isinstance(safe_message, str) and safe_message else ""
        st.warning(f"Campaign stopped safely: {code}.{suffix}")
    if st.button("Refresh Discover"):
        rerun_fn()
    policy_bound = isinstance(getattr(request, "activation_policy_digest", None), str)
    if policy_bound and state in {"queued", "running"} and st.button("Cancel Discover"):
        try:
            cancel_campaign_fn(campaign_id, root)
        except (OSError, ValueError) as error:
            _safe_discovery_error("Cancel Discover", error)
        else:
            rerun_fn()
    if policy_bound and state in {"interrupted", "cancelled", "blocked"} and st.button("Resume Discover"):
        try:
            st.session_state[_DISCOVERY_CAMPAIGN_KEY] = resume_discovery_fn(campaign_id, root=root)
        except (OSError, ValueError) as error:
            _safe_discovery_error("Resume Discover", error)
        else:
            rerun_fn()
    if _continuation_is_legal(manifest) and st.button("Continue Discover"):
        try:
            st.session_state[_DISCOVERY_CAMPAIGN_KEY] = continue_discovery_fn(campaign_id, root=root)
        except (OSError, ValueError) as error:
            _safe_discovery_error("Continue Discover", error)
        else:
            rerun_fn()


def _scope_status_path(job_id: str, benchmark_directory: Path) -> Path:
    """Resolve a scope-expansion status sidecar inside its benchmark root."""

    if not isinstance(job_id, str) or not job_id.startswith("fse_"):
        raise ValueError("scope expansion job ID is invalid")
    root = benchmark_directory.resolve()
    candidate = (root / "jobs" / f"{job_id}.status.json").resolve()
    if root not in candidate.parents:
        raise ValueError("scope expansion status path is outside benchmark directory")
    return candidate


def _read_scope_status(job_id: str, benchmark_directory: Path) -> ScopeExpansionStatus:
    return read_scope_status(_scope_status_path(job_id, benchmark_directory))


def _scope_expansion_note(tickers: Sequence[str]) -> str:
    """Describe the normalized ticker expansion in the editable audit note."""

    values = tuple(tickers)
    if not values:
        return "Scope expansion for Flexible Rulebook discovery."
    if len(values) == 1:
        names = values[0]
    elif len(values) == 2:
        names = f"{values[0]} and {values[1]}"
    else:
        names = f"{', '.join(values[:-1])} and {values[-1]}"
    return f"{names} scope expansion for Flexible Rulebook discovery."


def _scope_ticker_values() -> tuple[str, ...]:
    """Return valid typed expansion tickers without making input errors fatal."""

    try:
        return parse_scope_values(str(st.session_state.get(_SCOPE_TICKERS_KEY, "")), "ticker")
    except ValueError:
        return ()


def _initialize_scope_expansion_metadata() -> None:
    """Set editable audit defaults once before Streamlit creates its widgets."""

    if st.session_state.get(_SCOPE_METADATA_INITIALIZED_KEY):
        return
    if not st.session_state.get(_SCOPE_OPERATOR_KEY):
        st.session_state[_SCOPE_OPERATOR_KEY] = f"admin {datetime.now(_HCM):%d%b%y}"
    generated_note = _scope_expansion_note(_scope_ticker_values())
    if not st.session_state.get(_SCOPE_NOTE_KEY):
        st.session_state[_SCOPE_NOTE_KEY] = generated_note
    st.session_state[_SCOPE_GENERATED_NOTE_KEY] = st.session_state[_SCOPE_NOTE_KEY]
    st.session_state[_SCOPE_METADATA_INITIALIZED_KEY] = True


def _refresh_scope_expansion_note() -> None:
    """Refresh only the still-generated note when the ticker widget changes."""

    current_note = st.session_state.get(_SCOPE_NOTE_KEY, "")
    generated_note = st.session_state.get(_SCOPE_GENERATED_NOTE_KEY)
    if current_note not in ("", generated_note):
        return
    next_note = _scope_expansion_note(_scope_ticker_values())
    st.session_state[_SCOPE_NOTE_KEY] = next_note
    st.session_state[_SCOPE_GENERATED_NOTE_KEY] = next_note


def _render_scope_expansion(
    engine: object,
    *,
    policy: object | None,
    policy_reason: str,
    common_as_of_preflight_fn: Callable[[object, tuple[str, ...]], object],
    scope_submit_fn: Callable[..., str],
    scope_status_fn: Callable[[str, Path], ScopeExpansionStatus],
    scope_benchmark_directory_fn: Callable[[], Path],
    scope_refresh_fn: Callable[[], None],
    scope_rerun_fn: Callable[[], None],
) -> None:
    """Render additive scope inputs, one benchmark/activate action, and progress."""

    with st.expander("Expand Discovery Scope", expanded=False):
        _initialize_scope_expansion_metadata()
        policy_digest = getattr(policy, "policy_digest", None)
        current_tickers = tuple(getattr(policy, "allowed_tickers", ()))
        current_seeds = tuple(getattr(policy, "allowed_seeds", ()))
        valid_policy = (
            isinstance(policy_digest, str)
            and bool(policy_digest)
            and bool(current_tickers)
            and bool(current_seeds)
            and getattr(policy, "worker_count", None) == 1
            and isinstance(getattr(policy, "cap_attempts", None), int)
            and getattr(policy, "cap_attempts", 0) > 0
        )
        additional_tickers = st.text_input(
            "Additional tickers",
            key=_SCOPE_TICKERS_KEY,
            on_change=_refresh_scope_expansion_note,
        )
        additional_seeds = st.text_input(
            "Additional seeds", key="flexible_scope_additional_seeds_v1",
        )
        approved_by = st.text_input("Operator identity", key=_SCOPE_OPERATOR_KEY)
        approval_note = st.text_area("Approval note", key=_SCOPE_NOTE_KEY)
        parse_error: str | None = None
        try:
            extra_tickers = parse_scope_values(additional_tickers, "ticker")
            extra_seeds = parse_scope_values(additional_seeds, "seed")
        except ValueError as error:
            extra_tickers, extra_seeds = (), ()
            parse_error = str(error)
        union_tickers = tuple(sorted(set(current_tickers).union(extra_tickers)))
        union_seeds = tuple(sorted(set(current_seeds).union(extra_seeds)))
        is_new_scope = bool(
            set(union_tickers) - set(current_tickers)
            or set(union_seeds) - set(current_seeds)
        )
        pair_count = len(union_tickers) * len(union_seeds)
        st.caption(
            f"Union scope: {', '.join(union_tickers) or 'unavailable'} × "
            f"{', '.join(union_seeds) or 'unavailable'} "
            f"({pair_count} pairs; {pair_count * 100:,} cold windows)."
        )
        if parse_error:
            st.warning(parse_error)
        if not valid_policy:
            st.info(f"Scope expansion is unavailable until an active policy is loaded. {policy_reason}")
        enabled = bool(
            valid_policy and is_new_scope and not parse_error
            and approved_by.strip() and approval_note.strip()
        )
        if st.button("Benchmark and Activate Scope", disabled=not enabled):
            try:
                common = common_as_of_preflight_fn(engine, union_tickers)
                state = getattr(common, "state", None)
                snapshots = tuple(getattr(common, "snapshots", ()))
                if state == "ready":
                    benchmark_as_of = getattr(common, "common_as_of", None)
                elif (
                    state == "blocked_common_as_of"
                    and snapshots
                    and all(
                        getattr(item, "quality_state", None) == "eligible"
                        and getattr(item, "as_of_date", None) is not None
                        for item in snapshots
                    )
                ):
                    # A lagging member still has a valid completed bar.  Use
                    # the latest date available to every member (the minimum
                    # per-ticker watermark), then let the benchmark loader
                    # slice each source causally at that shared date.
                    benchmark_as_of = min(item.as_of_date for item in snapshots)
                else:
                    raise ValueError("latest common completed bar is unavailable for the full ticker union")
                from datetime import date as _date
                if type(benchmark_as_of) is not _date:
                    raise ValueError("latest common completed bar is unavailable for the full ticker union")
                request = build_scope_expansion_request(
                    policy,
                    benchmark_as_of=benchmark_as_of,
                    additional_tickers=additional_tickers,
                    additional_seeds=additional_seeds,
                    approved_by=approved_by,
                    approval_note=approval_note,
                )
                job_id = scope_submit_fn(
                    request,
                    benchmark_directory=scope_benchmark_directory_fn(),
                )
            except (OSError, RuntimeError, ValueError) as error:
                _safe_discovery_error("Scope expansion", error)
            else:
                st.session_state[_SCOPE_EXPANSION_JOB_KEY] = job_id
                st.success(f"Scope expansion `{job_id}` submitted; activation follows benchmark success.")
                scope_rerun_fn()

    job_id = st.session_state.get(_SCOPE_EXPANSION_JOB_KEY)
    if not isinstance(job_id, str) or not job_id:
        return
    try:
        status = scope_status_fn(job_id, scope_benchmark_directory_fn())
    except (OSError, ValueError):
        return
    total_pairs = max(1, status.total_pairs)
    within_pair = min(1.0, status.completed_windows / max(1, status.required_windows))
    progress = min(1.0, max(0.0, (status.completed_pairs + within_pair) / total_pairs))
    st.subheader("Scope expansion progress")
    st.progress(progress, text=f"{status.phase}: {status.completed_pairs}/{status.total_pairs} pairs")
    current = ""
    if status.current_ticker and status.current_seed:
        current = f"Current pair: {status.current_ticker} / {status.current_seed}. "
    st.caption(
        f"Job `{status.job_id}` — **{status.state}**. {current}"
        f"Windows: {status.completed_windows}/{status.required_windows}; "
        f"elapsed: {status.elapsed_seconds:.1f}s."
    )
    if status.report_digest:
        st.caption(f"Report: `{status.report_digest}`; policy: `{status.policy_digest or 'unavailable'}`.")
    if status.safe_error:
        st.warning(f"Scope expansion stopped safely: {status.safe_error}")
    if status.state in {"queued", "running"}:
        if st.button("Refresh Scope Expansion"):
            scope_refresh_fn()
        st.caption("Progress updates every 3 seconds while active.")
        # ponytail: Streamlit 1.32 has no fragment scheduler. This blocks only
        # the active scope session briefly; upgrade to native fragments later.
        time.sleep(_SCOPE_POLL_SECONDS)
        scope_refresh_fn()
    elif status.state == "interrupted" and st.button("Refresh Scope Expansion"):
        scope_refresh_fn()


def _render_discover(
    engine: object,
    *,
    root: Path,
    policy_loader_fn: Callable[[], tuple[object | None, str]],
    discovery_preflight_fn: Callable[..., object],
    discovery_submit_fn: Callable[..., str],
    common_as_of_preflight_fn: Callable[[object, tuple[str, ...]], object],
    scope_submit_fn: Callable[..., str],
    scope_status_fn: Callable[[str, Path], ScopeExpansionStatus],
    scope_benchmark_directory_fn: Callable[[], Path],
    scope_refresh_fn: Callable[[], None],
    scope_rerun_fn: Callable[[], None],
    campaign_reader_fn: Callable[[str, Path], object],
    cancel_campaign_fn: Callable[[str, Path], None],
    resume_discovery_fn: Callable[..., str],
    continue_discovery_fn: Callable[..., str],
    rerun_fn: Callable[[], None],
) -> None:
    """Render a preflight-first policy-bound Discover workspace."""

    fallback = safe_default_scale_policy()
    catalog = catalog_revision_1()
    space = candidate_space(catalog)
    try:
        policy, policy_reason = policy_loader_fn()
    except (OSError, ValueError) as error:
        policy, policy_reason = None, str(error)
    policy_digest = getattr(policy, "policy_digest", None)
    allowed_tickers = tuple(getattr(policy, "allowed_tickers", ()))
    allowed_seeds = tuple(getattr(policy, "allowed_seeds", ()))
    cap_attempts = getattr(policy, "cap_attempts", fallback.max_discovery_attempt_count)
    worker_count = getattr(policy, "worker_count", fallback.worker_count)
    policy_ready = (
        isinstance(policy_digest, str)
        and bool(policy_digest)
        and allowed_tickers
        and allowed_seeds
        and isinstance(cap_attempts, int)
        and cap_attempts > 0
        and worker_count == 1
    )

    st.subheader("Discover")
    st.markdown(
        f"Candidate space: `{space.size:,}` frozen catalog definitions. "
        f"Safe policy: **{cap_attempts} attempts**, {worker_count} worker."
    )

    _render_scope_expansion(
        engine,
        policy=policy,
        policy_reason=str(policy_reason),
        common_as_of_preflight_fn=common_as_of_preflight_fn,
        scope_submit_fn=scope_submit_fn,
        scope_status_fn=scope_status_fn,
        scope_benchmark_directory_fn=scope_benchmark_directory_fn,
        scope_refresh_fn=scope_refresh_fn,
        scope_rerun_fn=scope_rerun_fn,
    )

    if not policy_ready:
        _clear_discovery_preflight()
        st.info(
            "The UI cannot authorize a discovery cap. Discovery is intentionally paused until a "
            "production-scale benchmark records a fixed attempt limit. To continue now, open "
            "Rulebook Library to inspect saved definitions, then use Cross-ticker Qualification "
            "to evaluate them; Current Group BUY Scan requires qualified evidence."
        )
        if isinstance(policy_reason, str) and policy_reason:
            st.caption(f"Activation status: {policy_reason}")
        st.button(
            "Preflight Discover",
            disabled=True,
            help="An active immutable policy is required before preflight.",
        )
        st.button(
            "Start Discover",
            disabled=True,
            help="A production benchmark record must authorize a fixed discovery attempt cap first.",
        )
        _render_discovery_lifecycle(
            root=root,
            campaign_reader_fn=campaign_reader_fn,
            cancel_campaign_fn=cancel_campaign_fn,
            resume_discovery_fn=resume_discovery_fn,
            continue_discovery_fn=continue_discovery_fn,
            rerun_fn=rerun_fn,
        )
        return

    ticker = st.selectbox(
        "Source ticker",
        ("— Select ticker —", *allowed_tickers),
        key="flexible_discovery_ticker_v2",
    )
    seed = st.selectbox(
        "Seed",
        ("— Select seed —", *allowed_seeds),
        key="flexible_discovery_seed_v2",
    )
    ticker = ticker.strip().upper() if isinstance(ticker, str) else ""
    seed = seed.strip() if isinstance(seed, str) else ""
    st.caption(
        f"Active policy `{policy_digest}`; benchmark report `{getattr(policy, 'report_digest', 'unavailable')}`; "
        f"fixed cap {cap_attempts}. Allowed tickers: {', '.join(allowed_tickers)}. "
        f"Allowed seeds: {', '.join(allowed_seeds)}. Benchmark anchors: "
        f"{_policy_anchor_summary(policy)}."
    )
    input_key = (policy_digest, ticker, seed)
    stored = st.session_state.get(_DISCOVERY_PREFLIGHT_KEY)
    if isinstance(stored, dict) and stored.get("input_key") != input_key:
        _clear_discovery_preflight()
        stored = None

    selected_scope = ticker in allowed_tickers and seed in allowed_seeds
    if st.button("Preflight Discover", disabled=not selected_scope):
        _clear_discovery_preflight()
        if ticker not in allowed_tickers or seed not in allowed_seeds:
            st.warning("Ticker or seed is outside the active policy scope.")
        else:
            try:
                preflight = discovery_preflight_fn(
                    engine,
                    ticker,
                    seed,
                    policy,
                    root=root,
                    now=datetime.now(_HCM),
                )
                source_fingerprint = _preflight_source_fingerprint(preflight)
                if (
                    _preflight_policy_digest(preflight) != policy_digest
                    or getattr(preflight, "ticker", None) != ticker
                    or getattr(preflight, "seed", None) != seed
                    or source_fingerprint is None
                ):
                    raise ValueError("preflight does not match the active policy and source input")
            except (OSError, ValueError) as error:
                _safe_discovery_error("Preflight Discover", error)
            else:
                st.session_state[_DISCOVERY_PREFLIGHT_KEY] = {
                    "input_key": input_key,
                    "source_fingerprint": source_fingerprint,
                    "preflight": preflight,
                }
                stored = st.session_state[_DISCOVERY_PREFLIGHT_KEY]

    if isinstance(stored, dict):
        preflight = stored.get("preflight")
        source_fingerprint = stored.get("source_fingerprint")
        offer = getattr(preflight, "cache_offer", None)
        reusable = tuple(getattr(offer, "reusable_keys", ()))
        stale = tuple(getattr(offer, "stale_keys", ()))
        missing = tuple(getattr(offer, "missing_keys", ()))
        options = [_CACHE_CHOICE_PLACEHOLDER]
        if reusable and not stale and not missing:
            options.append("reuse")
        options.append("rebuild")
        choice = st.selectbox(
            "Indicator cache",
            options,
            key=f"flexible_discovery_cache_v2_{policy_digest[:12]}_{source_fingerprint[:12]}",
        )
        st.caption(
            f"Cache diagnostics — reusable: {len(reusable)}, stale: {len(stale)}, missing: {len(missing)}."
        )
        full_key = (*input_key, source_fingerprint, choice)
        st.session_state[_DISCOVERY_PREFLIGHT_KEY]["key"] = full_key
        can_start = choice in {"reuse", "rebuild"}
        if st.button("Start Discover", disabled=not can_start):
            try:
                campaign_id = discovery_submit_fn(preflight, cache_choice=choice, root=root)
            except (OSError, ValueError) as error:
                if "cache preflight changed" in str(error):
                    _clear_discovery_preflight()
                _safe_discovery_error("Start Discover", error)
            else:
                st.session_state[_DISCOVERY_CAMPAIGN_KEY] = campaign_id
                _clear_discovery_preflight()
                st.success(f"Discover campaign `{campaign_id}` was submitted.")
                rerun_fn()
    else:
        st.button(
            "Start Discover",
            disabled=True,
            help="Run a matching policy preflight and select its cache treatment first.",
        )

    _render_discovery_lifecycle(
        root=root,
        campaign_reader_fn=campaign_reader_fn,
        cancel_campaign_fn=cancel_campaign_fn,
        resume_discovery_fn=resume_discovery_fn,
        continue_discovery_fn=continue_discovery_fn,
        rerun_fn=rerun_fn,
    )


def _display_scalar(value: object) -> object:
    """Decode canonical scalar wrappers only for read-only Streamlit labels."""

    if not isinstance(value, dict) or len(value) != 1:
        return value
    if "$date" in value or "$datetime" in value or "$decimal" in value:
        return str(next(iter(value.values())))
    if "$float" in value:
        try:
            return float(str(value["$float"]))
        except ValueError:
            return "Unavailable"
    return value


def _primitive_label(value: object) -> str:
    """Make one immutable primitive readable without changing its identity."""

    if not isinstance(value, dict) or not isinstance(value.get("family"), str):
        return "Unavailable"
    settings = value.get("settings")
    if not isinstance(settings, dict) or not settings:
        return value["family"]
    rendered = ", ".join(f"{key}={_display_scalar(settings[key])}" for key in sorted(settings))
    return f"{value['family']}({rendered})"


def _definition_profile(definition: object) -> str:
    """Summarize the reusable primitive families of one definition."""

    predicates = (
        *getattr(definition, "buy_predicates", ()),
        *getattr(definition, "gates", ()),
        *getattr(definition, "filters", ()),
        *getattr(definition, "exits", ()),
    )
    labels = {
        _primitive_label(predicate.primitive.to_dict())
        for predicate in predicates
        if hasattr(predicate, "primitive")
    }
    atr = getattr(definition, "atr_primitive", None)
    if atr is not None and hasattr(atr, "to_dict"):
        labels.add(_primitive_label(atr.to_dict()))
    return ", ".join(sorted(labels)) or "Unavailable"


def _document_profile(document: dict[str, object]) -> str:
    profile = document.get("feature_profile")
    specs = profile.get("primitive_specs") if isinstance(profile, dict) else None
    if not isinstance(specs, list):
        return "Unavailable"
    labels = {_primitive_label(item) for item in specs}
    return ", ".join(sorted(labels)) or "Unavailable"


def _split_label(document: dict[str, object]) -> str:
    split = document.get("split")
    if not isinstance(split, dict):
        return "Unavailable"
    training = split.get("training")
    test = split.get("test")
    if not isinstance(training, dict) or not isinstance(test, dict):
        return "Unavailable"
    training_end = _display_scalar(training.get("end"))
    test_start = _display_scalar(test.get("start"))
    if not isinstance(training_end, str) or not isinstance(test_start, str):
        return "Unavailable"
    return f"train ≤ {training_end}; test ≥ {test_start}"


def _library_rows(root: Path) -> tuple[dict[str, object], ...]:
    """Project only readable Flexible signal-set evidence for the library."""

    rows: list[dict[str, object]] = []
    membership_index = selection_memberships_by_evaluation(root)
    try:
        definitions = reusable_rulebooks(root)
    except ValueError:
        definitions = ()
    for definition in definitions:
        identifier = rulebook_id(definition)
        rows.append(
            {
                "Ticker": "—",
                "Alias": animal_alias(identifier),
                "Rulebook ID": identifier,
                "Short ID": f"{identifier[:16]}…",
                "Feature profile": _definition_profile(definition),
                "Source as-of": "—",
                "Split": "—",
                "Training n": None,
                "Test n": None,
                "Training win rate %": None,
                "Test win rate %": None,
                "Training profit %": None,
                "Test profit %": None,
                "Training Sharpe": None,
                "Test Sharpe": None,
                "Training rank": None,
                "Selection scope": "Definition only",
                "Selection status": "Definition only",
                "Duplicate blocker": "—",
                "Artifact": identifier,
                "Persistence": "definition",
                "_document": {
                    "artifact_kind": "flexible_rulebook_definition",
                    "rulebook_id": identifier,
                    "definition": definition.to_semantic_dict(),
                },
            }
        )
    for path in iter_signal_set_paths(root):
        try:
            document = read_signal_set(path)
            training = document["training_metrics"]
            test = document["test_metrics"]
            if not isinstance(training, dict) or not isinstance(test, dict):
                raise ValueError("metrics are unavailable")
            source = document.get("source_snapshot")
            for selection in selection_states_for_document(
                root,
                document,
                membership_index=membership_index,
            ):
                rows.append(
                    {
                        "Ticker": document["ticker"],
                        "Alias": document["animal_alias"],
                        "Rulebook ID": document["rulebook_id"],
                        "Short ID": f"{str(document['rulebook_id'])[:16]}…",
                        "Feature profile": _document_profile(document),
                        "Source as-of": _display_scalar(source.get("as_of_date", "Unavailable")) if isinstance(source, dict) else "Unavailable",
                        "Split": _split_label(document),
                        "Training n": training["n"],
                        "Test n": test["n"],
                        "Training win rate %": _display_scalar(training["win_rate"]),
                        "Test win rate %": _display_scalar(test["win_rate"]),
                        "Training profit %": _display_scalar(training["total_return_pct"]),
                        "Test profit %": _display_scalar(test["total_return_pct"]),
                        "Training Sharpe": _display_scalar(training["sharpe"]),
                        "Test Sharpe": _display_scalar(test["sharpe"]),
                        **selection,
                        "Artifact": document["evaluation_id"],
                        "Persistence": document["persistence_reason"],
                        "_document": document,
                    }
                )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(rows)


def filter_library_rows(
    rows: Sequence[dict[str, object]],
    *,
    ticker_filter: str,
    rulebook_filter: str,
) -> tuple[dict[str, object], ...]:
    """Filter an existing library projection without reading or replaying work."""

    ticker = ticker_filter.strip().upper()
    rulebook = rulebook_filter.strip().lower()
    return tuple(
        row
        for row in rows
        if ticker in str(row.get("Ticker", "")).upper()
        and rulebook in str(row.get("Rulebook ID", "")).lower()
    )


def selection_states_for_document(
    root: Path,
    document: dict[str, object],
    *,
    membership_index: Mapping[str, Sequence[dict[str, object]]] | None = None,
) -> tuple[dict[str, object], ...]:
    """Resolve only campaign membership records that prove this evaluation link."""

    identifier = document.get("rulebook_id")
    evaluation_id = document.get("evaluation_id")
    ticker = document.get("ticker")
    source = document.get("source_snapshot")
    split = document.get("split")
    default = {
        "Training rank": None,
        "Selection scope": "Unlinked evidence",
        "Selection status": "No campaign selection link",
        "Duplicate blocker": "—",
    }
    if (
        not isinstance(identifier, str)
        or not isinstance(evaluation_id, str)
        or not isinstance(ticker, str)
        or not isinstance(source, dict)
        or not isinstance(split, dict)
    ):
        return (default,)
    fingerprint = source.get("raw_history_fingerprint")
    if membership_index is None:
        try:
            memberships = selection_memberships_for_evaluation(root, evaluation_id)
        except ValueError:
            return (default,)
    else:
        memberships = tuple(membership_index.get(evaluation_id, ()))
    states: list[dict[str, object]] = []
    for membership in memberships:
        if (
            membership.get("rulebook_id") != identifier
            or membership.get("ticker") != ticker
            or membership.get("source_fingerprint") != fingerprint
            or membership.get("split") != split
        ):
            continue
        campaign_id = membership["campaign_id"]
        selection_snapshot_id = membership["selection_snapshot_id"]
        try:
            snapshot = read_selection_snapshot(root, campaign_id, selection_snapshot_id)
        except ValueError:
            states.append({**default, "Selection status": "Linked selection evidence unavailable"})
            continue
        ranked = snapshot.get("ranked_rulebook_ids")
        selected = snapshot.get("selected_rulebook_ids")
        blockers = snapshot.get("blocker_relations")
        if not isinstance(ranked, list) or not isinstance(selected, list) or not isinstance(blockers, list):
            states.append({**default, "Selection status": "Linked selection evidence unavailable"})
            continue
        rank = ranked.index(identifier) + 1 if identifier in ranked else None
        state: dict[str, object] = {
            "Training rank": rank,
            "Selection scope": str(snapshot.get("selection_scope", "Unavailable")),
            "Selection status": (
                "Top 3 selected"
                if identifier in selected
                else "Ranked, not selected"
                if identifier in ranked
                else "Not present in linked selection snapshot"
            ),
            "Duplicate blocker": "—",
        }
        for blocker in blockers:
            if not isinstance(blocker, dict) or blocker.get("blocked_rulebook_id") != identifier:
                continue
            representative = blocker.get("representative_rulebook_id")
            numerator = blocker.get("overlap_numerator")
            denominator = blocker.get("overlap_denominator")
            if isinstance(representative, str) and isinstance(numerator, int) and isinstance(denominator, int):
                state["Selection status"] = "Rejected near-duplicate"
                state["Duplicate blocker"] = (
                    f"{animal_alias(representative)} ({numerator}/{denominator}; ≥75% overlap)"
                )
            break
        states.append(state)
    return tuple(states) or (default,)


def selection_state_for_document(root: Path, document: dict[str, object]) -> dict[str, object]:
    """Return one state for focused use; the library expands multiple campaigns."""

    return selection_states_for_document(root, document)[0]


def _visible_library_row(row: dict[str, object]) -> dict[str, object]:
    """Keep document bytes available for detail/download without table leakage."""

    return {key: value for key, value in row.items() if not key.startswith("_")}


def _render_library(root: Path) -> None:
    """Render immutable Flexible evidence without any campaign replay."""

    st.subheader("Rulebook Library")
    rows = _library_rows(root)
    if not rows:
        st.info(
            f"No Flexible Rulebook definitions or signal-set evidence found at `{root}`. "
            "Discover is paused because no benchmark-authorized attempt cap exists. "
            "Legacy V3 artifacts are not used."
        )
        return
    ticker_column, rulebook_column = st.columns(2)
    with ticker_column:
        ticker_filter = st.text_input("Library ticker filter", key="flexible_library_ticker_filter_v1")
    with rulebook_column:
        rulebook_filter = st.text_input("Library rulebook ID filter", key="flexible_library_rulebook_filter_v1")
    filtered = filter_library_rows(
        rows,
        ticker_filter=ticker_filter,
        rulebook_filter=rulebook_filter,
    )
    rejected = tuple(
        row for row in filtered if row.get("Selection status") == "Rejected near-duplicate"
    )
    visible = tuple(
        row for row in filtered if row.get("Selection status") != "Rejected near-duplicate"
    )
    st.caption(
        f"Showing {len(visible)} of {len(rows)} immutable Flexible records. "
        f"{len(rejected)} rejected near-duplicate record(s) remain in read-only evidence."
    )
    page_size = st.selectbox("Library page size", (25, 50, 100), key="flexible_library_page_size_v1")
    page_count = max(1, (len(visible) + page_size - 1) // page_size)
    page = int(
        st.number_input(
            "Library page",
            min_value=1,
            max_value=page_count,
            value=1,
            step=1,
            key="flexible_library_page_v1",
        )
    )
    start = (page - 1) * page_size
    page_rows = visible[start : start + page_size]
    st.dataframe(
        tuple(_visible_library_row(row) for row in page_rows),
        use_container_width=True,
        hide_index=True,
    )
    if page_rows:
        with st.expander("Read-only artifact details and downloads", expanded=False):
            for index, row in enumerate(page_rows, start=start):
                document = row.get("_document")
                if not isinstance(document, dict):
                    continue
                artifact = str(row["Artifact"])
                st.caption(f"{row['Alias']} — {artifact}")
                st.download_button(
                    f"Download {artifact}",
                    data=canonical_json(document),
                    file_name=f"{artifact}.json",
                    mime="application/json",
                    key=f"flexible_library_download_{artifact}_{index}",
                )
    if rejected:
        with st.expander("Rejected near-duplicate evidence", expanded=False):
            st.dataframe(
                tuple(_visible_library_row(row) for row in rejected),
                use_container_width=True,
                hide_index=True,
            )


def _parse_rulebook_ids(value: str) -> tuple[str, ...]:
    """Accept only full immutable Flexible IDs from a user-entered list."""

    identifiers = tuple(item.strip() for item in value.replace(",", " ").split())
    if (
        not identifiers
        or len(set(identifiers)) != len(identifiers)
        or any(
            not item.startswith("frb_")
            or len(item) != 68
            or any(character not in "0123456789abcdef" for character in item[4:])
            for item in identifiers
        )
    ):
        raise ValueError("enter unique full immutable Flexible rulebook IDs")
    return identifiers


def _available_rulebook_definitions(
    root: Path,
    loader_fn: Callable[[Path], tuple[object, ...]],
) -> dict[str, object]:
    """Load only valid immutable definitions for read-only selector options."""

    try:
        definitions = tuple(loader_fn(root))
    except (OSError, RuntimeError, ValueError, TypeError):
        return {}
    by_id: dict[str, object] = {}
    for definition in definitions:
        try:
            identifier = rulebook_id(definition)
        except (AttributeError, TypeError, ValueError):
            continue
        by_id.setdefault(identifier, definition)
    return dict(sorted(by_id.items()))


def _available_group_names(group_names_fn: Callable[[], Sequence[str]]) -> tuple[str, ...]:
    """Normalize selector labels without allowing pseudo-group values."""

    try:
        values = group_names_fn()
        if isinstance(values, (str, bytes)):
            return ()
        values = tuple(values)
    except (OSError, RuntimeError, ValueError, TypeError):
        return ()
    names = {
        item.strip().upper()
        for item in values
        if isinstance(item, str) and item.strip() and item.strip().upper() not in {"-", "N/A"}
    }
    return tuple(sorted(names))


def _single_ticker_group(ticker: str) -> FrozenGroup:
    """Give one manual ticker a stable local group identity for qualification."""

    member = ticker.strip().upper()
    if not member or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in member):
        raise ValueError("single-ticker qualification requires a valid ticker")
    return FrozenGroup(
        group_name=f"SINGLE {member}",
        group_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"flexible-rulebook-single:{member}")),
        members=(member,),
        source_updated_at="manual-single-ticker-v1",
    )


def _render_qualification(
    engine: object,
    *,
    root: Path,
    group_snapshot_fn: Callable[[str], object],
    group_names_fn: Callable[[], Sequence[str]],
    rulebook_loader_fn: Callable[[Path], tuple[object, ...]],
    qualification_preflight_fn: Callable[..., dict[tuple[str, str], FeaturePreflight]],
    qualification_runner_fn: Callable[..., object],
) -> None:
    """Freeze definitions/targets and make cache choice explicit before running."""

    st.subheader("Cross-ticker Qualification")
    definitions_by_id = _available_rulebook_definitions(root, rulebook_loader_fn)
    available_ids = tuple(definitions_by_id)
    selected_ids = tuple(
        st.multiselect(
            "Immutable rulebook IDs",
            options=available_ids,
            key="flexible_qualification_ids_v2",
        )
    )
    if not available_ids:
        st.info("No valid immutable Flexible rulebooks are available for qualification.")
    target_kind = st.selectbox("Qualification target", ("Single ticker", "Named Group"))
    if target_kind == "Single ticker":
        target_value = st.text_input("Ticker", key="flexible_qualification_ticker_v2")
    else:
        group_names = _available_group_names(group_names_fn)
        group_options = ("—", *group_names)
        target_value = st.selectbox(
            "Named Group",
            group_options,
            key="flexible_qualification_group_v2",
        )
        if not group_names:
            st.info("No valid named Groups are available for qualification.")
    target_value = str(target_value)
    target_ready = (
        bool(target_value.strip())
        if target_kind == "Single ticker"
        else target_value != "—"
    )
    can_preflight = bool(selected_ids) and bool(available_ids) and target_ready
    if st.button("Preflight Qualification", disabled=not can_preflight):
        try:
            identifiers = selected_ids
            definitions = tuple(definitions_by_id[item] for item in identifiers)
            group = (
                _single_ticker_group(target_value)
                if target_kind == "Single ticker"
                else group_snapshot_fn(target_value)
            )
            if not isinstance(group, FrozenGroup) or not group.members:
                raise ValueError("qualification target is unavailable")
            limit = safe_default_scale_policy().max_current_scan_tickers
            if len(group.members) > limit:
                st.warning(f"Cross-ticker qualification is limited to {limit} tickers by the active scale policy.")
                return
            progress = st.progress(0.0, text="source: starting")
            def on_progress(event: object) -> None:
                total = max(1, int(getattr(event, "total", 1)))
                completed = max(0, min(total, int(getattr(event, "completed", 0))))
                progress.progress(completed / total, text=f"{getattr(event, 'phase', 'work')}: {getattr(event, 'label', '')}")
            preflights = _call_with_progress(
                qualification_preflight_fn,
                engine,
                group,
                definitions,
                root,
                datetime.now(_HCM),
                progress_fn=on_progress,
            )
            build_qualification_request(group, identifiers, preflights)
        except (KeyError, OSError, RuntimeError, ValueError):
            st.warning("Qualification preflight is unavailable; no target was evaluated.")
        else:
            st.session_state["flexible_qualification_preflight_v1"] = (
                identifiers,
                group,
                preflights,
                (identifiers, target_kind, target_value.strip().upper()),
            )

    stored = st.session_state.get("flexible_qualification_preflight_v1")
    if not isinstance(stored, tuple) or len(stored) != 4:
        return
    identifiers, group, preflights, frozen_draft = stored
    if frozen_draft != (selected_ids, target_kind, target_value.strip().upper()):
        st.info("Qualification inputs changed. Run preflight again before qualification.")
        return
    if not isinstance(group, FrozenGroup) or not isinstance(preflights, dict):
        st.warning("Qualification preflight is unavailable; no target was evaluated.")
        return
    st.caption(f"Frozen targets: {', '.join(group.members)}")
    offer_rows = [
        {
            "Ticker": ticker,
            "Reusable components": len(preflight.cache_offer.reusable_keys),
            "Stale components": len(preflight.cache_offer.stale_keys),
            "Missing components": len(preflight.cache_offer.missing_keys),
        }
        for (ticker, _contract), preflight in preflights.items()
    ]
    st.dataframe(offer_rows, use_container_width=True, hide_index=True)
    has_reusable_components = any(preflight.cache_offer.choice_required for preflight in preflights.values())
    if has_reusable_components:
        cache_choice_label = st.selectbox(
            "Qualification indicator cache",
            ("Reuse verified indicator cache", "Recalculate now"),
            key="flexible_qualification_cache_choice_v1",
        )
    else:
        cache_choice_label = "Recalculate now"
        st.caption("No verified reusable components are available; all components will be recalculated.")
    if not st.button("Run Cross-ticker Qualification"):
        return
    try:
        request = build_qualification_request(group, identifiers, preflights)
        cache_choice = "reuse" if cache_choice_label == "Reuse verified indicator cache" else "rebuild"
        progress = st.progress(0.0, text="source: starting")
        def on_progress(event: object) -> None:
            total = max(1, int(getattr(event, "total", 1)))
            completed = max(0, min(total, int(getattr(event, "completed", 0))))
            progress.progress(completed / total, text=f"{getattr(event, 'phase', 'work')}: {getattr(event, 'label', '')}")
        result = _call_with_progress(
            qualification_runner_fn,
            engine,
            identifiers,
            group,
            request,
            root=root,
            cache_choice=cache_choice,
            progress_fn=on_progress,
        )
    except (OSError, RuntimeError, ValueError):
        st.warning("Qualification failed safely; no new evidence was accepted.")
        return
    for item in getattr(result, "items", ()):
        ticker = getattr(item, "ticker", "Unknown")
        item_state = getattr(item, "state", "failed")
        if item_state == "qualified":
            st.success(f"{ticker}: qualified Flexible evidence saved.")
        elif item_state == "no_qualified_candidate_within_budget":
            st.info(f"{ticker}: no qualified evidence for the selected immutable rulebook IDs.")
        else:
            st.warning(f"{ticker}: {item_state}; no evidence was accepted.")


def _render_current_scan(
    engine: object,
    *,
    root: Path,
    group_snapshot_fn: Callable[[str], object],
    common_as_of_preflight_fn: Callable[[object, tuple[str, ...]], object],
    current_cache_preflight_fn: Callable[..., object],
    scan_current_setup_fn: Callable[[object, CampaignRequest, Path], object],
) -> None:
    """Offer only the required read-only common-as-of preflight first."""

    st.subheader("Current Group BUY Scan")
    st.markdown("**BUY setup — next-session open model. Manual research, not trading advice.**")
    group_name = st.text_input("Named Group", key="flexible_current_group_v1")
    st.caption("Every frozen member must share one latest completed bar before any current evaluation.")
    if st.button("Preflight Current Group"):
        if not group_name.strip():
            st.warning("Enter a named Group before common-as-of preflight.")
        else:
            try:
                group = group_snapshot_fn(group_name)
                members = getattr(group, "members", None)
                if not isinstance(members, tuple) or not members:
                    raise ValueError("named group has no members")
                limit = safe_default_scale_policy().max_current_scan_tickers
                if len(members) > limit:
                    st.warning(f"Current Group scan is limited to {limit} tickers by the active scale policy.")
                    return
                progress = st.progress(0.0, text="common-as-of: starting")
                def on_progress(event: object) -> None:
                    total = max(1, int(getattr(event, "total", 1)))
                    completed = max(0, min(total, int(getattr(event, "completed", 0))))
                    progress.progress(completed / total, text=f"{getattr(event, 'phase', 'work')}: {getattr(event, 'label', '')}")
                preflight = common_as_of_preflight_fn(engine, members)
                progress.progress(1.0, text="common-as-of: verified")
                cache_preflight = (
                    _call_with_progress(
                        current_cache_preflight_fn,
                        engine,
                        preflight,
                        root,
                        now=datetime.now(_HCM),
                        progress_fn=on_progress,
                    )
                    if getattr(preflight, "state", None) == "ready"
                    else None
                )
            except (OSError, ValueError, RuntimeError):
                st.warning("Current Group preflight is unavailable; no evaluation was run.")
            else:
                st.session_state["flexible_current_preflight_v1"] = (
                    group_name.strip().upper(),
                    preflight,
                    cache_preflight,
                )

    stored = st.session_state.get("flexible_current_preflight_v1")
    if (
        not isinstance(stored, tuple)
        or len(stored) != 3
        or stored[0] != group_name.strip().upper()
    ):
        return
    preflight = stored[1]
    cache_preflight = stored[2]
    state = getattr(preflight, "state", None)
    common_as_of = getattr(preflight, "common_as_of", None)
    laggards = getattr(preflight, "lagging_tickers", ())
    if state != "ready":
        if state == "blocked_common_as_of":
            st.warning(f"Blocked common as-of; lagging tickers: {', '.join(laggards)}.")
        else:
            st.warning("Current Group preflight did not produce an evaluable common as-of date.")
        return

    if getattr(cache_preflight, "state", None) == "source_changed":
        changed = getattr(cache_preflight, "changed_tickers", ())
        st.warning(f"Qualified evidence changed for: {', '.join(changed)}. No current conclusion was produced.")
        return
    if getattr(cache_preflight, "state", None) == "no_historically_qualified_rulebook":
        st.info("No historically qualified Flexible rulebook is available for this frozen group.")
        return
    offers = getattr(cache_preflight, "feature_preflights", None)
    if getattr(cache_preflight, "state", None) != "ready" or not isinstance(offers, Mapping):
        st.warning("Current Group cache preflight is unavailable; no evaluation was run.")
        return
    offer_rows = [
        {
            "Ticker": ticker,
            "Reusable components": len(offer.cache_offer.reusable_keys),
            "Stale components": len(offer.cache_offer.stale_keys),
            "Missing components": len(offer.cache_offer.missing_keys),
        }
        for (ticker, _contract), offer in offers.items()
    ]
    st.success(f"Common as-of: {common_as_of}. Cache offers are verified for the frozen evidence.")
    st.dataframe(offer_rows, use_container_width=True, hide_index=True)
    if any(offer.cache_offer.choice_required for offer in offers.values()):
        cache_choice_label = st.selectbox(
            "Indicator cache",
            ("Reuse verified indicator cache", "Recalculate now"),
            key="flexible_current_cache_choice_v1",
        )
    else:
        cache_choice_label = "Recalculate now"
        st.caption("No verified reusable components are available; all components will be recalculated.")
    if not st.button("Run Current Group BUY Scan"):
        return
    snapshots = getattr(preflight, "snapshots", None)
    try:
        cache_choice = (
            "reuse"
            if cache_choice_label == "Reuse verified indicator cache"
            else "rebuild"
        )
        request = build_current_scan_request(snapshots, cache_choice=cache_choice)
        progress = st.progress(0.0, text="common-as-of: starting")
        def on_progress(event: object) -> None:
            total = max(1, int(getattr(event, "total", 1)))
            completed = max(0, min(total, int(getattr(event, "completed", 0))))
            progress.progress(completed / total, text=f"{getattr(event, 'phase', 'work')}: {getattr(event, 'label', '')}")
        result = _call_with_progress(
            scan_current_setup_fn,
            engine,
            request,
            root,
            progress_fn=on_progress,
        )
    except (OSError, RuntimeError, ValueError):
        st.warning("Current Group scan failed safely; no BUY setup conclusion was produced.")
        return
    for item in getattr(result, "items", ()):
        ticker = getattr(item, "ticker", "Unknown")
        item_state = getattr(item, "state", "current_evaluation_failed")
        if item_state == "current_setup_found":
            st.success(f"{ticker}: BUY setup — next-session open model. Manual research only.")
        elif item_state == "no_current_setup":
            st.info(f"{ticker}: no current setup after every qualified rulebook evaluated.")
        elif item_state == "no_historically_qualified_rulebook":
            st.info(f"{ticker}: no historically qualified Flexible rulebook.")
        else:
            st.warning(f"{ticker}: {item_state}; no BUY setup conclusion was produced.")


def render_flexible_rulebook_page(
    engine: object,
    *,
    root: Path | None = None,
    root_resolver: Callable[[], Path] = resolve_flexible_root,
    group_snapshot_fn: Callable[[str], object] = snapshot_named_group,
    group_names_fn: Callable[[], Sequence[str]] = available_named_group_names,
    common_as_of_preflight_fn: Callable[[object, tuple[str, ...]], object] = preflight_common_as_of,
    scope_policy_loader_fn: Callable[[], tuple[object | None, str]] | None = None,
    scope_submit_fn: Callable[..., str] = submit_scope_expansion,
    scope_status_fn: Callable[[str, Path], ScopeExpansionStatus] = _read_scope_status,
    scope_benchmark_directory_fn: Callable[[], Path] = active_policy_directory,
    scope_refresh_fn: Callable[[], None] | None = None,
    scope_rerun_fn: Callable[[], None] | None = None,
    current_cache_preflight_fn: Callable[..., object] = preflight_current_scan_cache,
    scan_current_setup_fn: Callable[[object, CampaignRequest, Path], object] = scan_current_setup,
    rulebook_loader_fn: Callable[[Path], tuple[object, ...]] = reusable_rulebooks,
    qualification_preflight_fn: Callable[..., dict[tuple[str, str], FeaturePreflight]] = preflight_group_feature_components,
    qualification_runner_fn: Callable[..., object] = qualify_rulebooks_for_group,
    discover_policy_loader_fn: Callable[[], tuple[object | None, str]] = load_active_policy,
    discovery_preflight_fn: Callable[..., object] = preflight_activated_discovery,
    discovery_submit_fn: Callable[..., str] = submit_activated_discovery,
    campaign_reader_fn: Callable[[str, Path], object] = read_campaign,
    cancel_campaign_fn: Callable[[str, Path], None] = request_cancel,
    resume_discovery_fn: Callable[..., str] = resume_activated_discovery,
    continue_discovery_fn: Callable[..., str] = continue_activated_discovery,
    rerun_fn: Callable[[], None] = st.rerun,
) -> None:
    """Render one lazy workspace selector without any V3 or order path."""

    output_root = root_resolver() if root is None else root
    if not isinstance(output_root, Path) or not output_root.is_absolute():
        raise ValueError("Flexible Rulebook root must be an absolute path")

    st.header("Flexible Rulebook")
    st.markdown("**Exploratory — gross. Manual research; no orders.**")
    st.caption("Persistence: unverified development storage.")
    workspace = st.radio("Workspace", _WORKSPACES, horizontal=True)
    scope_refresh = rerun_fn if scope_refresh_fn is None else scope_refresh_fn
    scope_rerun = rerun_fn if scope_rerun_fn is None else scope_rerun_fn

    if workspace == "Discover":
        scope_loader = discover_policy_loader_fn if scope_policy_loader_fn is None else scope_policy_loader_fn
        _render_discover(
            engine,
            root=output_root,
            policy_loader_fn=scope_loader,
            discovery_preflight_fn=discovery_preflight_fn,
            discovery_submit_fn=discovery_submit_fn,
            common_as_of_preflight_fn=common_as_of_preflight_fn,
            scope_submit_fn=scope_submit_fn,
            scope_status_fn=scope_status_fn,
            scope_benchmark_directory_fn=scope_benchmark_directory_fn,
            scope_refresh_fn=scope_refresh,
            scope_rerun_fn=scope_rerun,
            campaign_reader_fn=campaign_reader_fn,
            cancel_campaign_fn=cancel_campaign_fn,
            resume_discovery_fn=resume_discovery_fn,
            continue_discovery_fn=continue_discovery_fn,
            rerun_fn=rerun_fn,
        )
    elif workspace == "Rulebook Library":
        _render_library(output_root)
    elif workspace == "Cross-ticker Qualification":
        _render_qualification(
            engine,
            root=output_root,
            group_snapshot_fn=group_snapshot_fn,
            group_names_fn=group_names_fn,
            rulebook_loader_fn=rulebook_loader_fn,
            qualification_preflight_fn=qualification_preflight_fn,
            qualification_runner_fn=qualification_runner_fn,
        )
    else:
        _render_current_scan(
            engine,
            root=output_root,
            group_snapshot_fn=group_snapshot_fn,
            common_as_of_preflight_fn=common_as_of_preflight_fn,
            current_cache_preflight_fn=current_cache_preflight_fn,
            scan_current_setup_fn=scan_current_setup_fn,
        )


__all__ = ["render_flexible_rulebook_page"]
