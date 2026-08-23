"""Atomic schema-4 persistence for exploratory V3 rulebook aggregates."""

import json
import math
import os
import tempfile
from collections.abc import Mapping
from datetime import date, datetime
from numbers import Real
from pathlib import Path

import pytz

from .config import HORIZONS, THEME_VARIANTS, _normalize_ticker, rulebook_for
from .data_quality import unavailable_v3_audit_eligibility
from .models import RulebookExecution


_SCHEMA_VERSION = 4
_TERMINAL_STATES = {"success", "empty", "failed", "requires_regeneration"}
_MARKET_TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")
_EVALUATION_LABEL = "Exploratory — gross"
_P_VALUE_NA_STATUS = "not_estimated_n_le_block_size"
_P_VALUE_INFORMATIONAL_STATUS = "informational"


def signal_artifact_path(ticker: str, horizon: str, output_dir: str) -> Path:
    """Return the one canonical schema-4 path for a ticker/horizon aggregate."""

    normalized_ticker = _normalize_ticker(ticker)
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    return Path(output_dir) / normalized_ticker / f"{normalized_ticker}_signals_{horizon}.json"


def _json_rulebook(horizon: str) -> dict[str, object]:
    """Normalize immutable dataclass tuples to their JSON shape."""

    return json.loads(json.dumps(rulebook_for(horizon).to_dict()))


def _finite_number(value: object, field: str, *, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number" + (" or null" if allow_none else ""))


def _validate_date_range(value: object, field: str) -> None:
    if not isinstance(value, Mapping) or set(value) != {"start", "end", "reason"}:
        raise ValueError(f"{field} must contain start, end, and reason")
    start, end, reason = value["start"], value["end"], value["reason"]
    if (start is None) != (end is None):
        raise ValueError(f"{field} start and end must be paired")
    if start is not None:
        if not isinstance(start, str) or not isinstance(end, str):
            raise ValueError(f"{field} dates must be ISO strings or null pairs")
        try:
            if date.fromisoformat(start) > date.fromisoformat(end):
                raise ValueError(f"{field} start must not exceed end")
        except ValueError as error:
            if str(error).endswith("must not exceed end"):
                raise
            raise ValueError(f"{field} dates must be ISO strings or null pairs") from error
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError(f"{field} reason must be a non-empty string or null")
    if start is not None and reason is not None:
        raise ValueError(f"{field} reason is only valid for unavailable date pairs")
    if start is None and reason is None:
        raise ValueError(f"{field} unavailable date pairs require a reason")


def _validate_split(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {"method", "train", "test"}:
        raise ValueError("split must contain method, train, and test")
    if value["method"] not in {"calendar_10y_5y", "chronological_65_35"}:
        raise ValueError("split method is invalid")
    partitions: list[tuple[date, date]] = []
    for key in ("train", "test"):
        item = value[key]
        if not isinstance(item, Mapping) or set(item) != {"start", "end"}:
            raise ValueError(f"split {key} must contain start and end")
        try:
            start, end = date.fromisoformat(item["start"]), date.fromisoformat(item["end"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"split {key} dates must be ISO strings") from error
        if start > end:
            raise ValueError(f"split {key} start must not exceed end")
        partitions.append((start, end))
    if partitions[0][1] >= partitions[1][0]:
        raise ValueError("split train must finish before test begins")


def _validate_audit(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("audit_eligibility must be an object")
    required = {
        "source", "eligible", "status", "reasons", "warnings", "effective_date_range"
    }
    if set(value) != required:
        raise ValueError("audit_eligibility has an invalid shape")
    source, status, eligible = value["source"], value["status"], value["eligible"]
    if source not in {"fresh_v3_raw_history", "unavailable"}:
        raise ValueError("audit_eligibility source is invalid")
    if not isinstance(eligible, bool):
        raise ValueError("audit_eligibility eligible must be boolean")
    if source == "fresh_v3_raw_history":
        if status not in {"clean", "indeterminate", "invalid"}:
            raise ValueError("audit_eligibility status is invalid")
        if eligible != (status == "clean"):
            raise ValueError("audit_eligibility eligible does not match status")
    elif status != "unavailable" or eligible:
        raise ValueError("unavailable audit metadata must be ineligible")
    for key in ("reasons", "warnings", "effective_date_range"):
        if not isinstance(value[key], list):
            raise ValueError(f"audit_eligibility {key} must be a list")
    if not all(isinstance(item, str) and item for item in value["reasons"]):
        raise ValueError("audit_eligibility reasons must contain text")
    if not all(isinstance(item, str) and item for item in value["warnings"]):
        raise ValueError("audit_eligibility warnings must contain text")
    bounds = value["effective_date_range"]
    if len(bounds) != 2 or (bounds[0] is None) != (bounds[1] is None):
        raise ValueError("audit_eligibility effective_date_range must be paired")
    if source == "unavailable" and (bounds != [None, None] or not value["reasons"]):
        raise ValueError("unavailable audit metadata requires null bounds and a reason")


def _validate_metrics(value: object, field: str) -> None:
    required = {"n", "win_rate", "profit_pct", "sharpe", "p_value", "p_value_status"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError(f"{field} has an invalid metric shape")
    n = value["n"]
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError(f"{field} n must be a non-negative integer")
    _finite_number(value["win_rate"], f"{field} win_rate")
    _finite_number(value["profit_pct"], f"{field} profit_pct")
    _finite_number(value["sharpe"], f"{field} sharpe", allow_none=True)
    if n < 2 and value["sharpe"] is not None:
        raise ValueError(f"{field} sharpe requires at least two completed exits")
    status, p_value = value["p_value_status"], value["p_value"]
    if n <= 20:
        if status != _P_VALUE_NA_STATUS or p_value is not None:
            raise ValueError(f"{field} p_value is N/A when n is at most block size")
    elif status != _P_VALUE_INFORMATIONAL_STATUS:
        raise ValueError(f"{field} p_value status must be informational above block size")
    elif isinstance(p_value, bool) or not isinstance(p_value, Real) or not 0 <= p_value <= 1:
        raise ValueError(f"{field} p_value must be between zero and one")


def _validate_treatment(value: object, key: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"treatment {key} must be an object")
    required = {"theme_variant", "theme_mode", "training", "test", "training_dsr", "dsr_status"}
    if set(value) != required or value["theme_variant"] != key:
        raise ValueError(f"treatment {key} has an invalid shape")
    expected_mode = "AND" if key == "background-theme" else None
    if key not in THEME_VARIANTS or value["theme_mode"] != expected_mode:
        raise ValueError(f"treatment {key} has an invalid theme mode")
    _validate_metrics(value["training"], f"treatment {key} training")
    _validate_metrics(value["test"], f"treatment {key} test")
    dsr, status = value["training_dsr"], value["dsr_status"]
    if status == "unavailable":
        if dsr is not None:
            raise ValueError(f"treatment {key} unavailable DSR must be null")
    elif status == "available":
        _finite_number(dsr, f"treatment {key} training_dsr")
    else:
        raise ValueError(f"treatment {key} dsr_status is invalid")


def _validate_candidate(value: object, horizon: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("candidate must be an object")
    required = {"rulebook_id", "selected_gates", "preferred_variant", "treatments"}
    if set(value) != required:
        raise ValueError("candidate has an invalid shape")
    gates = value["selected_gates"]
    if not isinstance(gates, list):
        raise ValueError("candidate selected_gates must be a list")
    try:
        no_theme = RulebookExecution(rulebook_for(horizon), tuple(gates))
        themed = RulebookExecution(rulebook_for(horizon), tuple(gates), "background-theme", "AND")
    except (TypeError, ValueError) as error:
        raise ValueError("candidate selected_gates are invalid") from error
    if value["rulebook_id"] != no_theme.rule_id:
        raise ValueError("candidate rulebook_id is invalid")
    treatments = value["treatments"]
    if not isinstance(treatments, Mapping) or set(treatments) != {"no-background-theme", "background-theme"}:
        raise ValueError("candidate requires both treatments")
    _validate_treatment(treatments["no-background-theme"], "no-background-theme")
    _validate_treatment(treatments["background-theme"], "background-theme")
    if treatments["no-background-theme"]["training"]["n"] < rulebook_for(horizon).min_n:
        raise ValueError("candidate no-theme training n is below the rulebook minimum")
    no_status = treatments["no-background-theme"]["dsr_status"]
    theme_status = treatments["background-theme"]["dsr_status"]
    if no_status != theme_status:
        raise ValueError("candidate treatment DSR availability must match")
    preferred = value["preferred_variant"]
    if preferred not in {"no-background-theme", "background-theme"}:
        raise ValueError("candidate preferred_variant is invalid")
    if no_status == "unavailable" and preferred != "no-background-theme":
        raise ValueError("candidate with unavailable DSR must prefer no-theme")
    if no_status == "available":
        no_dsr = treatments["no-background-theme"]["training_dsr"]
        themed_dsr = treatments["background-theme"]["training_dsr"]
        expected_preferred = "background-theme" if themed_dsr > no_dsr else "no-background-theme"
        if preferred != expected_preferred:
            raise ValueError("candidate preferred_variant does not follow training DSR")
    if themed.rule_id != no_theme.rule_id:
        raise AssertionError("paired treatments must share the rulebook id")


def _candidate_rank(candidate: Mapping[str, object]) -> tuple[float, float, float, str]:
    treatment = candidate["treatments"][candidate["preferred_variant"]]
    metrics = treatment["training"]
    sharpe = metrics["sharpe"]
    return (-metrics["win_rate"], -metrics["profit_pct"], -(sharpe if sharpe is not None else float("-inf")), candidate["rulebook_id"])


def _validate_success_candidates(candidates: object, top_rulebook_ids: object, horizon: str) -> None:
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("success terminal_state requires candidates")
    for candidate in candidates:
        _validate_candidate(candidate, horizon)
    candidate_ids = [candidate["rulebook_id"] for candidate in candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate rulebook_id values must be unique")
    if not isinstance(top_rulebook_ids, list) or not 1 <= len(top_rulebook_ids) <= 3:
        raise ValueError("top_rulebook_ids must contain one to three rulebook ids")
    expected = [candidate["rulebook_id"] for candidate in sorted(candidates, key=_candidate_rank)[:3]]
    if top_rulebook_ids != expected:
        raise ValueError("top_rulebook_ids must equal the deterministic top-three ranking")


def validate_rulebook_document(payload: object) -> bool:
    """Validate one complete schema-4 exploratory terminal document."""

    if not isinstance(payload, Mapping):
        raise ValueError("rulebook result must be an object")
    required = {
        "schema_version", "ticker", "horizon", "evaluated_at", "terminal_state", "empty",
        "failure_reason", "rejection_reason", "evaluation_label", "rulebook", "audit_eligibility",
        "requested_date_range", "effective_data_range", "split", "candidates", "top_rulebook_ids",
    }
    if set(payload) != required:
        raise ValueError("rulebook result has an invalid schema")
    if payload["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("unsupported rulebook result schema")
    if _normalize_ticker(payload["ticker"]) != payload["ticker"]:
        raise ValueError("rulebook result ticker must be normalized")
    horizon = payload["horizon"]
    if horizon not in HORIZONS:
        raise ValueError("rulebook result horizon is invalid")
    if not isinstance(payload["evaluated_at"], str):
        raise ValueError("evaluated_at must be an ISO timestamp")
    try:
        datetime.fromisoformat(payload["evaluated_at"])
    except ValueError as error:
        raise ValueError("evaluated_at must be an ISO timestamp") from error
    state = payload["terminal_state"]
    if state not in _TERMINAL_STATES:
        raise ValueError("terminal_state is invalid")
    if not isinstance(payload["empty"], bool) or payload["empty"] != (state != "success"):
        raise ValueError("empty must match terminal_state")
    if payload["evaluation_label"] != _EVALUATION_LABEL:
        raise ValueError("evaluation_label must be Exploratory — gross")
    if json.loads(json.dumps(payload["rulebook"])) != _json_rulebook(horizon):
        raise ValueError("rulebook must equal the canonical V3 horizon rulebook")
    _validate_audit(payload["audit_eligibility"])
    _validate_date_range(payload["requested_date_range"], "requested_date_range")
    _validate_date_range(payload["effective_data_range"], "effective_data_range")
    candidates = payload["candidates"]
    top_rulebook_ids = payload["top_rulebook_ids"]
    failure_reason = payload["failure_reason"]
    rejection_reason = payload["rejection_reason"]
    if state == "success":
        if failure_reason is not None or rejection_reason is not None:
            raise ValueError("success terminal_state cannot contain a failure or rejection reason")
        _validate_split(payload["split"])
        _validate_success_candidates(candidates, top_rulebook_ids, horizon)
    elif state == "failed":
        if payload["split"] is not None or candidates or top_rulebook_ids or rejection_reason is not None:
            raise ValueError("failed terminal_state cannot contain candidates or a rejection")
        if not isinstance(failure_reason, str) or not failure_reason.strip():
            raise ValueError("failed terminal_state requires failure_reason")
    elif state == "empty":
        if candidates or top_rulebook_ids or failure_reason is not None:
            raise ValueError("empty terminal_state cannot contain candidates or a failure")
        if not isinstance(rejection_reason, str) or not rejection_reason.strip():
            raise ValueError("empty terminal_state requires rejection_reason")
        _validate_split(payload["split"])
    else:
        if payload["split"] is not None or candidates or top_rulebook_ids or failure_reason is not None:
            raise ValueError("requires_regeneration terminal_state cannot contain candidates or a failure")
        if not isinstance(rejection_reason, str) or not rejection_reason.strip():
            raise ValueError("requires_regeneration terminal_state requires rejection_reason")
    return True


def _write_json_atomically(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_path = temporary.name
            json.dump(payload, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def save_rulebook_result(ticker: str, result: Mapping[str, object], output_dir: str) -> str:
    """Atomically replace one ticker/horizon schema-4 aggregate."""

    if not isinstance(result, Mapping):
        raise ValueError("result must be an object")
    normalized_ticker = _normalize_ticker(ticker)
    payload = json.loads(json.dumps(result))
    payload.update(
        {
            "schema_version": _SCHEMA_VERSION,
            "ticker": normalized_ticker,
            "evaluated_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
        }
    )
    validate_rulebook_document(payload)
    target = signal_artifact_path(normalized_ticker, str(payload["horizon"]), output_dir)
    _write_json_atomically(target, payload)
    return str(target)


def save_regeneration_marker(ticker: str, horizon: str, output_dir: str) -> str:
    """Replace the canonical aggregate with a clear regeneration terminal marker."""

    return write_regeneration_marker(
        signal_artifact_path(ticker, horizon, output_dir), ticker, horizon
    )


def write_regeneration_marker(path: str | Path, ticker: str, horizon: str) -> str:
    """Write a schema-4 marker without inspecting the prior file at ``path``."""

    normalized_ticker = _normalize_ticker(ticker)
    if horizon not in HORIZONS:
        raise ValueError(f"horizon must be one of {HORIZONS}")
    reason = "Regenerate under amended rulebook."
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "ticker": normalized_ticker,
        "horizon": horizon,
        "evaluated_at": datetime.now(_MARKET_TIMEZONE).isoformat(),
        "terminal_state": "requires_regeneration",
        "empty": True,
        "failure_reason": None,
        "rejection_reason": reason,
        "evaluation_label": _EVALUATION_LABEL,
        "rulebook": _json_rulebook(horizon),
        "audit_eligibility": unavailable_v3_audit_eligibility(reason),
        "requested_date_range": {"start": None, "end": None, "reason": reason},
        "effective_data_range": {"start": None, "end": None, "reason": reason},
        "split": None,
        "candidates": [],
        "top_rulebook_ids": [],
    }
    validate_rulebook_document(payload)
    target = Path(path)
    _write_json_atomically(target, payload)
    return str(target)


def load_rulebook_result(path: str | Path) -> dict[str, object]:
    """Read exactly one schema-4 terminal document; legacy schemas are rejected."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_rulebook_document(payload)
    return dict(payload)


__all__ = [
    "load_rulebook_result",
    "save_regeneration_marker",
    "save_rulebook_result",
    "signal_artifact_path",
    "validate_rulebook_document",
    "write_regeneration_marker",
]
