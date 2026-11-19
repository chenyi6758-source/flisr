"""Tests for fault isolation and the never-reclose safety invariant."""

import pytest

from flisr.isolate import Fault, isolate_fault, isolate_faults
from flisr.network import load_case
from flisr.topology import closed_line_indices


def test_line_fault_opens_branch_and_deenergizes_downstream():
    net = load_case("case33")
    work, result = isolate_fault(net, Fault(line=5))  # line 6 (6-7)
    assert result.opened_lines == [5]
    assert result.forbidden_lines == [5]
    assert result.deenergized_buses_1based == list(range(7, 19))
    assert result.isolated_buses_1based == list(range(7, 19))
    # The faulted branch stays open in the working network.
    assert 5 not in closed_line_indices(work)
    assert not bool(work.line.at[5, "in_service"])
    # The input network is not modified.
    assert bool(net.line.at[5, "in_service"])


def test_faulted_branch_is_never_a_restoration_candidate():
    from flisr.restore import _candidate_ties

    net = load_case("case33")
    work, result = isolate_fault(net, Fault(line=5))
    weights = {b: 1.0 for b in range(len(net.bus))}
    candidates = _candidate_ties(work, set(result.forbidden_lines), weights)
    ties = [c["tie"] for c in candidates]
    assert 5 not in ties


def test_bus_fault_opens_all_incident_lines():
    net = load_case("case33")
    work, result = isolate_fault(net, Fault(bus=5))  # bus 6 (0-based 5)
    # Bus 6 connects to lines 5 (5-6), 6 (6-7) and 25 (6-26), 0-based
    # 4, 5 and 24.
    assert result.opened_lines == [4, 5, 24]
    assert 6 in result.deenergized_buses_1based  # bus 6 itself (1-based)
    assert set(range(7, 19)) <= set(result.deenergized_buses_1based)
    assert set(range(26, 34)) <= set(result.deenergized_buses_1based)


def test_fault_on_open_switch_rejected():
    net = load_case("case33")
    with pytest.raises(ValueError, match="already open"):
        isolate_fault(net, Fault(line=32))  # tie 33 is open in the base case


def test_fault_requires_exactly_one_target():
    with pytest.raises(ValueError):
        Fault()
    with pytest.raises(ValueError):
        Fault(line=1, bus=2)


def test_multi_fault_respects_both_isolations():
    net = load_case("case33")
    work, result = isolate_faults(net, [Fault(line=5), Fault(line=17)])
    assert result.opened_lines == [5, 17]
    assert result.forbidden_lines == [5, 17]
    assert result.deenergized_buses_1based == list(range(7, 23))
    assert 5 not in closed_line_indices(work)
    assert 17 not in closed_line_indices(work)
