"""Locked finite fast-first Swing catalog revision one."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib

from .contracts import FeatureProfile, PrimitiveSpec, canonical_json


@dataclass(frozen=True)
class CatalogRevision:
    revision: str
    buy_ema_pairs: tuple[tuple[int, int], ...]
    rsi_periods: tuple[int, ...]
    rsi_levels: tuple[int, ...]
    breakout_lookbacks: tuple[int, ...]
    relative_volume_windows: tuple[int, ...]
    relative_volume_minima: tuple[Decimal, ...]
    adx_period: int
    adx_minima: tuple[int, ...]
    atr_stop_multipliers: tuple[Decimal, ...]
    atr_target_multipliers: tuple[Decimal, ...]
    atr_trailing_multipliers: tuple[Decimal | None, ...]
    timeout_bars: tuple[int, ...]
    max_buy_predicates: int
    max_gate_filter_predicates: int

    @property
    def catalog_hash(self) -> str:
        return hashlib.sha256(canonical_json(self.__dict__).encode("utf-8")).hexdigest()


def catalog_revision_1() -> CatalogRevision:
    return CatalogRevision(
        revision="flexible-swing-catalog-v1",
        buy_ema_pairs=((3, 8), (5, 13), (5, 21), (8, 21)),
        rsi_periods=(5, 9, 14), rsi_levels=(50, 52, 55),
        breakout_lookbacks=(10, 20, 40),
        relative_volume_windows=(5, 10, 20),
        relative_volume_minima=(Decimal("1.10"), Decimal("1.20"), Decimal("1.30")),
        adx_period=14, adx_minima=(15, 20, 25),
        atr_stop_multipliers=(Decimal("2.0"),),
        atr_target_multipliers=(Decimal("3.0"),),
        atr_trailing_multipliers=(None,),
        timeout_bars=(10, 15, 22, 30),
        max_buy_predicates=2, max_gate_filter_predicates=2,
    )


def feature_profile(catalog: CatalogRevision) -> FeatureProfile:
    if not isinstance(catalog, CatalogRevision) or catalog.revision != "flexible-swing-catalog-v1":
        raise ValueError("unsupported Flexible catalog revision")
    specs: list[PrimitiveSpec] = [PrimitiveSpec("atr", "atr-wilder-v1", (("period", 14),)), PrimitiveSpec("adx", "adx-wilder-v1", (("period", catalog.adx_period),))]
    specs += [PrimitiveSpec("ema", "ema-recursive-v1", (("fast_period", fast), ("slow_period", slow))) for fast, slow in catalog.buy_ema_pairs]
    specs += [PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", period),)) for period in catalog.rsi_periods]
    specs += [PrimitiveSpec("breakout", "prior-extrema-v1", (("lookback", lookback),)) for lookback in catalog.breakout_lookbacks]
    specs += [PrimitiveSpec("relative_volume", "prior-window-v1", (("window", window),)) for window in catalog.relative_volume_windows]
    return FeatureProfile(tuple(specs))


__all__ = ["CatalogRevision", "catalog_revision_1", "feature_profile"]
