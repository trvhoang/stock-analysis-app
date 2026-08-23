"""Schema-4 Streamlit Backtest Lab for exploratory gross rulebook evidence."""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from collections.abc import Iterable, Mapping
from typing import Callable

import pandas as pd
import pytz
import streamlit as st

from commons.price_utils import PRICE_OUTPUT_UI, prepare_price_for_output, price_from_ui_k_vnd
from backtest_engine.config import DEFAULT_SIGNAL_DIR, BacktestBatchConfig
from backtest_engine.job_runner import read_job_status, submit_backtest
from backtest_engine.manual_position_store import (
    build_v4_risk_snapshot,
    create_manual_position,
    delete_manual_position,
    update_manual_position,
)
from backtest_engine.persistence import load_rulebook_result
from backtest_engine.position_overview import (
    build_position_trade_rows,
    load_all_positions,
    load_completed_trading_sessions,
    load_latest_close_prices,
    summarize_positions,
)
from backtest_engine.position_store import delete_position, update_position
from backtest_engine.position_risk import (
    list_validate_position_candidates,
    validate_open_positions,
)
from backtest_engine.result_store import (
    list_validation_group_choices,
    replace_group_tickers,
    resolve_group_tickers,
)
from backtest_engine.signal_catalog import list_current_signal_set_rows
from backtest_engine.validation_advice import validate_saved_signals


TIME_RANGE_OPTIONS = ("5y", "15y", "Custom")
HORIZON_OPTIONS = ("swing", "midterm")
HORIZON_LABELS = {"swing": "Swing", "midterm": "Mid-term"}
MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")
STATUS_REFRESH_SECONDS = 1
MATCH_CLASSIFICATION_OPTIONS = ("No Match", "Weak", "Nearly Match", "Closely Match")
MATCH_CLASSIFICATION_VALUES = {
    "No Match": "no_match", "Weak": "weak", "Nearly Match": "nearly_match", "Closely Match": "closely_match",
}
POSITION_ACTION_OPTIONS = ("ALL", "can BUY", "expired BUY", "can SELL", "HOLD")
_POSITION_OVERVIEW_KEY = "backtest_position_overview_v4"
_POSITION_SELECTED_IDS_KEY = "backtest_position_selected_ids_v4"
_POSITION_SELECT_ALL_VISIBLE_KEY = "backtest_position_select_all_visible_v4"
_POSITION_DELETE_CONFIRMATION_KEY = "backtest_position_delete_confirmation_v4"
_POSITION_EDITING_ID_KEY = "backtest_position_editing_id_v4"
_POSITION_FEEDBACK_KEY = "backtest_position_feedback_v4"
_POSITION_TICKER_FILTER_KEY = "backtest_position_ticker_filter_v4"
_VIEW_SIGNAL_TICKER_FILTER_KEY = "backtest_view_signal_ticker_filter_v4"
_VIEW_SIGNAL_HORIZON_FILTER_KEY = "backtest_view_signal_horizon_filter_v4"
_VIEW_SIGNAL_HORIZON_OPTIONS = ("Both", "Swing", "Mid-term")
_NEW_POSITION_TICKER_KEY = "backtest_new_position_ticker_v4"
_NEW_POSITION_SAVED_SET_KEY = "backtest_position_saved_set_v4"
_NEW_POSITION_VALIDATION_KEY = "backtest_new_position_validation_v4"
_NEW_POSITION_VALIDATION_ERROR_KEY = "backtest_new_position_validation_error_v4"
_COLLECT_GROUP_KEY = "backtest_collect_group_v4"
_COLLECT_NEW_GROUP_OPTION = "New group…"
_COLLECT_GROUP_DRAFT_KEY = "backtest_collect_group_draft_v4"


def _preset_dates(time_range: str) -> tuple[date | None, date | None]:
    if time_range == "Custom":
        return None, None
    end = datetime.now(MARKET_TIMEZONE).date()
    return (pd.Timestamp(end) - pd.DateOffset(years=int(time_range[:-1]))).date(), end


def parse_batch_tickers(value: str, maximum: int = 15) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(token.upper() for token in re.split(r"[\s,]+", value.strip()) if token))
    if not 1 <= len(values) <= maximum:
        raise ValueError(f"Tickers must contain between 1 and {maximum} values.")
    return values


def _validation_tickers(
    tickers_text: str,
    group_name: str,
    signal_dir: str,
    group_resolver: Callable,
) -> tuple[str, ...]:
    """Resolve manual input or every member of the selected ticker group."""

    if group_name == "-":
        return parse_batch_tickers(tickers_text)
    tickers = tuple(group_resolver(group_name, signal_dir))
    if not tickers:
        raise ValueError("Selected Ticker group has no tickers.")
    return tickers


def _ticker_chunks(
    tickers: tuple[str, ...], size: int = 15
) -> tuple[tuple[str, ...], ...]:
    """Return consecutive bounded chunks without reordering ticker input."""

    return tuple(
        tuple(tickers[index:index + size])
        for index in range(0, len(tickers), size)
    )


def _run_validation_batches(
    tickers: tuple[str, ...],
    engine,
    signal_dir: str,
    positions_dir: str,
    validate_fn: Callable,
    progress_fn: Callable[[int, int, str], None] | None = None,
) -> dict[str, object]:
    """Validate every ticker serially, retaining independent failures."""

    by_ticker: dict[str, dict[str, object]] = {}
    errors: dict[str, str] = {}
    chunks = _ticker_chunks(tickers)
    completed = 0
    for chunk in chunks:
        for ticker in chunk:
            try:
                by_ticker[ticker] = validate_fn(
                    ticker, engine, signal_dir, positions_dir
                )
            except (OSError, ValueError) as error:
                errors[ticker] = str(error)
            finally:
                completed += 1
                if progress_fn is not None:
                    progress_fn(completed, len(tickers), ticker)
    return {"chunks": chunks, "by_ticker": by_ticker, "errors": errors}


def _validation_result_for_ticker(
    value: object, ticker: str
) -> dict[str, object] | None:
    """Read one ticker result from legacy single or new batch session state."""

    if not isinstance(value, dict):
        return None
    if value.get("ticker") == ticker:
        return value
    candidate = value.get("by_ticker", {}).get(ticker)
    return candidate if isinstance(candidate, dict) else None


def build_backtest_batch_config(
    tickers: tuple[str, ...], horizon: str | None, time_range: str,
    start_date: date | None = None, end_date: date | None = None,
    group_name: str = "N/A",
) -> BacktestBatchConfig:
    if horizon not in HORIZON_OPTIONS or time_range not in TIME_RANGE_OPTIONS:
        raise ValueError("A valid horizon and time range are required.")
    preset_start, preset_end = _preset_dates(time_range)
    return BacktestBatchConfig(
        tickers=tickers, horizon=horizon,
        start_date=start_date if time_range == "Custom" else preset_start,
        end_date=end_date if time_range == "Custom" else preset_end,
        group_name=group_name,
    )


def schedule_status_refresh(is_busy: bool, sleep_fn: Callable = time.sleep, rerun_fn: Callable = st.rerun) -> None:
    if is_busy:
        sleep_fn(STATUS_REFRESH_SECONDS)
        rerun_fn()


def format_job_status(status) -> str:
    if status.state == "requires_regeneration":
        return "Requires regeneration — 100%"
    return f"{status.state.title()} — {round(float(status.progress) * 100)}%"


def _render_v4_artifact(path: str) -> None:
    try:
        payload = load_rulebook_result(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return
    title = f"{payload['ticker']} — {HORIZON_LABELS[payload['horizon']]}"
    st.caption(f"{title}: {payload['evaluation_label']} — {payload['terminal_state']}")
    if payload["terminal_state"] == "requires_regeneration":
        st.warning(payload["rejection_reason"])
    st.download_button(
        f"Download {title} JSON", data=json.dumps(payload, indent=2, sort_keys=True),
        file_name=Path(path).name, mime="application/json",
        key=f"backtest_v4_download_{payload['ticker']}_{payload['horizon']}",
    )


def _render_collect(
    engine_factory,
    status_dir: str,
    signal_dir: str,
    submit_fn,
    read_status_fn,
    schedule_refresh_fn,
    group_choices_fn: Callable,
    group_resolver_fn: Callable,
) -> None:
    st.subheader("Collect Signals")
    try:
        named_groups = tuple(
            group for group in group_choices_fn(signal_dir)
            if group not in {"-", "N/A"}
        )
    except (OSError, ValueError) as error:
        named_groups = ()
        st.warning(f"Group choices are unavailable: {error}")
    group_options = ("N/A", _COLLECT_NEW_GROUP_OPTION, *named_groups)
    active_group = st.session_state.get(_COLLECT_GROUP_KEY, "N/A")
    if active_group not in group_options:
        st.session_state[_COLLECT_GROUP_KEY] = "N/A"
        active_group = "N/A"
    collect_row = st.columns((3, 1, 1))
    group_selection = collect_row[1].selectbox(
        "Group", group_options, key=_COLLECT_GROUP_KEY
    )
    resolved_tickers: tuple[str, ...] = ()
    resolution_error: ValueError | OSError | None = None
    if group_selection not in {"N/A", _COLLECT_NEW_GROUP_OPTION}:
        try:
            resolved_tickers = tuple(group_resolver_fn(group_selection, signal_dir))
        except (OSError, ValueError) as error:
            resolution_error = error
    if group_selection in {"N/A", _COLLECT_NEW_GROUP_OPTION}:
        tickers_text = collect_row[0].text_input("Tickers", key="backtest_collect_tickers_v4")
    else:
        tickers_text = collect_row[0].text_input(
            "Tickers",
            value=" ".join(resolved_tickers),
            disabled=True,
            key="backtest_collect_group_tickers_v4",
        )
    new_group_name = ""
    if group_selection == _COLLECT_NEW_GROUP_OPTION:
        new_group_name = collect_row[1].text_input(
            "New group name", key="backtest_collect_new_group_v4"
        )
    if group_selection not in {"N/A", _COLLECT_NEW_GROUP_OPTION}:
        draft = st.session_state.get(_COLLECT_GROUP_DRAFT_KEY)
        if not isinstance(draft, dict) or draft.get("group") != group_selection:
            st.session_state[_COLLECT_GROUP_DRAFT_KEY] = {
                "group": group_selection, "tickers": list(resolved_tickers)
            }
        with collect_row[2].popover("Edit Group"):
            draft = st.session_state[_COLLECT_GROUP_DRAFT_KEY]
            for index in range(0, len(draft["tickers"]), 2):
                member_columns = st.columns(4)
                for offset, ticker in enumerate(draft["tickers"][index:index + 2]):
                    member_columns[offset * 2].write(ticker)
                    if member_columns[offset * 2 + 1].button(
                        "X", key=f"backtest_collect_remove_{group_selection}_{ticker}", type="primary"
                    ):
                        draft["tickers"] = [item for item in draft["tickers"] if item != ticker]
                        st.session_state[_COLLECT_GROUP_DRAFT_KEY] = draft
                        st.rerun()
            added = st.text_input("Add ticker", max_chars=3, key="backtest_collect_group_add_v4")
            add_column, save_column = st.columns(2)
            if add_column.button("Add", key="backtest_collect_group_add_button_v4") and added.strip():
                ticker = parse_batch_tickers(added, maximum=1)[0]
                draft["tickers"] = sorted(set(draft["tickers"]) | {ticker})
                st.session_state[_COLLECT_GROUP_DRAFT_KEY] = draft
                st.rerun()
            if save_column.button("Save Group", key="backtest_collect_group_save_v4"):
                replace_group_tickers(group_selection, draft["tickers"], signal_dir)
                st.session_state.pop(_COLLECT_GROUP_DRAFT_KEY, None)
                st.rerun()
    horizon_column, range_column, action_column = st.columns(3)
    horizon_label = horizon_column.selectbox(
        "Horizon", tuple(HORIZON_LABELS.values()), key="backtest_collect_horizon_v4"
    )
    horizon = next(
        key for key, label in HORIZON_LABELS.items() if label == horizon_label
    )
    time_range = range_column.selectbox(
        "Range", TIME_RANGE_OPTIONS, index=1, key="backtest_collect_range_v4"
    )
    st.caption("Exploratory — gross. Every run evaluates no-theme and VN-Index AND treatments.")
    if action_column.button("Run Backtest", key="backtest_collect_submit_v4"):
        try:
            if resolution_error is not None:
                raise resolution_error
            if group_selection == _COLLECT_NEW_GROUP_OPTION:
                group_name = new_group_name.strip().upper()
                if not group_name or group_name == "N/A":
                    raise ValueError("New group name is required.")
                if group_name in named_groups:
                    raise ValueError("Group already exists; select it from Group.")
            else:
                group_name = group_selection
            tickers = (
                resolved_tickers
                if group_selection not in {"N/A", _COLLECT_NEW_GROUP_OPTION}
                else parse_batch_tickers(tickers_text)
            )
            config = build_backtest_batch_config(
                tickers, horizon, time_range, group_name=group_name
            )
            if engine_factory is None:
                raise ValueError("Backtest engine factory is not configured.")
            st.session_state["backtest_v4_job"] = submit_fn(config, engine_factory, status_dir)
        except ValueError as error:
            st.error(str(error))
    job_id = st.session_state.get("backtest_v4_job")
    if not isinstance(job_id, str):
        return
    try:
        status = read_status_fn(job_id, status_dir)
    except (OSError, ValueError, KeyError) as error:
        st.error(f"Unable to read Backtest status: {error}")
        return
    st.progress(status.progress, text=format_job_status(status))
    if status.output_paths:
        result_columns = st.columns(4)
        for index, path in enumerate(status.output_paths):
            with result_columns[index % 4]:
                _render_v4_artifact(path)
    if status.state in {"queued", "running"}:
        schedule_refresh_fn(True)


def _render_validation_result(
    ticker: str,
    result: Mapping[str, object],
    allowed: set[str],
    position_action: str = "ALL",
) -> None:
    """Render one completed ticker validation without changing its advice."""

    visible_items = [
        item for item in result["results"]
        if item.get("availability") == "available"
        and isinstance(item.get("monitoring"), Mapping)
        and item["monitoring"].get("match_classification") in allowed
        and (
            position_action == "ALL"
            or item.get("position_action", "expired BUY") == position_action
        )
    ]
    if not visible_items:
        return
    st.subheader(ticker)
    for item in visible_items:
        label = f"{HORIZON_LABELS[item['horizon']]} — {item['rulebook_id']} — {item['preferred_variant']}"
        with st.expander(label):
            monitoring = item.get("monitoring")
            action = item.get("position_action", "expired BUY")
            st.write(
                f"Monitoring: {monitoring['match_level']}% — "
                f"{monitoring['match_classification'].replace('_', ' ')} | {action}"
            )
            st.caption(f"{item['evaluation_label']} — training and test evidence")
            if item.get("buy_block_reason") == "audit_ineligible":
                st.warning("BUY is blocked: audit-ineligible raw history.")
            elif item.get("buy_block_reason") == "open_position":
                st.caption("BUY is blocked: this saved rulebook already has an OPEN position.")
            st.json(
                {
                    "audit_eligibility": item["audit_eligibility"],
                    "current_gates": item["current"],
                    "both_treatments": item["candidate"]["treatments"],
                },
                expanded=False,
            )
    if result["historical_positions"]:
        st.caption("Historical positions are P&L/manual-management history only.")


def _render_validate(
    engine,
    signal_dir: str,
    positions_dir: str,
    validate_fn,
    group_choices_fn: Callable,
    group_resolver_fn: Callable,
) -> None:
    st.subheader("Validate Signals")
    group_key = "backtest_validate_group_v4"
    tickers_row = st.columns((3, 1))
    resolved_tickers: tuple[str, ...] = ()
    resolution_error: ValueError | OSError | None = None
    try:
        group_choices = group_choices_fn(signal_dir)
    except (OSError, ValueError) as error:
        group_choices = ("-",)
        resolution_error = error
    group_name = tickers_row[1].selectbox(
        "Ticker group", group_choices, key=group_key
    )
    if group_name != "-":
        try:
            resolved_tickers = _validation_tickers(
                "", group_name, signal_dir, group_resolver_fn
            )
        except (OSError, ValueError) as error:
            resolution_error = error
    if group_name == "-":
        tickers_text = tickers_row[0].text_input(
            "Tickers", key="backtest_validate_tickers_v4"
        )
    else:
        tickers_text = tickers_row[0].text_input(
            "Tickers",
            value=" ".join(resolved_tickers),
            disabled=True,
            key="backtest_validate_group_tickers_v4",
        )

    filters = st.columns((2, 2, 1))
    selected = filters[0].multiselect(
        "Monitoring classifications",
        MATCH_CLASSIFICATION_OPTIONS,
        default=list(MATCH_CLASSIFICATION_OPTIONS),
        key="backtest_validate_match_classifications_v4",
    )
    position_action = filters[1].selectbox(
        "Position actions",
        POSITION_ACTION_OPTIONS,
        key="backtest_validate_position_action_v4",
    )
    validate_clicked = filters[2].button(
        "Validate", key="backtest_validate_submit_v4"
    )

    if resolution_error is not None:
        st.error(str(resolution_error))
    if validate_clicked:
        try:
            tickers = _validation_tickers(
                tickers_text, group_name, signal_dir, group_resolver_fn
            )
        except (OSError, ValueError) as error:
            st.error(str(error))
            return

        progress = st.progress(0, text=f"Validating 0/{len(tickers)} tickers")

        def update_progress(completed: int, total: int, ticker: str) -> None:
            progress.progress(
                completed / total,
                text=f"Validated {completed}/{total} tickers: {ticker}",
            )

        batch = _run_validation_batches(
            tickers,
            engine,
            signal_dir,
            positions_dir,
            validate_fn,
            progress_fn=update_progress,
        )
        for ticker, error in batch["errors"].items():
            st.error(f"Validate {ticker} failed: {error}")
        if batch["by_ticker"]:
            st.session_state["backtest_v4_validation_result"] = batch

    latest = st.session_state.get("backtest_v4_validation_result")
    if not isinstance(latest, Mapping) or not latest.get("by_ticker"):
        return
    allowed = {MATCH_CLASSIFICATION_VALUES[name] for name in selected}
    for ticker, result in latest["by_ticker"].items():
        if isinstance(result, Mapping):
            _render_validation_result(ticker, result, allowed, position_action)


_VIEW_SIGNAL_COLUMNS = (
    "Ticker",
    "Horizon",
    "Theme",
    "Train-test",
    "n",
    "Win rate %",
    "Profit %",
    "Sharpe",
)


def _view_metric(value: object, decimals: int | None = None) -> str:
    """Render one stored train/test metric without changing its scale."""

    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{decimals}f}" if decimals is not None else str(value)


def _view_signal_rows(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Project raw catalog rows into the approved concise View Signals table."""

    output = []
    for row in rows:
        def paired(metric: str, decimals: int | None = None) -> str:
            return (
                f"{_view_metric(row.get('Training ' + metric), decimals)} - "
                f"{_view_metric(row.get('Test ' + metric), decimals)}"
            )

        output.append(
            {
                "Ticker": row.get("Ticker"),
                "Horizon": row.get("Horizon"),
                "Theme": (
                    "Included"
                    if row.get("Preferred treatment") == "background-theme"
                    else "Excluded"
                ),
                "Train-test": (
                    "YES" if "Training n" in row and "Test n" in row else "NO"
                ),
                "n": paired("n"),
                "Win rate %": paired("win rate %", 1),
                "Profit %": paired("profit %", 1),
                "Sharpe": paired("Sharpe", 1),
            }
        )
    return output


def _filter_view_signal_rows(
    rows: Iterable[Mapping[str, object]],
    ticker_filter: str,
    horizon_filter: str,
) -> list[dict[str, object]]:
    """Return projected View Signals rows matching both local UI filters."""

    ticker = ticker_filter.strip().upper()
    return [
        dict(row)
        for row in rows
        if (not ticker or ticker in str(row.get("Ticker", "")).upper())
        and (
            horizon_filter == "Both"
            or row.get("Horizon") == horizon_filter
        )
    ]


def _render_view(signal_dir: str) -> None:
    st.subheader("View Signals")
    catalog = list_current_signal_set_rows(signal_dir)
    ticker_column, horizon_column = st.columns(2)
    with ticker_column:
        ticker_filter = st.text_input(
            "Ticker",
            max_chars=3,
            key=_VIEW_SIGNAL_TICKER_FILTER_KEY,
            on_change=_uppercase_ticker_state,
            args=(_VIEW_SIGNAL_TICKER_FILTER_KEY,),
        )
    with horizon_column:
        horizon_filter = st.selectbox(
            "Horizon",
            _VIEW_SIGNAL_HORIZON_OPTIONS,
            key=_VIEW_SIGNAL_HORIZON_FILTER_KEY,
        )
    rows = _filter_view_signal_rows(
        _view_signal_rows(catalog["valid"]),
        ticker_filter,
        horizon_filter,
    )
    if rows:
        st.dataframe(
            pd.DataFrame(rows, columns=_VIEW_SIGNAL_COLUMNS),
            use_container_width=True,
            height=720,
        )
    for warning in catalog["warnings"]:
        st.warning(warning)


def _position_horizon(position: dict[str, object]) -> str | None:
    reference = position.get("signal_reference")
    if isinstance(reference, dict) and reference.get("schema_version") == 4:
        horizon = reference.get("horizon")
        return str(horizon) if horizon in HORIZON_LABELS else None
    return None


def _saved_set_label(position: dict[str, object]) -> str:
    reference = position.get("signal_reference")
    horizon = _position_horizon(position)
    if isinstance(reference, dict) and reference.get("schema_version") == 4 and horizon:
        return f"{HORIZON_LABELS[horizon]} — {reference['rulebook_id']} — {reference['preferred_variant']}"
    return "Historical saved set" if horizon is None else f"Historical saved set — {HORIZON_LABELS[horizon]}"


def _display_position_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{
        "Ticker": row["ticker"], "State": row["status"], "Saved signal set": _saved_set_label(row["position"]),
        "BUY (k VND)": prepare_price_for_output(row["actual_buy_price"], PRICE_OUTPUT_UI),
        "SELL (k VND)": None if row["actual_sell_price"] is None else prepare_price_for_output(row["actual_sell_price"], PRICE_OUTPUT_UI),
        "P&L (%)": row["profit_pct"], "Holding sessions": row["holding_sessions"],
    } for row in rows]


def _validated_v4_candidates(validation: object, ticker: str) -> dict[str, dict[str, object]]:
    validation = _validation_result_for_ticker(validation, ticker)
    if validation is None:
        return {}
    candidates = {}
    for item in validation.get("results", ()):
        if not isinstance(item, dict) or not item.get("buy_eligible"):
            continue
        horizon, reference = item.get("horizon"), item.get("signal_reference")
        if not isinstance(reference, dict) or horizon not in HORIZON_LABELS:
            continue
        candidates[f"{HORIZON_LABELS[horizon]} — {item['rulebook_id']} — {item['preferred_variant']}"] = item
    return candidates


def _refresh_new_position_saved_sets(
    engine,
    signal_dir: str,
    positions_dir: str,
    validate_fn: Callable,
) -> None:
    """Refresh only the New Position candidate state after a ticker commit."""

    _uppercase_ticker_state(_NEW_POSITION_TICKER_KEY)
    ticker = str(st.session_state.get(_NEW_POSITION_TICKER_KEY, "")).strip()
    st.session_state[_NEW_POSITION_SAVED_SET_KEY] = "Manual P&L only"
    st.session_state.pop(_NEW_POSITION_VALIDATION_KEY, None)
    st.session_state.pop(_NEW_POSITION_VALIDATION_ERROR_KEY, None)
    if not ticker:
        return
    try:
        st.session_state[_NEW_POSITION_VALIDATION_KEY] = validate_fn(
            ticker, engine, signal_dir, positions_dir
        )
    except (OSError, TypeError, ValueError) as error:
        st.session_state[_NEW_POSITION_VALIDATION_ERROR_KEY] = str(error)


def _raw_current_value(value: object, field: str) -> int:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric) or float(numeric) <= 0 or not float(numeric).is_integer():
        raise ValueError(f"{field} must be a positive raw integer")
    return int(numeric)


def _create_position_from_form(
    ticker: str,
    selected: str,
    candidates: dict[str, dict[str, object]],
    buy_k_vnd: object,
    buy_date: date,
    quantity: int,
    positions_dir: str,
    *,
    status: str = "OPEN",
    sell_k_vnd: object = None,
    sell_date: date | None = None,
) -> None:
    buy_price = price_from_ui_k_vnd(buy_k_vnd)
    sell_values = {}
    if status == "CLOSED":
        sell_values = {
            "actual_sell_price": price_from_ui_k_vnd(sell_k_vnd),
            "sell_date": sell_date,
        }
    if selected == "Manual P&L only":
        create_manual_position(
            ticker,
            buy_price,
            buy_date,
            quantity=quantity or None,
            positions_dir=positions_dir,
            **sell_values,
        )
        return
    item = candidates[selected]
    current = item["current"]
    monitoring = item.get("monitoring") or {"match_level": 0.0}
    create_manual_position(
        ticker, buy_price, buy_date, quantity=quantity or None, signal_reference=item["signal_reference"],
        entry_context={"match_level": monitoring["match_level"], "current_price": _raw_current_value(current["latest_close"], "current latest_close"), "as_of_date": current["as_of_date"]},
        risk_snapshot=build_v4_risk_snapshot(item["horizon"], _raw_current_value(current["latest_atr"], "current latest_atr"), buy_price),
        positions_dir=positions_dir, **sell_values,
    )


def _load_position_overview(engine, positions_dir: str) -> dict[str, object]:
    """Load one coherent overview; filter and sort reruns reuse this snapshot."""

    records, errors = load_all_positions(positions_dir)
    latest: dict[str, dict[str, object]] = {}
    sessions: dict[str, list[str]] = {}
    if records and engine is not None:
        latest = load_latest_close_prices(
            (record["ticker"] for record in records if record["status"] == "open"),
            engine,
        )
        sessions = load_completed_trading_sessions(records, latest, engine)
    return {
        "rows": summarize_positions(records, latest, sessions),
        "errors": errors,
    }


def _uppercase_ticker_state(widget_key: str) -> None:
    value = st.session_state.get(widget_key)
    if isinstance(value, str):
        st.session_state[widget_key] = value.strip().upper()


def _filter_and_sort_positions(
    rows: Iterable[Mapping[str, object]],
    ticker_filter: str,
    states: Iterable[str],
    sort_by: str,
    direction: str,
) -> list[Mapping[str, object]]:
    """Filter the cached overview and keep unavailable sort values last."""

    ticker = ticker_filter.strip().upper()
    allowed_states = {str(state).strip().lower() for state in states}
    filtered = [
        row
        for row in rows
        if (not ticker or str(row.get("ticker", "")).upper() == ticker)
        and str(row.get("status", "")).lower() in allowed_states
    ]
    sort_fields = {
        "Open date": "opened_at",
        "Ticker": "ticker",
        "State": "status",
        "BUY price": "actual_buy_price",
        "Profit %": "profit_pct",
        "Profit": "profit_raw",
        "Hold time": "holding_sessions",
    }
    field = sort_fields.get(sort_by, "opened_at")
    available = [row for row in filtered if row.get(field) is not None]
    unavailable = [row for row in filtered if row.get(field) is None]
    available.sort(
        key=lambda row: row.get(field),
        reverse=str(direction).upper() == "DESC",
    )
    return [*available, *unavailable]


def _display_price(value: object) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        return prepare_price_for_output(value, PRICE_OUTPUT_UI)
    except (TypeError, ValueError):
        return "-"


def _position_trade_display_frame(
    buy: Mapping[str, object], sell: Mapping[str, object]
) -> pd.DataFrame:
    """Format raw projection values only at the Streamlit display boundary."""

    suggestion = sell.get("suggestion")
    suggestion = suggestion if isinstance(suggestion, Mapping) else {}
    if suggestion and any(value is not None for value in suggestion.values()):
        projected = suggestion.get("projected_exit") or "-"
        holding = suggestion.get("suggested_holding_bars")
        holding = holding if holding is not None else "-"
        stop_loss = _display_price(suggestion.get("stop_loss"))
        take_profit = _display_price(suggestion.get("take_profit"))
        sell_suggestion = (
            f"Projected exit: {projected} | Holding: {holding} | "
            f"SL/TP: {stop_loss} / {take_profit}"
        )
    else:
        sell_suggestion = "-"
    sell_price, sell_date = sell.get("actual_sell_price"), sell.get("sell_date")
    actual_sell = (
        f"{_display_price(sell_price)} / {sell_date}"
        if sell_price is not None and sell_date is not None
        else "-"
    )
    def display_text(value: object) -> str:
        return str(value) if value not in (None, "") else "-"

    profit_pct = buy.get("profit_pct")
    profit_pct = "-" if profit_pct is None else f"{float(profit_pct):.2f}%"
    return pd.DataFrame(
        [
            {
                "Trade": "BUY",
                "Price": display_text(_display_price(buy.get("actual_buy_price"))),
                "Date": display_text(buy.get("buy_date")),
                "Volume": display_text(buy.get("quantity")),
                "Saved signal set": display_text(buy.get("signal_set")),
                "Current price": display_text(_display_price(buy.get("current_price"))),
                "Profit %": profit_pct,
                "Profit": display_text(_display_price(buy.get("profit_raw"))),
                "Hold time": display_text(buy.get("holding_sessions")),
                "Risk Suggestion": display_text(
                    buy.get("risk_suggestion_text") or "N/A"
                ),
                "SELL suggestion": "-",
                "Actual SELL": "-",
            },
            {
                "Trade": "SELL",
                "Price": "-",
                "Date": "-",
                "Volume": "-",
                "Saved signal set": "-",
                "Current price": "-",
                "Profit %": "-",
                "Profit": "-",
                "Hold time": "-",
                "Risk Suggestion": "-",
                "SELL suggestion": sell_suggestion,
                "Actual SELL": actual_sell,
            },
        ]
    )


def _position_trade_display_styles(
    frame: pd.DataFrame, *, buy: Mapping[str, object]
) -> pd.DataFrame:
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    if buy.get("risk_struck") and not frame.empty:
        styles.loc[frame.index[0], "Risk Suggestion"] = (
            "text-decoration: line-through"
        )
    return styles


def _overview_position_id(row: Mapping[str, object]) -> str:
    position_id = row.get("id")
    if not isinstance(position_id, str) or not position_id.strip():
        raise ValueError("position row requires a non-empty id")
    return position_id


def _visible_position_ids(rows: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    return tuple(_overview_position_id(row) for row in rows)


def _pruned_selection(
    selected_ids: set[str], visible_ids: tuple[str, ...]
) -> set[str]:
    return set(selected_ids).intersection(visible_ids)


def _position_selection_widget_key(position_id: str) -> str:
    return f"backtest_position_select_v4_{position_id}"


def _sync_visible_position_selection(visible_ids: tuple[str, ...]) -> None:
    selected = st.session_state.get(_POSITION_SELECTED_IDS_KEY, set())
    selected = set(selected) if isinstance(selected, (set, tuple, list)) else set()
    selected = _pruned_selection(selected, visible_ids)
    st.session_state[_POSITION_SELECTED_IDS_KEY] = selected
    st.session_state[_POSITION_SELECT_ALL_VISIBLE_KEY] = bool(visible_ids) and selected == set(visible_ids)
    for position_id in visible_ids:
        st.session_state[_position_selection_widget_key(position_id)] = (
            position_id in selected
        )


def _apply_position_selection(position_id: str) -> None:
    selected = set(st.session_state.get(_POSITION_SELECTED_IDS_KEY, set()))
    if st.session_state.get(_position_selection_widget_key(position_id), False):
        selected.add(position_id)
    else:
        selected.discard(position_id)
    st.session_state[_POSITION_SELECTED_IDS_KEY] = selected
    st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)


def _apply_select_all_visible(visible_ids: tuple[str, ...]) -> None:
    checked = bool(st.session_state.get(_POSITION_SELECT_ALL_VISIBLE_KEY))
    selected = set(visible_ids) if checked else set()
    st.session_state[_POSITION_SELECTED_IDS_KEY] = selected
    for position_id in visible_ids:
        st.session_state[_position_selection_widget_key(position_id)] = checked
    st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)


def _position_row_locator(row: Mapping[str, object]) -> Mapping[str, object]:
    locator = row.get("position_locator")
    if isinstance(locator, Mapping):
        return locator
    position = row.get("position")
    if isinstance(position, Mapping) and isinstance(
        position.get("position_locator"), Mapping
    ):
        return position["position_locator"]
    raise ValueError("position locator is unavailable")


def _validated_delete_locator(locator: Mapping[str, object]) -> dict[str, str]:
    if not isinstance(locator, Mapping):
        raise ValueError("position locator must be a mapping")
    source = locator.get("record_source")
    required = ("record_source", "ticker", "id")
    if source == "legacy":
        required += ("theme_variant", "metric")
    elif source != "manual":
        raise ValueError("position locator has an invalid record source")
    if any(
        not isinstance(locator.get(field), str) or not str(locator[field]).strip()
        for field in required
    ):
        raise ValueError("position locator is incomplete")
    return {field: str(locator[field]) for field in required}


def _update_by_locator(
    locator: Mapping[str, object],
    updates: Mapping[str, object],
    positions_dir: str,
    update_position_fn: Callable,
    manual_update_fn: Callable,
) -> dict[str, object]:
    valid = _validated_delete_locator(locator)
    if valid["record_source"] == "manual":
        return manual_update_fn(
            valid["ticker"], valid["id"], updates, positions_dir
        )
    return update_position_fn(
        valid["ticker"],
        valid["theme_variant"],
        valid["metric"],
        valid["id"],
        updates,
        positions_dir,
    )


def _delete_by_locator(
    locator: Mapping[str, object],
    positions_dir: str,
    delete_position_fn: Callable,
    manual_delete_fn: Callable,
) -> dict[str, object]:
    valid = _validated_delete_locator(locator)
    if valid["record_source"] == "manual":
        return manual_delete_fn(valid["ticker"], valid["id"], positions_dir)
    return delete_position_fn(
        valid["ticker"],
        valid["theme_variant"],
        valid["metric"],
        valid["id"],
        positions_dir,
    )


def _position_delete_summary(row: Mapping[str, object]) -> str:
    return (
        f"{row.get('ticker', '-')} — {str(row.get('status', '-')).upper()} — "
        f"BUY {_display_price(row.get('actual_buy_price'))} k VND"
    )


def _prepare_batch_delete(
    rows: Iterable[Mapping[str, object]], selected_ids: set[str]
) -> tuple[dict[str, object], ...]:
    entries = []
    for row in rows:
        position_id = _overview_position_id(row)
        if position_id not in selected_ids:
            continue
        entries.append(
            {
                "position_id": position_id,
                "locator": _validated_delete_locator(_position_row_locator(row)),
                "summary": _position_delete_summary(row),
            }
        )
    if not entries:
        raise ValueError("Select at least one visible position")
    return tuple(entries)


def _position_display_context(
    ticker_filter: str, states: Iterable[str], sort_by: str, direction: str
) -> tuple[str, tuple[str, ...], str, str]:
    """Normalize the controls that define the pending delete's displayed rows."""
    return (
        ticker_filter.strip().upper(),
        tuple(sorted({str(state).strip().upper() for state in states})),
        str(sort_by).strip(),
        str(direction).strip().upper(),
    )


def _delete_confirmation_is_current(
    confirmation: Mapping[str, object],
    visible_ids: tuple[str, ...],
    selected_ids: tuple[str, ...],
    display_context: tuple[str, tuple[str, ...], str, str],
) -> bool:
    expected = tuple(confirmation.get("selected_ids", ()))
    return (
        confirmation.get("display_context") == display_context
        and expected == selected_ids
        and all(position_id in visible_ids for position_id in expected)
    )


def _run_batch_delete(
    entries: tuple[Mapping[str, object], ...],
    positions_dir: str,
    delete_position_fn: Callable,
    manual_delete_fn: Callable,
) -> tuple[int, Mapping[str, object] | None, Exception | None]:
    deleted = 0
    for entry in entries:
        try:
            _delete_by_locator(
                entry["locator"],
                positions_dir,
                delete_position_fn,
                manual_delete_fn,
            )
        except (KeyError, OSError, TypeError, ValueError) as error:
            return deleted, entry, error
        deleted += 1
    return deleted, None, None


def _batch_delete_feedback(
    deleted: int,
    entries: tuple[Mapping[str, object], ...],
    failed: Mapping[str, object] | None,
    error: Exception | None,
) -> dict[str, object]:
    if error is None:
        return {
            "level": "success",
            "message": f"{deleted} positions permanently deleted.",
            "duration_seconds": 2,
        }
    return {
        "level": "error",
        "message": (
            f"Deleted {deleted} of {len(entries)} positions; stopped at "
            f"{failed['summary']}: {error}"
        ),
        "duration_seconds": None,
    }


def _editor_row_to_updates(row: Mapping[str, object]) -> dict[str, object]:
    status = str(row.get("State", "")).strip().lower()
    if status not in {"open", "closed"}:
        raise ValueError("State must be OPEN or CLOSED")
    buy_value = row.get("BUY price (k)", row.get("BUY price"))
    sell_value = row.get("SELL price (k)", row.get("SELL price"))
    buy_date = row.get("BUY date")
    sell_date = row.get("SELL date")
    quantity = row.get("Volume")
    updates = {
        "status": status,
        "actual_buy_price": price_from_ui_k_vnd(buy_value),
        "buy_date": buy_date.isoformat() if isinstance(buy_date, date) else buy_date,
        "quantity": int(quantity) if quantity not in (None, 0) else None,
        "actual_sell_price": None,
        "sell_date": None,
    }
    if status == "closed":
        updates.update(
            {
                "actual_sell_price": price_from_ui_k_vnd(sell_value),
                "sell_date": sell_date.isoformat()
                if isinstance(sell_date, date)
                else sell_date,
            }
        )
    return updates


def _position_date_value(value: object, fallback: date | None = None) -> date:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return fallback or datetime.now(MARKET_TIMEZONE).date()
    return parsed.date()


def _render_position_edit_form(
    row: Mapping[str, object],
    positions_dir: str,
    update_position_fn: Callable,
    manual_update_fn: Callable,
    rerun_fn: Callable,
) -> None:
    position_id = _overview_position_id(row)
    key_prefix = f"backtest_position_edit_v4_{position_id}"
    st.caption(f"Ticker: {row.get('ticker', '-')}")
    st.caption(f"Saved signal set: {row.get('signal_set') or '-'}")
    buy_date_default = _position_date_value(row.get("buy_date"))
    with st.form(f"{key_prefix}_form"):
        state = st.selectbox(
            "State",
            ("OPEN", "CLOSED"),
            index=0 if str(row.get("status", "")).lower() == "open" else 1,
            key=f"{key_prefix}_state",
        )
        buy_k_vnd = st.number_input(
            "BUY price (k)",
            min_value=0.001,
            value=float(row.get("actual_buy_price") or 0) / 1000,
            step=0.001,
            key=f"{key_prefix}_buy_price",
        )
        buy_date = st.date_input(
            "BUY date", value=buy_date_default, key=f"{key_prefix}_buy_date"
        )
        quantity = st.number_input(
            "Volume",
            min_value=0,
            value=int(row.get("quantity") or 0),
            step=100,
            key=f"{key_prefix}_volume",
        )
        sell_k_vnd = st.number_input(
            "SELL price (k)",
            min_value=0.0,
            value=float(row.get("actual_sell_price") or 0) / 1000,
            step=0.001,
            key=f"{key_prefix}_sell_price",
        )
        sell_date = st.date_input(
            "SELL date",
            value=_position_date_value(row.get("sell_date"), buy_date_default),
            key=f"{key_prefix}_sell_date",
        )
        save = st.form_submit_button("Save position changes")
    if not save:
        return
    try:
        updates = _editor_row_to_updates(
            {
                "State": state,
                "BUY price (k)": buy_k_vnd,
                "BUY date": buy_date,
                "Volume": quantity,
                "SELL price (k)": sell_k_vnd,
                "SELL date": sell_date,
            }
        )
        _update_by_locator(
            _position_row_locator(row),
            updates,
            positions_dir,
            update_position_fn,
            manual_update_fn,
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        st.error(f"Unable to update position: {error}")
        return
    st.session_state.pop(_POSITION_OVERVIEW_KEY, None)
    st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
    st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
    st.session_state[_POSITION_SELECTED_IDS_KEY] = set()
    st.session_state[_POSITION_FEEDBACK_KEY] = "Position updated."
    rerun_fn()


def _render_position_trade_group(
    row: Mapping[str, object],
    *,
    positions_dir: str,
    update_position_fn: Callable,
    manual_update_fn: Callable,
    rerun_fn: Callable,
) -> None:
    position_id = _overview_position_id(row)
    st.checkbox(
        "Select",
        key=_position_selection_widget_key(position_id),
        on_change=_apply_position_selection,
        args=(position_id,),
    )
    label = f"{row.get('ticker', '-')} — {str(row.get('status', '')).upper()}"
    with st.expander(label):
        buy, sell = build_position_trade_rows(row)
        frame = _position_trade_display_frame(buy, sell)
        styled = frame.style.apply(
            _position_trade_display_styles, buy=buy, axis=None
        )
        st.dataframe(styled, use_container_width=True)
        if st.button(
            "Edit position", key=f"backtest_position_edit_button_v4_{position_id}"
        ):
            st.session_state[_POSITION_EDITING_ID_KEY] = position_id
        if st.session_state.get(_POSITION_EDITING_ID_KEY) == position_id:
            _render_position_edit_form(
                row,
                positions_dir,
                update_position_fn,
                manual_update_fn,
                rerun_fn,
            )


def _render_new_position_section(
    positions_dir: str,
    engine,
    signal_dir: str,
    validate_fn: Callable,
    rerun_fn: Callable,
) -> None:
    """Render live new-position controls above the Current Positions filters."""

    with st.expander("New Position", expanded=False):
        identity_row = st.columns((1, 1, 2))
        ticker = identity_row[0].text_input(
            "Ticker",
            max_chars=3,
            key=_NEW_POSITION_TICKER_KEY,
            on_change=_refresh_new_position_saved_sets,
            args=(engine, signal_dir, positions_dir, validate_fn),
        ).strip().upper()
        validation = st.session_state.get(_NEW_POSITION_VALIDATION_KEY)
        validation_for_ticker = _validation_result_for_ticker(validation, ticker)
        candidates = _validated_v4_candidates(validation_for_ticker, ticker)
        validation_error = st.session_state.get(_NEW_POSITION_VALIDATION_ERROR_KEY)
        if ticker and isinstance(validation_error, str):
            st.warning(f"Saved signal sets could not be refreshed: {validation_error}")
        elif ticker and validation_for_ticker is not None and not candidates:
            blocked_reasons = sorted({
                str(item.get("buy_block_reason")).replace("_", " ")
                for item in validation_for_ticker.get("results", ())
                if isinstance(item, Mapping) and item.get("buy_block_reason")
            })
            detail = f" ({', '.join(blocked_reasons)})" if blocked_reasons else ""
            st.info(f"{ticker}: saved signal sets found, but none are BUY-eligible{detail}.")
        state = identity_row[1].selectbox(
            "State",
            ("OPEN", "CLOSED"),
            key="backtest_position_new_state_v4",
        )
        selected = identity_row[2].selectbox(
            "Saved signal set",
            ["Manual P&L only", *candidates],
            key=_NEW_POSITION_SAVED_SET_KEY,
        )
        trade_row = st.columns(5)
        buy_k_vnd = trade_row[0].number_input(
            "BUY price",
            min_value=0.001,
            step=0.001,
            key="backtest_position_new_buy_v4",
        )
        buy_date = trade_row[1].date_input(
            "BUY date", key="backtest_position_new_buy_date_v4"
        )
        quantity = trade_row[2].number_input(
            "Volume (0 = unspecified)",
            min_value=0,
            step=100,
            key="backtest_position_new_quantity_v4",
        )
        sell_k_vnd = trade_row[3].number_input(
            "SELL price",
            min_value=0.0,
            step=0.001,
            key="backtest_position_new_sell_v4",
        )
        sell_date = trade_row[4].date_input(
            "SELL date", value=None, key="backtest_position_new_sell_date_v4"
        )
        create = st.button("Add Position", key="backtest_position_create_v4_submit")
        if not create:
            return
        try:
            if not ticker:
                raise ValueError("Ticker is required.")
            _create_position_from_form(
                ticker,
                selected,
                candidates,
                buy_k_vnd,
                buy_date,
                quantity,
                positions_dir,
                status=state,
                sell_k_vnd=sell_k_vnd,
                sell_date=sell_date,
            )
        except (KeyError, OSError, TypeError, ValueError) as error:
            st.error(f"Unable to add position: {error}")
            return
        st.session_state.pop(_POSITION_OVERVIEW_KEY, None)
        st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
        st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
        st.session_state[_POSITION_SELECTED_IDS_KEY] = set()
        st.session_state[_POSITION_FEEDBACK_KEY] = "Position added."
        rerun_fn()


def _render_delete_confirmation(
    visible_ids: tuple[str, ...],
    selected_ids: tuple[str, ...],
    display_context: tuple[str, tuple[str, ...], str, str],
    positions_dir: str,
    delete_position_fn: Callable,
    manual_delete_fn: Callable,
    rerun_fn: Callable,
) -> None:
    confirmation = st.session_state.get(_POSITION_DELETE_CONFIRMATION_KEY)
    if not isinstance(confirmation, Mapping):
        return
    if not _delete_confirmation_is_current(
        confirmation, visible_ids, selected_ids, display_context
    ):
        st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
        return
    entries = tuple(confirmation.get("entries", ()))
    st.warning(
        "Permanently delete the selected positions?\n\n"
        + "\n".join(f"- {entry['summary']}" for entry in entries)
    )
    confirm, cancel = st.columns(2)
    if confirm.button(
        "Confirm permanent delete", key="backtest_position_confirm_delete_v4"
    ):
        deleted, failed, error = _run_batch_delete(
            entries,
            positions_dir,
            delete_position_fn,
            manual_delete_fn,
        )
        st.session_state.pop(_POSITION_OVERVIEW_KEY, None)
        st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
        st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
        st.session_state[_POSITION_SELECTED_IDS_KEY] = set()
        st.session_state[_POSITION_FEEDBACK_KEY] = _batch_delete_feedback(
            deleted, entries, failed, error
        )
        rerun_fn()
    if cancel.button("Cancel", key="backtest_position_cancel_delete_v4"):
        st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
        rerun_fn()


def _render_positions(
    positions_dir: str,
    engine,
    *,
    signal_dir: str,
    validate_fn: Callable,
    position_overview_fn: Callable,
    update_position_fn: Callable,
    manual_update_fn: Callable,
    delete_position_fn: Callable,
    manual_delete_fn: Callable,
    rerun_fn: Callable,
) -> None:
    st.subheader("Current Positions")
    feedback = st.session_state.pop(_POSITION_FEEDBACK_KEY, None)
    if isinstance(feedback, str):
        st.success(feedback)
    elif isinstance(feedback, Mapping):
        if feedback.get("level") == "error":
            st.error(str(feedback.get("message", "")))
        elif feedback.get("level") == "success":
            st.success(str(feedback.get("message", "")))
            if feedback.get("duration_seconds") == 2:
                time.sleep(2)
                rerun_fn()
    if _POSITION_OVERVIEW_KEY not in st.session_state:
        st.session_state[_POSITION_OVERVIEW_KEY] = position_overview_fn(
            engine, positions_dir
        )
    overview = st.session_state[_POSITION_OVERVIEW_KEY]
    if not isinstance(overview, Mapping):
        st.error("Position overview is unavailable.")
        return
    rows = list(overview.get("rows", ()))
    for error in overview.get("errors", ()):
        st.warning(str(error))

    _render_new_position_section(
        positions_dir, engine, signal_dir, validate_fn, rerun_fn
    )

    toolbar = st.columns(5)
    with toolbar[0]:
        ticker_filter = st.text_input(
            "Ticker filter",
            max_chars=3,
            key=_POSITION_TICKER_FILTER_KEY,
            on_change=_uppercase_ticker_state,
            args=(_POSITION_TICKER_FILTER_KEY,),
        )
    with toolbar[1]:
        states = st.multiselect(
            "Position state",
            ("OPEN", "CLOSED"),
            default=("OPEN",),
            key="backtest_position_states_v4",
        )
    with toolbar[2]:
        sort_by = st.selectbox(
            "Sort by",
            ("Open date", "Ticker", "State", "BUY price", "Profit %", "Profit", "Hold time"),
            key="backtest_position_sort_v4",
        )
    with toolbar[3]:
        direction = st.selectbox(
            "Direction", ("ASC", "DESC"), key="backtest_position_direction_v4"
        )
    with toolbar[4]:
        if st.button("↻", help="Refresh positions", key="backtest_position_refresh_v4"):
            st.session_state.pop(_POSITION_OVERVIEW_KEY, None)
            st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
            st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
            st.session_state[_POSITION_SELECTED_IDS_KEY] = set()
            rerun_fn()

    visible_rows = _filter_and_sort_positions(
        rows, ticker_filter, states, sort_by, direction
    )
    display_context = _position_display_context(
        ticker_filter, states, sort_by, direction
    )
    visible_ids = _visible_position_ids(visible_rows)
    _sync_visible_position_selection(visible_ids)
    if st.session_state.get(_POSITION_EDITING_ID_KEY) not in visible_ids:
        st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
    st.checkbox(
        "Select all visible",
        key=_POSITION_SELECT_ALL_VISIBLE_KEY,
        on_change=_apply_select_all_visible,
        args=(visible_ids,),
    )

    for row in visible_rows:
        _render_position_trade_group(
            row,
            positions_dir=positions_dir,
            update_position_fn=update_position_fn,
            manual_update_fn=manual_update_fn,
            rerun_fn=rerun_fn,
        )
    if not rows:
        st.info("No saved positions.")
    elif not visible_rows:
        st.info("No positions match the current filters.")

    selected = set(st.session_state.get(_POSITION_SELECTED_IDS_KEY, set()))
    selected_ordered_ids = tuple(
        position_id for position_id in visible_ids if position_id in selected
    )
    if st.button(
        "Delete position",
        disabled=not selected_ordered_ids,
        key="backtest_position_delete_v4",
    ):
        try:
            entries = _prepare_batch_delete(visible_rows, selected)
        except (KeyError, TypeError, ValueError) as error:
            st.error(f"Unable to prepare deletion: {error}")
        else:
            st.session_state[_POSITION_DELETE_CONFIRMATION_KEY] = {
                "selected_ids": selected_ordered_ids,
                "entries": entries,
                "display_context": display_context,
            }
    _render_delete_confirmation(
        visible_ids,
        selected_ordered_ids,
        display_context,
        positions_dir,
        delete_position_fn,
        manual_delete_fn,
        rerun_fn,
    )


def _render_validate_positions(
    engine,
    positions_dir: str,
    *,
    candidates_fn: Callable = list_validate_position_candidates,
    validate_positions_fn: Callable = validate_open_positions,
) -> None:
    st.title("Validate Positions")
    candidates = candidates_fn(positions_dir)
    if not candidates:
        st.info("No eligible OPEN positions.")
    can_load_current = candidates and hasattr(engine, "raw_connection")
    latest = load_latest_close_prices((item["ticker"] for item in candidates), engine) if can_load_current else {}
    sessions = load_completed_trading_sessions(
        (item["position"] for item in candidates), latest, engine
    ) if can_load_current else {}
    selection_rows = []
    for candidate in candidates:
        position = candidate["position"]
        ticker = str(candidate["ticker"])
        latest_price = latest.get(ticker, {}) if isinstance(latest, Mapping) else {}
        current_price = latest_price.get("close") if isinstance(latest_price, Mapping) else None
        buy_date = position.get("buy_date")
        current_date = latest_price.get("date") if isinstance(latest_price, Mapping) else None
        holding = sum(
            buy_date < session <= current_date
            for session in sessions.get(ticker, ())
        ) if isinstance(buy_date, str) and isinstance(current_date, str) else None
        selection_rows.append(
            {
                "Select": False,
                "Ticker": ticker,
                "BUY price (k VND)": _display_price(position.get("actual_buy_price")),
                "Volume": position.get("quantity") or "-",
                "Current price (k VND)": _display_price(current_price),
                "Hold time": holding if holding is not None else "-",
                "Evaluation": candidate["evaluation"],
                "_position_id": candidate["id"],
            }
        )
    edited = st.data_editor(
        pd.DataFrame(selection_rows),
        hide_index=True,
        use_container_width=True,
        key="backtest_validate_positions_table",
        column_config={
            "Select": st.column_config.CheckboxColumn("Select"),
            "_position_id": None,
        },
        disabled=[
            "Ticker", "BUY price (k VND)", "Volume", "Current price (k VND)",
            "Hold time", "Evaluation", "_position_id",
        ],
    )
    selected_ids = tuple(
        str(row["_position_id"])
        for row in edited.to_dict("records")
        if bool(row.get("Select"))
    )
    valid_count = 1 <= len(selected_ids) <= 5
    if selected_ids and not valid_count:
        st.error("Select one to five OPEN positions.")
    if st.button("Run validation", disabled=not valid_count):
        try:
            result = validate_positions_fn(selected_ids, engine, positions_dir)
        except (OSError, TypeError, ValueError) as error:
            st.error(f"Failed — assess failed. ({error})")
            return
        as_of = result.get("as_of_date") if isinstance(result, Mapping) else None
        if isinstance(as_of, str):
            as_of_value = pd.to_datetime(as_of, errors="coerce")
            if not pd.isna(as_of_value):
                st.subheader(f"As of: {as_of_value:%d/%m/%Y}")
        rows = result.get("results", ()) if isinstance(result, Mapping) else ()
        if rows:
            result_rows = [
                {
                    "Ticker": row.get("ticker"),
                    "Evaluation": row.get("evaluation"),
                    "Risk": row.get("risk_suggestion"),
                    "Result": row.get("result"),
                }
                for row in rows if isinstance(row, Mapping)
            ]
            st.dataframe(pd.DataFrame(result_rows), use_container_width=True)
            if any(
                row.get("result") in ("Updated", "Unavailable — risk score missing/invalid.")
                for row in rows if isinstance(row, Mapping)
            ):
                st.session_state.pop(_POSITION_OVERVIEW_KEY, None)


def render_backtest_page(
    engine=None, status_dir: str = "backtest-status", signal_dir: str = DEFAULT_SIGNAL_DIR,
    positions_dir: str = "backtest-positions", engine_factory: Callable | None = None,
    submit_fn: Callable = submit_backtest, read_status_fn: Callable = read_job_status,
    schedule_refresh_fn: Callable = schedule_status_refresh,
    validate_fn: Callable = validate_saved_signals,
    group_choices_fn: Callable = list_validation_group_choices,
    group_resolver_fn: Callable = resolve_group_tickers,
    position_overview_fn: Callable = _load_position_overview,
    update_position_fn: Callable = update_position,
    manual_update_fn: Callable = update_manual_position,
    delete_position_fn: Callable = delete_position,
    manual_delete_fn: Callable = delete_manual_position,
    risk_candidates_fn: Callable = list_validate_position_candidates,
    validate_positions_fn: Callable = validate_open_positions,
    rerun_fn: Callable = st.rerun,
    **_unused,
) -> None:
    """Render schema-4 exploratory collection, replay, and position history."""

    st.title("Backtest Lab")
    collect, view_signals, validate, positions, validate_positions = st.tabs(
        (
            "Collect Signals",
            "View Signals",
            "Validate Signals",
            "Current Positions",
            "Validate Positions",
        )
    )
    with collect:
        _render_collect(
            engine_factory,
            status_dir,
            signal_dir,
            submit_fn,
            read_status_fn,
            schedule_refresh_fn,
            group_choices_fn,
            group_resolver_fn,
        )
    with view_signals:
        _render_view(signal_dir)
    with validate:
        _render_validate(
            engine,
            signal_dir,
            positions_dir,
            validate_fn,
            group_choices_fn,
            group_resolver_fn,
        )
    with positions:
        _render_positions(
            positions_dir,
            engine,
            signal_dir=signal_dir,
            validate_fn=validate_fn,
            position_overview_fn=position_overview_fn,
            update_position_fn=update_position_fn,
            manual_update_fn=manual_update_fn,
            delete_position_fn=delete_position_fn,
            manual_delete_fn=manual_delete_fn,
            rerun_fn=rerun_fn,
        )
    with validate_positions:
        _render_validate_positions(
            engine,
            positions_dir,
            candidates_fn=risk_candidates_fn,
            validate_positions_fn=validate_positions_fn,
        )


if __name__ == "__main__":
    render_backtest_page()
