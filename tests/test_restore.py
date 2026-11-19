"""Tests for the greedy restoration planner.

All MW figures below are measured values from the planner itself
(see BUILD_REPORT.md); the tests pin the behaviour, not a target the
planner was tuned to hit.
"""

import copy

import pytest

from flisr.isolate import Fault
from flisr.network import load_case, synthetic_feeder
from flisr.restore import plan_restoration
from flisr.topology import is_radial_forest


def _final_topology_is_radial(net, result):
    """Rebuild the final switching state and check it has no loops."""
    work = copy.deepcopy(net)
    for line in result.isolation.opened_lines:
        work.line.at[line, "in_service"] = False
    for step in result.steps:
        if step.accepted:
            work.line.at[step.tie, "in_service"] = True
    radial, reason = is_radial_forest(work)
    assert radial, reason


def _no_forbidden_line_closed(result):
    forbidden = set(result.isolation.forbidden_lines)
    closed = {s.tie for s in result.steps if s.accepted}
    assert closed & forbidden == set()


def test_demo_fault_restores_all_outage_load():
    net = load_case("case33")
    result = plan_restoration(net, [Fault(line=5)])  # line 6 (6-7)
    assert result.restored_load_mw == pytest.approx(1.075, abs=1e-3)
    assert result.restored_of_outage_pct == pytest.approx(100.0, abs=1e-6)
    assert result.shed_load_mw == 0.0
    assert result.n_operations == 1
    assert result.steps[0].tie_1based == 35  # tie (12-22): best min voltage
    assert result.final_min_vm_pu == pytest.approx(0.9263, abs=1e-4)
    assert result.final_loss_kw == pytest.approx(168.20, abs=0.05)
    _final_topology_is_radial(net, result)
    _no_forbidden_line_closed(result)


def test_best_tie_beats_first_tie_on_case33_line25():
    # Fault line 25: tie 36 restores 0.24 MW after shedding, tie 37 the
    # full 0.92 MW with no shedding. The planner must pick tie 37.
    net = load_case("case33")
    result = plan_restoration(net, [Fault(line=24)])
    assert result.restored_load_mw == pytest.approx(0.920, abs=1e-3)
    assert result.restored_of_outage_pct == pytest.approx(100.0, abs=1e-6)
    assert result.steps[0].tie_1based == 37
    assert result.shed_load_mw == 0.0


def test_shedding_restores_what_fits_on_case33_line2():
    net = load_case("case33")
    result = plan_restoration(net, [Fault(line=1)])
    assert result.restored_load_mw == pytest.approx(1.455, abs=1e-3)
    assert result.shed_load_mw == pytest.approx(1.800, abs=1e-3)
    assert result.restored_of_outage_pct == pytest.approx(44.7, abs=0.1)
    assert result.final_min_vm_pu >= 0.90
    _final_topology_is_radial(net, result)
    _no_forbidden_line_closed(result)


def test_case69_fault_sheds_the_big_load():
    net = load_case("case69")
    result = plan_restoration(net, [Fault(line=5)])  # line 6 (6-7)
    assert result.restored_load_mw == pytest.approx(1.430, abs=1e-3)
    assert result.restored_of_outage_pct == pytest.approx(53.5, abs=0.1)
    assert result.steps[0].shed_buses == [61]  # the 1.244 MW load at bus 61
    assert result.shed_load_mw == pytest.approx(1.244, abs=1e-3)


def test_feeder_head_fault_cannot_be_restored():
    # Fault line 1 (1-2): every tie has both ends in the outage area,
    # so no tie can re-energize anything from this single-source feeder.
    net = load_case("case33")
    result = plan_restoration(net, [Fault(line=0)])
    assert result.restored_load_mw == 0.0
    assert result.steps == []
    assert result.unrestored_load_mw == pytest.approx(3.715, abs=1e-9)


def test_lateral_without_tie_cannot_be_restored():
    # Fault line 28 (3-28) on case69: the 28-35 lateral has no tie.
    net = load_case("case69")
    result = plan_restoration(net, [Fault(line=27)])
    assert result.restored_load_mw == 0.0
    assert result.steps == []
    assert result.unrestored_load_mw == pytest.approx(0.066, abs=1e-3)


def test_strict_voltage_band_rejects_everything_on_case33():
    # The healthy IEEE 33-bus case already sits at 0.9131 p.u., below
    # 0.95: with v_min=0.95 no tie can be accepted. This is why the
    # default band is 0.90-1.05 p.u.
    net = load_case("case33")
    result = plan_restoration(net, [Fault(line=5)], v_min=0.95)
    assert result.restored_load_mw == 0.0
    assert result.steps == []
    assert len(result.skipped) == 3  # ties 33, 35, 36 reach the outage area


def test_priority_protects_critical_load_on_case69():
    net = load_case("case69")
    plain = plan_restoration(net, [Fault(line=5)])
    assert plain.steps[0].shed_buses == [61]
    prio = plan_restoration(net, [Fault(line=5)], priorities={60: 10.0})
    # Bus 61 (0-based 60) is now shed last: it stays on, other loads go.
    assert 61 not in prio.steps[0].shed_buses
    assert prio.restored_load_mw == pytest.approx(2.043, abs=1e-3)
    assert prio.restored_of_outage_pct == pytest.approx(76.4, abs=0.1)
    assert prio.restored_load_mw > plain.restored_load_mw


def test_priority_shedding_single_tie():
    # Synthetic feeder with only one tie (tie 11 removed): fault line 2
    # with a strict 0.995 p.u. floor forces shedding. Without priorities
    # the largest loads go first; with bus 3 critical (weight 10) the
    # critical load stays on and the low-priority loads are shed.
    net = synthetic_feeder()
    net.line = net.line.drop(index=10)
    plain = plan_restoration(net, [Fault(line=1)], v_min=0.995)
    assert plain.steps[0].shed_buses == [3, 4]
    assert plain.restored_load_mw == pytest.approx(0.250, abs=1e-3)
    prio = plan_restoration(net, [Fault(line=1)], priorities={2: 10.0}, v_min=0.995)
    assert prio.steps[0].shed_buses == [4, 5, 6]
    assert prio.restored_load_mw == pytest.approx(0.200, abs=1e-3)
    assert 3 in prio.steps[0].restored_buses  # critical bus 3 stays on


def test_loading_limit_forces_shedding():
    # Both ties rated 0.02 kA: closing a tie with the full 0.6 MW would
    # load it to ~150%, so the largest load must be shed first.
    net = synthetic_feeder()
    net.line.at[9, "max_i_ka"] = 0.02
    net.line.at[10, "max_i_ka"] = 0.02
    result = plan_restoration(net, [Fault(line=1)])
    assert result.restored_load_mw == pytest.approx(0.400, abs=1e-3)
    assert result.steps[0].shed_buses == [3]
    assert result.steps[0].max_loading_pct <= 100.0
    assert result.steps[0].max_loading_pct == pytest.approx(96.3, abs=0.5)


def test_multi_fault_small_feeder_restores_in_two_steps():
    net = synthetic_feeder()
    result = plan_restoration(net, [Fault(line=1), Fault(line=8)])
    assert result.restored_of_outage_pct == pytest.approx(100.0, abs=1e-6)
    assert [s.tie_1based for s in result.steps] == [11, 10]
    assert result.isolation.forbidden_lines == [1, 8]
    _final_topology_is_radial(net, result)
    _no_forbidden_line_closed(result)


def test_multi_fault_case33_respects_both_isolations():
    net = load_case("case33")
    result = plan_restoration(net, [Fault(line=5), Fault(line=17)])
    assert result.isolation.deenergized_buses_1based == list(range(7, 23))
    assert result.restored_load_mw == pytest.approx(0.345, abs=1e-3)
    assert result.restored_of_outage_pct == pytest.approx(24.0, abs=0.1)
    _final_topology_is_radial(net, result)
    _no_forbidden_line_closed(result)


def test_input_network_not_modified():
    net = load_case("case33")
    before = net.line.in_service.copy()
    plan_restoration(net, [Fault(line=5)])
    assert (net.line.in_service == before).all()
    assert (net.bus.in_service).all()
    assert (net.load.in_service).all()
