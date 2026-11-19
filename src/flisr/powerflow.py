"""Exact power-flow evaluation of a (possibly islanded) topology.

The power flow is run on the network as given: buses that are out of
service (``bus.in_service == False``) are excluded by pandapower, so a
network with a de-energized zone converges on the energized part only
(verified: ``runpp`` with ``bfsw`` converges and reports ``NaN``
voltages for the out-of-service buses). Losses are computed from the
in-service loads only, never from loads sitting on dead buses.

The constraint check is a pure function of the result, so it can be
unit-tested directly with fabricated results.
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pandapower as pp


class PowerFlowResult:
    """Outcome of one exact power-flow evaluation.

    Attributes
    ----------
    converged:
        Whether the power flow solved.
    loss_kw:
        Total active-power loss (ext-grid injection minus in-service
        load), in kW. ``inf`` when not converged.
    min_vm_pu / max_vm_pu:
        Minimum / maximum bus voltage magnitude over in-service buses,
        in p.u. (``nan`` if not converged).
    min_vm_bus:
        1-based bus number of the minimum voltage.
    max_loading_pct:
        Maximum line loading over in-service lines, in percent of
        ``max_i_ka``. ``nan`` when there is no in-service line.

    """

    def __init__(self) -> None:
        self.converged = False
        self.loss_kw = math.inf
        self.min_vm_pu = math.nan
        self.max_vm_pu = math.nan
        self.min_vm_bus = -1
        self.max_loading_pct = math.nan


def solve_power_flow(net) -> PowerFlowResult:
    """Evaluate the topology of ``net`` (not modified) and return it.

    Tries the backward-forward sweep first (fast on radial networks)
    and falls back to Newton-Raphson. Anything that does not converge
    is reported as non-converged instead of raising.
    """
    result = PowerFlowResult()
    work = copy.deepcopy(net)
    converged = False
    for algorithm in ("bfsw", "nr"):
        try:
            pp.runpp(work, algorithm=algorithm, init="flat", numba=False)
            converged = bool(work.converged)
        except Exception:  # noqa: BLE001 - any solver failure is "no result"
            converged = False
        if converged:
            break
    if not converged:
        return result

    result.converged = True
    p_in = float(np.sum(work.res_ext_grid.p_mw.values))
    in_service_buses = set(work.bus.index[work.bus.in_service])
    p_load = 0.0
    for _, row in work.load.iterrows():
        if bool(row.in_service) and int(row.bus) in in_service_buses:
            p_load += float(row.p_mw)
    result.loss_kw = (p_in - p_load) * 1000.0
    vm = work.res_bus.vm_pu
    vm_in_service = vm[[int(b) in in_service_buses for b in vm.index]]
    result.min_vm_pu = float(vm_in_service.min())
    result.max_vm_pu = float(vm_in_service.max())
    result.min_vm_bus = int(vm_in_service.idxmin()) + 1
    if len(work.res_line):
        loading = work.res_line.loading_percent
        loading_in_service = loading[
            [bool(work.line.at[i, "in_service"]) for i in loading.index]
        ]
        if len(loading_in_service):
            result.max_loading_pct = float(loading_in_service.max())
        else:
            result.max_loading_pct = 0.0
    else:
        result.max_loading_pct = 0.0
    return result


def evaluate(net) -> PowerFlowResult:
    """Evaluate the topology of ``net`` without modifying it."""
    return solve_power_flow(net)


def check_constraints(
    pf: PowerFlowResult,
    v_min: float = 0.90,
    v_max: float = 1.05,
    max_loading_pct: float = 100.0,
) -> tuple[bool, list[str]]:
    """Check a power-flow result against the restoration limits.

    A step is accepted only if the power flow converged, every
    in-service bus voltage lies inside ``[v_min, v_max]`` p.u., and no
    in-service line exceeds ``max_loading_pct`` percent of its rating.
    Returns ``(ok, violations)`` with one human-readable string per
    violated limit.
    """
    violations: list[str] = []
    if not pf.converged:
        return False, ["power flow did not converge"]
    if pf.min_vm_pu < v_min:
        violations.append(
            f"voltage {pf.min_vm_pu:.4f} p.u. at bus {pf.min_vm_bus} "
            f"below {v_min:.2f} p.u."
        )
    if pf.max_vm_pu > v_max:
        violations.append(f"voltage {pf.max_vm_pu:.4f} p.u. above {v_max:.2f} p.u.")
    if not math.isnan(pf.max_loading_pct) and pf.max_loading_pct > max_loading_pct:
        violations.append(
            f"line loading {pf.max_loading_pct:.1f}% above {max_loading_pct:.0f}%"
        )
    return (not violations), violations
