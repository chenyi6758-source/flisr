"""Greedy service restoration: close tie switches, best load first.

After isolation the de-energized buses form one or more components
(connected through their still-closed internal branches). A candidate
tie switch is an open line, never a faulted one, with exactly one end
energized: closing it re-energizes the whole de-energized component
on its dead end, without creating a loop. Candidates are ranked by
the priority-weighted load they would restore (per-load priority,
default weight 1.0; critical loads get a higher weight). Every
candidate is trial-closed and checked with an exact pandapower power
flow; the best feasible candidate -- most priority-weighted load
restored, then highest minimum voltage -- is accepted, and the rest
are recorded as skipped. Ranking by pre-check restorable load alone
would be misleading: two ties into the same outage area restore the
same load on paper, but one may need heavy shedding to satisfy the
voltage limit while the other needs none (on IEEE 33, fault line 25:
tie 36 restores 0.24 MW after shedding, tie 37 restores the full
0.92 MW; the planner picks tie 37).

After each tentative closure a pandapower power flow is run and the
result is checked against the voltage band and the line-loading limit.
If the step violates a limit, the lowest-priority restored loads are
shed one at a time (load ``in_service = False``; the bus stays
energized) and the check is repeated. If the step still violates with
every restored load shed, the tie is skipped and the next candidate
is tried. Radiality (no loops) is verified after every accepted step.

Voltage band default: 0.90-1.05 p.u. The IEEE 33-bus base case itself
has a minimum voltage of 0.9131 p.u., so the usual 0.95 p.u. normal
limit would reject even the healthy network; 0.90 p.u. is the
emergency-restoration floor used in FLISR studies. The band is a
parameter (``v_min`` / ``v_max``) and the CLI exposes it.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field

from .isolate import Fault, IsolationResult, isolate_faults
from .powerflow import check_constraints, solve_power_flow
from .topology import (
    components,
    deenergized_buses,
    energized_buses,
    is_radial_forest,
    line_endpoints,
    load_by_bus,
    open_line_indices,
    total_load_mw,
)

DEFAULT_V_MIN = 0.90
DEFAULT_V_MAX = 1.05
DEFAULT_MAX_LOADING_PCT = 100.0


@dataclass
class RestorationStep:
    """One accepted (or skipped) tie-switch operation.

    Bus/line numbers are 1-based in the readable fields.
    """

    tie: int  # 0-based line index of the tie switch
    accepted: bool
    restored_buses: list[int] = field(default_factory=list)  # 1-based
    restored_load_mw: float = 0.0
    shed_buses: list[int] = field(default_factory=list)  # 1-based
    shed_load_mw: float = 0.0
    min_vm_pu: float = float("nan")
    max_loading_pct: float = float("nan")
    loss_kw: float = float("nan")
    reason: str = ""

    @property
    def tie_1based(self) -> int:
        """Tie switch, 1-based line number."""
        return self.tie + 1


@dataclass
class RestorationResult:
    """Outcome of one restoration run."""

    case: str | None = None
    faults: list[Fault] = field(default_factory=list)
    isolation: IsolationResult | None = None
    steps: list[RestorationStep] = field(default_factory=list)
    skipped: list[RestorationStep] = field(default_factory=list)
    total_load_mw: float = 0.0
    outage_load_mw: float = 0.0
    restored_load_mw: float = 0.0
    shed_load_mw: float = 0.0
    unrestored_load_mw: float = 0.0
    base_loss_kw: float = float("nan")
    base_min_vm_pu: float = float("nan")
    isolated_loss_kw: float = float("nan")
    isolated_min_vm_pu: float = float("nan")
    final_loss_kw: float = float("nan")
    final_min_vm_pu: float = float("nan")
    final_max_vm_pu: float = float("nan")
    final_max_loading_pct: float = float("nan")
    elapsed_s: float = 0.0
    v_min: float = DEFAULT_V_MIN
    v_max: float = DEFAULT_V_MAX
    max_loading_pct: float = DEFAULT_MAX_LOADING_PCT

    @property
    def restored_pct(self) -> float:
        """Restored load as a percentage of total system load."""
        if self.total_load_mw <= 0:
            return 0.0
        return 100.0 * self.restored_load_mw / self.total_load_mw

    @property
    def restored_of_outage_pct(self) -> float:
        """Restored load as a percentage of the de-energized load.

        This is the FLISR headline metric: what fraction of the load
        that actually lost supply came back. ``restored_pct`` is
        relative to the whole system instead.
        """
        if self.outage_load_mw <= 0:
            return 100.0
        return 100.0 * self.restored_load_mw / self.outage_load_mw

    @property
    def unrestored_buses_1based(self) -> list[int]:
        """Buses still de-energized at the end, 1-based, sorted."""
        if self.isolation is None:
            return []
        restored: set[int] = set()
        for step in self.steps:
            if step.accepted:
                restored |= {b - 1 for b in step.restored_buses}
        dead = self.isolation.deenergized_buses - restored
        return sorted(b + 1 for b in dead)

    @property
    def unserved_buses_1based(self) -> list[int]:
        """Buses with no supply at the end, 1-based, sorted.

        Still de-energized buses plus buses whose load was shed (the
        bus is energized but its load is off). This is the list the
        ``unrestored: X MW at buses [...]`` report line uses.
        """
        shed: set[int] = set()
        for step in self.steps:
            if step.accepted:
                shed |= {b - 1 for b in step.shed_buses}
        return sorted(set(self.unrestored_buses_1based) | {b + 1 for b in shed})

    @property
    def n_operations(self) -> int:
        """Accepted tie closures (switching operations)."""
        return sum(1 for s in self.steps if s.accepted)


def _priorities_by_bus(priorities: dict[int, float] | None, net) -> dict[int, float]:
    """Per-bus priority weights, 0-based bus index -> weight (default 1.0)."""
    weights = {bus: 1.0 for bus in range(len(net.bus))}
    for bus, weight in (priorities or {}).items():
        if bus < 0 or bus >= len(net.bus):
            raise ValueError(f"priority given for unknown bus {bus + 1}")
        if weight <= 0:
            raise ValueError(f"priority weight for bus {bus + 1} must be > 0")
        weights[bus] = float(weight)
    return weights


def _candidate_ties(net, forbidden: set[int], weights: dict[int, float]) -> list[dict]:
    """Open, non-faulted lines joining an energized and a dead bus.

    Each candidate carries the dead component it would re-energize and
    the priority-weighted load of that component. A tie joining two
    energized buses would close a loop; a tie joining two dead
    components re-energizes nothing; neither is a candidate.
    """
    energized = energized_buses(net)
    endpoints = line_endpoints(net)
    comps = components(net)
    comp_of = {}
    for comp in comps:
        for bus in comp:
            comp_of[bus] = comp
    loads = load_by_bus(net)
    candidates = []
    for idx in open_line_indices(net):
        if idx in forbidden:
            continue  # safety invariant: never re-close a faulted branch
        f, t = endpoints[idx]
        f_live, t_live = f in energized, t in energized
        if f_live == t_live:
            continue
        dead_end = t if f_live else f
        comp = comp_of[dead_end]
        weighted = sum(weights[b] * loads.get(b, 0.0) for b in comp)
        candidates.append(
            {
                "tie": idx,
                "dead_component": comp,
                "restorable_mw": sum(loads.get(b, 0.0) for b in comp),
                "restorable_weighted_mw": weighted,
            }
        )
    candidates.sort(key=lambda c: (-c["restorable_weighted_mw"], c["tie"]))
    return candidates


def _set_component_in_service(net, component: set[int], in_service: bool) -> None:
    """Set buses and their loads of one component in/out of service."""
    for bus in component:
        net.bus.at[bus, "in_service"] = in_service
    for idx, row in net.load.iterrows():
        if int(row.bus) in component:
            net.load.at[idx, "in_service"] = in_service


def _set_bus_loads_in_service(net, bus: int, in_service: bool) -> None:
    """Set all loads on one bus in/out of service (the bus stays as is)."""
    for idx, row in net.load.iterrows():
        if int(row.bus) == bus:
            net.load.at[idx, "in_service"] = in_service


def _shed_order(component: set[int], loads: dict[int, float], weights) -> list[int]:
    """Buses of a component ordered for shedding: lowest priority first.

    Ties are broken by shedding the largest load first, so each shed
    operation removes as much violating load as possible.
    """
    return sorted(component, key=lambda b: (weights[b], -loads.get(b, 0.0)))


def _try_close_tie(
    work,
    cand: dict,
    loads: dict[int, float],
    weights: dict[int, float],
    v_min: float,
    v_max: float,
    max_loading_pct: float,
) -> tuple[object, RestorationStep]:
    """Trial-close one candidate tie on a copy of ``work``.

    Returns ``(trial net, step)``. The step is accepted when the
    post-closure power flow satisfies the limits, possibly after
    shedding the lowest-priority restored loads one at a time. The
    input network is not modified; the caller commits the trial net
    only when the step is the best accepted one of the round.
    """
    tie = cand["tie"]
    comp = cand["dead_component"]
    trial = copy.deepcopy(work)
    trial.line.at[tie, "in_service"] = True
    radial, reason = is_radial_forest(trial)
    if not radial:
        return trial, RestorationStep(tie=tie, accepted=False, reason=reason)
    # Energize the whole dead component through the tie.
    _set_component_in_service(trial, comp, True)
    pf = solve_power_flow(trial)
    ok, violations = check_constraints(pf, v_min, v_max, max_loading_pct)
    shed_buses: list[int] = []
    if not ok:
        # Shed the lowest-priority restored loads, one at a time,
        # re-checking after each shed.
        for bus in _shed_order(comp, loads, weights):
            if loads.get(bus, 0.0) <= 0:
                continue
            _set_bus_loads_in_service(trial, bus, False)
            shed_buses.append(bus)
            pf = solve_power_flow(trial)
            ok, violations = check_constraints(pf, v_min, v_max, max_loading_pct)
            if ok:
                break
    if not ok:
        return trial, RestorationStep(
            tie=tie,
            accepted=False,
            restored_buses=sorted(b + 1 for b in comp),
            reason="; ".join(violations),
        )
    restored_buses = [b for b in comp if b not in shed_buses]
    restored_mw = sum(loads.get(b, 0.0) for b in restored_buses)
    if shed_buses and restored_mw <= 0 and sum(loads.get(b, 0.0) for b in comp) > 0:
        # Closing a switch to restore nothing is not a restoration:
        # every restorable load had to be shed to satisfy the limits.
        detail = "; ".join(violations)
        return trial, RestorationStep(
            tie=tie,
            accepted=False,
            restored_buses=sorted(b + 1 for b in comp),
            reason="all restorable load would have to be shed"
            + (f" ({detail})" if detail else ""),
        )
    return trial, RestorationStep(
        tie=tie,
        accepted=True,
        restored_buses=sorted(b + 1 for b in restored_buses),
        restored_load_mw=restored_mw,
        shed_buses=sorted(b + 1 for b in shed_buses),
        shed_load_mw=sum(loads.get(b, 0.0) for b in shed_buses),
        min_vm_pu=pf.min_vm_pu,
        max_loading_pct=pf.max_loading_pct,
        loss_kw=pf.loss_kw,
        reason="ok" if not shed_buses else "ok after shedding",
    )


def plan_restoration(
    net,
    faults: list[Fault],
    priorities: dict[int, float] | None = None,
    v_min: float = DEFAULT_V_MIN,
    v_max: float = DEFAULT_V_MAX,
    max_loading_pct: float = DEFAULT_MAX_LOADING_PCT,
) -> RestorationResult:
    """Plan and execute greedy restoration for ``faults`` on ``net``.

    Parameters
    ----------
    net:
        Pandapower network in its healthy base state (all sectionalizing
        switches closed, ties open). Not modified.
    faults:
        One or more :class:`flisr.isolate.Fault` values (0-based indices).
    priorities:
        Optional map 0-based bus index -> priority weight (default 1.0).
        Higher weight means the load is restored earlier and shed later.
    v_min, v_max:
        Accepted voltage band in p.u. (default 0.90-1.05; see module
        docstring for why the lower bound is not 0.95).
    max_loading_pct:
        Accepted line-loading limit in percent of ``max_i_ka``.

    Returns a :class:`RestorationResult` with the step-by-step switching
    sequence, per-step power-flow checks, and restored/unrestored load.

    """
    started = time.perf_counter()
    result = RestorationResult(
        faults=list(faults),
        v_min=v_min,
        v_max=v_max,
        max_loading_pct=max_loading_pct,
    )
    result.total_load_mw = total_load_mw(net)
    weights = _priorities_by_bus(priorities, net)

    base_pf = solve_power_flow(net)
    result.base_loss_kw = base_pf.loss_kw
    result.base_min_vm_pu = base_pf.min_vm_pu

    work, isolation = isolate_faults(net, faults)
    result.isolation = isolation
    forbidden = set(isolation.forbidden_lines)

    isolated_pf = solve_power_flow(work)
    result.isolated_loss_kw = isolated_pf.loss_kw
    result.isolated_min_vm_pu = isolated_pf.min_vm_pu

    loads = load_by_bus(net)
    restored_load = 0.0
    shed_load = 0.0
    result.outage_load_mw = sum(loads.get(b, 0.0) for b in isolation.deenergized_buses)
    skipped_ties: set[int] = set()

    while True:
        dead = deenergized_buses(work)
        if not dead:
            break
        candidates = _candidate_ties(work, forbidden, weights)
        if not candidates:
            break
        # Trial-close every candidate and accept the best feasible one:
        # most priority-weighted load restored, then highest minimum
        # voltage, then lowest tie number.
        best = None
        for cand in candidates:
            if not cand["dead_component"] & dead:
                continue
            trial, step = _try_close_tie(
                work, cand, loads, weights, v_min, v_max, max_loading_pct
            )
            if not step.accepted:
                if step.tie not in skipped_ties:
                    skipped_ties.add(step.tie)
                    result.skipped.append(step)
                continue
            weighted = sum(
                weights[b] * loads.get(b, 0.0)
                for b in cand["dead_component"]
                if (b + 1) not in step.shed_buses
            )
            score = (weighted, step.restored_load_mw, step.min_vm_pu, -step.tie)
            if best is None or score > best[0]:
                best = (score, step, trial)
        if best is None:
            break
        _, step, work = best
        result.steps.append(step)
        restored_load += step.restored_load_mw
        shed_load += step.shed_load_mw

    final_pf = solve_power_flow(work)
    result.restored_load_mw = restored_load
    result.shed_load_mw = shed_load
    result.unrestored_load_mw = (
        sum(loads.get(b, 0.0) for b in deenergized_buses(work)) + shed_load
    )
    result.final_loss_kw = final_pf.loss_kw
    result.final_min_vm_pu = final_pf.min_vm_pu
    result.final_max_vm_pu = final_pf.max_vm_pu
    result.final_max_loading_pct = final_pf.max_loading_pct
    result.elapsed_s = time.perf_counter() - started
    return result


def enumerate_restoration(
    net,
    faults: list[Fault],
    priorities: dict[int, float] | None = None,
    v_min: float = DEFAULT_V_MIN,
    v_max: float = DEFAULT_V_MAX,
    max_loading_pct: float = DEFAULT_MAX_LOADING_PCT,
) -> dict:
    """Exhaustively enumerate tie-switch combinations for small networks.

    Every subset of the open (non-faulted) tie switches is tried: the
    subset is closed, the power flow is run, and the subset is feasible
    only if the topology is a radial forest and the voltage/loading
    limits hold. Returns the best feasible restored load (MW and
    weighted MW), the winning tie set, and the number of combinations
    tried. Used to measure the greedy planner's optimality gap.
    """
    weights = _priorities_by_bus(priorities, net)
    loads = load_by_bus(net)
    work, isolation = isolate_faults(net, faults)
    forbidden = set(isolation.forbidden_lines)
    ties = [i for i in open_line_indices(work) if i not in forbidden]
    from itertools import combinations

    best = {
        "restored_mw": -1.0,
        "restored_weighted_mw": -1.0,
        "ties": [],
        "n_tried": 0,
        "n_feasible": 0,
    }
    for r in range(len(ties) + 1):
        for subset in combinations(ties, r):
            best["n_tried"] += 1
            trial = copy.deepcopy(work)
            for tie in subset:
                trial.line.at[tie, "in_service"] = True
            radial, _ = is_radial_forest(trial)
            if not radial:
                continue
            live = energized_buses(trial)
            _set_component_in_service(trial, live, True)
            pf = solve_power_flow(trial)
            ok, _ = check_constraints(pf, v_min, v_max, max_loading_pct)
            if not ok:
                continue
            best["n_feasible"] += 1
            restored = sum(loads.get(b, 0.0) for b in live)
            restored -= sum(loads.get(b, 0.0) for b in energized_buses(work))
            weighted = sum(weights[b] * loads.get(b, 0.0) for b in live)
            weighted -= sum(
                weights[b] * loads.get(b, 0.0) for b in energized_buses(work)
            )
            if weighted > best["restored_weighted_mw"] + 1e-9:
                best.update(
                    restored_mw=restored,
                    restored_weighted_mw=weighted,
                    ties=[t + 1 for t in subset],
                )
    return best
