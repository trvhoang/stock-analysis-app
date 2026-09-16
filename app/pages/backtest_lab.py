"""Schema-4 Streamlit Backtest Lab for exploratory gross rulebook evidence."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from math import isfinite
import re
import time
from datetime import date, datetime
from pathlib import Path
from collections.abc import Iterable, Mapping, Sequence
from typing import Callable

import pandas as pd
import pytz
import streamlit as st

from commons.price_utils import PRICE_OUTPUT_UI, prepare_price_for_output, price_from_ui_k_vnd
from commons.ui_controls import utility_icon_button
from backtest_engine.config import DEFAULT_SIGNAL_DIR, BacktestBatchConfig
from backtest_engine.flexible_adapter import collect_published_flexible_signals
from backtest_engine.job_runner import read_job_status, submit_backtest
from backtest_engine.listing_status import load_listing_statuses
from backtest_engine.manual_position_store import (
    build_v5_risk_snapshot,
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
    validate_open_position_batches,
)
from backtest_engine.result_store import (
    create_group,
    delete_group,
    list_groups,
    list_validation_group_choices,
    replace_group_tickers,
    resolve_group_tickers,
    update_group,
)
from backtest_engine.signal_catalog import list_current_signal_set_rows
from backtest_engine.signal_removal import (
    SignalCandidateKey,
    SignalRemovalBlockedError,
    remove_saved_signal_candidates,
)
from backtest_engine.validation_advice import validate_saved_signals
from flexible_rulebook.v2.service import published_library
from flexible_rulebook.v2.storage import resolve_v2_root


TIME_RANGE_OPTIONS = ("Lifetime", "5y", "15y", "Custom")
HORIZON_OPTIONS = ("swing", "midterm")
HORIZON_LABELS = {"swing": "Swing", "midterm": "Mid-term"}
COLLECT_HORIZON_OPTIONS = ("Both", *HORIZON_LABELS.values())
MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")
STATUS_REFRESH_SECONDS = 1
MATCH_CLASSIFICATION_OPTIONS = ("No Match", "Weak", "Nearly Match", "Closely Match")
MATCH_CLASSIFICATION_VALUES = {
    "No Match": "no_match", "Weak": "weak", "Nearly Match": "nearly_match", "Closely Match": "closely_match",
}
TREND_STATE_OPTIONS = ("Fresh", "On-going", "Weakening", "Invalidated")
TREND_STATE_VALUES = {
    "Fresh": "fresh",
    "On-going": "ongoing",
    "Weakening": "weakening",
    "Invalidated": "invalidated",
}
_TREND_STATE_FILTER_ALL = frozenset(TREND_STATE_VALUES.values())
POSITION_ACTION_OPTIONS = ("ALL", "can BUY", "expired BUY", "can SELL", "HOLD")
_RISK_LEVEL_CIRCLES = {"low": "🟢", "medium": "🟡", "high": "🟠", "very": "🔴"}
_RISK_LEVEL_LEGEND = " · ".join(
    f"{circle} {level.capitalize()}" for level, circle in _RISK_LEVEL_CIRCLES.items()
)
_POSITION_OVERVIEW_KEY = "backtest_position_overview_v4"
_POSITION_SELECTED_IDS_KEY = "backtest_position_selected_ids_v4"
_POSITION_SELECT_ALL_VISIBLE_KEY = "backtest_position_select_all_visible_v4"
_POSITION_DELETE_CONFIRMATION_KEY = "backtest_position_delete_confirmation_v4"
_POSITION_DELETE_BUSY_KEY = "backtest_position_delete_busy_v4"
_POSITION_EDITING_ID_KEY = "backtest_position_editing_id_v4"
_POSITION_FEEDBACK_KEY = "backtest_position_feedback_v4"
_POSITION_TICKER_FILTER_KEY = "backtest_position_ticker_filter_v4"
_VALIDATE_POSITION_SELECTED_IDS_KEY = "backtest_validate_position_selected_ids_v1"
_VALIDATE_POSITION_SELECT_ALL_KEY = "backtest_validate_position_select_all_v1"
_VALIDATE_POSITION_TABLE_GENERATION_KEY = "backtest_validate_position_table_generation_v1"
_VALIDATE_POSITION_RESULT_KEY = "backtest_validate_position_result_v1"
_VIEW_SIGNAL_TICKER_FILTER_KEY = "backtest_view_signal_ticker_filter_v4"
_VIEW_SIGNAL_HORIZON_FILTER_KEY = "backtest_view_signal_horizon_filter_v4"
_VIEW_SIGNAL_HORIZON_OPTIONS = ("Both", "Swing", "Mid-term")
_VIEW_SIGNAL_COLUMNS_KEY = "backtest_view_signal_columns_v4"
_VIEW_SIGNAL_SELECTED_KEYS_KEY = "backtest_view_signal_selected_keys_v4"
_VIEW_SIGNAL_SELECT_ALL_VISIBLE_KEY = "backtest_view_signal_select_all_visible_v4"
_VIEW_SIGNAL_CATALOG_SIGNATURE_KEY = "backtest_view_signal_catalog_signature_v4"
_VIEW_SIGNAL_FEEDBACK_KEY = "backtest_view_signal_feedback_v4"
_VIEW_SIGNAL_RESET_SELECTION_KEY = "backtest_view_signal_reset_selection_v4"
_VIEW_SIGNAL_TABLE_GENERATION_KEY = "backtest_view_signal_table_generation_v4"
_VIEW_SIGNAL_PENDING_REMOVAL_KEY = "backtest_view_signal_pending_removal_v5"
_VIEW_SIGNAL_PAGE_SIZE_KEY = "backtest_view_signal_page_size_v5"
_VIEW_SIGNAL_PAGE_KEY = "backtest_view_signal_page_v5"
_VIEW_SIGNAL_PAGE_SIZE_OPTIONS = (50, 100, 150)
_NEW_POSITION_TICKER_KEY = "backtest_new_position_ticker_v4"
_NEW_POSITION_SAVED_SET_KEY = "backtest_position_saved_set_v4"
_NEW_POSITION_VALIDATION_KEY = "backtest_new_position_validation_v4"
_NEW_POSITION_VALIDATION_ERROR_KEY = "backtest_new_position_validation_error_v4"
_POSITION_CREATE_BUSY_KEY = "backtest_position_create_busy_v4"
_POSITION_CREATE_RESET_PENDING_KEY = "backtest_position_create_reset_pending_v4"
_NEW_POSITION_FORM_WIDGET_KEYS = (
    _NEW_POSITION_TICKER_KEY,
    "backtest_position_new_state_v4",
    _NEW_POSITION_SAVED_SET_KEY,
    "backtest_position_new_buy_v4",
    "backtest_position_new_buy_date_v4",
    "backtest_position_new_quantity_v4",
    "backtest_position_new_sell_v4",
    "backtest_position_new_sell_date_v4",
)
_COLLECT_GROUP_KEY = "backtest_collect_group_v4"
_COLLECT_SOURCE_KEY = "backtest_collect_source_v1"
_COLLECT_FLEXIBLE_RESULTS_KEY = "backtest_collect_flexible_results_v1"
BACKTEST_RULEBOOK_SOURCE_OPTIONS = ("Standard", "Flexible")
BACKTEST_RULEBOOK_SOURCE_DEFAULT = "Standard"
_COLLECT_NEW_GROUP_OPTION = "New group…"
_COLLECT_ALL_GROUP_OPTION = "ALL"
_COLLECT_GROUP_DRAFT_KEY = "backtest_collect_group_draft_v4"
_COLLECT_GROUP_TICKER_REFRESH_KEY = "backtest_collect_group_ticker_refresh_v4"
_GROUP_MANAGER_FEEDBACK_KEY = "backtest_group_manager_feedback_v1"
_GROUP_MANAGER_DELETE_CONFIRMATION_KEY = "backtest_group_manager_delete_confirmation_v1"
# ponytail: queue state stays session-local; add a durable parent job only if interrupted batch continuation becomes required.
_COLLECT_QUEUE_KEY = "backtest_collect_queue_v5"
_COLLECT_TERMINAL_STATES = {"done", "failed", "requires_regeneration"}
_BACKTEST_TAB_KEY = "backtest_lab_tab_v1"
_BACKTEST_PREVIOUS_TAB_KEY = "backtest_lab_previous_tab_v1"
_BACKTEST_COLLECT_TAB = "Collect Signals"
_BACKTEST_VALIDATE_TAB = "Validate Signals"
_VALIDATE_TRAIN_PROFIT_FILTER_KEY = "backtest_validate_train_profit_filter_v5"
_VALIDATE_TEST_PROFIT_FILTER_KEY = "backtest_validate_test_profit_filter_v5"
_VALIDATE_WIN_RATE_SORT_KEY = "backtest_validate_win_rate_sort_v2"
_VALIDATE_RESULT_TICKER_FILTER_KEY = "backtest_validate_result_ticker_v1"
_VALIDATE_WIN_RATE_SORT_OPTIONS = ("None", "Training DESC", "Test DESC")
_PROFIT_FILTER_LABELS = {
    "all": "All",
    "potential": "Potential (5% - 15%)",
    "profitable": "Profitable (>15% - 30%)",
    "attractive": "Attractive (>30% - 50%)",
    "outstanding": "Outstanding (>50%)",
}


def _reset_collect_tab_state() -> None:
    """Restore Collect inputs and terminal output after leaving its tab."""

    st.session_state[_COLLECT_GROUP_KEY] = "N/A"
    st.session_state[_COLLECT_SOURCE_KEY] = "Standard"
    st.session_state["backtest_collect_tickers_v4"] = ""
    st.session_state.pop("backtest_collect_new_group_v4", None)
    st.session_state.pop(_COLLECT_GROUP_DRAFT_KEY, None)
    st.session_state.pop(_COLLECT_FLEXIBLE_RESULTS_KEY, None)
    st.session_state.pop("backtest_collect_group_add_v4", None)
    for key in tuple(st.session_state):
        if str(key).startswith("backtest_collect_group_tickers_v4_"):
            st.session_state.pop(key, None)

    queue = st.session_state.get(_COLLECT_QUEUE_KEY)
    if not isinstance(queue, Mapping) or bool(queue.get("complete")):
        st.session_state.pop(_COLLECT_QUEUE_KEY, None)


def _reset_validate_tab_state() -> None:
    """Restore Validate inputs and discard its displayed cached result."""

    st.session_state["backtest_validate_group_v4"] = "-"
    st.session_state["backtest_validate_tickers_v4"] = ""
    for key in tuple(st.session_state):
        if str(key).startswith("backtest_validate_group_tickers_v4_"):
            st.session_state.pop(key, None)
    st.session_state.pop("backtest_v4_validation_result", None)
    st.session_state.pop(_VALIDATE_RESULT_TICKER_FILTER_KEY, None)


def _reset_backtest_tab_state_on_change() -> None:
    """Reset only the input/result state belonging to the tab being left."""

    current = st.session_state.get(_BACKTEST_TAB_KEY)
    previous = st.session_state.get(_BACKTEST_PREVIOUS_TAB_KEY)
    if current == previous:
        return
    if previous == _BACKTEST_COLLECT_TAB:
        _reset_collect_tab_state()
    elif previous == _BACKTEST_VALIDATE_TAB:
        _reset_validate_tab_state()
    st.session_state[_BACKTEST_PREVIOUS_TAB_KEY] = current


def _preset_dates(time_range: str) -> tuple[date | None, date | None]:
    if time_range in {"Custom", "Lifetime"}:
        return None, None
    end = datetime.now(MARKET_TIMEZONE).date()
    return (pd.Timestamp(end) - pd.DateOffset(years=int(time_range[:-1]))).date(), end


def parse_batch_tickers(value: str, maximum: int = 15) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(token.upper() for token in re.split(r"[\s,]+", value.strip()) if token))
    if not 1 <= len(values) <= maximum:
        raise ValueError(f"Tickers must contain between 1 and {maximum} values.")
    return values


def _parse_group_members(value: str) -> tuple[str, ...]:
    """Normalize an optional Group member list without a Backtest batch limit."""

    if not isinstance(value, str):
        raise ValueError("Group tickers must be text")
    return tuple(dict.fromkeys(
        token.upper() for token in re.split(r"[\s,]+", value.strip()) if token
    ))


def _group_manager_rows(
    groups: Sequence[object],
    statuses: Mapping[str, object],
) -> list[dict[str, str]]:
    """Project mutable Group metadata with non-persistent live ticker status."""

    rows: list[dict[str, str]] = []
    for group in groups:
        name = str(getattr(group, "group_name", "")).strip().upper()
        members = tuple(getattr(group, "tickers", ()))
        if not members:
            rows.append({
                "Group": name,
                "Ticker": "—",
                "Status": "—",
                "Ticker latest": "—",
                "VN-Index latest": "—",
            })
            continue
        for ticker in members:
            normalized = str(ticker).strip().upper()
            status = statuses.get(normalized)
            ticker_latest = getattr(status, "ticker_latest", None)
            vnindex_latest = getattr(status, "vnindex_latest", None)
            state = getattr(status, "state", None)
            rows.append({
                "Group": name,
                "Ticker": normalized,
                "Status": (
                    "Listed" if state == "listed" else "Delisted"
                    if state == "delisted" else "Unavailable"
                ),
                "Ticker latest": "—" if ticker_latest is None else ticker_latest.isoformat(),
                "VN-Index latest": "—" if vnindex_latest is None else vnindex_latest.isoformat(),
            })
    return rows


def _filter_group_manager_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    ticker: str,
    states: Sequence[str],
    group_name: str,
) -> list[dict[str, str]]:
    """Filter the Group Manager projection only; stored groups stay untouched."""

    target_ticker = str(ticker).strip().upper()
    selected_states = set(states)
    selected_group = str(group_name).strip().upper()
    return [
        dict(row)
        for row in rows
        if (not target_ticker or target_ticker in row["Ticker"])
        and (row["Status"] not in {"Listed", "Delisted"} or row["Status"] in selected_states)
        and (selected_group == "ALL" or row["Group"] == selected_group)
    ]


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


def _listed_validation_tickers(
    tickers: tuple[str, ...],
    engine,
    listing_statuses_fn: Callable = load_listing_statuses,
) -> tuple[str, ...]:
    """Keep Delisted tickers outside the validation run and its progress total."""

    try:
        statuses = listing_statuses_fn(tickers, engine)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise ValueError(f"Listing status unavailable: {error}") from error
    listed = []
    for ticker in tickers:
        status = statuses.get(ticker) if isinstance(statuses, Mapping) else None
        if status is None:
            raise ValueError(f"Listing status unavailable for {ticker}.")
        if bool(getattr(status, "is_listed", False)):
            listed.append(ticker)
    return tuple(listed)


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
        use_lifetime_range=time_range == "Lifetime",
        group_name=group_name,
    )


def _collect_batch_configs(
    tickers: tuple[str, ...], horizons: str | tuple[str, ...], time_range: str, group_name: str,
) -> tuple[BacktestBatchConfig, ...]:
    """Split selected group members into bounded, ordered worker requests."""

    persisted_group = "N/A" if group_name == _COLLECT_ALL_GROUP_OPTION else group_name
    selected_horizons = (horizons,) if isinstance(horizons, str) else tuple(horizons)
    if not selected_horizons or any(horizon not in HORIZON_OPTIONS for horizon in selected_horizons):
        raise ValueError("A valid horizon is required.")
    return tuple(
        build_backtest_batch_config(chunk, horizon, time_range, group_name=persisted_group)
        for horizon in selected_horizons
        for chunk in _ticker_chunks(tickers)
    )


def _new_collect_queue(configs: tuple[BacktestBatchConfig, ...]) -> dict[str, object]:
    if not configs:
        raise ValueError("Selected Ticker group has no tickers.")
    return {
        "configs": configs,
        "next_index": 0,
        "completed_batches": 0,
        "job_id": None,
        "output_paths": (),
        "errors": (),
        "complete": False,
    }


def _advance_collect_queue(
    queue: Mapping[str, object], status: object | None, submit_fn: Callable,
    engine_factory, status_dir: str,
) -> dict[str, object]:
    """Record one terminal batch then submit exactly one later batch, if any."""

    updated = dict(queue)
    configs = tuple(updated["configs"])
    if status is not None:
        state = getattr(status, "state", None)
        if state not in _COLLECT_TERMINAL_STATES:
            return updated
        updated["completed_batches"] = int(updated["completed_batches"]) + 1
        updated["job_id"] = None
        updated["output_paths"] = tuple(dict.fromkeys((
            *tuple(updated["output_paths"]), *tuple(getattr(status, "output_paths", ())),
        )))
        if state != "done":
            reason = getattr(status, "error_text", None) or state
            updated["errors"] = (*tuple(updated["errors"]), (
                f"Batch {updated['completed_batches']}/{len(configs)} {state}: {reason}"
            ))

    while updated["job_id"] is None and int(updated["next_index"]) < len(configs):
        index = int(updated["next_index"])
        updated["next_index"] = index + 1
        try:
            job_id = submit_fn(configs[index], engine_factory, status_dir)
            if not isinstance(job_id, str) or not job_id:
                raise ValueError("Backtest submission returned no job id.")
        except (OSError, ValueError) as error:
            updated["completed_batches"] = int(updated["completed_batches"]) + 1
            updated["errors"] = (*tuple(updated["errors"]), (
                f"Batch {index + 1}/{len(configs)} failed to queue: {error}"
            ))
        else:
            updated["job_id"] = job_id

    updated["complete"] = updated["job_id"] is None and int(updated["next_index"]) == len(configs)
    return updated


def _collect_queue_progress(queue: Mapping[str, object], status: object) -> float:
    """Return aggregate progress across finished and current serial batches."""

    configs = tuple(queue["configs"])
    return min(1.0, (
        int(queue["completed_batches"]) + float(getattr(status, "progress", 0.0))
    ) / len(configs))


def schedule_status_refresh(is_busy: bool, sleep_fn: Callable = time.sleep, rerun_fn: Callable = st.rerun) -> None:
    if is_busy:
        sleep_fn(STATUS_REFRESH_SECONDS)
        rerun_fn()


def format_job_status(status) -> str:
    if status.state == "requires_regeneration":
        return "Requires regeneration — 100%"
    return f"{status.state.title()} — {round(float(status.progress) * 100)}%"


def format_ticker_result(status) -> str:
    """Render a terminal ticker outcome without treating a deliberate skip as failure."""

    if status.state == "skipped":
        reason = status.error_texts[-1] if status.error_texts else "ticker is Delisted"
        return f"{status.ticker}: skipped — {reason}"
    return f"{status.ticker}: {status.state}"


def _render_v5_artifact(path: str) -> None:
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
    *,
    engine=None,
    flexible_collect_fn: Callable = collect_published_flexible_signals,
    published_library_fn: Callable = published_library,
) -> None:
    try:
        named_groups = tuple(
            group for group in group_choices_fn(signal_dir)
            if group not in {"-", "N/A", _COLLECT_ALL_GROUP_OPTION}
        )
    except (OSError, ValueError) as error:
        named_groups = ()
        st.warning(f"Group choices are unavailable: {error}")
    group_options = (
        "N/A", _COLLECT_NEW_GROUP_OPTION, _COLLECT_ALL_GROUP_OPTION, *named_groups,
    )
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
        refreshes = st.session_state.get(_COLLECT_GROUP_TICKER_REFRESH_KEY, {})
        generation = refreshes.get(group_selection, 0) if isinstance(refreshes, dict) else 0
        ticker_key = f"backtest_collect_group_tickers_v4_{group_selection}"
        if isinstance(generation, int) and generation > 0:
            ticker_key = f"{ticker_key}_{generation}"
        tickers_text = collect_row[0].text_input(
            "Tickers",
            value=" ".join(resolved_tickers),
            disabled=True,
            key=ticker_key,
        )
    new_group_name = ""
    if group_selection == _COLLECT_NEW_GROUP_OPTION:
        new_group_name = collect_row[1].text_input(
            "New group name", key="backtest_collect_new_group_v4"
        )
    if group_selection in named_groups:
        draft = st.session_state.get(_COLLECT_GROUP_DRAFT_KEY)
        if not isinstance(draft, dict) or draft.get("group") != group_selection:
            st.session_state[_COLLECT_GROUP_DRAFT_KEY] = {
                "group": group_selection, "tickers": list(resolved_tickers)
            }

        def add_draft_ticker() -> None:
            added = st.session_state.get("backtest_collect_group_add_v4", "")
            if not isinstance(added, str) or not added.strip():
                return
            ticker = parse_batch_tickers(added, maximum=1)[0]
            current_draft = st.session_state[_COLLECT_GROUP_DRAFT_KEY]
            if ticker in current_draft["tickers"]:
                return
            current_draft["tickers"] = sorted(set(current_draft["tickers"]) | {ticker})
            st.session_state[_COLLECT_GROUP_DRAFT_KEY] = current_draft
            st.session_state["backtest_collect_group_add_v4"] = ""

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
            st.text_input("Add ticker", max_chars=3, key="backtest_collect_group_add_v4")
            add_column, save_column = st.columns(2)
            add_column.button(
                "Add", key="backtest_collect_group_add_button_v4", on_click=add_draft_ticker
            )
            if save_column.button("Save Group", key="backtest_collect_group_save_v4"):
                replace_group_tickers(group_selection, draft["tickers"], signal_dir)
                refreshes = st.session_state.get(_COLLECT_GROUP_TICKER_REFRESH_KEY, {})
                refreshes = dict(refreshes) if isinstance(refreshes, dict) else {}
                refreshes[group_selection] = int(refreshes.get(group_selection, 0)) + 1
                st.session_state[_COLLECT_GROUP_TICKER_REFRESH_KEY] = refreshes
                st.session_state.pop(_COLLECT_GROUP_DRAFT_KEY, None)
                st.rerun()
    source_column, horizon_column, range_column, action_column = st.columns(4)
    source = source_column.selectbox(
        "Source", BACKTEST_RULEBOOK_SOURCE_OPTIONS,
        index=BACKTEST_RULEBOOK_SOURCE_OPTIONS.index(BACKTEST_RULEBOOK_SOURCE_DEFAULT),
        key=_COLLECT_SOURCE_KEY,
    )
    horizon_label = horizon_column.selectbox(
        "Horizon", COLLECT_HORIZON_OPTIONS, key="backtest_collect_horizon_v4"
    )
    horizons = (
        HORIZON_OPTIONS
        if horizon_label == "Both"
        else (next(key for key, label in HORIZON_LABELS.items() if label == horizon_label),)
    )
    time_range = range_column.selectbox(
        "Range", TIME_RANGE_OPTIONS, index=0, key="backtest_collect_range_v4"
    )
    selected_flexible = ()
    if source == "Flexible":
        try:
            available_flexible = tuple(
                (rulebook, short_id)
                for rulebook, short_id in published_library_fn(resolve_v2_root())
                if rulebook.definition.horizon in horizons
            )
        except (OSError, ValueError) as error:
            available_flexible = ()
            st.warning(f"Flexible rulebooks are unavailable: {error}")
        labels = {
            f"Flexible · {short_id} — {HORIZON_LABELS[rulebook.definition.horizon]}": rulebook
            for rulebook, short_id in available_flexible
        }
        selected_labels = st.multiselect(
            "Flexible rulebooks",
            tuple(labels),
            key="backtest_collect_flexible_rulebooks_v1",
            placeholder="Select one or more published rulebooks",
        )
        selected_flexible = tuple(labels[label] for label in selected_labels)
        st.caption("Flexible runs are exploratory — gross and use the published immutable definition.")
    else:
        st.caption("Exploratory — gross. Every run evaluates no-theme and VN-Index AND treatments.")
    existing_queue = st.session_state.get(_COLLECT_QUEUE_KEY)
    collect_busy = isinstance(existing_queue, Mapping) and not bool(existing_queue.get("complete"))
    if action_column.button(
        "Run Backtest", key="backtest_collect_submit_v4", disabled=collect_busy,
    ):
        try:
            if resolution_error is not None:
                raise resolution_error
            if group_selection == _COLLECT_NEW_GROUP_OPTION:
                group_name = new_group_name.strip().upper()
                if not group_name or group_name == "N/A":
                    raise ValueError("New group name is required.")
                if group_name == _COLLECT_ALL_GROUP_OPTION:
                    raise ValueError("ALL is reserved for the virtual Group selector.")
                if group_name in named_groups:
                    raise ValueError("Group already exists; select it from Group.")
            else:
                group_name = group_selection
            tickers = (
                resolved_tickers
                if group_selection not in {"N/A", _COLLECT_NEW_GROUP_OPTION}
                else parse_batch_tickers(tickers_text)
            )
            if source == "Flexible":
                if engine is None:
                    raise ValueError("Database engine is not configured for Flexible collection.")
                if not selected_flexible:
                    raise ValueError("Select at least one published Flexible rulebook.")
                progress = st.progress(0.0, text="Collecting Flexible signals…")
                outcomes = []
                chunks = _ticker_chunks(tickers)
                for index, chunk in enumerate(chunks, start=1):
                    start_date, end_date = _preset_dates(time_range)
                    outcomes.extend(flexible_collect_fn(
                        selected_flexible,
                        tickers=chunk,
                        signal_dir=signal_dir,
                        start_date=start_date if time_range != "Custom" else None,
                        end_date=end_date if time_range != "Custom" else None,
                        engine=engine,
                    ))
                    progress.progress(index / len(chunks), text=f"Collected Flexible batch {index}/{len(chunks)}")
                st.session_state.pop(_COLLECT_QUEUE_KEY, None)
                st.session_state[_COLLECT_FLEXIBLE_RESULTS_KEY] = tuple(outcomes)
            else:
                if engine_factory is None:
                    raise ValueError("Backtest engine factory is not configured.")
                queue = _new_collect_queue(
                    _collect_batch_configs(tickers, horizons, time_range, group_name)
                )
                st.session_state.pop("backtest_v4_job", None)
                st.session_state[_COLLECT_QUEUE_KEY] = _advance_collect_queue(
                    queue, None, submit_fn, engine_factory, status_dir
                )
        except (OSError, ValueError) as error:
            st.error(str(error))
    flexible_outcomes = st.session_state.get(_COLLECT_FLEXIBLE_RESULTS_KEY)
    if isinstance(flexible_outcomes, tuple):
        for outcome in flexible_outcomes:
            terminal_state = getattr(outcome, "terminal_state", "failed")
            ticker = getattr(outcome, "ticker", "?")
            rulebook_id = getattr(outcome, "rulebook_id", "?")
            if terminal_state == "completed":
                st.success(f"{ticker}: Flexible · {rulebook_id[5:13].upper()} collected.")
            else:
                st.error(f"{ticker}: Flexible · {rulebook_id[5:13].upper()} — {terminal_state}: {getattr(outcome, 'message', '')}")
        return
    queue = st.session_state.get(_COLLECT_QUEUE_KEY)
    if not isinstance(queue, Mapping):
        return
    job_id = queue.get("job_id")
    if not isinstance(job_id, str):
        for error in tuple(queue.get("errors", ())):
            st.error(str(error))
        return
    try:
        status = read_status_fn(job_id, status_dir)
    except (OSError, ValueError, KeyError) as error:
        st.error(f"Unable to read Backtest status: {error}")
        return
    batch_count = len(tuple(queue["configs"]))
    current_batch = int(queue["completed_batches"]) + 1
    st.progress(
        _collect_queue_progress(queue, status),
        text=f"Backtesting batch {current_batch}/{batch_count}: {format_job_status(status)}",
    )
    output_paths = tuple(dict.fromkeys((
        *tuple(queue["output_paths"]), *tuple(status.output_paths),
    )))
    if output_paths:
        result_columns = st.columns(4)
        for index, path in enumerate(output_paths):
            with result_columns[index % 4]:
                _render_v5_artifact(path)
    for ticker_result in tuple(getattr(status, "ticker_results", ())):
        if ticker_result.state == "skipped":
            st.info(format_ticker_result(ticker_result))
    if status.state in _COLLECT_TERMINAL_STATES:
        queue = _advance_collect_queue(
            queue, status, submit_fn, engine_factory, status_dir
        )
        st.session_state[_COLLECT_QUEUE_KEY] = queue
    for error in tuple(queue["errors"]):
        st.error(str(error))
    if not queue["complete"]:
        schedule_refresh_fn(True)


def _preferred_profit_band(item: Mapping[str, object], partition: str) -> str | None:
    """Classify one preferred-treatment gross profit metric for cached filtering."""

    if partition not in ("training", "test"):
        raise ValueError("profit partition must be training or test")
    candidate = item.get("candidate")
    preferred = item.get("preferred_variant")
    treatments = candidate.get("treatments") if isinstance(candidate, Mapping) else None
    treatment = treatments.get(preferred) if isinstance(treatments, Mapping) else None
    metrics = treatment.get(partition) if isinstance(treatment, Mapping) else None
    value = metrics.get("profit_pct") if isinstance(metrics, Mapping) else None
    if isinstance(value, bool):
        return None
    try:
        profit_pct = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(profit_pct) or profit_pct < 5:
        return None
    if profit_pct <= 15:
        return "potential"
    if profit_pct <= 30:
        return "profitable"
    if profit_pct <= 50:
        return "attractive"
    return "outstanding"


def _preferred_win_rate(item: Mapping[str, object], partition: str) -> float | None:
    """Return one finite preferred-treatment win rate for display ordering."""

    if partition not in ("training", "test"):
        raise ValueError("win-rate partition must be training or test")
    candidate = item.get("candidate")
    preferred = item.get("preferred_variant")
    treatments = candidate.get("treatments") if isinstance(candidate, Mapping) else None
    treatment = treatments.get(preferred) if isinstance(treatments, Mapping) else None
    metrics = treatment.get(partition) if isinstance(treatment, Mapping) else None
    value = metrics.get("win_rate") if isinstance(metrics, Mapping) else None
    if isinstance(value, bool):
        return None
    try:
        win_rate = float(value)
    except (TypeError, ValueError):
        return None
    return win_rate if isfinite(win_rate) else None


def _validation_win_rate_sort_key(
    item: Mapping[str, object], partition: str
) -> tuple[float, str, str]:
    """Sort a displayed candidate by one preferred-treatment win-rate value."""

    win_rate = _preferred_win_rate(item, partition)
    return (
        -(win_rate if win_rate is not None else float("-inf")),
        str(item.get("rulebook_id", "")),
        str(item.get("preferred_variant", "")),
    )


def _profit_filter_matches(
    item: Mapping[str, object], partition: str, selected: object
) -> bool:
    selected = _canonical_profit_filter(selected)
    return selected == "all" or _preferred_profit_band(item, partition) == selected


def _canonical_profit_filter(selected: object) -> str:
    """Return a stable profit-filter key from current or stale widget state."""

    if not isinstance(selected, str):
        return "all"
    if selected in _PROFIT_FILTER_LABELS:
        return selected
    for key, label in _PROFIT_FILTER_LABELS.items():
        if selected == label or selected.startswith(f"{label} - "):
            return key
    return "all"


def _available_validation_items(
    items: Iterable[Mapping[str, object]],
    allowed: set[str],
    position_action: str,
    horizon_filter: str,
    allowed_trends: set[str] | None = None,
) -> list[Mapping[str, object]]:
    """Apply shared cached Validate Signals filters before profit filtering."""

    return [
        item
        for item in items
        if item.get("availability") == "available"
        and isinstance(item.get("monitoring"), Mapping)
        and item["monitoring"].get("match_classification") in allowed
        and (
            position_action == "ALL"
            or item.get("position_action", "expired BUY") == position_action
        )
        and (
            horizon_filter == "Both"
            or HORIZON_LABELS.get(item.get("horizon")) == horizon_filter
        )
        and _trend_filter_matches(item, allowed_trends)
    ]


def _available_validation_ticker_options(
    results_by_ticker: Mapping[str, object],
) -> tuple[str, ...]:
    """List only tickers with at least one available cached validation item."""

    available = sorted(
        str(ticker)
        for ticker, result in results_by_ticker.items()
        if isinstance(result, Mapping)
        and any(
            isinstance(item, Mapping) and item.get("availability") == "available"
            for item in result.get("results", ())
        )
    )
    return ("ALL", *available)


def _validation_item_trend(item: Mapping[str, object]) -> str | None:
    """Return the canonical progressive trend state from one replay result."""

    signal_state = item.get("signal_state")
    if not isinstance(signal_state, Mapping):
        return None
    state = signal_state.get("state")
    return state if state in TREND_STATE_VALUES.values() else None


def _position_action_filter_labels(
    items: Iterable[Mapping[str, object]],
) -> dict[str, str]:
    """Count valid cached candidates for each Position actions option."""

    candidates = list(items)
    counts = {action: 0 for action in POSITION_ACTION_OPTIONS if action != "ALL"}
    for item in candidates:
        action = item.get("position_action", "expired BUY")
        if action in counts:
            counts[action] += 1
    return {
        action: f"{action} - {len(candidates) if action == 'ALL' else counts[action]}"
        for action in POSITION_ACTION_OPTIONS
    }


def _trend_filter_matches(
    item: Mapping[str, object], allowed_trends: set[str] | None
) -> bool:
    """Keep legacy state-less results visible only for the default all-state view."""

    if allowed_trends is None:
        return True
    trend = _validation_item_trend(item)
    return trend in allowed_trends or (
        trend is None and allowed_trends == _TREND_STATE_FILTER_ALL
    )


def _profit_filter_labels(
    items: Iterable[Mapping[str, object]],
    *,
    partition: str,
    other_partition: str,
    other_filter: str,
) -> dict[str, str]:
    """Count current cached candidates while ignoring this control's selection."""

    candidates = [
        item
        for item in items
        if _profit_filter_matches(item, other_partition, other_filter)
    ]
    counts = {key: 0 for key in _PROFIT_FILTER_LABELS if key != "all"}
    for item in candidates:
        band = _preferred_profit_band(item, partition)
        if band is not None:
            counts[band] += 1
    return {
        key: f"{label} - {len(candidates) if key == 'all' else counts[key]}"
        for key, label in _PROFIT_FILTER_LABELS.items()
    }


def _render_validation_candidate(
    ticker: str,
    item: Mapping[str, object],
) -> None:
    """Render one already-filtered candidate without changing its advice."""

    rulebook_id = item["rulebook_id"]
    flexible = item.get("origin") == "flexible" or (
        isinstance(rulebook_id, str) and rulebook_id.startswith("frb2_")
    )
    rulebook_label = (
        f"Flexible · FR-{rulebook_id[5:13].upper()}"
        if flexible and isinstance(rulebook_id, str)
        else rulebook_id
    )
    label = f"{ticker} — {rulebook_label} — {item['preferred_variant']}"
    with st.expander(label):
        monitoring = item.get("monitoring")
        action = item.get("position_action", "expired BUY")
        signal_state = item.get("signal_state")
        state_name = _display_signal_state(
            signal_state.get("state") if isinstance(signal_state, Mapping) else None
        )
        signal_date = _display_signal_date(item.get("signal_date"))
        win_rates = (
            item.get("win_rate") if isinstance(item.get("win_rate"), Mapping) else {}
        )
        st.write(
            f"Monitoring: {monitoring['match_level']}% - "
            f"{monitoring['match_classification'].replace('_', ' ')} | {action} | "
            f"trend: {state_name} | signal date: {signal_date} | win rate training / test: "
            f"{_display_win_rate(win_rates.get('training'))} / "
            f"{_display_win_rate(win_rates.get('test'))}"
        )
        labels = item.get("partition_labels", {})
        st.caption(
            f"{item['evaluation_label']} — "
            f"{labels.get('training', 'in-sample')} / "
            f"{labels.get('test', 'historical test — previously observed')}"
        )
        evidence = item.get("evidence_eligibility", {})
        st.caption(f"Evidence: {evidence.get('status', 'unavailable')}")
        if item.get("buy_block_reason") == "evidence_ineligible":
            st.warning("BUY is blocked: current evidence is ineligible.")
        elif item.get("buy_block_reason") == "open_position":
            st.caption("BUY is blocked: this saved rulebook already has an OPEN position.")
        elif item.get("buy_block_reason") == "signal_weakening":
            st.warning(f"BUY is blocked: signal is {state_name}.")
        st.json(
            {
                "audit_eligibility": item["audit_eligibility"],
                "evidence_eligibility": evidence,
                "current_gates": item["current"],
                "both_treatments": item["candidate"]["treatments"],
            },
            expanded=False,
        )


def _render_validation_result(
    ticker: str,
    result: Mapping[str, object],
    allowed: set[str],
    position_action: str = "ALL",
    horizon_filter: str = "Both",
    train_profit_filter: str = "all",
    test_profit_filter: str = "all",
    win_rate_partition: str | None = None,
    allowed_trends: set[str] | None = None,
) -> None:
    """Render one completed ticker validation without changing its advice."""

    if win_rate_partition not in (None, "training", "test"):
        raise ValueError("win-rate partition must be None, training, or test")

    unavailable_items = [
        item for item in result["results"]
        if item.get("availability") == "unavailable"
        and (
            horizon_filter == "Both"
            or HORIZON_LABELS.get(item.get("horizon")) == horizon_filter
        )
    ]
    visible_items = [
        item
        for item in _available_validation_items(
            result["results"], allowed, position_action, horizon_filter, allowed_trends
        )
        if _profit_filter_matches(item, "training", train_profit_filter)
        and _profit_filter_matches(item, "test", test_profit_filter)
    ]
    if win_rate_partition is not None:
        visible_items.sort(
            key=lambda item: _validation_win_rate_sort_key(item, win_rate_partition)
        )
    if not visible_items and not unavailable_items:
        return
    for item in unavailable_items:
        st.warning(
            f"{ticker}: Validation unavailable: "
            f"{item.get('reason', 'unknown reason')}"
        )
    for item in visible_items:
        _render_validation_candidate(ticker, item)
    if result["historical_positions"]:
        st.caption(
            f"{ticker}: Historical positions are P&L/manual-management history only."
        )


def _render_globally_sorted_validation_results(
    results_by_ticker: Mapping[str, object],
    allowed: set[str],
    position_action: str,
    horizon_filter: str,
    train_profit_filter: str,
    test_profit_filter: str,
    win_rate_partition: str,
    allowed_trends: set[str] | None = None,
) -> None:
    """Render a globally ranked, already-cached candidate list across tickers."""

    if win_rate_partition not in ("training", "test"):
        raise ValueError("global win-rate partition must be training or test")

    ranked_items: list[tuple[str, Mapping[str, object]]] = []
    for ticker, result in results_by_ticker.items():
        if not isinstance(result, Mapping):
            continue
        result_items = result.get("results", ())
        ranked_items.extend(
            (str(ticker), item)
            for item in _available_validation_items(
                result_items, allowed, position_action, horizon_filter, allowed_trends
            )
            if _profit_filter_matches(item, "training", train_profit_filter)
            and _profit_filter_matches(item, "test", test_profit_filter)
        )
        for item in result_items:
            if isinstance(item, Mapping) and (
                item.get("availability") == "unavailable"
                and (
                    horizon_filter == "Both"
                    or HORIZON_LABELS.get(item.get("horizon")) == horizon_filter
                )
            ):
                st.warning(
                    f"{ticker}: Validation unavailable: "
                    f"{item.get('reason', 'unknown reason')}"
                )

    ranked_items.sort(
        key=lambda entry: (
            *_validation_win_rate_sort_key(entry[1], win_rate_partition),
            entry[0],
        )
    )
    for ticker, item in ranked_items:
        _render_validation_candidate(ticker, item)

    for ticker, result in results_by_ticker.items():
        if isinstance(result, Mapping) and result.get("historical_positions"):
            st.caption(
                f"{ticker}: Historical positions are P&L/manual-management history only."
            )


def _render_validate(
    engine,
    signal_dir: str,
    positions_dir: str,
    validate_fn,
    group_choices_fn: Callable,
    group_resolver_fn: Callable,
    listing_statuses_fn: Callable = load_listing_statuses,
) -> None:
    group_key = "backtest_validate_group_v4"
    validate_row = st.columns((3, 2, 0.6))
    resolved_tickers: tuple[str, ...] = ()
    resolution_error: ValueError | OSError | None = None
    try:
        group_choices = group_choices_fn(signal_dir)
    except (OSError, ValueError) as error:
        group_choices = ("-",)
        resolution_error = error
    group_name = validate_row[1].selectbox(
        "Ticker group", group_choices, key=group_key, width="stretch"
    )
    if group_name != "-":
        try:
            resolved_tickers = _validation_tickers(
                "", group_name, signal_dir, group_resolver_fn
            )
        except (OSError, ValueError) as error:
            resolution_error = error
    if group_name == "-":
        tickers_text = validate_row[0].text_input(
            "Tickers", key="backtest_validate_tickers_v4"
        )
    else:
        tickers_text = validate_row[0].text_input(
            "Tickers",
            value=" ".join(resolved_tickers),
            disabled=True,
            key=f"backtest_validate_group_tickers_v4_{group_name}",
        )
    validate_clicked = validate_row[2].button(
        "Validate", key="backtest_validate_submit_v4", width="stretch"
    )

    latest = st.session_state.get("backtest_v4_validation_result")
    selected = st.session_state.get(
        "backtest_validate_match_classifications_v4",
        list(MATCH_CLASSIFICATION_OPTIONS),
    )
    allowed = {MATCH_CLASSIFICATION_VALUES[name] for name in selected}
    selected_trends = st.session_state.get(
        "backtest_validate_trend_states_v1",
        list(TREND_STATE_OPTIONS),
    )
    allowed_trends = {
        TREND_STATE_VALUES[name]
        for name in selected_trends
        if name in TREND_STATE_VALUES
    }
    position_action = st.session_state.get(
        "backtest_validate_position_action_v4", "ALL"
    )
    horizon_filter = st.session_state.get("backtest_validate_horizon_v5", "Both")
    cached_by_ticker = (
        latest.get("by_ticker", {}) if isinstance(latest, Mapping) else {}
    )
    ticker_options = _available_validation_ticker_options(cached_by_ticker)
    selected_ticker = st.session_state.get(_VALIDATE_RESULT_TICKER_FILTER_KEY, "ALL")
    if selected_ticker not in ticker_options:
        selected_ticker = "ALL"
        st.session_state[_VALIDATE_RESULT_TICKER_FILTER_KEY] = selected_ticker
    displayed_results_by_ticker = (
        cached_by_ticker
        if selected_ticker == "ALL"
        else {selected_ticker: cached_by_ticker[selected_ticker]}
    )
    all_items = [
        item
        for result in displayed_results_by_ticker.values()
        if isinstance(result, Mapping)
        for item in result.get("results", ())
        if isinstance(item, Mapping)
    ]
    has_available_results = len(ticker_options) > 1
    base_items = _available_validation_items(
        all_items, allowed, position_action, horizon_filter, allowed_trends
    )
    stored_train_profit_filter = st.session_state.get(
        _VALIDATE_TRAIN_PROFIT_FILTER_KEY, "all"
    )
    stored_test_profit_filter = st.session_state.get(
        _VALIDATE_TEST_PROFIT_FILTER_KEY, "all"
    )
    train_profit_filter = _canonical_profit_filter(stored_train_profit_filter)
    test_profit_filter = _canonical_profit_filter(stored_test_profit_filter)
    if train_profit_filter != stored_train_profit_filter:
        st.session_state[_VALIDATE_TRAIN_PROFIT_FILTER_KEY] = train_profit_filter
    if test_profit_filter != stored_test_profit_filter:
        st.session_state[_VALIDATE_TEST_PROFIT_FILTER_KEY] = test_profit_filter
    action_count_items = [
        item
        for item in _available_validation_items(
            all_items, allowed, "ALL", horizon_filter, allowed_trends
        )
        if _profit_filter_matches(item, "training", train_profit_filter)
        and _profit_filter_matches(item, "test", test_profit_filter)
    ]
    action_labels = _position_action_filter_labels(action_count_items)
    train_labels = _profit_filter_labels(
        base_items,
        partition="training",
        other_partition="test",
        other_filter=test_profit_filter,
    )
    test_labels = _profit_filter_labels(
        base_items,
        partition="test",
        other_partition="training",
        other_filter=train_profit_filter,
    )

    filters = st.columns((0.75, 1.25, 1.7, 0.75, 1.6, 1.6, 1.6, 1))
    with filters[0]:
        st.caption("Class")
        with st.popover(
            ":material/filter_list:",
            help="Filter Monitoring classifications",
            key="backtest_validate_match_filter_v5",
            type="tertiary",
            disabled=not has_available_results,
        ):
            selected = st.pills(
                "Class",
                MATCH_CLASSIFICATION_OPTIONS,
                selection_mode="multi",
                default=list(MATCH_CLASSIFICATION_OPTIONS),
                key="backtest_validate_match_classifications_v4",
                label_visibility="collapsed",
                disabled=not has_available_results,
            )
    win_rate_sort = filters[1].selectbox(
        "Win rate",
        _VALIDATE_WIN_RATE_SORT_OPTIONS,
        key=_VALIDATE_WIN_RATE_SORT_KEY,
        disabled=not has_available_results,
    )
    position_action = filters[2].selectbox(
        "Position actions",
        tuple(action_labels),
        format_func=action_labels.__getitem__,
        key="backtest_validate_position_action_v4",
        disabled=not has_available_results,
    )
    with filters[3]:
        st.caption("Trend")
        with st.popover(
            ":material/filter_list:",
            help="Filter progressive trend states",
            key="backtest_validate_trend_filter_v1",
            type="tertiary",
            disabled=not has_available_results,
        ):
            selected_trends = st.pills(
                "Trend",
                TREND_STATE_OPTIONS,
                selection_mode="multi",
                default=list(TREND_STATE_OPTIONS),
                key="backtest_validate_trend_states_v1",
                label_visibility="collapsed",
                disabled=not has_available_results,
            )
    horizon_filter = filters[4].selectbox(
        "Horizon",
        _VIEW_SIGNAL_HORIZON_OPTIONS,
        key="backtest_validate_horizon_v5",
        disabled=not has_available_results,
    )
    train_profit_filter = filters[5].selectbox(
        "Train Profit %",
        tuple(train_labels),
        format_func=train_labels.__getitem__,
        key=_VALIDATE_TRAIN_PROFIT_FILTER_KEY,
        disabled=not has_available_results,
    )
    test_profit_filter = filters[6].selectbox(
        "Test Profit %",
        tuple(test_labels),
        format_func=test_labels.__getitem__,
        key=_VALIDATE_TEST_PROFIT_FILTER_KEY,
        disabled=not has_available_results,
    )
    selected_ticker = filters[7].selectbox(
        "Ticker",
        ticker_options,
        key=_VALIDATE_RESULT_TICKER_FILTER_KEY,
        disabled=not has_available_results,
    )
    if resolution_error is not None:
        st.error(str(resolution_error))
    if validate_clicked:
        try:
            tickers = _validation_tickers(
                tickers_text, group_name, signal_dir, group_resolver_fn
            )
            tickers = _listed_validation_tickers(
                tickers, engine, listing_statuses_fn
            )
        except (OSError, ValueError) as error:
            st.error(str(error))
            return
        if not tickers:
            st.info("No Listed tickers are available for validation.")
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
            # Keep a partial-batch error visible; otherwise rerun once so cached
            # profit-count labels reflect the newly saved successful results.
            if not batch["errors"]:
                st.rerun()

    latest = st.session_state.get("backtest_v4_validation_result")
    if not isinstance(latest, Mapping) or not latest.get("by_ticker"):
        return
    allowed = {MATCH_CLASSIFICATION_VALUES[name] for name in selected}
    allowed_trends = {
        TREND_STATE_VALUES[name]
        for name in selected_trends
        if name in TREND_STATE_VALUES
    }
    win_rate_partition = {
        "None": None,
        "Training DESC": "training",
        "Test DESC": "test",
    }[win_rate_sort]
    if win_rate_partition is not None:
        _render_globally_sorted_validation_results(
            displayed_results_by_ticker,
            allowed,
            position_action,
            horizon_filter,
            train_profit_filter,
            test_profit_filter,
            win_rate_partition,
            allowed_trends,
        )
        return
    for ticker, result in displayed_results_by_ticker.items():
        if isinstance(result, Mapping):
            _render_validation_result(
                ticker,
                result,
                allowed,
                position_action,
                horizon_filter,
                train_profit_filter,
                test_profit_filter,
                win_rate_partition,
                allowed_trends,
            )


_VIEW_SIGNAL_FIXED_COLUMNS = ("No", "Select", "Ticker")
_VIEW_SIGNAL_OPTIONAL_COLUMNS = (
    "Horizon",
    "Train-test",
    "n",
    "Win rate %",
    "Profit %",
    "Sharpe",
    "Evidence",
    "Theme",
)
_VIEW_SIGNAL_DEFAULT_COLUMNS = _VIEW_SIGNAL_OPTIONAL_COLUMNS[:-2]


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
        ticker = row.get("Ticker")
        horizon_label = row.get("Horizon")
        rulebook_id = row.get("_rulebook_id", row.get("Rulebook"))
        if (
            not isinstance(ticker, str) or not ticker
            or horizon_label not in ("Swing", "Mid-term")
            or not isinstance(rulebook_id, str) or not rulebook_id
        ):
            raise ValueError("catalog View Signals row has an invalid immutable identity")

        def paired(metric: str, decimals: int | None = None) -> str:
            return (
                f"{_view_metric(row.get('Training ' + metric), decimals)} - "
                f"{_view_metric(row.get('Test ' + metric), decimals)}"
            )

        output.append(
            {
                "Ticker": ticker,
                "Horizon": horizon_label,
                "Evidence": row.get("Evidence", "unavailable"),
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
                "_ticker": ticker,
                "_horizon": "swing" if horizon_label == "Swing" else "midterm",
                "_rulebook_id": rulebook_id,
            }
        )
    return output


def _parse_view_signal_tickers(value: str) -> tuple[str, ...]:
    """Normalize exact View Signals ticker-filter tokens without a batch limit."""

    if not isinstance(value, str):
        raise ValueError("ticker filter must be text")
    tokens = [token.upper() for token in re.split(r"[\s,]+", value.strip()) if token]
    return tuple(dict.fromkeys(tokens))


def _view_signal_table_rows(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Add display-only visible ordinals and default unchecked selection."""

    return [
        {"No": index, "Select": False, **dict(row)}
        for index, row in enumerate(rows, start=1)
    ]


def _view_signal_key(row: Mapping[str, object]) -> SignalCandidateKey:
    """Return the private immutable candidate identity attached to one view row."""

    ticker, horizon, rulebook_id = (
        row.get("_ticker"), row.get("_horizon"), row.get("_rulebook_id"),
    )
    if (
        not isinstance(ticker, str) or not ticker
        or horizon not in HORIZON_OPTIONS
        or not isinstance(rulebook_id, str) or not rulebook_id
    ):
        raise ValueError("View Signals row has an invalid immutable identity")
    origin = row.get("_origin", "flexible" if rulebook_id.startswith("frb2_") else "standard")
    if origin not in {"standard", "flexible"}:
        raise ValueError("View Signals row has an invalid origin")
    return SignalCandidateKey(ticker, horizon, rulebook_id, origin)


def _view_selected_key_tuples(value: object) -> set[tuple[str, str, str]]:
    """Read only session-safe immutable selection tuples."""

    if not isinstance(value, (set, tuple, list)):
        return set()
    return {
        tuple(item)
        for item in value
        if isinstance(item, tuple) and len(item) == 3 and all(isinstance(part, str) for part in item)
    }


def _view_catalog_signature(rows: Iterable[Mapping[str, object]]) -> str:
    """Return a stable change detector for the full current catalog projection."""

    return json.dumps(list(rows), sort_keys=True, separators=(",", ":"), default=str)


def _view_signal_table_widget_key(
    visible_keys: tuple[tuple[str, str, str], ...],
    selected_keys: tuple[tuple[str, str, str], ...],
    visible_columns: tuple[str, ...],
    generation: int = 0,
) -> str:
    """Build a deterministic native-editor key for its immutable display context."""

    payload = json.dumps(
        {
            "visible_keys": visible_keys,
            "selected_keys": selected_keys,
            "visible_columns": visible_columns,
            "generation": generation,
        },
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"backtest_view_signal_table_v4_{digest}"


def _sync_view_signal_selection(
    catalog_signature: str,
    visible_keys: tuple[tuple[str, str, str], ...],
) -> tuple[set[tuple[str, str, str]], bool]:
    """Clear stale catalog/filter selection before View Signals widgets exist."""

    reset_requested = bool(st.session_state.pop(_VIEW_SIGNAL_RESET_SELECTION_KEY, False))
    catalog_changed = st.session_state.get(_VIEW_SIGNAL_CATALOG_SIGNATURE_KEY) != catalog_signature
    if reset_requested or catalog_changed:
        selected = set()
        st.session_state[_VIEW_SIGNAL_TABLE_GENERATION_KEY] = (
            int(st.session_state.get(_VIEW_SIGNAL_TABLE_GENERATION_KEY, 0)) + 1
        )
    else:
        selected = _view_selected_key_tuples(st.session_state.get(_VIEW_SIGNAL_SELECTED_KEYS_KEY))
        selected.intersection_update(visible_keys)
    st.session_state[_VIEW_SIGNAL_CATALOG_SIGNATURE_KEY] = catalog_signature
    st.session_state[_VIEW_SIGNAL_SELECTED_KEYS_KEY] = selected
    st.session_state[_VIEW_SIGNAL_SELECT_ALL_VISIBLE_KEY] = (
        bool(visible_keys) and selected == set(visible_keys)
    )
    return selected, reset_requested or catalog_changed


def _apply_view_select_all_visible(
    visible_keys: tuple[tuple[str, str, str], ...],
) -> None:
    """Synchronize the native header selection control with visible identities."""

    st.session_state[_VIEW_SIGNAL_SELECTED_KEYS_KEY] = (
        set(visible_keys)
        if st.session_state.get(_VIEW_SIGNAL_SELECT_ALL_VISIBLE_KEY, False)
        else set()
    )


def _view_feedback() -> None:
    feedback = st.session_state.pop(_VIEW_SIGNAL_FEEDBACK_KEY, None)
    if not isinstance(feedback, Mapping):
        return
    message = feedback.get("message")
    if not isinstance(message, str) or not message:
        return
    if feedback.get("level") == "success":
        st.success(message)
    else:
        st.error(message)


def _complete_view_signal_removal(
    pending: Sequence[SignalCandidateKey],
    *,
    signal_dir: str,
    positions_dir: str,
    remove_fn: Callable,
    rerun_fn: Callable,
) -> None:
    """Persist a user-confirmed removal while retaining the existing guard."""
    try:
        result = remove_fn(
            pending,
            signal_dir=signal_dir,
            positions_dir=positions_dir,
        )
    except SignalRemovalBlockedError as error:
        protected = "; ".join(
            f"{item.ticker} / {item.horizon} / {item.rulebook_id}"
            for item in error.protected
        )
        st.session_state[_VIEW_SIGNAL_FEEDBACK_KEY] = {
            "level": "error",
            "message": f"Removal blocked by saved position reference: {protected}",
        }
    except (OSError, TypeError, ValueError) as error:
        st.session_state[_VIEW_SIGNAL_FEEDBACK_KEY] = {
            "level": "error",
            "message": f"Unable to remove selected signals: {error}",
        }
    else:
        st.session_state[_VIEW_SIGNAL_FEEDBACK_KEY] = {
            "level": "success",
            "message": (
                f"Removed {len(result.removed)} selected signal(s). View refreshed; "
                "Top 3 may now show other stored candidates."
            ),
        }
        st.session_state[_VIEW_SIGNAL_SELECTED_KEYS_KEY] = set()
        st.session_state[_VIEW_SIGNAL_RESET_SELECTION_KEY] = True
    st.session_state.pop(_VIEW_SIGNAL_PENDING_REMOVAL_KEY, None)
    rerun_fn()


def _filter_view_signal_rows(
    rows: Iterable[Mapping[str, object]],
    ticker_filter: str,
    horizon_filter: str,
) -> list[dict[str, object]]:
    """Return projected View Signals rows matching both local UI filters."""

    tickers = set(_parse_view_signal_tickers(ticker_filter))
    return [
        dict(row)
        for row in rows
        if (not tickers or str(row.get("Ticker", "")).upper() in tickers)
        and (
            horizon_filter == "Both"
            or row.get("Horizon") == horizon_filter
        )
    ]


def _paginate_view_signal_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    page_size: int,
    requested_page: int,
) -> tuple[list[dict[str, object]], int, int]:
    """Return one bounded View Signals page and its one-based page metadata."""

    if page_size not in _VIEW_SIGNAL_PAGE_SIZE_OPTIONS:
        raise ValueError("View Signals page size is invalid")
    if isinstance(requested_page, bool) or not isinstance(requested_page, int):
        requested_page = 1
    page_count = (len(rows) + page_size - 1) // page_size
    if page_count == 0:
        return [], 0, 0
    page = min(max(requested_page, 1), page_count)
    start = (page - 1) * page_size
    return [dict(row) for row in rows[start:start + page_size]], page, page_count


def _render_view(
    signal_dir: str,
    positions_dir: str = "backtest-positions",
    *,
    remove_fn: Callable = remove_saved_signal_candidates,
    rerun_fn: Callable = st.rerun,
) -> None:
    _view_feedback()
    catalog = list_current_signal_set_rows(signal_dir)
    ticker_column, horizon_column, columns_column, page_size_column = st.columns(4)
    with ticker_column:
        ticker_filter = st.text_input(
            "Ticker",
            key=_VIEW_SIGNAL_TICKER_FILTER_KEY,
        )
    with horizon_column:
        horizon_filter = st.selectbox(
            "Horizon",
            _VIEW_SIGNAL_HORIZON_OPTIONS,
            key=_VIEW_SIGNAL_HORIZON_FILTER_KEY,
        )
    with columns_column:
        st.caption("Table")
        with st.popover(
            ":material/view_column:",
            help="Choose visible View Signals columns",
            key="backtest_view_signal_columns_v5",
            type="tertiary",
        ):
            selected_columns = st.pills(
                "Table",
                _VIEW_SIGNAL_OPTIONAL_COLUMNS,
                selection_mode="multi",
                default=_VIEW_SIGNAL_DEFAULT_COLUMNS,
                key=_VIEW_SIGNAL_COLUMNS_KEY,
                label_visibility="collapsed",
            )
    with page_size_column:
        page_size = st.selectbox(
            "Rows per page",
            _VIEW_SIGNAL_PAGE_SIZE_OPTIONS,
            key=_VIEW_SIGNAL_PAGE_SIZE_KEY,
        )
    projected_rows = _view_signal_rows(catalog["valid"])
    rows = _filter_view_signal_rows(
        projected_rows,
        ticker_filter,
        horizon_filter,
    )
    if rows:
        page_rows, page, page_count = _paginate_view_signal_rows(
            rows,
            page_size=page_size,
            requested_page=st.session_state.get(_VIEW_SIGNAL_PAGE_KEY, 1),
        )
        st.session_state[_VIEW_SIGNAL_PAGE_KEY] = page
        if page_count > 1:
            with st.container(horizontal=True, vertical_alignment="center", gap="xsmall"):
                if utility_icon_button(
                    "previous",
                    help="Previous View Signals page",
                    disabled=page == 1,
                    key="backtest_view_signal_previous_page_v5",
                ):
                    st.session_state[_VIEW_SIGNAL_PAGE_KEY] = page - 1
                    page_rows, page, page_count = _paginate_view_signal_rows(
                        rows, page_size=page_size, requested_page=page - 1,
                    )
                page_label = st.empty()
                if utility_icon_button(
                    "next",
                    help="Next View Signals page",
                    disabled=page == page_count,
                    key="backtest_view_signal_next_page_v5",
                ):
                    st.session_state[_VIEW_SIGNAL_PAGE_KEY] = page + 1
                    page_rows, page, page_count = _paginate_view_signal_rows(
                        rows, page_size=page_size, requested_page=page + 1,
                    )
                page_label.caption(f"Page {page} of {page_count} — {len(rows)} signals")
        table_rows = _view_signal_table_rows(page_rows)
        visible_keys = tuple(
            (key.ticker, key.horizon, key.rulebook_id)
            for key in (_view_signal_key(row) for row in table_rows)
        )
        selected, ignore_editor_selection = _sync_view_signal_selection(
            _view_catalog_signature(projected_rows), visible_keys,
        )
        for row, key in zip(table_rows, visible_keys, strict=True):
            row["Select"] = key in selected
        visible_columns = (*_VIEW_SIGNAL_FIXED_COLUMNS, *selected_columns)
        toolbar = st.empty()
        table_key = _view_signal_table_widget_key(
            visible_keys,
            tuple(sorted(selected)),
            visible_columns,
            int(st.session_state.get(_VIEW_SIGNAL_TABLE_GENERATION_KEY, 0)),
        )
        edited = st.data_editor(
            pd.DataFrame(table_rows).loc[:, visible_columns],
            hide_index=True,
            width="stretch",
            height=720,
            key=table_key,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select"),
                "No": st.column_config.NumberColumn("No", format="%d"),
            },
            disabled=[column for column in visible_columns if column != "Select"],
        )
        if ignore_editor_selection:
            selected = set()
        else:
            selected = {
                visible_keys[index]
                for index, record in enumerate(edited.to_dict("records"))
                if bool(record.get("Select"))
            }
        st.session_state[_VIEW_SIGNAL_SELECTED_KEYS_KEY] = selected
        st.session_state[_VIEW_SIGNAL_SELECT_ALL_VISIBLE_KEY] = (
            bool(visible_keys) and selected == set(visible_keys)
        )
        selected_keys = tuple(
            SignalCandidateKey(
                *key,
                origin="flexible" if key[2].startswith("frb2_") else "standard",
            )
            for key in visible_keys if key in selected
        )
        with toolbar.container():
            with st.container(
                horizontal=True,
                vertical_alignment="center",
                gap="xsmall",
            ):
                st.checkbox(
                    "Select all visible",
                    key=_VIEW_SIGNAL_SELECT_ALL_VISIBLE_KEY,
                    on_change=_apply_view_select_all_visible,
                    args=(visible_keys,),
                )
                remove_selected = utility_icon_button(
                    "remove",
                    help=f"Remove selected signals ({len(selected_keys)})",
                    disabled=not selected_keys,
                    key="backtest_view_signal_remove_v5",
                )
        if remove_selected:
            st.session_state[_VIEW_SIGNAL_PENDING_REMOVAL_KEY] = tuple(selected_keys)
    else:
        utility_icon_button(
            "remove",
            help="Remove selected signals (0)",
            disabled=True,
            key="backtest_view_signal_remove_v5",
        )

    pending = st.session_state.get(_VIEW_SIGNAL_PENDING_REMOVAL_KEY)
    if (
        isinstance(pending, tuple)
        and pending
        and all(isinstance(item, SignalCandidateKey) for item in pending)
    ):
        @st.dialog("Remove selected signals?")
        def confirm_view_signal_removal() -> None:
            st.warning(
                "This removes selected candidate evidence. Referenced position evidence is protected."
            )
            cancel, confirm = st.columns(2)
            if cancel.button("Cancel", key="backtest_view_signal_remove_cancel_v5"):
                st.session_state.pop(_VIEW_SIGNAL_PENDING_REMOVAL_KEY, None)
                rerun_fn()
            if confirm.button(
                "Remove selected signals",
                icon=":material/delete:",
                type="primary",
                key="backtest_view_signal_remove_confirm_v5",
            ):
                _complete_view_signal_removal(
                    pending,
                    signal_dir=signal_dir,
                    positions_dir=positions_dir,
                    remove_fn=remove_fn,
                    rerun_fn=rerun_fn,
                )

        confirm_view_signal_removal()
    elif pending is not None:
        st.session_state.pop(_VIEW_SIGNAL_PENDING_REMOVAL_KEY, None)
    for warning in catalog["warnings"]:
        st.warning(warning)


def _position_horizon(position: dict[str, object]) -> str | None:
    reference = position.get("signal_reference")
    if isinstance(reference, dict) and reference.get("schema_version") in {5, 6}:
        horizon = reference.get("horizon")
        return str(horizon) if horizon in HORIZON_LABELS else None
    return None


def _saved_set_label(position: dict[str, object]) -> str:
    reference = position.get("signal_reference")
    horizon = _position_horizon(position)
    if (
        isinstance(reference, dict)
        and reference.get("schema_version") == 6
        and reference.get("origin") == "flexible"
        and horizon
    ):
        rulebook_id = reference.get("rulebook_id")
        short_id = (
            f"FR-{rulebook_id[5:13].upper()}"
            if isinstance(rulebook_id, str) and rulebook_id.startswith("frb2_")
            else "FR-UNKNOWN"
        )
        return f"{HORIZON_LABELS[horizon]} — Flexible · {short_id}"
    if isinstance(reference, dict) and reference.get("schema_version") == 5 and horizon:
        return f"{HORIZON_LABELS[horizon]} — {reference['rulebook_id']} — {reference['preferred_variant']}"
    return "Historical saved set" if horizon is None else f"Historical saved set — {HORIZON_LABELS[horizon]}"


def _validation_rulebook_label(item: Mapping[str, object]) -> str:
    """Show a short Flexible identity while retaining the full ID backstage."""

    rulebook_id = item.get("rulebook_id")
    if isinstance(rulebook_id, str) and (
        item.get("origin") == "flexible" or rulebook_id.startswith("frb2_")
    ):
        return f"Flexible · FR-{rulebook_id[5:13].upper()}"
    return str(rulebook_id)


def _display_position_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{
        "Ticker": row["ticker"], "State": row["status"], "Saved signal set": _saved_set_label(row["position"]),
        "BUY (k VND)": prepare_price_for_output(row["actual_buy_price"], PRICE_OUTPUT_UI),
        "SELL (k VND)": None if row["actual_sell_price"] is None else prepare_price_for_output(row["actual_sell_price"], PRICE_OUTPUT_UI),
        "P&L (%)": row["profit_pct"], "Holding sessions": row["holding_sessions"],
    } for row in rows]


def _validated_v5_candidates(validation: object, ticker: str) -> dict[str, dict[str, object]]:
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
        candidates[
            f"{HORIZON_LABELS[horizon]} — {_validation_rulebook_label(item)} — {item['preferred_variant']}"
        ] = item
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


def _signal_date_iso(value: object) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed).date().isoformat()


def _display_signal_date(value: object) -> str:
    signal_date = _signal_date_iso(value)
    return "—" if signal_date is None else pd.Timestamp(signal_date).strftime("%d/%m/%Y")


def _ineligible_saved_signal_set_message(
    ticker: str, validation: Mapping[str, object]
) -> str:
    """Explain ineligible saved sets with one signal-date line per set."""

    results = validation.get("results", ())
    items = tuple(item for item in results if isinstance(item, Mapping))
    blocked_reasons = sorted({
        str(item.get("buy_block_reason")).replace("_", " ")
        for item in items if item.get("buy_block_reason")
    })
    detail = f" ({', '.join(blocked_reasons)})" if blocked_reasons else ""
    summary = f"{ticker}: saved signal sets found, but none are BUY-eligible{detail}."
    if len(items) <= 1:
        item = items[0] if items else {}
        return f"{summary} - signal date: {_display_signal_date(item.get('signal_date'))}"
    lines = []
    for index, item in enumerate(items, start=1):
        horizon = item.get("horizon")
        rulebook_id = _validation_rulebook_label(item)
        preferred_variant = item.get("preferred_variant")
        if (
            isinstance(horizon, str)
            and horizon in HORIZON_LABELS
            and isinstance(rulebook_id, str)
            and isinstance(preferred_variant, str)
        ):
            label = (
                f"{HORIZON_LABELS[horizon]} — {rulebook_id} — {preferred_variant}"
            )
        else:
            label = f"Saved signal set {index}"
        lines.append(
            f"- {label} - signal date: {_display_signal_date(item.get('signal_date'))}"
        )
    return f"{summary}\n\n" + "\n".join(lines)


def _display_signal_state(value: object) -> str:
    """Render the ephemeral signal state without exposing its internal token."""

    labels = {
        "fresh": "Fresh",
        "ongoing": "On-going",
        "weakening": "Weakening",
        "invalidated": "Invalidated",
    }
    return labels.get(str(value), "Unavailable")


def _display_win_rate(value: object) -> str:
    try:
        numeric = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    if not numeric.is_finite():
        return "—"
    return f"{numeric.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%"


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
    listing_guard: Callable[[str], None] | None = None,
) -> None:
    if listing_guard is not None:
        listing_guard(ticker)
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
    entry_context = {
        "match_level": monitoring["match_level"],
        "current_price": _raw_current_value(current["latest_close"], "current latest_close"),
        "as_of_date": current["as_of_date"],
    }
    signal_date = _signal_date_iso(item.get("signal_date"))
    if signal_date is not None:
        entry_context["signal_date"] = signal_date
    reference = item["signal_reference"]
    is_flexible = (
        isinstance(reference, Mapping)
        and reference.get("schema_version") == 6
        and reference.get("origin") == "flexible"
    )
    create_manual_position(
        ticker, buy_price, buy_date, quantity=quantity or None, signal_reference=reference,
        entry_context=entry_context,
        risk_snapshot=None if is_flexible else build_v5_risk_snapshot(
            item["horizon"], current["latest_atr"], buy_price,
        ),
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


def _require_listed_ticker(
    ticker: str,
    engine,
    *,
    listing_statuses_fn: Callable = load_listing_statuses,
) -> None:
    """Block a new position when its current source session is stale."""

    normalized = str(ticker).strip().upper()
    try:
        listing = listing_statuses_fn((normalized,), engine)[normalized]
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        raise ValueError(f"Listing status unavailable: {error}") from error
    if not listing.is_listed:
        raise ValueError(listing.reason)


def _mark_position_create_busy() -> None:
    st.session_state[_POSITION_CREATE_BUSY_KEY] = True


def _mark_position_delete_busy() -> None:
    st.session_state[_POSITION_DELETE_BUSY_KEY] = True


def _reset_new_position_form() -> None:
    for widget_key in _NEW_POSITION_FORM_WIDGET_KEYS:
        st.session_state.pop(widget_key, None)
    st.session_state.pop(_NEW_POSITION_VALIDATION_KEY, None)
    st.session_state.pop(_NEW_POSITION_VALIDATION_ERROR_KEY, None)


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
        if (
            ticker in ("", "ALL")
            or str(row.get("ticker", "")).upper() == ticker
        )
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


def _available_position_ticker_options(
    rows: Iterable[Mapping[str, object]],
) -> tuple[str, ...]:
    """List only ticker codes represented by the loaded position overview."""

    tickers = sorted(
        {
            str(row.get("ticker", "")).strip().upper()
            for row in rows
            if str(row.get("ticker", "")).strip()
        }
    )
    return ("ALL", *tickers)


def _display_price(value: object) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    try:
        displayed = prepare_price_for_output(value, PRICE_OUTPUT_UI)
        return "-" if pd.isna(displayed) else displayed
    except (TypeError, ValueError):
        return "-"


def _position_signal_set_display(value: object) -> str:
    """Keep v5 rulebook and treatment readable in the static position table."""

    label = str(value) if value not in (None, "") else "-"
    parts = label.split(" — ", maxsplit=2)
    if len(parts) != 3:
        return label
    theme = {
        "background-theme": "Included",
        "no-background-theme": "Excluded",
    }.get(parts[2])
    return label if theme is None else f"{parts[1]}\nTheme: {theme}"


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

    signal_set = _position_signal_set_display(buy.get("signal_set"))
    profit_pct = buy.get("profit_pct")
    profit_pct = "-" if profit_pct is None else f"{float(profit_pct):.2f}%"
    return pd.DataFrame(
        [
            {
                "Trade": "BUY",
                "Price": display_text(_display_price(buy.get("actual_buy_price"))),
                "Date": display_text(buy.get("buy_date")),
                "Volume": display_text(buy.get("quantity")),
                "Saved signal set": signal_set,
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


def _validate_position_table_key() -> str:
    generation = int(st.session_state.get(_VALIDATE_POSITION_TABLE_GENERATION_KEY, 0))
    return f"backtest_validate_positions_table_{generation}"


def _sync_validate_position_selection(visible_ids: tuple[str, ...]) -> set[str]:
    selected = st.session_state.get(_VALIDATE_POSITION_SELECTED_IDS_KEY, set())
    selected = set(selected) if isinstance(selected, (set, tuple, list)) else set()
    selected = _pruned_selection(selected, visible_ids)
    st.session_state[_VALIDATE_POSITION_SELECTED_IDS_KEY] = selected
    st.session_state[_VALIDATE_POSITION_SELECT_ALL_KEY] = (
        bool(visible_ids) and selected == set(visible_ids)
    )
    return selected


def _apply_validate_position_select_all(visible_ids: tuple[str, ...]) -> None:
    selected = set(st.session_state.get(_VALIDATE_POSITION_SELECTED_IDS_KEY, set()))
    if st.session_state.get(_VALIDATE_POSITION_SELECT_ALL_KEY, False):
        selected.update(visible_ids)
    else:
        selected.difference_update(visible_ids)
    st.session_state[_VALIDATE_POSITION_SELECTED_IDS_KEY] = selected
    st.session_state[_VALIDATE_POSITION_TABLE_GENERATION_KEY] = (
        int(st.session_state.get(_VALIDATE_POSITION_TABLE_GENERATION_KEY, 0)) + 1
    )


def _apply_validate_position_table_selection(
    table_key: str,
    visible_ids: tuple[str, ...],
) -> None:
    """Persist just changed table checkboxes before the next widget render."""

    widget_state = st.session_state.get(table_key, {})
    edits = widget_state.get("edited_rows", {}) if isinstance(widget_state, Mapping) else {}
    if not isinstance(edits, Mapping):
        edits = {}
    selected = set(st.session_state.get(_VALIDATE_POSITION_SELECTED_IDS_KEY, set()))
    for row_index, values in edits.items():
        try:
            position_id = visible_ids[int(row_index)]
        except (IndexError, TypeError, ValueError):
            continue
        if isinstance(values, Mapping) and "Select" in values:
            if bool(values["Select"]):
                selected.add(position_id)
            else:
                selected.discard(position_id)
    selected = _pruned_selection(selected, visible_ids)
    st.session_state[_VALIDATE_POSITION_SELECTED_IDS_KEY] = selected
    st.session_state[_VALIDATE_POSITION_SELECT_ALL_KEY] = (
        bool(visible_ids) and selected == set(visible_ids)
    )


def _clear_validate_position_selection() -> None:
    """Reset table selection through a new widget generation after a completed run."""

    st.session_state[_VALIDATE_POSITION_SELECTED_IDS_KEY] = set()
    st.session_state[_VALIDATE_POSITION_TABLE_GENERATION_KEY] = (
        int(st.session_state.get(_VALIDATE_POSITION_TABLE_GENERATION_KEY, 0)) + 1
    )


def _validate_position_risk_display(value: object) -> object:
    """Render persisted native-horizon risk text in the Validate Positions table."""

    if not isinstance(value, str):
        return value
    rendered = []
    for line in value.splitlines():
        match = re.fullmatch(r"(Swing|Mid-term): (.+) - (low|medium|high|very)", line)
        rendered.append(
            f"{match.group(1)}: {match.group(2)} - "
            f"{_RISK_LEVEL_CIRCLES[match.group(3)]} {match.group(3).capitalize()}"
            if match is not None
            else line
        )
    return " | ".join(rendered)


def _validate_position_profit_pct_display(value: object) -> str:
    """Format only finite validation P&L percentages for the result table."""

    if isinstance(value, bool):
        return "-"
    try:
        profit_pct = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{profit_pct:.2f}%" if isfinite(profit_pct) else "-"


def _validate_position_profit_display(value: object) -> str:
    """Format validation P&L in k VND without altering its raw snapshot."""

    displayed = _display_price(value)
    if isinstance(displayed, bool):
        return "-"
    try:
        profit = float(displayed)
    except (TypeError, ValueError):
        return "-"
    return f"{profit:.2f}" if isfinite(profit) else "-"


_VALIDATE_POSITION_TREND_STYLES = {
    "▲": "color: #22c55e",
    "▼": "color: #ef4444",
    "▶": "color: #eab308",
}


def _validate_position_trend(value: object) -> str:
    """Return the directional P&L triangle shown in the result table."""

    if isinstance(value, bool):
        return "-"
    try:
        profit = float(value)
    except (TypeError, ValueError):
        return "-"
    if not isfinite(profit):
        return "-"
    if profit > 0:
        return "▲"
    if profit < 0:
        return "▼"
    return "▶"


def _validate_position_result_styles(frame: pd.DataFrame) -> pd.DataFrame:
    """Color only the display-only directional triangle cells."""

    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    if "Trend" not in frame:
        return styles
    for triangle, style in _VALIDATE_POSITION_TREND_STYLES.items():
        styles.loc[frame["Trend"] == triangle, "Trend"] = style
    return styles


def _validate_position_result_rows(rows: Iterable[object]) -> list[dict[str, object]]:
    """Project immutable as-of P&L and risk output into the result table."""

    return [
        {
            "Ticker": row.get("ticker"),
            "Trend": _validate_position_trend(row.get("profit_raw")),
            "Profit %": _validate_position_profit_pct_display(row.get("profit_pct")),
            "Profit": _validate_position_profit_display(row.get("profit_raw")),
            "Risk": _validate_position_risk_display(row.get("risk_suggestion")),
            "Result": row.get("result"),
        }
        for row in rows if isinstance(row, Mapping)
    ]


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
    profit_pct = row.get("profit_pct")
    profit_label = "-" if profit_pct is None else f"{float(profit_pct):.2f}%"
    hold_time = row.get("holding_sessions")
    hold_time_label = "-" if hold_time is None else f"{hold_time} sessions"
    buy, sell = build_position_trade_rows(row)
    frame = _position_trade_display_frame(buy, sell)
    is_open = str(row.get("status", "")).lower() == "open"
    sell_label = (
        frame.loc[1, "SELL suggestion"]
        if is_open
        else _display_price(sell.get("actual_sell_price"))
    )
    label = (
        f"{row.get('ticker', '-')} — {str(row.get('status', '')).upper()} — "
        f"{profit_label} — {hold_time_label} — BUY: {frame.loc[0, 'Price']} — "
        f"SELL: {sell_label}"
    )
    with st.expander(label):
        styled = frame.style.apply(
            _position_trade_display_styles, buy=buy, axis=None
        )
        st.table(styled, width="content")
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
    listing_statuses_fn: Callable = load_listing_statuses,
) -> None:
    """Render live new-position controls above the Current Positions filters."""

    if st.session_state.pop(_POSITION_CREATE_RESET_PENDING_KEY, False):
        _reset_new_position_form()
    busy = bool(st.session_state.get(_POSITION_CREATE_BUSY_KEY))
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
        candidates = _validated_v5_candidates(validation_for_ticker, ticker)
        validation_error = st.session_state.get(_NEW_POSITION_VALIDATION_ERROR_KEY)
        if ticker and isinstance(validation_error, str):
            st.warning(f"Saved signal sets could not be refreshed: {validation_error}")
        elif ticker and validation_for_ticker is not None and not candidates:
            st.info(_ineligible_saved_signal_set_message(ticker, validation_for_ticker))
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
        if selected != "Manual P&L only":
            st.caption(f"Signal date: {_display_signal_date(candidates[selected].get('signal_date'))}")
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
        st.button(
            "Add Position",
            key="backtest_position_create_v4_submit",
            on_click=_mark_position_create_busy,
        )
        if not busy:
            return
        with st.spinner("Adding position…"):
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
                    listing_guard=lambda candidate_ticker: _require_listed_ticker(
                        candidate_ticker, engine,
                        listing_statuses_fn=listing_statuses_fn,
                    ),
                )
            except (KeyError, OSError, TypeError, ValueError) as error:
                st.session_state[_POSITION_CREATE_BUSY_KEY] = False
                st.session_state[_POSITION_FEEDBACK_KEY] = {
                    "level": "error", "message": f"Unable to add position: {error}"
                }
                rerun_fn()
                return
        st.session_state.pop(_POSITION_OVERVIEW_KEY, None)
        st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
        st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
        st.session_state[_POSITION_SELECTED_IDS_KEY] = set()
        st.session_state[_POSITION_CREATE_BUSY_KEY] = False
        st.session_state[_POSITION_CREATE_RESET_PENDING_KEY] = True
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
    listing_statuses_fn: Callable = load_listing_statuses,
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

    @st.dialog("Delete selected positions?")
    def confirm_position_delete() -> None:
        st.warning(
            "Permanently delete the selected positions?\n\n"
            + "\n".join(f"- {entry['summary']}" for entry in entries)
        )
        busy = bool(st.session_state.get(_POSITION_DELETE_BUSY_KEY))
        if busy:
            with st.spinner("Deleting selected positions…"):
                deleted, failed, error = _run_batch_delete(
                    entries,
                    positions_dir,
                    delete_position_fn,
                    manual_delete_fn,
                )
            st.session_state[_POSITION_DELETE_BUSY_KEY] = False
            st.session_state.pop(_POSITION_OVERVIEW_KEY, None)
            st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
            st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
            st.session_state[_POSITION_SELECTED_IDS_KEY] = set()
            st.session_state[_POSITION_FEEDBACK_KEY] = _batch_delete_feedback(
                deleted, entries, failed, error
            )
            rerun_fn()
            return
        confirm, cancel = st.columns(2)
        confirm.button(
            "Confirm permanent delete",
            key="backtest_position_confirm_delete_v4",
            on_click=_mark_position_delete_busy,
        )
        if cancel.button("Cancel", key="backtest_position_cancel_delete_v4"):
            st.session_state.pop(_POSITION_DELETE_CONFIRMATION_KEY, None)
            rerun_fn()

    confirm_position_delete()


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
    listing_statuses_fn: Callable = load_listing_statuses,
) -> None:
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

    ticker_options = _available_position_ticker_options(rows)
    if st.session_state.get(_POSITION_TICKER_FILTER_KEY, "ALL") not in ticker_options:
        st.session_state[_POSITION_TICKER_FILTER_KEY] = "ALL"

    _render_new_position_section(
        positions_dir, engine, signal_dir, validate_fn, rerun_fn, listing_statuses_fn
    )

    toolbar = st.columns(5)
    with toolbar[0]:
        ticker_filter = st.selectbox(
            "Ticker",
            ticker_options,
            key=_POSITION_TICKER_FILTER_KEY,
        )
    with toolbar[1]:
        st.caption("State")
        with st.popover(
            ":material/filter_list:",
            help="Filter Position state",
            key="backtest_position_state_filter_v5",
            type="tertiary",
        ):
            states = st.pills(
                "State",
                ("OPEN", "CLOSED"),
                selection_mode="multi",
                default=("OPEN",),
                key="backtest_position_states_v4",
                label_visibility="collapsed",
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
        if utility_icon_button(
            "refresh",
            help="Refresh positions",
            key="backtest_position_refresh_v4",
        ):
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
    selection_toolbar = st.empty()
    _sync_visible_position_selection(visible_ids)
    if st.session_state.get(_POSITION_EDITING_ID_KEY) not in visible_ids:
        st.session_state.pop(_POSITION_EDITING_ID_KEY, None)
    selected = set(st.session_state.get(_POSITION_SELECTED_IDS_KEY, set()))
    selected_ordered_ids = tuple(
        position_id for position_id in visible_ids if position_id in selected
    )
    with selection_toolbar.container(
        horizontal=True,
        vertical_alignment="center",
        gap="xsmall",
    ):
        st.checkbox(
            "Select all visible",
            key=_POSITION_SELECT_ALL_VISIBLE_KEY,
            on_change=_apply_select_all_visible,
            args=(visible_ids,),
        )
        delete_selected = utility_icon_button(
            "remove",
            help=f"Delete selected positions ({len(selected_ordered_ids)})",
            disabled=not selected_ordered_ids,
            key="backtest_position_delete_v4",
        )

    if delete_selected:
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
    validate_positions_fn: Callable = validate_open_position_batches,
) -> None:
    candidates = candidates_fn(positions_dir)
    if not candidates:
        st.info("No eligible OPEN positions.")
    can_load_current = candidates and hasattr(engine, "raw_connection")
    latest = load_latest_close_prices((item["ticker"] for item in candidates), engine) if can_load_current else {}
    sessions = load_completed_trading_sessions(
        (item["position"] for item in candidates), latest, engine
    ) if can_load_current else {}
    visible_ids = tuple(str(candidate["id"]) for candidate in candidates)
    selected = _sync_validate_position_selection(visible_ids)
    st.checkbox(
        "All",
        key=_VALIDATE_POSITION_SELECT_ALL_KEY,
        disabled=not visible_ids,
        on_change=_apply_validate_position_select_all,
        args=(visible_ids,),
    )
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
                "Select": candidate["id"] in selected,
                "Ticker": ticker,
                "BUY price (k VND)": _display_price(position.get("actual_buy_price")),
                "Volume": position.get("quantity") or "-",
                "Current price (k VND)": _display_price(current_price),
                "Hold time": holding if holding is not None else "-",
                "Evaluation": candidate["evaluation"],
                "_position_id": candidate["id"],
            }
        )
    table_key = _validate_position_table_key()
    edited = st.data_editor(
        pd.DataFrame(selection_rows),
        hide_index=True,
        width="stretch",
        key=table_key,
        on_change=_apply_validate_position_table_selection,
        args=(table_key, visible_ids),
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
    if st.button("Run validation", disabled=not selected_ids):
        progress = st.progress(0, text=f"Validating 0/{len(selected_ids)} positions")

        def update_progress(completed: int, total: int) -> None:
            batch = (completed + 4) // 5
            total_batches = (total + 4) // 5
            progress.progress(
                completed / total,
                text=f"Validated {completed}/{total} positions (batch {batch}/{total_batches})",
            )

        try:
            result = validate_positions_fn(
                selected_ids,
                engine,
                positions_dir,
                progress_fn=update_progress,
            )
        except (OSError, TypeError, ValueError) as error:
            progress.empty()
            st.error(f"Failed — assess failed. ({error})")
            return
        progress.progress(1.0, text=f"Validated {len(selected_ids)}/{len(selected_ids)} positions")
        time.sleep(3)
        progress.empty()
        st.session_state[_VALIDATE_POSITION_RESULT_KEY] = result
        _clear_validate_position_selection()
        st.rerun()
    result = st.session_state.pop(_VALIDATE_POSITION_RESULT_KEY, None)
    as_of = result.get("as_of_date") if isinstance(result, Mapping) else None
    if isinstance(as_of, str):
        as_of_value = pd.to_datetime(as_of, errors="coerce")
        if not pd.isna(as_of_value):
            st.subheader(f"As of: {as_of_value:%d/%m/%Y}")
    rows = result.get("results", ()) if isinstance(result, Mapping) else ()
    if rows:
        result_rows = _validate_position_result_rows(rows)
        result_frame = pd.DataFrame(result_rows)
        st.caption(_RISK_LEVEL_LEGEND)
        st.dataframe(
            result_frame.style.apply(_validate_position_result_styles, axis=None),
            width="stretch",
            hide_index=True,
        )
        if any(
            row.get("result") in ("Updated", "Unavailable — risk score missing/invalid.")
            for row in rows if isinstance(row, Mapping)
        ):
            st.session_state.pop(_POSITION_OVERVIEW_KEY, None)


def _render_group_manager(
    engine,
    signal_dir: str,
    *,
    rerun_fn: Callable,
    listing_statuses_fn: Callable = load_listing_statuses,
) -> None:
    """Manage named ticker Groups and show their live Listed/Delisted status."""

    feedback = st.session_state.pop(_GROUP_MANAGER_FEEDBACK_KEY, None)
    if isinstance(feedback, Mapping):
        level = str(feedback.get("level", "info"))
        message = str(feedback.get("message", ""))
        getattr(st, level if level in {"success", "error", "warning", "info"} else "info")(message)
    try:
        groups = list_groups(signal_dir)
    except (OSError, TypeError, ValueError) as error:
        st.error(f"Group metadata is unavailable: {error}")
        return

    members = tuple(sorted({ticker for group in groups for ticker in group.tickers}))
    try:
        statuses = listing_statuses_fn(members, engine) if members else {}
        status_error = None
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        statuses = {}
        status_error = str(error)
        st.warning(f"Live ticker status is unavailable: {status_error}")
    rows = _group_manager_rows(groups, statuses)
    filter_row = st.columns((1, 1, 1))
    with filter_row[0]:
        group_filter = st.selectbox(
            "Group name", ("ALL", *(group.group_name for group in groups)),
            key="backtest_group_manager_group_filter_v1",
        )
    with filter_row[1]:
        ticker_filter = st.text_input(
            "Ticker", key="backtest_group_manager_ticker_filter_v1",
        )
    with filter_row[2]:
        st.caption("Status")
        with st.popover(
            ":material/filter_list:",
            help="Filter live ticker status",
            key="backtest_group_manager_status_filter_v2",
            type="tertiary",
        ):
            status_filter = st.pills(
                "Status",
                ("Listed", "Delisted"),
                selection_mode="multi",
                default=("Listed", "Delisted"),
                key="backtest_group_manager_status_pills_v1",
                label_visibility="collapsed",
            )
    visible_rows = _filter_group_manager_rows(
        rows,
        ticker=ticker_filter,
        states=status_filter,
        group_name=group_filter,
    )
    if visible_rows:
        st.dataframe(pd.DataFrame(visible_rows), hide_index=True, width="stretch")
    elif groups:
        st.info("No Group members match the current filters.")
    else:
        st.info("No named Groups yet. Create one below.")

    create_column, edit_column = st.columns(2)
    with create_column:
        st.markdown("#### Create Group")
        with st.form("backtest_group_manager_create_v1", clear_on_submit=True):
            new_name = st.text_input("Group name", key="backtest_group_manager_create_name_v1")
            new_members = st.text_area(
                "Tickers", help="Optional; separate ticker codes with spaces or commas.",
                key="backtest_group_manager_create_members_v1",
            )
            create_submitted = st.form_submit_button("Create Group")
        if create_submitted:
            try:
                created = create_group(
                    new_name, _parse_group_members(new_members), signal_dir
                )
            except (OSError, TypeError, ValueError) as error:
                st.error(f"Unable to create Group: {error}")
            else:
                st.session_state[_GROUP_MANAGER_FEEDBACK_KEY] = {
                    "level": "success", "message": f"Group {created.group_name} created."
                }
                rerun_fn()

    with edit_column:
        st.markdown("#### Update Group")
        names = tuple(group.group_name for group in groups)
        if not names:
            st.caption("Create a Group before updating or deleting one.")
        else:
            selected_name = st.selectbox(
                "Group", names, key="backtest_group_manager_selected_v1",
            )
            selected_group = next(group for group in groups if group.group_name == selected_name)
            with st.form(f"backtest_group_manager_update_{selected_group.group_id}"):
                updated_name = st.text_input(
                    "Group name", value=selected_group.group_name,
                    key=f"backtest_group_manager_name_{selected_group.group_id}",
                )
                updated_members = st.text_area(
                    "Tickers", value=" ".join(selected_group.tickers),
                    key=f"backtest_group_manager_members_{selected_group.group_id}",
                    help="Optional; separate ticker codes with spaces or commas.",
                )
                save_submitted = st.form_submit_button("Save Group")
                delete_submitted = st.form_submit_button("Delete Group", type="secondary")
            if save_submitted:
                try:
                    updated = update_group(
                        selected_group.group_name,
                        updated_name,
                        _parse_group_members(updated_members),
                        signal_dir,
                    )
                except (OSError, TypeError, ValueError) as error:
                    st.error(f"Unable to save Group: {error}")
                else:
                    st.session_state[_GROUP_MANAGER_FEEDBACK_KEY] = {
                        "level": "success", "message": f"Group {updated.group_name} saved."
                    }
                    rerun_fn()
            if delete_submitted:
                st.session_state[_GROUP_MANAGER_DELETE_CONFIRMATION_KEY] = selected_group.group_name

    delete_name = st.session_state.get(_GROUP_MANAGER_DELETE_CONFIRMATION_KEY)
    if isinstance(delete_name, str):
        @st.dialog("Delete Group?")
        def confirm_group_delete() -> None:
            st.warning(
                f"Delete Group {delete_name}? Its ticker membership will be removed. "
                "Signals and positions will remain unchanged."
            )
            confirm, cancel = st.columns(2)
            if confirm.button("Confirm delete", key="backtest_group_manager_confirm_delete_v1"):
                try:
                    delete_group(delete_name, signal_dir)
                except (OSError, TypeError, ValueError) as error:
                    st.error(f"Unable to delete Group: {error}")
                    return
                st.session_state.pop(_GROUP_MANAGER_DELETE_CONFIRMATION_KEY, None)
                st.session_state[_GROUP_MANAGER_FEEDBACK_KEY] = {
                    "level": "success", "message": f"Group {delete_name} deleted."
                }
                rerun_fn()
            if cancel.button("Cancel", key="backtest_group_manager_cancel_delete_v1"):
                st.session_state.pop(_GROUP_MANAGER_DELETE_CONFIRMATION_KEY, None)
                rerun_fn()

        confirm_group_delete()


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
    validate_positions_fn: Callable = validate_open_position_batches,
    remove_signals_fn: Callable = remove_saved_signal_candidates,
    listing_statuses_fn: Callable = load_listing_statuses,
    rerun_fn: Callable = st.rerun,
    **_unused,
) -> None:
    """Render schema-5 exploratory collection, replay, and position history."""

    st.title("Backtest Lab")
    tab_labels = (
        _BACKTEST_COLLECT_TAB,
        "View Signals",
        _BACKTEST_VALIDATE_TAB,
        "Current Positions",
        "Validate Positions",
        "Group Manager",
    )
    collect, view_signals, validate, positions, validate_positions, group_manager = st.tabs(
        tab_labels,
        key=_BACKTEST_TAB_KEY,
        on_change=_reset_backtest_tab_state_on_change,
    )
    if _BACKTEST_PREVIOUS_TAB_KEY not in st.session_state:
        st.session_state[_BACKTEST_PREVIOUS_TAB_KEY] = st.session_state.get(
            _BACKTEST_TAB_KEY, tab_labels[0]
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
            engine=engine,
        )
    with view_signals:
        _render_view(
            signal_dir,
            positions_dir,
            remove_fn=remove_signals_fn,
            rerun_fn=rerun_fn,
        )
    with validate:
        _render_validate(
            engine,
            signal_dir,
            positions_dir,
            validate_fn,
            group_choices_fn,
            group_resolver_fn,
            listing_statuses_fn,
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
            listing_statuses_fn=listing_statuses_fn,
        )
    with validate_positions:
        _render_validate_positions(
            engine,
            positions_dir,
            candidates_fn=risk_candidates_fn,
            validate_positions_fn=validate_positions_fn,
        )
    with group_manager:
        _render_group_manager(
            engine,
            signal_dir,
            rerun_fn=rerun_fn,
            listing_statuses_fn=listing_statuses_fn,
        )


if __name__ == "__main__":
    render_backtest_page()
