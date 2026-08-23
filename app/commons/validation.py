"""Empirical validation helpers for technical score comparisons."""

import math

import pandas as pd


MIN_VALIDATION_BUCKET_SIZE = 30

_TREND_REQUIRED_COLUMNS = {
    "ticker",
    "possibility_up",
    "possibility_down",
    "total_signals",
}

_REQUIRED_COLUMNS = {
    "ticker",
    "signal_date",
    "result",
    "result_delta",
    "legacy_score",
    "new_score",
}

_RESULT_DIRECTION = {
    "up": "Up",
    "strong up": "Up",
    "down": "Down",
    "strong down": "Down",
    "no change": "No Change",
    "sideways": "No Change",
}


def _empty_frame(columns):
    return pd.DataFrame(columns=columns)


def _normalize_result(value):
    if pd.isna(value):
        return None
    return _RESULT_DIRECTION.get(str(value).strip().casefold())


def legacy_statistical_trend(possibility_up):
    """Apply the historical Up-probability-only trend thresholds."""
    try:
        probability = float(possibility_up)
    except (TypeError, ValueError):
        return None
    if pd.isna(probability):
        return None

    if probability > 70:
        return "Strong Up"
    if probability >= 53:
        return "Up"
    if probability >= 48:
        return "Sideways"
    if probability >= 30:
        return "Down"
    return "Strong Down"


def current_statistical_trend(possibility_up, possibility_down):
    """Apply current classification using direct Up and Down evidence."""
    try:
        up_probability = float(possibility_up)
        down_probability = float(possibility_down)
    except (TypeError, ValueError):
        return None
    if pd.isna(up_probability) or pd.isna(down_probability):
        return None

    if up_probability > 70:
        return "Strong Up"
    if up_probability >= 53:
        return "Up"
    if down_probability > 70:
        return "Strong Down"
    if down_probability >= 53:
        return "Down"
    return "Sideways"


def _dominant_outcome(possibility_up, possibility_down):
    """Return probability majority with deterministic tie ordering."""
    try:
        up_probability = float(possibility_up)
        down_probability = float(possibility_down)
    except (TypeError, ValueError):
        return None
    if pd.isna(up_probability) or pd.isna(down_probability):
        return None

    probabilities = {
        "Up": up_probability,
        "Down": down_probability,
        "No Change": 100 - up_probability - down_probability,
    }
    return max(("Up", "Down", "No Change"), key=probabilities.get)


def compare_trend_classifications(records):
    """Annotate database-derived probability records with old/new trends."""
    missing = _TREND_REQUIRED_COLUMNS.difference(records.columns)
    if missing:
        raise ValueError(f"Missing validation columns: {sorted(missing)}")

    result = records.copy()
    up_values = pd.to_numeric(result["possibility_up"], errors="coerce")
    down_values = pd.to_numeric(result["possibility_down"], errors="coerce")
    signal_counts = pd.to_numeric(result["total_signals"], errors="coerce")
    valid_probabilities = up_values.notna() & down_values.notna()

    result["legacy_trend"] = pd.Series(pd.NA, index=result.index, dtype="object")
    result["current_trend"] = pd.Series(pd.NA, index=result.index, dtype="object")
    result.loc[valid_probabilities, "legacy_trend"] = up_values.loc[
        valid_probabilities
    ].map(legacy_statistical_trend)
    result.loc[valid_probabilities, "current_trend"] = [
        current_statistical_trend(up, down)
        for up, down in zip(
            up_values.loc[valid_probabilities], down_values.loc[valid_probabilities]
        )
    ]
    result["dominant_outcome"] = [
        _dominant_outcome(up, down)
        for up, down in zip(up_values, down_values)
    ]
    result["changed"] = pd.Series(False, index=result.index, dtype="bool")
    result.loc[valid_probabilities, "changed"] = (
        result.loc[valid_probabilities, "legacy_trend"]
        != result.loc[valid_probabilities, "current_trend"]
    )
    result["eligible"] = (
        valid_probabilities & signal_counts.ge(MIN_VALIDATION_BUCKET_SIZE).fillna(False)
    )
    return result


def score_to_direction(score):
    """Map the existing 0-100 score bands to a realized direction bucket."""
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        return None

    if pd.isna(numeric_score):
        return None
    if numeric_score >= 53:
        return "Up"
    if numeric_score >= 48:
        return "No Change"
    return "Down"


def select_global_split_date(observations, train_fraction=0.8):
    """Select one chronological split date from pooled signal dates."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    if "signal_date" not in observations.columns:
        raise ValueError("observations must contain signal_date")

    dates = (
        pd.to_datetime(observations["signal_date"], errors="coerce")
        .dropna()
        .drop_duplicates()
        .sort_values()
    )
    if dates.empty:
        raise ValueError("observations contain no valid signal dates")

    split_index = min(
        len(dates) - 1,
        max(0, math.ceil(len(dates) * train_fraction) - 1),
    )
    return pd.Timestamp(dates.iloc[split_index])


def build_validation_report(
    observations,
    train_fraction=0.8,
    min_bucket_size=MIN_VALIDATION_BUCKET_SIZE,
):
    """Build pooled in/out-of-sample metrics for legacy and new scores.

    The split is selected once from all ticker dates. Bucket counts are then
    pooled across tickers before the minimum-sample gate is applied. The
    returned ``comparison`` contains only phases where both models have at
    least ``min_bucket_size`` valid observations.
    """
    missing = _REQUIRED_COLUMNS.difference(observations.columns)
    if missing:
        raise ValueError(f"Missing validation columns: {sorted(missing)}")
    if min_bucket_size <= 0:
        raise ValueError("min_bucket_size must be positive")

    work = observations.copy()
    work["signal_date"] = pd.to_datetime(work["signal_date"], errors="coerce")
    work["actual_direction"] = work["result"].map(_normalize_result)
    work["result_delta"] = pd.to_numeric(work["result_delta"], errors="coerce")
    work["legacy_score"] = pd.to_numeric(work["legacy_score"], errors="coerce")
    work["new_score"] = pd.to_numeric(work["new_score"], errors="coerce")

    valid = work[
        work["signal_date"].notna()
        & work["actual_direction"].notna()
        & work["result_delta"].notna()
        & work["legacy_score"].notna()
        & work["new_score"].notna()
    ].copy()
    excluded_rows = len(work) - len(valid)
    if valid.empty:
        raise ValueError("observations contain no valid validation rows")

    split_date = select_global_split_date(valid, train_fraction=train_fraction)
    valid["split_date"] = split_date
    valid["phase"] = valid["signal_date"].map(
        lambda value: "in_sample" if value <= split_date else "out_of_sample"
    )

    bucket_rows = []
    model_frames = {}
    for model, score_column in (("legacy", "legacy_score"), ("new", "new_score")):
        model_frame = valid[["phase", "actual_direction", "result_delta", score_column]].copy()
        model_frame["model"] = model
        model_frame["predicted_direction"] = model_frame[score_column].map(score_to_direction)
        model_frame["is_hit"] = model_frame["predicted_direction"] == model_frame["actual_direction"]
        model_frames[model] = model_frame

        for (phase, direction), bucket in model_frame.groupby(
            ["phase", "predicted_direction"], dropna=False, sort=True
        ):
            sample_size = len(bucket)
            bucket_rows.append(
                {
                    "model": model,
                    "phase": phase,
                    "predicted_direction": direction,
                    "sample_size": sample_size,
                    "hit_rate": bucket["is_hit"].mean() * 100,
                    "expectancy": bucket["result_delta"].mean(),
                    "eligible": sample_size >= min_bucket_size,
                }
            )

    bucket_columns = [
        "model",
        "phase",
        "predicted_direction",
        "sample_size",
        "hit_rate",
        "expectancy",
        "eligible",
    ]
    buckets = pd.DataFrame(bucket_rows, columns=bucket_columns)

    model_rows = []
    for model, model_frame in model_frames.items():
        for phase, phase_frame in model_frame.groupby("phase", sort=True):
            sample_size = len(phase_frame)
            model_rows.append(
                {
                    "model": model,
                    "phase": phase,
                    "sample_size": sample_size,
                    "hit_rate": phase_frame["is_hit"].mean() * 100,
                    "expectancy": phase_frame["result_delta"].mean(),
                    "eligible": sample_size >= min_bucket_size,
                }
            )

    model_columns = ["model", "phase", "sample_size", "hit_rate", "expectancy", "eligible"]
    model_metrics = pd.DataFrame(model_rows, columns=model_columns)

    legacy = model_metrics[model_metrics["model"] == "legacy"].drop(columns="model")
    new = model_metrics[model_metrics["model"] == "new"].drop(columns="model")
    comparison = legacy.merge(new, on="phase", suffixes=("_legacy", "_new"))
    comparison = comparison[
        comparison["eligible_legacy"] & comparison["eligible_new"]
    ].copy()
    comparison = comparison.rename(
        columns={
            "sample_size_legacy": "legacy_sample_size",
            "sample_size_new": "new_sample_size",
            "hit_rate_legacy": "legacy_hit_rate",
            "hit_rate_new": "new_hit_rate",
            "expectancy_legacy": "legacy_expectancy",
            "expectancy_new": "new_expectancy",
        }
    )
    comparison["hit_rate_delta"] = (
        comparison["new_hit_rate"] - comparison["legacy_hit_rate"]
    )
    comparison["expectancy_delta"] = (
        comparison["new_expectancy"] - comparison["legacy_expectancy"]
    )

    return {
        "split_date": split_date,
        "observations": valid,
        "excluded_rows": excluded_rows,
        "buckets": buckets,
        "model_metrics": model_metrics,
        "comparison": comparison,
    }
