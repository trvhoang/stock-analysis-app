"""Lazy, seeded, structurally stratified Swing candidate traversal."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import itertools
import math
import time
from typing import Callable, Iterator

from .catalog import CatalogRevision
from .cap_benchmark import SlotPhaseTiming, WindowPhaseTiming
from .contracts import EvaluationSplit, ExecutionContract, PredicateSpec, PrimitiveSpec, RulebookDefinition, RulebookEvaluation, RuntimeBudget, canonical_json, rulebook_id
from .execution import ExecutionInterrupted, execute_rulebook
from .features import FeatureResolution, compose_entry_mask, compose_technical_exit_mask
from .history import HistorySnapshot, make_evaluation_split
from .metrics import partition_metrics, qualifies

_SPACE_VERSION = "flexible-candidate-space-v2"
_FRONTIER_VERSION = "flexible-frontier-stratified-v1"
_STRATIFICATION_VERSION = "buy-family-count-gate-count-tech-price-hold-v1"


def _subsets(count: int, maximum: int, *, optional: bool) -> tuple[tuple[int, ...], ...]:
    result = [()] if optional else []
    result.extend(indexes for size in range(1, maximum + 1) for indexes in itertools.combinations(range(count), size))
    return tuple(result)


def _affine(material: str, size: int) -> tuple[int, int]:
    if size == 1: return 0, 0
    digest = hashlib.sha256(material.encode("utf-8")).digest(); multiplier = int.from_bytes(digest[:8], "big") % size
    while math.gcd(multiplier, size) != 1: multiplier = (multiplier + 1) % size
    return multiplier, int.from_bytes(digest[8:16], "big") % size


@dataclass(frozen=True)
class SearchBudget:
    attempt_count: int
    runtime: RuntimeBudget = field(default_factory=RuntimeBudget)
    def __post_init__(self) -> None:
        if isinstance(self.attempt_count, bool) or not isinstance(self.attempt_count, int) or self.attempt_count <= 0: raise ValueError("attempt_count must be positive")
        if not isinstance(self.runtime, RuntimeBudget): raise ValueError("runtime must be RuntimeBudget")


@dataclass(frozen=True)
class _Layout:
    stratum_id: str
    buy_members: tuple[int, ...]
    gate_members: tuple[int, ...]
    technical_active: bool
    price_index: int
    timeout_index: int
    base: int
    size: int


@dataclass(frozen=True)
class CandidateSpace:
    catalog: CatalogRevision = field(repr=False, compare=False)
    candidate_space_hash: str = field(init=False)
    candidate_space_algorithm_version: str = _SPACE_VERSION
    size: int = field(init=False)
    _buy_subsets: tuple[tuple[int, ...], ...] = field(init=False, repr=False, compare=False)
    _gate_subsets: tuple[tuple[int, ...], ...] = field(init=False, repr=False, compare=False)
    _layouts: tuple[_Layout, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, CatalogRevision): raise ValueError("CandidateSpace requires CatalogRevision")
        buys = self._buy_instances(); gates = self._gate_instances()
        buy_subsets = _subsets(len(buys), self.catalog.max_buy_predicates, optional=False)
        gate_subsets = _subsets(len(gates), self.catalog.max_gate_filter_predicates, optional=True)
        buy_groups: dict[str, list[int]] = {}; gate_groups: dict[int, list[int]] = {}
        for index, subset in enumerate(buy_subsets): buy_groups.setdefault("+".join(sorted(item.primitive.family for item in (buys[x] for x in subset))), []).append(index)
        for index, subset in enumerate(gate_subsets): gate_groups.setdefault(len(subset), []).append(index)
        layouts: list[_Layout] = []; base = 0; technical_size = (1 << len(buys)) - 1
        for buy_key, buy_members in buy_groups.items():
            for gate_count, gate_members in gate_groups.items():
                for technical_active in (False, True):
                    for price_index in range(4):
                        for timeout_index, timeout in enumerate(self.catalog.timeout_bars):
                            size = len(buy_members) * len(gate_members) * (technical_size if technical_active else 1)
                            price = ("none", "stop", "target", "stop_target")[price_index]
                            stratum_id = f"buy={buy_key};gates={gate_count};technical={'on' if technical_active else 'off'};price={price};hold={timeout}"
                            layouts.append(_Layout(stratum_id, tuple(buy_members), tuple(gate_members), technical_active, price_index, timeout_index, base, size)); base += size
        material = {"catalog": self.catalog.__dict__, "mapping_revision": _SPACE_VERSION, "stratification": _STRATIFICATION_VERSION}
        object.__setattr__(self, "candidate_space_hash", hashlib.sha256(canonical_json(material).encode()).hexdigest())
        object.__setattr__(self, "size", base); object.__setattr__(self, "_buy_subsets", buy_subsets); object.__setattr__(self, "_gate_subsets", gate_subsets); object.__setattr__(self, "_layouts", tuple(layouts))

    def _buy_instances(self) -> tuple[PredicateSpec, ...]:
        ema = tuple(PredicateSpec("buy", PrimitiveSpec("ema", "ema-recursive-v1", (("fast_period", a), ("slow_period", b))), (("direction", "cross_up"),)) for a,b in self.catalog.buy_ema_pairs)
        rsi = tuple(PredicateSpec("buy", PrimitiveSpec("rsi", "rsi-wilder-v1", (("period", p),)), (("cross", "up"), ("level", Decimal(v)))) for p in self.catalog.rsi_periods for v in self.catalog.rsi_levels)
        breakout = tuple(PredicateSpec("buy", PrimitiveSpec("breakout", "prior-extrema-v1", (("lookback", n),)), (("direction", "up"),)) for n in self.catalog.breakout_lookbacks)
        return (*ema,*rsi,*breakout)
    def _gate_instances(self) -> tuple[PredicateSpec, ...]:
        ema = tuple(PredicateSpec("gate", PrimitiveSpec("ema", "ema-recursive-v1", (("fast_period", a), ("slow_period", b))), (("direction", "up"),)) for a,b in self.catalog.buy_ema_pairs)
        volume = tuple(PredicateSpec("gate", PrimitiveSpec("relative_volume", "prior-window-v1", (("window", w),)), (("minimum", m),)) for w in self.catalog.relative_volume_windows for m in self.catalog.relative_volume_minima)
        adx = tuple(PredicateSpec("gate", PrimitiveSpec("adx", "adx-wilder-v1", (("period", self.catalog.adx_period),)), (("minimum", m),)) for m in self.catalog.adx_minima)
        return (*ema,*volume,*adx)
    def _exit_instances(self) -> tuple[PredicateSpec, ...]:
        result=[]
        for item in self._buy_instances():
            if item.primitive.family == "ema": condition=(("direction","cross_down"),)
            elif item.primitive.family == "rsi": condition=(("cross","down"),("level",dict(item.condition)["level"]))
            else: condition=(("direction","down"),)
            result.append(PredicateSpec("technical_sell", item.primitive, condition))
        return tuple(result)
    @property
    def layouts(self) -> tuple[_Layout, ...]: return self._layouts
    def definition_at(self, canonical_index: int) -> RulebookDefinition:
        if isinstance(canonical_index,bool) or not isinstance(canonical_index,int) or not 0 <= canonical_index < self.size: raise ValueError("canonical index outside CandidateSpace")
        layout = next(item for item in self._layouts if item.base <= canonical_index < item.base + item.size); local = canonical_index-layout.base
        tech_count = (1 << len(self._buy_instances()))-1 if layout.technical_active else 1
        exit_mask = (local % tech_count)+1 if layout.technical_active else 0; local //= tech_count
        gate_subset = self._gate_subsets[layout.gate_members[local % len(layout.gate_members)]]; local //= len(layout.gate_members)
        buy_subset = self._buy_subsets[layout.buy_members[local]]; buys=self._buy_instances(); gates=self._gate_instances(); exits=self._exit_instances()
        return RulebookDefinition(buy_predicates=tuple(buys[i] for i in buy_subset), gates=tuple(gates[i] for i in gate_subset), exits=tuple(exits[i] for i in range(len(exits)) if exit_mask & (1<<i)), atr_stop_multiplier=self.catalog.atr_stop_multipliers[0] if layout.price_index in (1,3) else None, atr_target_multiplier=self.catalog.atr_target_multipliers[0] if layout.price_index in (2,3) else None, max_hold_bars=self.catalog.timeout_bars[layout.timeout_index])

@dataclass(frozen=True)
class StratumAssignment:
    stratum_id: str; size: int; quota: int; multiplier: int; offset: int

@dataclass(frozen=True)
class FrontierAssignment:
    candidate_space_hash: str; candidate_space_algorithm_version: str; frontier_seed: str; source_ticker: str; start_slot: int; attempt_count: int; strata: tuple[StratumAssignment,...]; stratum_multiplier: int; stratum_offset: int; algorithm_version: str = _FRONTIER_VERSION; stratification_revision: str = _STRATIFICATION_VERSION; assignment_hash: str = field(init=False)
    def __post_init__(self) -> None:
        if self.start_slot < 0 or self.attempt_count <= 0 or not self.frontier_seed or not self.source_ticker: raise ValueError("invalid frontier assignment")
        material={"space":self.candidate_space_hash,"version":self.candidate_space_algorithm_version,"seed":self.frontier_seed,"ticker":self.source_ticker,"start":self.start_slot,"count":self.attempt_count,"strata":[item.__dict__ for item in self.strata],"stratum_multiplier":self.stratum_multiplier,"stratum_offset":self.stratum_offset,"algorithm":self.algorithm_version,"stratification":self.stratification_revision}; object.__setattr__(self,"assignment_hash",hashlib.sha256(canonical_json(material).encode()).hexdigest())

@dataclass(frozen=True)
class DiscoveryResult:
    state: str
    frontier_size: int
    chain_attempted_count: int
    next_slot: int
    uncommitted_slot: int | None
    unsearched_count: int
    assigned_candidate_indices: tuple[int, ...]
    frozen_rulebook_ids: tuple[str, ...]
    outcomes: tuple[tuple[int, str], ...]
    evaluations: tuple[RulebookEvaluation, ...]

def candidate_space(catalog: CatalogRevision) -> CandidateSpace: return CandidateSpace(catalog)
def assign_frontier(space: CandidateSpace, *, frontier_seed: str, source_ticker: str, start_slot: int, budget: SearchBudget) -> FrontierAssignment:
    if start_slot < 0 or start_slot+budget.attempt_count > space.size: raise ValueError("frontier window must not wrap CandidateSpace")
    layouts=space.layouts; stratum_multiplier, stratum_offset = _affine("|".join((frontier_seed,space.candidate_space_hash,source_ticker,"stratum-order",_FRONTIER_VERSION)),len(layouts)); quotas=[0]*len(layouts)
    for slot in range(start_slot, start_slot + budget.attempt_count): quotas[(stratum_multiplier*slot+stratum_offset)%len(layouts)]+=1
    strata=[]
    for layout,quota in zip(layouts,quotas):
        a,b=_affine("|".join((frontier_seed,space.candidate_space_hash,source_ticker,layout.stratum_id,_FRONTIER_VERSION)),layout.size); strata.append(StratumAssignment(layout.stratum_id,layout.size,quota,a,b))
    return FrontierAssignment(space.candidate_space_hash,space.candidate_space_algorithm_version,frontier_seed,source_ticker,start_slot,budget.attempt_count,tuple(strata),stratum_multiplier,stratum_offset)
def scheduled_candidates(space: CandidateSpace, assignment: FrontierAssignment) -> Iterator[tuple[int,str,int,RulebookDefinition]]:
    if assignment.candidate_space_hash != space.candidate_space_hash or assignment.candidate_space_algorithm_version != space.candidate_space_algorithm_version: raise ValueError("frontier assignment does not match CandidateSpace")
    layouts={item.stratum_id:item for item in space.layouts}
    for stratum in assignment.strata:
        if math.gcd(stratum.multiplier,stratum.size)!=1 and stratum.size != 1: raise ValueError("non-coprime multiplier")
    count = len(assignment.strata)
    if math.gcd(assignment.stratum_multiplier, count) != 1 and count != 1: raise ValueError("non-coprime stratum multiplier")
    inverse = pow(assignment.stratum_multiplier, -1, count) if count != 1 else 0
    for global_slot in range(assignment.start_slot, assignment.start_slot + assignment.attempt_count):
        stratum_index = (assignment.stratum_multiplier * global_slot + assignment.stratum_offset) % count
        stratum = assignment.strata[stratum_index]
        layout = layouts[stratum.stratum_id]
        first_slot = (inverse * (stratum_index - assignment.stratum_offset)) % count if count != 1 else 0
        local = (stratum.multiplier * ((global_slot - first_slot) // count) + stratum.offset) % stratum.size
        canonical = layout.base + local
        yield global_slot, stratum.stratum_id, canonical, space.definition_at(canonical)

def discover_and_evaluate(snapshot: HistorySnapshot, features: FeatureResolution, space: CandidateSpace, assignment: FrontierAssignment, *, monotonic: object, split: EvaluationSplit | None = None, execution_contract: ExecutionContract | None = None, phase_observer: Callable[[SlotPhaseTiming | WindowPhaseTiming], None] | None = None) -> DiscoveryResult:
    """Evaluate only frozen slots; deadline leaves current slot uncommitted."""
    if not isinstance(snapshot, HistorySnapshot) or not isinstance(features, FeatureResolution): raise ValueError("discovery requires HistorySnapshot and FeatureResolution")
    if not callable(monotonic): raise ValueError("monotonic must be callable")
    if phase_observer is not None and not callable(phase_observer): raise ValueError("phase_observer must be callable or None")
    observe = (lambda _event: None) if phase_observer is None else phase_observer
    split = make_evaluation_split(snapshot) if split is None else split
    execution_contract = ExecutionContract() if execution_contract is None else execution_contract
    if not isinstance(split, EvaluationSplit) or not isinstance(execution_contract, ExecutionContract):
        raise ValueError("discovery requires frozen split and execution contract")
    attempted=[]; frozen=[]; outcomes=[]; evaluations=[]

    def exhausted(slot: int) -> DiscoveryResult:
        """Report a global cursor; current-window attempts are not the chain count."""

        return DiscoveryResult(
            "time_budget_exhausted",
            space.size,
            slot,
            slot,
            slot,
            space.size - slot,
            tuple(attempted),
            tuple(frozen),
            tuple(outcomes),
            tuple(evaluations),
        )

    for slot, _, canonical, definition in scheduled_candidates(space, assignment):
        if float(monotonic()) >= 16_200:
            return exhausted(slot)
        entry_started = time.monotonic()
        entry = compose_entry_mask(features.store, definition)
        observe(
            SlotPhaseTiming(
                slot,
                "entry_mask",
                max(0.0, time.monotonic() - entry_started),
            )
        )
        train_entries = int(entry[split.training.start_ordinal:split.training.end_ordinal+1].sum())
        attempted.append(canonical)
        if train_entries < 12:
            outcomes.append((slot, "training_entry_upper_bound")); continue
        technical = compose_technical_exit_mask(features.store, definition)
        stop = lambda: float(monotonic()) >= 17_700
        training_started = time.monotonic()
        train = execute_rulebook(features.store, entry, technical, definition, split.training, should_stop=stop)
        observe(
            SlotPhaseTiming(
                slot,
                "training",
                max(0.0, time.monotonic() - training_started),
            )
        )
        if isinstance(train, ExecutionInterrupted):
            attempted.pop(); return exhausted(slot)
        train_metrics = partition_metrics(train)
        if train_metrics.n < 12 or train_metrics.win_rate is None or train_metrics.win_rate < 65 or train_metrics.mean_return_pct is None or train_metrics.mean_return_pct < 15:
            outcomes.append((slot, "training_threshold")); continue
        frozen.append(rulebook_id(definition))
        test_started = time.monotonic()
        test = execute_rulebook(features.store, entry, technical, definition, split.test, should_stop=stop)
        observe(
            SlotPhaseTiming(
                slot,
                "test",
                max(0.0, time.monotonic() - test_started),
            )
        )
        if isinstance(test, ExecutionInterrupted):
            attempted.pop(); frozen.pop(); return exhausted(slot)
        test_metrics = partition_metrics(test)
        evaluations.append(RulebookEvaluation(definition, snapshot.ticker, features.plan.snapshot, space.catalog.catalog_hash, split, execution_contract, features.plan.build_contract, features.plan.profile, features.receipt, train_metrics, test_metrics, training_trades=train, test_trades=test))
        outcomes.append((slot, "qualified" if qualifies(train_metrics, test_metrics) else "test_threshold"))
    next_slot = assignment.start_slot + assignment.attempt_count
    state = "frontier_exhausted_no_qualified_candidate" if next_slot == space.size else "no_qualified_candidate_within_budget"
    return DiscoveryResult(state, space.size, next_slot, next_slot, None, space.size-next_slot, tuple(attempted), tuple(frozen), tuple(outcomes), tuple(evaluations))

__all__=["CandidateSpace","DiscoveryResult","FrontierAssignment","SearchBudget","StratumAssignment","assign_frontier","candidate_space","discover_and_evaluate","scheduled_candidates"]
