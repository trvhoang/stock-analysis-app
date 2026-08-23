"""Boolean V3 rulebook-entry composition without compact score strategies."""

from itertools import combinations

import pandas as pd

from .config import ENTRY_GATE_NAMES, HORIZONS, rulebook_for
from .models import RulebookExecution


_MISSING_INPUT_COLUMN = "rulebook_missing_required_input"


def gate_subsets() -> tuple[tuple[str, ...], ...]:
    """Return all non-empty lexical gate subsets in deterministic order."""

    return tuple(
        subset
        for width in range(1, len(ENTRY_GATE_NAMES) + 1)
        for subset in combinations(ENTRY_GATE_NAMES, width)
    )


def generate_rulebook_executions(
    horizon: str,
) -> tuple[RulebookExecution, ...]:
    """Return both treatments for every non-empty rulebook gate subset."""

    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    rulebook = rulebook_for(horizon)
    return tuple(
        execution
        for selected_gates in gate_subsets()
        for execution in (
            RulebookExecution(rulebook, selected_gates),
            RulebookExecution(
                rulebook,
                selected_gates,
                theme_variant="background-theme",
                theme_mode="AND",
            ),
        )
    )


def rulebook_entry_signal(
    frame: pd.DataFrame,
    execution: RulebookExecution,
    theme_eligible: pd.Series | None = None,
) -> pd.Series:
    """Return causal V3 entries after every required Boolean gate passes."""

    if not isinstance(execution, RulebookExecution):
        raise ValueError("execution must be a RulebookExecution")
    if not isinstance(frame, pd.DataFrame):
        raise ValueError("frame must be a pandas DataFrame")
    required_columns = (*execution.selected_gates, _MISSING_INPUT_COLUMN)
    missing_columns = [column for column in required_columns if column not in frame]
    if missing_columns:
        return pd.Series(False, index=frame.index, dtype=bool)

    def gate(column: str) -> pd.Series:
        return frame[column].fillna(False).astype(bool)

    entry = ~gate(_MISSING_INPUT_COLUMN)
    for column in execution.selected_gates:
        entry &= gate(column)
    if execution.theme_variant == "no-background-theme":
        return entry.astype(bool)
    if theme_eligible is None:
        return pd.Series(False, index=frame.index, dtype=bool)
    themed = pd.Series(theme_eligible, index=frame.index).fillna(False).astype(bool)
    return (entry & themed).astype(bool)


__all__ = [
    "gate_subsets",
    "generate_rulebook_executions",
    "rulebook_entry_signal",
]
