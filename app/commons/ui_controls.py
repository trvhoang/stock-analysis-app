"""Small presentation-only conventions shared by Streamlit pages."""

from __future__ import annotations

from typing import Literal

import streamlit as st


_UTILITY_ICONS = {
    "remove": ":material/delete:",
    "columns": ":material/view_column:",
    "refresh": ":material/refresh:",
    "clear_cache": ":material/delete_sweep:",
    "edit": ":material/edit:",
    "previous": ":material/chevron_left:",
    "next": ":material/chevron_right:",
}
_NOTICE_ICONS = {
    "info": ":material/info:",
    "success": ":material/check_circle:",
    "warning": ":material/warning:",
    "error": ":material/error:",
}


def utility_icon_button(
    action: str,
    *,
    help: str,
    key: str,
    disabled: bool = False,
) -> bool:
    """Render one compact, tooltip-labelled Material utility action."""

    if action not in _UTILITY_ICONS:
        raise ValueError("unknown utility action")
    if not isinstance(help, str) or not help.strip():
        raise ValueError("icon utility tooltip is required")
    return st.button(
        _UTILITY_ICONS[action],
        help=help,
        key=key,
        disabled=disabled,
        type="tertiary",
        width="content",
    )


def read_only_dataframe_kwargs(
    *,
    height: int | None = None,
    column_config: object | None = None,
) -> dict[str, object]:
    """Return the shared responsive options for read-only dataframes."""

    result: dict[str, object] = {"width": "stretch", "hide_index": True}
    if height is not None:
        result["height"] = height
    if column_config is not None:
        result["column_config"] = column_config
    return result


def show_transient_success(message: str) -> None:
    """Show a short-lived successful-action confirmation."""

    st.toast(message, icon=_NOTICE_ICONS["success"])


def show_operational_notice(
    level: Literal["info", "success", "warning", "error"],
    title: str,
    message: str,
) -> None:
    """Show a titled persistent workflow notice at the requested level."""

    if level not in _NOTICE_ICONS:
        raise ValueError("unknown notice level")
    getattr(st, level)(
        f"**{title}**\n\n{message}",
        icon=_NOTICE_ICONS[level],
    )
