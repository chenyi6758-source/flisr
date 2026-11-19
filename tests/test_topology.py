"""Tests for the pure-Python topology helpers."""

from flisr.network import load_case, synthetic_feeder
from flisr.topology import (
    deenergized_buses,
    downstream_buses,
    energized_buses,
    is_radial_forest,
)


def test_base_case_is_radial_forest():
    for case in ("case33", "case69", "small"):
        net = load_case(case)
        radial, reason = is_radial_forest(net)
        assert radial, reason
        assert len(energized_buses(net)) == len(net.bus)
        assert deenergized_buses(net) == set()


def test_downstream_set_case33_line6():
    net = load_case("case33")
    # Line 6 (1-based) feeds buses 7-18 (1-based).
    downstream = {b + 1 for b in downstream_buses(net, 5)}
    assert downstream == set(range(7, 19))


def test_closing_a_tie_on_healthy_network_creates_loop():
    net = load_case("case33")
    net.line.at[32, "in_service"] = True  # tie 33 (8-21) on the healthy net
    radial, reason = is_radial_forest(net)
    assert not radial
    assert "loop" in reason


def test_islanded_zone_is_still_a_forest():
    net = load_case("case33")
    net.line.at[5, "in_service"] = False  # fault line 6: island buses 7-18
    radial, reason = is_radial_forest(net)
    assert radial, reason
    assert deenergized_buses(net) == {b - 1 for b in range(7, 19)}


def test_small_feeder_downstream():
    net = synthetic_feeder()
    downstream = {b + 1 for b in downstream_buses(net, 1)}  # line 2 (2-3)
    assert downstream == {3, 4, 5, 6}
