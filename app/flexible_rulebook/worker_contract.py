"""Portable worker request contract shared by module and ``python -m`` entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_REF = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")


@dataclass(frozen=True)
class WorkerRequest:
    """Portable worker inputs; campaign semantics remain in its manifest."""

    campaign_id: str
    root: Path
    service_ref: str
    source_loader_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.campaign_id, str) or not re.fullmatch(
            r"fcmp_[0-9a-f]{64}", self.campaign_id
        ):
            raise ValueError("worker campaign_id is invalid")
        if not isinstance(self.root, Path) or not self.root.is_absolute():
            raise ValueError("worker root must be absolute")
        for name in ("service_ref", "source_loader_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _REF.fullmatch(value):
                raise ValueError(f"worker {name} must be a module:callable reference")

    def to_dict(self) -> dict[str, str]:
        return {
            "campaign_id": self.campaign_id,
            "root": str(self.root),
            "service_ref": self.service_ref,
            "source_loader_ref": self.source_loader_ref,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "WorkerRequest":
        if not isinstance(payload, dict) or set(payload) != {
            "campaign_id", "root", "service_ref", "source_loader_ref"
        }:
            raise ValueError("worker request schema is invalid")
        root = payload["root"]
        if not isinstance(root, str):
            raise ValueError("worker root must be text")
        return cls(
            campaign_id=payload["campaign_id"],
            root=Path(root),
            service_ref=payload["service_ref"],
            source_loader_ref=payload["source_loader_ref"],
        )


__all__ = ["WorkerRequest"]
