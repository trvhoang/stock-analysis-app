"""User-authored, non-trading Flexible Rulebook v2 workspaces."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytz
import streamlit as st

from backtest_engine.result_store import list_groups
from flexible_rulebook.v2.contracts import (
    AtrExitV2,
    EvaluationRequest,
    PredicateV2,
    RulebookDefinitionV2,
    RulebookDraft,
)
from flexible_rulebook.v2.registry import DEFAULT_INDICATOR_REGISTRY, IndicatorRegistry
from flexible_rulebook.v2.service import (
    EvaluationProgress,
    clone_draft,
    draft_is_evaluated,
    evaluate_draft,
    publish_draft,
    published_library,
)
from flexible_rulebook.v2.storage import (
    discard_draft,
    list_drafts,
    list_evaluations,
    list_published_rulebooks,
    published_short_ids,
    read_draft,
    resolve_v2_root,
    retire_rulebook,
    unretire_rulebook,
    write_draft,
)


_WORKSPACES = ("Rulebook Builder", "Rulebook Backtest", "Rulebook Library")
_HCM = pytz.timezone("Asia/Ho_Chi_Minh")


def _now() -> datetime:
    return datetime.now(_HCM)


def _families_for(role: str, horizon: str, registry: IndicatorRegistry) -> tuple[str, ...]:
    native = "daily" if horizon == "swing" else "weekly"
    return tuple(
        family for family in registry.families
        if role in registry.for_family(family).roles
        and native in registry.for_family(family).native_timeframes
    )


def _default_settings(family: str) -> dict[str, object]:
    """Only defaults; every accepted bound remains registry-owned."""

    return {
        "sma": {"fast_period": 5, "slow_period": 13},
        "ema": {"fast_period": 5, "slow_period": 13},
        "rsi": {"period": 9},
        "alligator": {
            "jaw_period": 8, "teeth_period": 5, "lips_period": 3,
            "jaw_offset": 5, "teeth_offset": 3, "lips_offset": 2,
        },
        "adx_dmi": {"period": 14},
        "stochastic": {"k_period": 10, "k_smoothing": 3, "d_period": 3},
        "breakout": {"period": 20},
        "relative_volume": {"period": 10},
        "obv": {"period": 20},
        "atr": {"period": 14},
        "bollinger": {"period": 20, "multiplier": 2.0},
        "supertrend": {"period": 14, "multiplier": 3.0},
    }[family]


def _default_operator(role: str, family: str, operators: tuple[str, ...]) -> str:
    preferred = {
        ("buy", "rsi"): "upcross",
        ("buy", "ema"): "bullish_cross",
        ("buy", "sma"): "bullish_cross",
        ("buy", "supertrend"): "bullish_state",
        ("gate", "adx_dmi"): "above",
        ("technical_sell", "rsi"): "downcross",
        ("technical_sell", "ema"): "bearish_cross",
        ("technical_sell", "sma"): "bearish_cross",
        ("technical_sell", "supertrend"): "bearish_state",
    }.get((role, family))
    return preferred if preferred in operators else operators[0]


def _requires_threshold(operator: str) -> bool:
    return operator in {
        "above", "below", "upcross", "downcross",
        "percent_b_above", "percent_b_below", "bandwidth_above", "bandwidth_below",
    }


def _requires_lookback(operator: str) -> bool:
    return operator in {"rising", "falling", "direction", "opening", "closing"}


def _label(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _number_setting(*, label: str, parameter: object, value: object, key: str) -> int | float:
    """Render one registry-bound scalar without duplicating its bounds in the UI."""

    kind = getattr(parameter, "kind")
    minimum = getattr(parameter, "minimum")
    maximum = getattr(parameter, "maximum")
    if kind == "int":
        default = {"value": int(value)} if key not in st.session_state else {}
        return int(st.number_input(
            label,
            min_value=None if minimum is None else int(minimum),
            max_value=None if maximum is None else int(maximum),
            step=1,
            key=key,
            **default,
        ))
    if kind == "decimal":
        default = {"value": float(value)} if key not in st.session_state else {}
        return float(st.number_input(
            label,
            min_value=None if minimum is None else float(minimum),
            max_value=None if maximum is None else float(maximum),
            step=0.1,
            key=key,
            **default,
        ))
    raise ValueError(f"unsupported parameter kind {kind}")


def _settings_editor(prefix: str, family: str, spec: object) -> dict[str, object]:
    """Build settings controls directly from the selected registry specification."""

    defaults = _default_settings(family)
    parameters = tuple(getattr(spec, "parameters"))
    names = {item.name for item in parameters}
    use_ma_variant = {"period", "fast_period", "slow_period"}.issubset(names)
    if use_ma_variant:
        mode = st.selectbox(
            "MA setup",
            ("Cross pair", "Single period"),
            key=f"{prefix}_setting_mode",
        )
        requested = ("fast_period", "slow_period") if mode == "Cross pair" else ("period",)
    else:
        requested = tuple(item.name for item in parameters)
    by_name = {item.name: item for item in parameters}
    return {
        name: _number_setting(
            label=_label(name),
            parameter=by_name[name],
            value=defaults.get(name, 2),
            key=f"{prefix}_setting_{name}",
        )
        for name in requested
    }


def _condition_default(family: str, name: str) -> float:
    if name != "threshold":
        return 0.0
    if family in {"rsi", "stochastic"}:
        return 52.0
    if family == "relative_volume":
        return 1.1
    return 20.0


def _condition_editor(prefix: str, family: str, spec: object) -> dict[str, object]:
    return {
        item.name: _number_setting(
            label=_label(item.name),
            parameter=item,
            value=_condition_default(family, item.name),
            key=f"{prefix}_condition_{item.name}",
        )
        for item in tuple(getattr(spec, "condition_parameters"))
    }


def _predicate_summary(predicate: PredicateV2) -> str:
    settings = ", ".join(f"{key}={value}" for key, value in predicate.settings_dict.items())
    condition = ", ".join(f"{key}={value}" for key, value in predicate.condition_dict.items())
    suffix = f"; {condition}" if condition else ""
    if predicate.direction_lookback is not None:
        suffix += f"; lookback={predicate.direction_lookback}"
    return f"{predicate.family} {predicate.operator} ({settings}{suffix})"


def _render_definition_summary(
    *,
    horizon: str,
    entry_operator: str,
    buy: tuple[PredicateV2, ...],
    gates: tuple[PredicateV2, ...],
    exits: tuple[PredicateV2, ...],
    atr_exit: AtrExitV2 | None,
    max_hold: int,
) -> None:
    segments = [
        f"Horizon: {horizon}",
        f"BUY ({entry_operator.upper()}): " + "; ".join(_predicate_summary(item) for item in buy),
        "Gates (ALL): " + ("; ".join(_predicate_summary(item) for item in gates) or "none"),
        "Technical SELL (ANY): " + ("; ".join(_predicate_summary(item) for item in exits) or "none"),
        f"ATR exits: {'enabled' if atr_exit is not None else 'none'}",
        "Minimum hold: 3 native bars",
        f"Maximum hold: {max_hold} native bars",
    ]
    st.markdown("**Rulebook summary**")
    st.code("\n".join(segments), language=None)


def _predicate_editor(
    *,
    role: str,
    ordinal: int,
    horizon: str,
    registry: IndicatorRegistry,
) -> PredicateV2:
    prefix = f"frb2_{role}_{ordinal}"
    families = _families_for(role, horizon, registry)
    family = st.selectbox("Indicator", families, key=f"{prefix}_family")
    spec = registry.for_family(family)
    operators = tuple(sorted(spec.operators))
    default_operator = _default_operator(role, family, operators)
    operator = st.selectbox(
        "Predicate",
        operators,
        key=f"{prefix}_operator",
        **({"index": operators.index(default_operator)} if f"{prefix}_operator" not in st.session_state else {}),
    )
    st.caption(f"Formula: {spec.formula_revision}.")
    settings = _settings_editor(prefix, family, spec)
    condition: dict[str, object] = {}
    if _requires_threshold(operator):
        condition = _condition_editor(prefix, family, spec)
    lookback = None
    if _requires_lookback(operator):
        lookback_key = f"{prefix}_lookback"
        lookback = int(st.number_input(
            "Direction lookback", min_value=1, max_value=20,
            key=lookback_key,
            **({"value": 3} if lookback_key not in st.session_state else {}),
        ))
    return PredicateV2(
        role=role,
        family=family,
        family_revision=spec.formula_revision,
        settings=settings,
        operator=operator,
        condition=condition,
        direction_lookback=lookback,
    )


def _predicate_group(
    title: str,
    role: str,
    horizon: str,
    registry: IndicatorRegistry,
    *,
    minimum: int,
    maximum: int,
    default: int,
) -> tuple[PredicateV2, ...]:
    count = int(st.number_input(
        f"{title} count",
        min_value=minimum,
        max_value=maximum,
        key=f"frb2_{role}_count",
        **({"value": default} if f"frb2_{role}_count" not in st.session_state else {}),
    ))
    predicates: list[PredicateV2] = []
    for ordinal in range(count):
        with st.expander(f"{title} {ordinal + 1}", expanded=ordinal == 0):
            predicates.append(_predicate_editor(
                role=role,
                ordinal=ordinal,
                horizon=horizon,
                registry=registry,
            ))
    return tuple(predicates)


def _clear_builder_state() -> None:
    for key in tuple(st.session_state):
        if key.startswith("frb2_buy_") or key.startswith("frb2_gate_") or key.startswith("frb2_technical_sell_"):
            st.session_state.pop(key, None)
    for key in (
        "frb2_builder_name", "frb2_builder_description", "frb2_builder_horizon",
        "frb2_builder_entry", "frb2_edit_draft_id", "frb2_loaded_draft_id",
    ):
        st.session_state.pop(key, None)


def _load_draft_state(root: Path, registry: IndicatorRegistry) -> RulebookDraft | None:
    """Populate widget state before construction so an edit starts from saved semantics."""

    identifier = st.session_state.get("frb2_edit_draft_id")
    if not isinstance(identifier, str) or not identifier:
        return None
    draft = read_draft(root, identifier)
    if st.session_state.get("frb2_loaded_draft_id") == identifier:
        return draft
    definition = draft.definition
    st.session_state["frb2_builder_name"] = draft.name
    st.session_state["frb2_builder_description"] = draft.description
    st.session_state["frb2_builder_horizon"] = definition.horizon
    st.session_state["frb2_builder_entry"] = definition.entry_operator
    for role, predicates in (
        ("buy", definition.buy_predicates),
        ("gate", definition.gates),
        ("technical_sell", definition.technical_exits),
    ):
        st.session_state[f"frb2_{role}_count"] = len(predicates)
        for ordinal, predicate in enumerate(predicates):
            prefix = f"frb2_{role}_{ordinal}"
            st.session_state[f"{prefix}_family"] = predicate.family
            st.session_state[f"{prefix}_operator"] = predicate.operator
            parameter_names = set(predicate.settings_dict)
            if parameter_names == {"fast_period", "slow_period"}:
                st.session_state[f"{prefix}_setting_mode"] = "Cross pair"
            elif parameter_names == {"period"} and {"period", "fast_period", "slow_period"}.issubset(
                {item.name for item in registry.for_family(predicate.family).parameters}
            ):
                st.session_state[f"{prefix}_setting_mode"] = "Single period"
            for name, value in predicate.settings_dict.items():
                st.session_state[f"{prefix}_setting_{name}"] = value
            if _requires_threshold(predicate.operator):
                for name, value in predicate.condition_dict.items():
                    st.session_state[f"{prefix}_condition_{name}"] = value
            if predicate.direction_lookback is not None:
                st.session_state[f"{prefix}_lookback"] = predicate.direction_lookback
    st.session_state["frb2_builder_use_atr"] = definition.atr_exit is not None
    if definition.atr_exit is not None:
        st.session_state["frb2_builder_atr_period"] = definition.atr_exit.period
        st.session_state["frb2_builder_atr_stop"] = float(definition.atr_exit.stop_multiplier or 0)
        st.session_state["frb2_builder_atr_target"] = float(definition.atr_exit.target_multiplier or 0)
        st.session_state["frb2_builder_atr_trailing"] = float(definition.atr_exit.trailing_multiplier or 0)
    st.session_state["frb2_builder_max_hold"] = definition.max_hold_bars
    st.session_state["frb2_loaded_draft_id"] = identifier
    return draft


def _open_draft_in_builder(draft_id: str) -> None:
    st.session_state["frb2_edit_draft_id"] = draft_id
    st.session_state.pop("frb2_loaded_draft_id", None)
    st.session_state["frb2_workspace"] = "Rulebook Builder"


def _clone_published_to_builder(root: Path, definition: RulebookDefinitionV2, name: str) -> None:
    """Create the mutable clone in a callback before the workspace radio is built."""

    copied = RulebookDraft.new(
        name=f"{name} copy",
        description="",
        definition=definition,
        now=_now(),
    )
    write_draft(root, copied, expected_revision=0)
    _open_draft_in_builder(copied.draft_id)


def _render_builder(root: Path, registry: IndicatorRegistry) -> None:
    st.subheader("Rulebook Builder")
    st.caption("Build a bounded, causal long-only rulebook. Exploratory — gross; no order is sent.")
    st.info("Create Rulebook, then evaluate the exact saved draft before publishing it.")
    editing = _load_draft_state(root, registry)
    if editing is not None:
        st.caption(f"Editing {editing.name}, revision {editing.revision}. Saving creates revision {editing.revision + 1}.")
    name = st.text_input("Name", key="frb2_builder_name")
    description = st.text_area("Description", key="frb2_builder_description")
    horizon = st.selectbox(
        "Horizon",
        ("swing", "midterm"),
        format_func=lambda value: "Swing (daily)" if value == "swing" else "Mid-term (completed W-FRI)",
        key="frb2_builder_horizon",
    )
    entry_operator = st.selectbox(
        "BUY condition operator",
        ("all", "any"),
        format_func=lambda value: "ALL selected BUY conditions" if value == "all" else "ANY selected BUY condition",
        key="frb2_builder_entry",
    )
    buy = _predicate_group("BUY condition", "buy", horizon, registry, minimum=1, maximum=8, default=1)
    gates = _predicate_group("Gate", "gate", horizon, registry, minimum=0, maximum=8, default=0)
    exits = _predicate_group("Technical SELL", "technical_sell", horizon, registry, minimum=0, maximum=8, default=0)
    use_atr = st.checkbox("Use ATR price exit", key="frb2_builder_use_atr")
    atr_exit = None
    if use_atr:
        atr_period_key = "frb2_builder_atr_period"
        atr_period = int(st.number_input(
            "ATR period", min_value=2, max_value=100, key=atr_period_key,
            **({"value": 14} if atr_period_key not in st.session_state else {}),
        ))
        stop_key = "frb2_builder_atr_stop"
        stop = st.number_input(
            "ATR stop multiplier (0 disables)", min_value=0.0, max_value=20.0, key=stop_key,
            **({"value": 1.5} if stop_key not in st.session_state else {}),
        )
        target_key = "frb2_builder_atr_target"
        target = st.number_input(
            "ATR target multiplier (0 disables)", min_value=0.0, max_value=20.0, key=target_key,
            **({"value": 0.0} if target_key not in st.session_state else {}),
        )
        trailing_key = "frb2_builder_atr_trailing"
        trailing = st.number_input(
            "ATR trailing multiplier (0 disables)", min_value=0.0, max_value=20.0, key=trailing_key,
            **({"value": 0.0} if trailing_key not in st.session_state else {}),
        )
        atr_exit = AtrExitV2(
            period=atr_period,
            stop_multiplier=stop or None,
            target_multiplier=target or None,
            trailing_multiplier=trailing or None,
        )
    max_hold_key = "frb2_builder_max_hold"
    max_hold = int(st.number_input(
        "Maximum hold (native bars)", min_value=4, max_value=64, key=max_hold_key,
        **({"value": 22} if max_hold_key not in st.session_state else {}),
    ))
    st.caption("Minimum hold is fixed at 3 native bars.")
    _render_definition_summary(
        horizon=horizon,
        entry_operator=entry_operator,
        buy=buy,
        gates=gates,
        exits=exits,
        atr_exit=atr_exit,
        max_hold=max_hold,
    )
    if st.button("Save draft", icon=":material/save:"):
        try:
            definition = RulebookDefinitionV2(
                horizon=horizon,
                entry_operator=entry_operator,
                buy_predicates=buy,
                gates=gates,
                technical_exits=exits,
                atr_exit=atr_exit,
                max_hold_bars=max_hold,
            )
            definition.validate(registry)
            draft = (
                RulebookDraft.new(name=name, description=description, definition=definition, now=_now())
                if editing is None
                else editing.with_changes(name=name, description=description, definition=definition, now=_now())
            )
            write_draft(root, draft, expected_revision=0 if editing is None else editing.revision)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state["frb2_edit_draft_id"] = draft.draft_id
            st.session_state["frb2_loaded_draft_id"] = draft.draft_id
            st.success(f"Draft saved: {draft.name} (revision {draft.revision}).")
    st.button("Reset", icon=":material/restart_alt:", on_click=_clear_builder_state)


def _parse_tickers(value: str) -> tuple[str, ...]:
    tickers = tuple(dict.fromkeys(item.strip().upper() for item in value.replace(",", " ").split() if item.strip()))
    if not tickers:
        raise ValueError("Enter at least one ticker")
    return tickers


def _metric_rows(result: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in result.items:
        row: dict[str, object] = {
            "Ticker": item.ticker,
            "State": item.terminal_state,
            "Message": item.message or "—",
        }
        if item.evaluation is not None:
            for partition in ("training", "test"):
                metrics = item.evaluation.metrics[partition]
                row[f"{partition.title()} n"] = metrics["n"]
                row[f"{partition.title()} Win rate %"] = round(float(metrics["win_rate"]), 2)
                row[f"{partition.title()} Profit %"] = round(float(metrics["total_return_pct"]), 2)
                row[f"{partition.title()} Sharpe"] = round(float(metrics["sharpe"]), 2)
        rows.append(row)
    return rows


def _trade_rows(trades: tuple[object, ...]) -> list[dict[str, object]]:
    """Format execution values at the sole UI boundary; storage remains raw BIGINT."""

    rows: list[dict[str, object]] = []
    for trade in trades:
        row = dict(trade)
        entry_price = row.pop("entry_price")
        exit_price = row.pop("exit_price")
        row["Entry price (k VND)"] = round(float(entry_price) / 1000.0, 2)
        row["Exit price (k VND)"] = round(float(exit_price) / 1000.0, 2)
        row["Return %"] = round(float(row.pop("return_pct")), 2)
        rows.append(row)
    return rows


def _evaluation_history_rows(evaluations: tuple[object, ...]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for evaluation in evaluations:
        row: dict[str, object] = {
            "Ticker": evaluation.ticker,
            "As of": evaluation.source.get("end_date", "—"),
        }
        for partition in ("training", "test"):
            metrics = evaluation.metrics[partition]
            row[f"{partition.title()} n"] = metrics["n"]
            row[f"{partition.title()} Win rate %"] = round(float(metrics["win_rate"]), 2)
            row[f"{partition.title()} Profit %"] = round(float(metrics["total_return_pct"]), 2)
            row[f"{partition.title()} Sharpe"] = round(float(metrics["sharpe"]), 2)
        rows.append(row)
    return rows


def _render_backtest(root: Path, engine: object, registry: IndicatorRegistry) -> None:
    st.subheader("Rulebook Backtest")
    drafts = list_drafts(root)
    published = published_library(root)
    options: dict[str, RulebookDraft] = {f"Draft · {item.name} · r{item.revision}": item for item in drafts}
    for item, short_id in published:
        options[f"Flexible · {short_id}"] = RulebookDraft.new(
            name=f"Flexible {short_id}",
            definition=item.definition,
            now=item.published_at,
        )
    if not options:
        st.info("Create Rulebook in Rulebook Builder before starting a backtest.")
        return
    selected_label = st.selectbox("Rulebook", tuple(options))
    draft = options[selected_label]
    groups = tuple(list_groups())
    group_by_name = {item.group_name: item for item in groups}
    group_choice = st.selectbox("Ticker group", ("Manual", *tuple(sorted(group_by_name))))
    group_tickers = () if group_choice == "Manual" else group_by_name[group_choice].tickers
    tickers = st.text_input(
        "Tickers",
        value=" ".join(group_tickers),
        placeholder="VCB FPT HPG",
        disabled=group_choice != "Manual",
    )
    range_mode = st.selectbox("History range", ("Lifetime", "Custom range"))
    start_date = end_date = None
    if range_mode == "Custom range":
        start_date = st.date_input("Start date")
        end_date = st.date_input("End date")
    ratio_percent = st.selectbox("Training ratio", (50, 55, 60, 65, 70, 75, 80), index=3)
    use_cache = st.checkbox("Reuse verified indicator cache", value=True)
    st.caption("Each selected ticker completes or fails independently; later failures do not erase earlier evidence.")
    if st.button("Run Backtest", icon=":material/play_arrow:"):
        try:
            request = EvaluationRequest(
                semantic_digest=draft.definition.semantic_digest,
                tickers=_parse_tickers(tickers),
                training_ratio=ratio_percent,
                start_date=start_date,
                end_date=end_date,
                use_cache=use_cache,
            )
            progress = st.progress(0.0, text="source: starting")
            seen: list[str] = []
            def update(event: EvaluationProgress) -> None:
                if event.ticker not in seen:
                    seen.append(event.ticker)
                fraction = min(1.0, (len(seen) - 1) / max(1, len(request.tickers)))
                progress.progress(fraction, text=f"{event.ticker}: {event.phase}")
            result = evaluate_draft(
                draft,
                request,
                root=root,
                engine=engine,
                registry=registry,
                on_progress=update,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            progress.progress(1.0, text="Evaluation complete")
            st.dataframe(_metric_rows(result), width="stretch", hide_index=True)
            for item in result.items:
                if item.evaluation is not None:
                    with st.expander(f"{item.ticker} evidence", expanded=False):
                        st.markdown("**Completed trades**")
                        st.dataframe(
                            _trade_rows(item.evaluation.trades),
                            width="stretch",
                            hide_index=True,
                        )
                        st.markdown("**Diagnostics**")
                        st.json({
                            "source": dict(item.evaluation.source),
                            "split": dict(item.evaluation.split),
                            "warnings": list(item.evaluation.warnings),
                        })


def _render_library(root: Path, registry: IndicatorRegistry) -> None:
    st.subheader("Rulebook Library")
    drafts = list_drafts(root)
    active = published_library(root)
    retired = tuple(item for item in list_published_rulebooks(root) if item.is_retired)
    all_short_ids = published_short_ids(root) if active or retired else {}
    if not drafts and not active and not retired:
        st.info("No rulebooks yet. Create Rulebook in Rulebook Builder.")
        return
    if drafts:
        st.markdown("#### Drafts")
        for draft in drafts:
            evaluated = draft_is_evaluated(root, draft)
            with st.expander(f"{draft.name} · revision {draft.revision}", expanded=False):
                st.caption("Evaluated" if evaluated else "Not evaluated for this exact semantic definition")
                st.caption("Technical identity is retained backstage with its immutable evidence.")
                columns = st.columns(4)
                if columns[0].button("Clone", key=f"frb2_clone_{draft.draft_id}"):
                    clone_draft(root, draft, name=f"{draft.name} copy", now=_now())
                    st.rerun()
                columns[1].button(
                    "Edit",
                    key=f"frb2_edit_{draft.draft_id}",
                    on_click=_open_draft_in_builder,
                    args=(draft.draft_id,),
                )
                if columns[2].button("Publish", key=f"frb2_publish_{draft.draft_id}", disabled=not evaluated):
                    try:
                        publish_draft(root, draft, published_at=_now(), confirmed=True, registry=registry)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.rerun()
                with columns[3].popover("Discard"):
                    st.warning("Discard removes only this mutable draft. Immutable evidence remains.")
                    if st.button("Confirm discard", key=f"frb2_discard_{draft.draft_id}"):
                        discard_draft(root, draft.draft_id, confirmed=True)
                        st.rerun()
    if active:
        st.markdown("#### Published")
        for item, _active_short_id in active:
            short_id = all_short_ids[item.rulebook_id]
            evidence = list_evaluations(root, item.rulebook_id)
            matching_names = sorted({draft.name for draft in drafts if draft.definition.semantic_digest == item.definition.semantic_digest})
            name = matching_names[0] if len(matching_names) == 1 else f"Flexible {short_id}"
            with st.expander(f"{name} · {short_id} · {item.definition.horizon}", expanded=False):
                st.caption(
                    f"Published · {'Evaluated' if evidence else 'No evaluation found'} · "
                    f"{item.published_at:%d/%m/%Y %H:%M}"
                )
                st.markdown("**Evaluation history**")
                if evidence:
                    st.dataframe(_evaluation_history_rows(evidence), width="stretch", hide_index=True)
                else:
                    st.caption("No immutable evaluation history is available.")
                columns = st.columns(2)
                columns[0].button(
                    "Clone to edit",
                    key=f"frb2_clone_published_{item.rulebook_id}",
                    on_click=_clone_published_to_builder,
                    args=(root, item.definition, name),
                )
                if columns[1].button("Retire", key=f"frb2_retire_{item.rulebook_id}"):
                    retire_rulebook(root, item.rulebook_id, retired_at=_now())
                    st.rerun()
    if retired:
        st.markdown("#### Retired")
        for item in retired:
            short_id = all_short_ids[item.rulebook_id]
            if st.button(f"Unretire {short_id}", key=f"frb2_unretire_{item.rulebook_id}"):
                unretire_rulebook(root, item.rulebook_id, unretired_at=_now())
                st.rerun()


def render_flexible_rulebook_page(
    engine: object,
    *,
    root: Path | None = None,
    registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
) -> None:
    """Render the replacement UI without importing frozen V1 workflow modules."""

    output_root = resolve_v2_root() if root is None else root
    if not isinstance(output_root, Path) or not output_root.is_absolute():
        raise ValueError("Flexible Rulebook root must be an absolute Path")
    st.header("Flexible Rulebook")
    st.markdown("**Exploratory — gross. Manual research only; no order is sent.**")
    workspace = st.radio("Workspace", _WORKSPACES, horizontal=True, key="frb2_workspace")
    if workspace == "Rulebook Builder":
        _render_builder(output_root, registry)
    elif workspace == "Rulebook Backtest":
        _render_backtest(output_root, engine, registry)
    else:
        _render_library(output_root, registry)


__all__ = ["render_flexible_rulebook_page"]
