"""Read-only VCB rulebook-gate research primitives."""

from dataclasses import dataclass
from itertools import combinations

import pandas as pd

from .config import HORIZONS, THEME_VARIANTS


_GATE_COLUMNS = (
    ("rsi_upcross", "rulebook_rsi_upcross"),
    ("joint_trend", "rulebook_joint_trend_pass"),
    ("volume", "rulebook_volume_gate"),
    ("adx", "rulebook_adx_gate"),
)
_GATE_NAMES = tuple(name for name, _column in _GATE_COLUMNS)
_GATE_COLUMN_BY_NAME = dict(_GATE_COLUMNS)
_MISSING_INPUT_COLUMN = "rulebook_missing_required_input"


@dataclass(frozen=True)
class ResearchCandidate:
    """One ordered V3-gate subset evaluated only by the research optimizer."""

    horizon: str
    theme_variant: str
    gates: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        if self.theme_variant not in THEME_VARIANTS:
            raise ValueError(f"theme_variant must be one of {THEME_VARIANTS}")
        gates = tuple(self.gates)
        canonical_gates = tuple(name for name in _GATE_NAMES if name in gates)
        if (
            not gates
            or len(gates) != len(set(gates))
            or gates != canonical_gates
        ):
            raise ValueError("gates must be a non-empty canonical unique selection")
        object.__setattr__(self, "gates", gates)

    @property
    def identity(self) -> str:
        """Return stable identity without changing any V3 execution identity."""

        return f"{self.horizon}:{self.theme_variant}:{'+'.join(self.gates)}"


def enumerate_candidates(horizon: str) -> tuple[ResearchCandidate, ...]:
    """Return all non-empty ordered gate subsets for both registered treatments."""

    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    candidates = []
    for length in range(1, len(_GATE_NAMES) + 1):
        for gates in combinations(_GATE_NAMES, length):
            candidates.extend(
                (
                    ResearchCandidate(horizon, "no-background-theme", gates),
                    ResearchCandidate(horizon, "background-theme", gates),
                )
            )
    return tuple(candidates)


def candidate_entry_signal(
    frame: pd.DataFrame,
    candidate: ResearchCandidate,
    theme_signal: pd.Series | None = None,
) -> pd.Series:
    """Return a missing-input-safe selected-gate signal with optional theme AND."""

    if not isinstance(frame, pd.DataFrame):
        raise ValueError("frame must be a pandas DataFrame")
    if not isinstance(candidate, ResearchCandidate):
        raise ValueError("candidate must be a ResearchCandidate")
    required_columns = (
        _MISSING_INPUT_COLUMN,
        *(_GATE_COLUMN_BY_NAME[gate] for gate in candidate.gates),
    )
    missing_columns = [column for column in required_columns if column not in frame]
    if missing_columns:
        raise ValueError(
            "frame missing required research columns: " + ", ".join(missing_columns)
        )

    entry = ~frame[_MISSING_INPUT_COLUMN].fillna(True).astype(bool)
    for gate in candidate.gates:
        entry &= frame[_GATE_COLUMN_BY_NAME[gate]].fillna(False).astype(bool)

    if candidate.theme_variant == "background-theme":
        if not isinstance(theme_signal, pd.Series):
            raise ValueError("background-theme candidate requires a theme Series")
        if not theme_signal.index.equals(frame.index):
            raise ValueError("theme Series index must exactly match frame index")
        entry &= theme_signal.fillna(False).astype(bool)

    return entry.fillna(False).astype(bool).rename(None)


__all__ = [
    "ResearchCandidate",
    "candidate_entry_signal",
    "enumerate_candidates",
]
