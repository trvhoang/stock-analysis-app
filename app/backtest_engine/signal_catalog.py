"""Read only current schema-5 exploratory rulebook aggregates."""

from collections.abc import Mapping, Sequence

from .config import DEFAULT_SIGNAL_DIR, HORIZONS, _normalize_ticker
from .persistence import load_rulebook_result, signal_artifact_path
from .result_store import ensure_result_root, list_groups
from .signal_removal import recover_pending_signal_removal


_HORIZON_LABELS = {"swing": "Swing", "midterm": "Mid-term"}


def _top_candidates(result: Mapping[str, object]) -> list[dict[str, object]]:
    candidates = result.get("candidates")
    top_ids = result.get("top_rulebook_ids")
    if not isinstance(candidates, list) or not isinstance(top_ids, list):
        raise ValueError("schema-5 result candidates are invalid")
    by_id = {
        candidate.get("rulebook_id"): candidate
        for candidate in candidates
        if isinstance(candidate, dict)
    }
    try:
        return [dict(by_id[rulebook_id]) for rulebook_id in top_ids]
    except KeyError as error:
        raise ValueError("schema-5 result Top-3 identity is invalid") from error


def _catalog_success_row(result: Mapping[str, object], candidate: Mapping[str, object]) -> dict[str, object]:
    preferred = candidate["preferred_variant"]
    treatment = candidate["treatments"][preferred]
    training = treatment["training"]
    test = treatment["test"]
    return {
        "Ticker": result["ticker"],
        "Horizon": _HORIZON_LABELS[result["horizon"]],
        "Rulebook": candidate["rulebook_id"],
        "Selected gates": list(candidate["selected_gates"]),
        "Preferred treatment": preferred,
        "Evaluation": result["evaluation_label"],
        "Evidence": result["evidence_eligibility"]["status"],
        "Training n": training["n"],
        "Training win rate %": training["win_rate"],
        "Training profit %": training["profit_pct"],
        "Training Sharpe": training["sharpe"],
        "Test n": test["n"],
        "Test win rate %": test["win_rate"],
        "Test profit %": test["profit_pct"],
        "Test Sharpe": test["sharpe"],
        "Treatments": dict(candidate["treatments"]),
    }


def _terminal_row(result: Mapping[str, object]) -> dict[str, object]:
    state = result["terminal_state"]
    reason = result["failure_reason"] if state == "failed" else result["rejection_reason"]
    return {
        "ticker": result["ticker"],
        "horizon": result["horizon"],
        "terminal_state": state,
        "reason": reason,
        "evaluation_label": result["evaluation_label"],
    }


def list_current_signal_set_rows(signal_dir: str = DEFAULT_SIGNAL_DIR) -> dict[str, list[dict[str, object]]]:
    """List Top-3 rows and terminal schema-5 states; old paths remain invisible."""

    try:
        recover_pending_signal_removal(signal_dir)
    except (OSError, TypeError, ValueError) as error:
        return {
            "valid": [],
            "invalid": [],
            "terminal": [],
            "warnings": [f"Signal removal recovery is required: {error}"],
        }
    root = ensure_result_root(signal_dir)
    valid: list[dict[str, object]] = []
    invalid: list[dict[str, object]] = []
    terminal: list[dict[str, object]] = []
    warnings: list[str] = []
    try:
        groups_by_ticker: dict[str, tuple[str, ...]] = {}
        for group in list_groups(str(root)):
            for ticker in group.tickers:
                groups_by_ticker[ticker] = (*groups_by_ticker.get(ticker, ()), group.group_name)
    except (OSError, ValueError) as error:
        groups_by_ticker = {}
        warnings.append(f"Group metadata is unavailable: {error}")
    for ticker_dir in sorted(root.iterdir(), key=lambda item: item.name):
        if not ticker_dir.is_dir():
            continue
        try:
            ticker = _normalize_ticker(ticker_dir.name)
        except ValueError:
            continue
        for horizon in HORIZONS:
            path = signal_artifact_path(ticker, horizon, str(root))
            if not path.is_file():
                continue
            try:
                result = load_rulebook_result(path)
                if result["ticker"] != ticker or result["horizon"] != horizon:
                    raise ValueError("schema-5 document identity differs from its path")
            except (OSError, TypeError, ValueError) as error:
                invalid.append({"Ticker": ticker, "Horizon": _HORIZON_LABELS[horizon], "_source": str(path), "_issue": f"Invalid schema-5 signal artifact: {error}", "_groups": groups_by_ticker.get(ticker, ())})
                continue
            if result["terminal_state"] == "success":
                for candidate in _top_candidates(result):
                    row = _catalog_success_row(result, candidate)
                    row["_groups"] = groups_by_ticker.get(ticker, ())
                    valid.append(row)
            else:
                row = _terminal_row(result)
                row["_groups"] = groups_by_ticker.get(ticker, ())
                terminal.append(row)
    return {"valid": valid, "invalid": invalid, "terminal": terminal, "warnings": warnings}


def list_saved_signal_options(ticker: str, signal_dir: str = DEFAULT_SIGNAL_DIR) -> list[dict[str, object]]:
    """Return only schema-5 Top-3 preferred selections across both horizons."""

    normalized = _normalize_ticker(ticker)
    try:
        recover_pending_signal_removal(signal_dir)
    except (OSError, TypeError, ValueError):
        return []
    root = ensure_result_root(signal_dir)
    options = []
    for horizon in HORIZONS:
        path = signal_artifact_path(normalized, horizon, str(root))
        if not path.is_file():
            continue
        try:
            result = load_rulebook_result(path)
        except (OSError, TypeError, ValueError):
            continue
        if result["terminal_state"] != "success":
            continue
        for candidate in _top_candidates(result):
            preferred = candidate["preferred_variant"]
            options.append({
                "ticker": normalized,
                "horizon": horizon,
                "rulebook_id": candidate["rulebook_id"],
                "preferred_variant": preferred,
                "selected_gates": list(candidate["selected_gates"]),
                "candidate": candidate,
                "label": f"{_HORIZON_LABELS[horizon]} — {candidate['rulebook_id']} — {preferred}",
            })
    return options


def tickers_with_no_saved_signal(tickers: Sequence[str], signal_dir: str = DEFAULT_SIGNAL_DIR) -> tuple[str, ...]:
    """Return requested tickers without a readable nonempty schema-5 aggregate."""

    if isinstance(tickers, (str, bytes)) or not isinstance(tickers, Sequence):
        raise ValueError("tickers must be a sequence")
    normalized_tickers = tuple(_normalize_ticker(ticker) for ticker in tickers)
    try:
        recover_pending_signal_removal(signal_dir)
    except (OSError, TypeError, ValueError):
        return normalized_tickers
    root = ensure_result_root(signal_dir)
    missing = []
    for ticker in normalized_tickers:
        found = False
        for horizon in HORIZONS:
            path = signal_artifact_path(ticker, horizon, str(root))
            if not path.is_file():
                continue
            try:
                result = load_rulebook_result(path)
            except (OSError, TypeError, ValueError):
                continue
            if result["terminal_state"] == "success" and not result["empty"]:
                found = True
                break
        if not found:
            missing.append(ticker)
    return tuple(missing)


__all__ = ["list_current_signal_set_rows", "list_saved_signal_options", "tickers_with_no_saved_signal"]
