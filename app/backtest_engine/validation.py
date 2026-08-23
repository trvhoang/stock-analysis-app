"""Pure statistical helpers for exploratory evidence; no binary certification."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp, isfinite, sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd


_EULER_MASCHERONI = 0.5772156649
_NORMAL = NormalDist()


@dataclass(frozen=True)
class PermutationResult:
    """Reproducible one-sided centered moving-block bootstrap result."""

    observed_sharpe: float
    p_value: float
    null_sharpes: tuple[float, ...]
    count: int
    seed: int
    block_size: int


def _finite_returns(returns: Sequence[float]) -> np.ndarray:
    values = np.asarray(tuple(returns), dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("at least two returns are required")
    if not np.isfinite(values).all():
        raise ValueError("returns must be finite")
    return values


def _sharpe_from_array(values: np.ndarray) -> float:
    deviation = float(np.std(values, ddof=1))
    if deviation == 0 or not isfinite(deviation):
        return 0.0
    return float(np.mean(values) / deviation)


def calculate_unannualized_sharpe(returns: Sequence[float]) -> float:
    """Return mean/sample-standard-deviation Sharpe in input-return units."""

    return _sharpe_from_array(_finite_returns(returns))


def calculate_probabilistic_sharpe(returns: Sequence[float], expected_sharpe: float = 0.0) -> float:
    """Retain PSR math solely for the isolated research optimizer."""

    values = _finite_returns(returns)
    if not isfinite(expected_sharpe):
        raise ValueError("expected_sharpe must be finite")
    series = pd.Series(values, dtype=float)
    sharpe = _sharpe_from_array(values)
    skewness = float(series.skew())
    pearson_kurtosis = float(series.kurt()) + 3.0
    denominator_squared = 1.0 - skewness * sharpe + ((pearson_kurtosis - 1.0) / 4.0) * sharpe**2
    if denominator_squared <= 0 or not isfinite(denominator_squared):
        raise ValueError("PSR denominator must be positive")
    score = _NORMAL.cdf((sharpe - expected_sharpe) * sqrt(len(values) - 1) / sqrt(denominator_squared))
    if not isfinite(score):
        raise ValueError("PSR score must be finite")
    return float(score)


def calculate_deflated_sharpe(returns: Sequence[float], trials: Sequence[float]) -> float:
    """Calculate DSR for a treatment from the exact two-treatment Sharpe family."""

    values = _finite_returns(returns)
    trial_values = np.asarray(tuple(trials), dtype=float)
    if trial_values.ndim != 1 or len(trial_values) < 2 or not np.isfinite(trial_values).all():
        raise ValueError("at least two finite trial Sharpes are required")
    mean = float(np.mean(values))
    sample_std = float(np.std(values, ddof=1))
    population_variance = float(np.mean((values - mean) ** 2))
    if sample_std == 0 or population_variance == 0:
        return 0.0
    sharpe = mean / sample_std
    population_std = sqrt(population_variance)
    skewness = float(np.mean((values - mean) ** 3)) / population_std**3
    pearson_kurtosis = float(np.mean((values - mean) ** 4)) / population_variance**2
    trial_count = len(trial_values)
    trial_variance = float(np.var(trial_values, ddof=1))
    sr0 = sqrt(max(trial_variance, 0.0)) * (
        (1.0 - _EULER_MASCHERONI) * _NORMAL.inv_cdf(1.0 - 1.0 / trial_count)
        + _EULER_MASCHERONI * _NORMAL.inv_cdf(1.0 - 1.0 / (trial_count * exp(1.0)))
    )
    denominator_squared = 1.0 - skewness * sharpe + ((pearson_kurtosis - 1.0) / 4.0) * sharpe**2
    if denominator_squared <= 0:
        return 0.0
    return float(_NORMAL.cdf((sharpe - sr0) * sqrt(len(values) - 1) / sqrt(denominator_squared)))


def _resample_moving_blocks(returns: Sequence[float], rng: np.random.Generator, block_size: int) -> list[float]:
    values = tuple(float(value) for value in returns)
    if not values or block_size < 1:
        raise ValueError("returns must not be empty and block_size must be positive")
    effective_size = min(block_size, len(values))
    starts = rng.integers(0, len(values), size=int(np.ceil(len(values) / effective_size)))
    sample: list[float] = []
    for start in starts:
        sample.extend(values[(int(start) + offset) % len(values)] for offset in range(effective_size))
    return sample[:len(values)]


def moving_block_permutation_test(returns: Sequence[float], count: int = 1000, seed: int = 42, block_size: int = 20) -> PermutationResult:
    """Estimate an informational one-sided p-value with centered moving blocks."""

    if count < 1 or block_size < 1:
        raise ValueError("count and block_size must be positive")
    values = _finite_returns(returns)
    observed = _sharpe_from_array(values)
    centered = values - float(np.mean(values))
    rng = np.random.default_rng(seed)
    null_sharpes = tuple(
        _sharpe_from_array(np.asarray(_resample_moving_blocks(centered, rng, block_size)))
        for _ in range(count)
    )
    p_value = (sum(value >= observed for value in null_sharpes) + 1) / (count + 1)
    return PermutationResult(observed, float(p_value), null_sharpes, count, seed, block_size)


__all__ = [
    "PermutationResult", "calculate_deflated_sharpe", "calculate_probabilistic_sharpe",
    "calculate_unannualized_sharpe", "moving_block_permutation_test",
]
