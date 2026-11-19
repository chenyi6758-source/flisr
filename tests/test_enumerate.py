"""Exhaustive-enumeration optimality check on the synthetic feeder."""

import pytest

from flisr.isolate import Fault
from flisr.network import synthetic_feeder
from flisr.restore import enumerate_restoration, plan_restoration


@pytest.mark.parametrize("fault_line_1based", [2, 3, 5])
def test_greedy_matches_enumeration_single_fault(fault_line_1based):
    net = synthetic_feeder()
    fault = [Fault(line=fault_line_1based - 1)]
    greedy = plan_restoration(net, fault)
    best = enumerate_restoration(net, fault)
    assert best["n_tried"] == 4  # 2 ties -> 2**2 combinations
    assert best["restored_mw"] == pytest.approx(greedy.restored_load_mw, abs=1e-9)
    assert greedy.restored_of_outage_pct == pytest.approx(100.0, abs=1e-6)


def test_greedy_matches_enumeration_multi_fault():
    net = synthetic_feeder()
    faults = [Fault(line=1), Fault(line=8)]  # lines 2 and 9 (1-based)
    greedy = plan_restoration(net, faults)
    best = enumerate_restoration(net, faults)
    assert best["n_tried"] == 4
    assert best["n_feasible"] == 4
    assert best["restored_mw"] == pytest.approx(0.700, abs=1e-9)
    assert best["restored_mw"] == pytest.approx(greedy.restored_load_mw, abs=1e-9)
    assert best["ties"] == [10, 11]


def test_enumeration_counts_infeasible_loop():
    # Fault line 2: closing both ties loops the outage area through
    # feeders A and B, so the {10, 11} combination is infeasible.
    net = synthetic_feeder()
    best = enumerate_restoration(net, [Fault(line=1)])
    assert best["n_tried"] == 4
    assert best["n_feasible"] == 3  # {}, {10}, {11} feasible; {10, 11} loops
    assert best["restored_mw"] == pytest.approx(0.600, abs=1e-9)
