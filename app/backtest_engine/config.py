"""Immutable schema-5 rulebooks and request configuration for Backtest V4."""

from dataclasses import asdict, dataclass
from datetime import date
import re
from typing import Optional


HORIZONS = ("swing", "midterm")
THEME_VARIANTS = ("no-background-theme", "background-theme")
THEME_MODES = ("AND",)
ENTRY_GATE_NAMES = (
    "rulebook_adx_gate",
    "rulebook_joint_trend_pass",
    "rulebook_rsi_upcross",
    "rulebook_volume_gate",
)
MAX_BACKTEST_BATCH_TICKERS = 15
BACKTEST_RESULT_DIR = "backtest-result"
DEFAULT_SIGNAL_DIR = f"{BACKTEST_RESULT_DIR}/ticker-signals"
DEFAULT_GROUP_DIR = f"{BACKTEST_RESULT_DIR}/ticker-group"
_TICKER_PATTERN = re.compile(r"[A-Z0-9._-]+")


def _iso_date(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _normalize_ticker(ticker: object) -> str:
    """Return one persistence-safe uppercase ticker symbol."""

    if not isinstance(ticker, str):
        raise ValueError("ticker must be a string")
    normalized = ticker.strip().upper()
    if not normalized or not _TICKER_PATTERN.fullmatch(normalized):
        raise ValueError("ticker must contain only letters, numbers, '.', '_' or '-'")
    return normalized


def _normalize_group_name(group_name: object) -> str:
    """Return one display-safe Group name for a batch management request."""

    if not isinstance(group_name, str):
        raise ValueError("group_name must be text")
    normalized = group_name.strip().upper()
    return normalized or "N/A"


@dataclass(frozen=True)
class RulebookSpec:
    """One complete, canonical V3 rulebook owned by its horizon."""

    rule_id: str
    horizon: str
    native_timeframe: str
    weekly_frequency: Optional[str]
    ma_kind: str
    ma_pair: tuple[int, int]
    rsi_period: int
    rsi_upcross_level: float
    alligator_periods: tuple[int, int, int]
    alligator_lags: tuple[int, int, int]
    volume_window: int
    volume_multiplier: float
    adx_period: int
    adx_minimum: float
    joint_trend_required: bool
    atr_period: int
    atr_sl_multiplier: float
    atr_tp_multiplier: float
    theme_sma_window: int
    min_exit_offset_bars: int
    max_hold_bars: int
    min_n: int

    def __post_init__(self) -> None:
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon must be one of {HORIZONS}")
        if self.native_timeframe not in ("daily", "weekly"):
            raise ValueError("native_timeframe must be daily or weekly")
        if self.native_timeframe == "weekly" and self.weekly_frequency != "W-FRI":
            raise ValueError("weekly rulebooks must use W-FRI")
        if self.native_timeframe == "daily" and self.weekly_frequency is not None:
            raise ValueError("daily rulebooks cannot define weekly_frequency")
        if self.ma_kind not in ("EMA", "SMA"):
            raise ValueError("ma_kind must be EMA or SMA")
        if len(self.ma_pair) != 2 or min(self.ma_pair) < 1:
            raise ValueError("ma_pair must contain two positive periods")
        if len(self.alligator_periods) != 3 or min(self.alligator_periods) < 1:
            raise ValueError("alligator_periods must contain three positive periods")
        if len(self.alligator_lags) != 3 or min(self.alligator_lags) < 0:
            raise ValueError("alligator_lags must contain three non-negative lags")
        if min(
            self.rsi_period,
            self.volume_window,
            self.adx_period,
            self.atr_period,
            self.theme_sma_window,
            self.min_exit_offset_bars,
            self.max_hold_bars,
            self.min_n,
        ) < 1:
            raise ValueError("rulebook periods, clocks, and minimums must be positive")
        if self.min_exit_offset_bars >= self.max_hold_bars:
            raise ValueError("minimum exit offset must precede the timeout")
        if (
            self.rsi_upcross_level <= 0
            or self.volume_multiplier <= 0
            or self.adx_minimum <= 0
            or self.atr_sl_multiplier <= 0
            or self.atr_tp_multiplier <= 0
        ):
            raise ValueError("rulebook thresholds and ATR multipliers must be positive")
        if not self.joint_trend_required:
            raise ValueError("V3 rulebooks require joint MA/Alligator trend")

    @property
    def rsi_upcross(self) -> float:
        """Compatibility name for the locked RSI crossing level."""

        return self.rsi_upcross_level

    @property
    def min_hold_bars(self) -> int:
        """Return entry-plus-delay bars before a rulebook exit can occur."""

        return self.min_exit_offset_bars + 1

    def to_dict(self) -> dict[str, object]:
        """Return every locked rule parameter for V3 persistence."""

        return asdict(self)


_RULEBOOKS = {
    "swing": RulebookSpec(
        rule_id="swing_rulebook_v5",
        horizon="swing",
        native_timeframe="daily",
        weekly_frequency=None,
        ma_kind="EMA",
        ma_pair=(5, 13),
        rsi_period=9,
        rsi_upcross_level=52,
        alligator_periods=(8, 5, 3),
        alligator_lags=(5, 3, 2),
        volume_window=10,
        volume_multiplier=1.15,
        adx_period=14,
        adx_minimum=17,
        joint_trend_required=True,
        atr_period=14,
        atr_sl_multiplier=1.5,
        atr_tp_multiplier=2.5,
        theme_sma_window=50,
        min_exit_offset_bars=3,
        max_hold_bars=22,
        min_n=5,
    ),
    "midterm": RulebookSpec(
        rule_id="midterm_rulebook_v5",
        horizon="midterm",
        native_timeframe="weekly",
        weekly_frequency="W-FRI",
        ma_kind="SMA",
        ma_pair=(8, 21),
        rsi_period=14,
        rsi_upcross_level=65,
        alligator_periods=(13, 8, 5),
        alligator_lags=(8, 5, 3),
        volume_window=8,
        volume_multiplier=1.3,
        adx_period=14,
        adx_minimum=20,
        joint_trend_required=True,
        atr_period=14,
        atr_sl_multiplier=1.5,
        atr_tp_multiplier=2.5,
        theme_sma_window=20,
        min_exit_offset_bars=1,
        max_hold_bars=16,
        min_n=5,
    ),
}


def rulebook_for(horizon: str) -> RulebookSpec:
    """Return the one immutable rulebook registered for ``horizon``."""

    try:
        return _RULEBOOKS[horizon]
    except KeyError as error:
        raise ValueError(f"horizon must be one of {HORIZONS}") from error


@dataclass(frozen=True)
class BacktestConfig:
    """Request scope for one V3 ticker run; rules are never caller supplied."""

    ticker: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    horizon: str = "swing"
    permutation_count: int = 1000
    permutation_seed: int = 42
    permutation_block_size: int = 20
    worker_count: int = 6
    output_dir: str = DEFAULT_SIGNAL_DIR

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", _normalize_ticker(self.ticker))
        rulebook_for(self.horizon)
        if self.permutation_count < 1:
            raise ValueError("permutation_count must be positive")
        if self.permutation_block_size < 1:
            raise ValueError("permutation_block_size must be positive")
        if self.worker_count < 1:
            raise ValueError("worker_count must be positive")

    @classmethod
    def for_ticker(cls, ticker: str, **overrides: object) -> "BacktestConfig":
        """Build one validated V3 request without a rule-parameter override."""

        return cls(ticker=ticker, **overrides)

    def to_dict(self) -> dict[str, object]:
        values = asdict(self)
        values["start_date"] = _iso_date(self.start_date)
        values["end_date"] = _iso_date(self.end_date)
        values["request_type"] = "backtest_single_v5"
        return values

    def as_batch(self) -> "BacktestBatchConfig":
        """Delegate one V3 request to the common batch-of-one service."""

        return BacktestBatchConfig(
            tickers=(self.ticker,),
            start_date=self.start_date,
            end_date=self.end_date,
            horizon=self.horizon,
            permutation_count=self.permutation_count,
            permutation_seed=self.permutation_seed,
            permutation_block_size=self.permutation_block_size,
            worker_count=self.worker_count,
            output_dir=self.output_dir,
        )


@dataclass(frozen=True)
class BacktestBatchConfig:
    """Common request scope for one sequential V3 ticker batch."""

    tickers: tuple[str, ...]
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    horizon: str = "swing"
    group_name: str = "N/A"
    permutation_count: int = 1000
    permutation_seed: int = 42
    permutation_block_size: int = 20
    worker_count: int = 6
    output_dir: str = DEFAULT_SIGNAL_DIR

    def __post_init__(self) -> None:
        if isinstance(self.tickers, (str, bytes)):
            raise ValueError("tickers must be a sequence")
        try:
            normalized_tickers = tuple(_normalize_ticker(ticker) for ticker in self.tickers)
        except TypeError as error:
            raise ValueError("tickers must be a sequence") from error
        if not 1 <= len(normalized_tickers) <= MAX_BACKTEST_BATCH_TICKERS:
            raise ValueError(
                "tickers must contain between 1 and "
                f"{MAX_BACKTEST_BATCH_TICKERS} values"
            )
        if len(set(normalized_tickers)) != len(normalized_tickers):
            raise ValueError("tickers must not contain a duplicate")
        rulebook_for(self.horizon)
        if self.permutation_count < 1:
            raise ValueError("permutation_count must be positive")
        if self.permutation_block_size < 1:
            raise ValueError("permutation_block_size must be positive")
        if self.worker_count < 1:
            raise ValueError("worker_count must be positive")
        object.__setattr__(self, "tickers", normalized_tickers)
        object.__setattr__(self, "group_name", _normalize_group_name(self.group_name))

    def to_dict(self) -> dict[str, object]:
        values = asdict(self)
        values["start_date"] = _iso_date(self.start_date)
        values["end_date"] = _iso_date(self.end_date)
        values["request_type"] = "backtest_batch_v5"
        return values

    def for_ticker(self, ticker: str) -> BacktestConfig:
        """Return one V3 ticker request sharing only batch request scope."""

        return BacktestConfig(
            ticker=ticker,
            start_date=self.start_date,
            end_date=self.end_date,
            horizon=self.horizon,
            permutation_count=self.permutation_count,
            permutation_seed=self.permutation_seed,
            permutation_block_size=self.permutation_block_size,
            worker_count=self.worker_count,
            output_dir=self.output_dir,
        )
