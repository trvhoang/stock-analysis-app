"""Sequential evaluation and publication lifecycle for Flexible Rulebook v2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Mapping

import numpy as np
import pandas as pd
import pytz

from .cache import ComponentIdentity, safe_read_component, try_write_component
from .contracts import EvaluationRequest, EvaluationResult, PredicateV2, PublishedRulebook, RulebookDefinitionV2, RulebookDraft
from .execution import CompletedTrade, execute_rulebook
from .features import FeatureStore, component_cache_key
from .history import HistoryRange, HistorySnapshot, NativeBar, build_native_bars, load_history, make_native_split
from .metrics import PartitionMetrics, partition_metrics
from .registry import DEFAULT_INDICATOR_REGISTRY, IndicatorRegistry
from .storage import (
    list_evaluations,
    list_published_rulebooks,
    published_short_ids,
    write_draft,
    write_evaluation,
    write_published_rulebook,
)
from .validation import assess_progressive_state, compose_rulebook


_PHASES = ("source", "features", "execution", "metrics", "persistence")
_FEATURE_BUILD_REVISION = "flexible-rulebook-v2-feature-store-v1"
_HCM = pytz.timezone("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class EvaluationProgress:
    """One observable phase for a single sequential ticker evaluation."""

    ticker: str
    phase: str
    terminal_state: str | None = None

    def __post_init__(self) -> None:
        if self.phase not in _PHASES:
            raise ValueError("evaluation progress phase is invalid")
        if self.terminal_state not in {None, "completed", "skipped", "failed"}:
            raise ValueError("evaluation progress terminal state is invalid")


@dataclass(frozen=True)
class EvaluationItem:
    """One ticker terminal outcome; a failure never rewrites another item."""

    ticker: str
    terminal_state: str
    evaluation: EvaluationResult | None = None
    message: str = ""
    current_signal_events: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if self.terminal_state not in {"completed", "skipped", "failed"}:
            raise ValueError("evaluation item terminal state is invalid")
        if self.terminal_state == "completed" and not isinstance(self.evaluation, EvaluationResult):
            raise ValueError("completed evaluation item requires evidence")
        if self.terminal_state != "completed" and self.evaluation is not None:
            raise ValueError("non-completed evaluation item cannot expose evidence")
        if not isinstance(self.message, str):
            raise ValueError("evaluation item message must be text")
        events = tuple(self.current_signal_events)
        for event in events:
            if not isinstance(event, Mapping) or set(event) != {"signal_date", "signal_bar_ordinal"}:
                raise ValueError("current signal events are invalid")
            if type(event["signal_date"]) is not date:
                raise ValueError("current signal event date is invalid")
            ordinal = event["signal_bar_ordinal"]
            if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
                raise ValueError("current signal event ordinal is invalid")
        if self.terminal_state != "completed" and events:
            raise ValueError("only completed items can expose current signal events")
        object.__setattr__(self, "current_signal_events", events)


@dataclass(frozen=True)
class EvaluationBatch:
    """Ordered immutable batch outcome for one draft/request pair."""

    request: EvaluationRequest
    items: tuple[EvaluationItem, ...]


@dataclass(frozen=True)
class PublishedCollectionItem:
    """One independently persisted published-rule outcome within a shared source pass."""

    rulebook_id: str
    ticker: str
    terminal_state: str
    evaluation: EvaluationResult | None = None
    message: str = ""
    current_signal_events: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.rulebook_id, str) or not self.rulebook_id.startswith("frb2_"):
            raise ValueError("published collection rulebook ID is invalid")
        # Reuse the established item validation so collection and draft runs
        # cannot disagree about terminal evidence semantics.
        EvaluationItem(
            ticker=self.ticker,
            terminal_state=self.terminal_state,
            evaluation=self.evaluation,
            message=self.message,
            current_signal_events=self.current_signal_events,
        )


@dataclass(frozen=True)
class CurrentRulebookInspection:
    """Read-only causal facts for one published Flexible rulebook as of now."""

    ticker: str
    horizon: str
    source: Mapping[str, object]
    as_of_date: date
    latest_close: float
    latest_atr: float
    has_prior_event: bool
    signal_date: date | None
    signal_state: str
    age_native_bars: int | None
    support_percentage: float
    live_entry_support: bool
    all_gates_support: bool
    technical_exit: bool
    current_signal_events: tuple[Mapping[str, object], ...]


HistoryLoader = Callable[..., HistorySnapshot]
ProgressCallback = Callable[[EvaluationProgress], None]


def _emit(callback: ProgressCallback | None, ticker: str, phase: str, terminal_state: str | None = None) -> None:
    if callback is not None:
        callback(EvaluationProgress(ticker=ticker, phase=phase, terminal_state=terminal_state))


def _history_range(request: EvaluationRequest) -> HistoryRange:
    if request.start_date is None:
        return HistoryRange.lifetime()
    assert request.end_date is not None
    return HistoryRange.bounded(request.start_date, request.end_date)


def _native_frame(bars: tuple[NativeBar, ...]) -> pd.DataFrame:
    """Give every native feature one actual causal session date and raw OHLCV."""

    return pd.DataFrame(
        {
            "date": [bar.last_session for bar in bars],
            "open": [bar.open for bar in bars],
            "high": [bar.high for bar in bars],
            "low": [bar.low for bar in bars],
            "close": [bar.close for bar in bars],
            "volume": [bar.volume for bar in bars],
        }
    )


def _partition_document(partition: object) -> dict[str, object]:
    return {
        "start_ordinal": partition.start_ordinal,
        "end_ordinal": partition.end_ordinal,
        "start_bucket": partition.start_bucket,
        "end_bucket": partition.end_bucket,
        "start_session": partition.start_session,
        "end_session": partition.end_session,
        "row_count": partition.row_count,
    }


def _metrics_document(metrics: PartitionMetrics) -> dict[str, object]:
    return {
        "n": metrics.n,
        "win_rate": metrics.win_rate,
        "total_return_pct": metrics.total_return_pct,
        "mean_return_pct": metrics.mean_return_pct,
        "sharpe": metrics.sharpe,
    }


def _trade_document(trade: CompletedTrade, partition: str, ticker: str) -> dict[str, object]:
    return {
        "partition": partition,
        "trade_id": trade.trade_id,
        "ticker": ticker,
        "signal_date": trade.signal_date,
        "entry_date": trade.entry_date,
        "exit_date": trade.exit_date,
        "signal_bar_ordinal": trade.signal_bar_ordinal,
        "entry_bar_ordinal": trade.entry_bar_ordinal,
        "exit_bar_ordinal": trade.exit_bar_ordinal,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "exit_reason": trade.exit_reason,
        "return_pct": trade.return_pct,
    }


def _atr_values(
    store: FeatureStore,
    definition: RulebookDefinitionV2,
) -> np.ndarray | None:
    if definition.atr_exit is None:
        return None
    return store.component(_atr_exit_predicate(definition))["atr"].to_numpy(dtype=float)


def _atr_exit_predicate(definition: RulebookDefinitionV2) -> PredicateV2:
    """Represent the definition-owned price exit as a cacheable ATR component."""

    assert definition.atr_exit is not None
    return PredicateV2(
        role="gate",
        family="atr",
        family_revision=definition.atr_exit.formula_revision,
        settings={"period": definition.atr_exit.period},
        operator="above",
        condition={"threshold": 0},
    )


def _monitoring_atr_predicate(definition: RulebookDefinitionV2) -> PredicateV2:
    """Use ATR(14) only to normalize current price progression facts."""

    if definition.atr_exit is not None:
        return _atr_exit_predicate(definition)
    return PredicateV2(
        role="gate",
        family="atr",
        family_revision="atr-wilder-sma-seeded-v1",
        settings={"period": 14},
        operator="above",
        condition={"threshold": 0},
    )


def _cache_identity(snapshot: HistorySnapshot, definition: RulebookDefinitionV2, predicate: PredicateV2) -> ComponentIdentity:
    assert snapshot.source_fingerprint is not None
    assert snapshot.calendar_fingerprint is not None
    return ComponentIdentity(
        source_fingerprint=snapshot.source_fingerprint,
        calendar_fingerprint=snapshot.calendar_fingerprint,
        build_revision=f"{_FEATURE_BUILD_REVISION}-{definition.native_timeframe}",
        family=predicate.family,
        formula_revision=predicate.family_revision,
        settings=predicate.settings_dict,
    )


def _resolve_components(
    store: FeatureStore,
    definition: RulebookDefinitionV2,
    snapshot: HistorySnapshot,
    *,
    root,
    use_cache: bool,
) -> None:
    """Hydrate trusted math arrays, otherwise calculate once and cache opportunistically."""

    seen: set[str] = set()
    predicates = (*definition.buy_predicates, *definition.gates, *definition.technical_exits)
    if definition.atr_exit is not None:
        predicates = (*predicates, _atr_exit_predicate(definition))
    for predicate in predicates:
        key = component_cache_key(predicate)
        if key in seen:
            continue
        seen.add(key)
        identity = _cache_identity(snapshot, definition, predicate)
        expected = set(store.registry.for_family(predicate.family).output_names)
        cached = safe_read_component(root, identity) if use_cache else None
        if (
            cached is not None
            and set(cached.arrays) == expected
            and cached.state == {"native_bar_count": len(store.frame), "native_timeframe": definition.native_timeframe}
            and all(array.shape == (len(store.frame),) for array in cached.arrays.values())
        ):
            store._components[key] = pd.DataFrame(cached.arrays, index=store.frame.index)
            continue
        component = store.component(predicate)
        if use_cache:
            try_write_component(
                root,
                identity,
                {name: component[name].to_numpy(copy=True) for name in component.columns},
                {"native_bar_count": len(store.frame), "native_timeframe": definition.native_timeframe},
                datetime.now(_HCM),
            )


def _current_signal_events(
    bars: tuple[NativeBar, ...],
    entry_mask: pd.Series,
) -> tuple[dict[str, object], ...]:
    """Persist every causal entry event with its actual native session date."""

    if len(entry_mask) != len(bars):
        raise ValueError("entry mask must match native bars")
    return tuple(
        {"signal_date": bar.last_session, "signal_bar_ordinal": bar.ordinal}
        for bar, is_entry in zip(bars, entry_mask.to_numpy(dtype=bool), strict=True)
        if bool(is_entry)
    )


def _evaluate_one(
    definition: RulebookDefinitionV2,
    request: EvaluationRequest,
    snapshot: HistorySnapshot,
    registry: IndicatorRegistry,
    *,
    root,
    use_cache: bool,
    on_phase: Callable[[str], None],
) -> tuple[EvaluationResult, tuple[dict[str, object], ...]]:
    if snapshot.state != "available":
        raise ValueError("skipped history cannot produce evaluation evidence")
    assert snapshot.end_date is not None
    bars = build_native_bars(snapshot.frame, definition.horizon, completed_as_of=snapshot.end_date)
    if len(bars) < 2:
        raise ValueError("insufficient completed native bars")
    split = make_native_split(bars, request.training_ratio)
    store = FeatureStore(_native_frame(bars), horizon=definition.horizon, registry=registry)
    _resolve_components(
        store,
        definition,
        snapshot,
        root=root,
        use_cache=use_cache,
    )
    predicate_evaluations = {
        predicate: store.evaluate(predicate)
        for predicate in (*definition.buy_predicates, *definition.gates, *definition.technical_exits)
    }
    composition = compose_rulebook(definition, predicate_evaluations)
    atr_values = _atr_values(store, definition)
    on_phase("features")
    training = execute_rulebook(
        bars,
        composition.entry_mask,
        composition.technical_exit_mask,
        definition,
        split.training,
        atr_values=atr_values,
        ticker=snapshot.ticker,
    )
    test = execute_rulebook(
        bars,
        composition.entry_mask,
        composition.technical_exit_mask,
        definition,
        split.test,
        atr_values=atr_values,
        ticker=snapshot.ticker,
    )
    on_phase("execution")
    warnings = tuple(
        dict.fromkeys(
            diagnostic
            for evaluation in predicate_evaluations.values()
            for diagnostic in evaluation.diagnostics
        )
    )
    training_metrics = partition_metrics(training)
    test_metrics = partition_metrics(test)
    on_phase("metrics")
    result = EvaluationResult.completed(
        semantic_digest=definition.semantic_digest,
        ticker=snapshot.ticker,
        source={
            "requested_start": request.start_date,
            "requested_end": request.end_date,
            "start_date": snapshot.start_date,
            "end_date": snapshot.end_date,
            "source_fingerprint": snapshot.source_fingerprint,
            "calendar_fingerprint": snapshot.calendar_fingerprint,
            "snapshot_fingerprint": snapshot.fingerprint,
            "native_timeframe": definition.native_timeframe,
            "native_bar_count": len(bars),
            "indicator_build_revision": "flexible-rulebook-v2-feature-store-v1",
            "execution_contract": "flexible-rulebook-v2-reference-executor-v1",
        },
        split={
            "training_ratio": request.training_ratio,
            "warmup_bars": split.warmup_bars,
            "training": _partition_document(split.training),
            "test": _partition_document(split.test),
        },
        metrics={
            "training": _metrics_document(training_metrics),
            "test": _metrics_document(test_metrics),
        },
        trades=tuple(
            _trade_document(item, "training", snapshot.ticker) for item in training
        ) + tuple(
            _trade_document(item, "test", snapshot.ticker) for item in test
        ),
        warnings=warnings,
    )
    return result, _current_signal_events(bars, composition.entry_mask)


def inspect_current_definition(
    definition: RulebookDefinitionV2,
    ticker: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    engine: object | None = None,
    registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
    history_loader: HistoryLoader = load_history,
) -> CurrentRulebookInspection:
    """Recompute one definition's current causal facts without writing evidence.

    This is intentionally distinct from an evaluation: it writes neither cache
    components nor immutable evaluation documents, and returns enough facts for
    Validate Signals to compare a stored artifact with the same current source.
    """

    if not isinstance(definition, RulebookDefinitionV2):
        raise ValueError("definition must be RulebookDefinitionV2")
    definition.validate(registry)
    request = EvaluationRequest(
        semantic_digest=definition.semantic_digest,
        tickers=(ticker,),
        training_ratio=0.65,
        start_date=start_date,
        end_date=end_date,
        use_cache=False,
    )
    snapshot = history_loader(request.tickers[0], _history_range(request), engine=engine)
    if not isinstance(snapshot, HistorySnapshot):
        raise ValueError("history loader must return HistorySnapshot")
    if snapshot.state != "available":
        raise ValueError(snapshot.reason or "history is unavailable")
    assert snapshot.end_date is not None
    bars = build_native_bars(snapshot.frame, definition.horizon, completed_as_of=snapshot.end_date)
    if len(bars) < 2:
        raise ValueError("insufficient completed native bars")
    store = FeatureStore(_native_frame(bars), horizon=definition.horizon, registry=registry)
    predicates = (*definition.buy_predicates, *definition.gates, *definition.technical_exits)
    predicate_evaluations = {predicate: store.evaluate(predicate) for predicate in predicates}
    composition = compose_rulebook(definition, predicate_evaluations)
    atr_component = store.component(_monitoring_atr_predicate(definition))
    atr_values = atr_component["atr"].to_numpy(dtype=float)
    ordinal = len(bars) - 1
    events = _current_signal_events(bars, composition.entry_mask)
    latest_close = float(bars[ordinal].close)
    latest_atr = float(atr_values[ordinal])
    if not np.isfinite(latest_atr) or latest_atr <= 0:
        raise ValueError("latest ATR is unavailable")
    if events:
        event = events[-1]
        event_ordinal = int(event["signal_bar_ordinal"])
        signal_close = float(bars[event_ordinal].close)
        signal_atr = float(atr_values[event_ordinal])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            raise ValueError("signal ATR is unavailable")
        closes = np.asarray([bar.close for bar in bars[event_ordinal:]], dtype=float)
        drawdown = (latest_close - float(np.max(closes))) / signal_atr
        recent_decline = len(closes) >= 3 and bool(closes[-3] > closes[-2] > closes[-1])
        source_support = composition.live_entry_support(ordinal)
        gates_support = composition.all_gates_support(ordinal)
        age = ordinal - event_ordinal
        state = assess_progressive_state(
            has_prior_event=True,
            age_native_bars=age,
            price_change_atr=(latest_close - signal_close) / signal_atr,
            drawdown_from_high_atr=drawdown,
            recent_price_decline=recent_decline,
            source_support=source_support,
            gates_support=gates_support,
        )
        signal_date = event["signal_date"]
    else:
        age = None
        signal_date = None
        source_support = False
        gates_support = composition.all_gates_support(ordinal)
        state = assess_progressive_state(
            has_prior_event=False,
            age_native_bars=None,
            price_change_atr=0.0,
            drawdown_from_high_atr=0.0,
            recent_price_decline=False,
            source_support=False,
            gates_support=gates_support,
        )
    return CurrentRulebookInspection(
        ticker=snapshot.ticker,
        horizon=definition.horizon,
        source={
            "source_fingerprint": snapshot.source_fingerprint,
            "calendar_fingerprint": snapshot.calendar_fingerprint,
            "snapshot_fingerprint": snapshot.fingerprint,
            "start_date": snapshot.start_date,
            "end_date": snapshot.end_date,
        },
        as_of_date=bars[-1].last_session,
        latest_close=latest_close,
        latest_atr=latest_atr,
        has_prior_event=bool(events),
        signal_date=signal_date,
        signal_state=state,
        age_native_bars=age,
        support_percentage=composition.support_percentage(ordinal),
        live_entry_support=source_support,
        all_gates_support=gates_support,
        technical_exit=bool(composition.technical_exit_mask.iloc[ordinal]),
        current_signal_events=events,
    )


def _evaluate_definition(
    definition: RulebookDefinitionV2,
    request: EvaluationRequest,
    *,
    root,
    engine: object | None = None,
    registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
    history_loader: HistoryLoader = load_history,
    on_progress: ProgressCallback | None = None,
) -> EvaluationBatch:
    """Evaluate one validated immutable definition against a sequential ticker batch."""

    if not isinstance(request, EvaluationRequest):
        raise ValueError("request must be EvaluationRequest")
    if request.semantic_digest != definition.semantic_digest:
        raise ValueError("evaluation request semantic digest must match the rulebook definition")
    definition.validate(registry)
    history_range = _history_range(request)
    rulebook_id = f"frb2_{definition.semantic_digest}"
    items: list[EvaluationItem] = []

    for ticker in request.tickers:
        current_phase = "source"
        _emit(on_progress, ticker, current_phase)
        try:
            snapshot = history_loader(ticker, history_range, engine=engine)
            if not isinstance(snapshot, HistorySnapshot):
                raise ValueError("history loader must return HistorySnapshot")
            if snapshot.state == "skipped":
                _emit(on_progress, ticker, "source", "skipped")
                items.append(EvaluationItem(ticker=ticker, terminal_state="skipped", message=snapshot.reason))
                continue

            def report_phase(phase: str) -> None:
                nonlocal current_phase
                current_phase = phase
                _emit(on_progress, ticker, phase)

            evidence, current_signal_events = _evaluate_one(
                definition,
                request,
                snapshot,
                registry,
                root=root,
                use_cache=request.use_cache,
                on_phase=report_phase,
            )
            write_evaluation(root, rulebook_id, evidence)
            _emit(on_progress, ticker, "persistence", "completed")
            items.append(EvaluationItem(
                ticker=ticker,
                terminal_state="completed",
                evaluation=evidence,
                current_signal_events=current_signal_events,
            ))
        except Exception as error:
            _emit(on_progress, ticker, current_phase, "failed")
            items.append(EvaluationItem(ticker=ticker, terminal_state="failed", message=str(error)))
    return EvaluationBatch(request=request, items=tuple(items))


def evaluate_draft(
    draft: RulebookDraft,
    request: EvaluationRequest,
    *,
    root,
    engine: object | None = None,
    registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
    history_loader: HistoryLoader = load_history,
    on_progress: ProgressCallback | None = None,
) -> EvaluationBatch:
    """Evaluate one mutable draft while preserving its explicit lifecycle."""

    if not isinstance(draft, RulebookDraft):
        raise ValueError("draft must be RulebookDraft")
    return _evaluate_definition(
        draft.definition,
        request,
        root=root,
        engine=engine,
        registry=registry,
        history_loader=history_loader,
        on_progress=on_progress,
    )


def evaluate_published(
    published: PublishedRulebook,
    request: EvaluationRequest,
    *,
    root,
    engine: object | None = None,
    registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
    history_loader: HistoryLoader = load_history,
    on_progress: ProgressCallback | None = None,
) -> EvaluationBatch:
    """Evaluate an active immutable definition without manufacturing a draft."""

    if not isinstance(published, PublishedRulebook):
        raise ValueError("published must be PublishedRulebook")
    if published.is_retired:
        raise ValueError("retired Flexible rulebooks cannot be collected")
    return _evaluate_definition(
        published.definition,
        request,
        root=root,
        engine=engine,
        registry=registry,
        history_loader=history_loader,
        on_progress=on_progress,
    )


def evaluate_published_collection(
    published_rulebooks: tuple[PublishedRulebook, ...] | list[PublishedRulebook],
    *,
    tickers: tuple[str, ...] | list[str],
    root,
    training_ratio=0.65,
    start_date: date | None = None,
    end_date: date | None = None,
    use_cache: bool = True,
    engine: object | None = None,
    registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
    history_loader: HistoryLoader = load_history,
    on_progress: ProgressCallback | None = None,
) -> tuple[PublishedCollectionItem, ...]:
    """Evaluate selected published rules while loading each ticker source once.

    Rules remain sequential, preserving the bounded-memory contract.  Only raw
    ticker history is shared; each rule still owns its causal feature and
    execution evaluation.
    """

    if isinstance(published_rulebooks, (str, bytes)):
        raise ValueError("published_rulebooks must be a non-empty sequence")
    try:
        published = tuple(published_rulebooks)
    except TypeError as error:
        raise ValueError("published_rulebooks must be a non-empty sequence") from error
    if not published or any(not isinstance(item, PublishedRulebook) for item in published):
        raise ValueError("published_rulebooks must be a non-empty sequence")
    if len({item.rulebook_id for item in published}) != len(published):
        raise ValueError("published_rulebooks must not repeat a rulebook")
    if any(item.is_retired for item in published):
        raise ValueError("retired Flexible rulebooks cannot be collected")
    for item in published:
        item.definition.validate(registry)

    # EvaluationRequest is the existing authoritative validator for ticker,
    # time, split, and cache controls. Its digest is operationally irrelevant
    # here because every selected definition gets its own per-ticker request.
    template = EvaluationRequest(
        semantic_digest=published[0].definition.semantic_digest,
        tickers=tickers,
        training_ratio=training_ratio,
        start_date=start_date,
        end_date=end_date,
        use_cache=use_cache,
    )
    history_range = _history_range(template)
    items: list[PublishedCollectionItem] = []
    for ticker in template.tickers:
        _emit(on_progress, ticker, "source")
        try:
            snapshot = history_loader(ticker, history_range, engine=engine)
            if not isinstance(snapshot, HistorySnapshot):
                raise ValueError("history loader must return HistorySnapshot")
        except Exception as error:
            _emit(on_progress, ticker, "source", "failed")
            items.extend(
                PublishedCollectionItem(
                    rulebook_id=published_rulebook.rulebook_id,
                    ticker=ticker,
                    terminal_state="failed",
                    message=str(error),
                )
                for published_rulebook in published
            )
            continue
        if snapshot.state == "skipped":
            _emit(on_progress, ticker, "source", "skipped")
            items.extend(
                PublishedCollectionItem(
                    rulebook_id=published_rulebook.rulebook_id,
                    ticker=ticker,
                    terminal_state="skipped",
                    message=snapshot.reason,
                )
                for published_rulebook in published
            )
            continue
        for published_rulebook in published:
            request = EvaluationRequest(
                semantic_digest=published_rulebook.definition.semantic_digest,
                tickers=(ticker,),
                training_ratio=template.training_ratio,
                start_date=template.start_date,
                end_date=template.end_date,
                use_cache=template.use_cache,
            )
            phase = "source"
            try:
                def report_phase(next_phase: str) -> None:
                    nonlocal phase
                    phase = next_phase
                    _emit(on_progress, ticker, next_phase)

                evidence, current_signal_events = _evaluate_one(
                    published_rulebook.definition,
                    request,
                    snapshot,
                    registry,
                    root=root,
                    use_cache=request.use_cache,
                    on_phase=report_phase,
                )
                write_evaluation(root, published_rulebook.rulebook_id, evidence)
                _emit(on_progress, ticker, "persistence", "completed")
                items.append(PublishedCollectionItem(
                    rulebook_id=published_rulebook.rulebook_id,
                    ticker=ticker,
                    terminal_state="completed",
                    evaluation=evidence,
                    current_signal_events=current_signal_events,
                ))
            except Exception as error:
                _emit(on_progress, ticker, phase, "failed")
                items.append(PublishedCollectionItem(
                    rulebook_id=published_rulebook.rulebook_id,
                    ticker=ticker,
                    terminal_state="failed",
                    message=str(error),
                ))
    return tuple(items)


def draft_is_evaluated(root, draft: RulebookDraft) -> bool:
    """Only an exact current semantic digest with train/test metrics earns Evaluated."""

    if not isinstance(draft, RulebookDraft):
        raise ValueError("draft must be RulebookDraft")
    rulebook_id = f"frb2_{draft.definition.semantic_digest}"
    return any(
        item.is_completed
        and {"training", "test"} <= set(item.metrics)
        for item in list_evaluations(root, rulebook_id)
    )


def publish_draft(
    root,
    draft: RulebookDraft,
    *,
    published_at: datetime,
    confirmed: bool,
    registry: IndicatorRegistry = DEFAULT_INDICATOR_REGISTRY,
) -> PublishedRulebook:
    """Publish only after the operator explicitly confirms current train/test evidence."""

    if confirmed is not True:
        raise ValueError("publication requires explicit confirmation")
    if not isinstance(draft, RulebookDraft):
        raise ValueError("draft must be RulebookDraft")
    draft.validate(registry)
    if not draft_is_evaluated(root, draft):
        raise ValueError("publication requires completed train/test evidence for the current draft")
    published = PublishedRulebook.publish(draft.definition, published_at=published_at)
    write_published_rulebook(root, published)
    return published


def clone_draft(root, draft: RulebookDraft, *, name: str, now: datetime, description: str | None = None) -> RulebookDraft:
    """Create a new mutable draft that shares semantics but never identity or evidence."""

    if not isinstance(draft, RulebookDraft):
        raise ValueError("draft must be RulebookDraft")
    clone = RulebookDraft.new(
        name=name,
        description=draft.description if description is None else description,
        definition=draft.definition,
        now=now,
    )
    write_draft(root, clone, expected_revision=0)
    return clone


def published_library(root) -> tuple[tuple[PublishedRulebook, str], ...]:
    """Return only non-retired choices with collision-safe display IDs."""

    published = list_published_rulebooks(root, include_retired=False)
    short_ids = published_short_ids(root, include_retired=False)
    return tuple((item, short_ids[item.rulebook_id]) for item in published)


__all__ = [
    "EvaluationBatch",
    "EvaluationItem",
    "EvaluationProgress",
    "CurrentRulebookInspection",
    "PublishedCollectionItem",
    "clone_draft",
    "draft_is_evaluated",
    "evaluate_draft",
    "evaluate_published",
    "evaluate_published_collection",
    "inspect_current_definition",
    "publish_draft",
    "published_library",
]
