"""Tests for the built-in cases and the synthetic teaching feeder."""

import pytest

from flisr.network import available_cases, case_source, load_case, synthetic_feeder
from flisr.powerflow import solve_power_flow
from flisr.topology import total_load_mw


def test_available_cases():
    assert available_cases() == ["case33", "case69", "small"]


def test_unknown_case():
    with pytest.raises(ValueError, match="unknown case"):
        load_case("case119")


def test_case33_structure_and_base_loss():
    net = load_case("case33")
    assert len(net.bus) == 33
    assert len(net.line) == 37
    assert len(net.load) == 32
    assert total_load_mw(net) == pytest.approx(3.715, abs=1e-9)
    open_lines = [i for i, s in net.line.in_service.items() if not bool(s)]
    assert open_lines == [32, 33, 34, 35, 36]  # the five tie switches
    pf = solve_power_flow(net)
    assert pf.converged
    # Literature (Baran & Wu 1989): ~202.7 kW.
    assert pf.loss_kw == pytest.approx(202.68, abs=0.05)
    assert pf.min_vm_pu == pytest.approx(0.9131, abs=1e-4)
    assert pf.max_loading_pct < 0.01  # max_i_ka = 99999: loading is vacuous here


def test_case69_structure_and_base_loss():
    net = load_case("case69")
    assert len(net.bus) == 69
    assert len(net.line) == 73
    assert total_load_mw(net) == pytest.approx(3.802, abs=1e-3)
    open_lines = [i for i, s in net.line.in_service.items() if not bool(s)]
    assert open_lines == [68, 69, 70, 71, 72]  # the five tie switches
    pf = solve_power_flow(net)
    assert pf.converged
    # Literature (Baran & Wu 1989): ~225.0 kW.
    assert pf.loss_kw == pytest.approx(224.99, abs=0.05)
    assert pf.min_vm_pu == pytest.approx(0.9092, abs=1e-4)


def test_case_aliases():
    assert len(load_case("33").bus) == 33
    assert len(load_case("69").bus) == 69
    assert len(load_case("case33bw").bus) == 33
    assert "Baran" in case_source("case33")


def test_synthetic_feeder_structure():
    net = synthetic_feeder()
    assert len(net.bus) == 10
    assert len(net.line) == 11
    assert total_load_mw(net) == pytest.approx(1.3, abs=1e-9)
    open_lines = [i for i, s in net.line.in_service.items() if not bool(s)]
    assert open_lines == [9, 10]  # the two tie switches
    pf = solve_power_flow(net)
    assert pf.converged
    assert pf.loss_kw == pytest.approx(1.79, abs=0.05)
    assert pf.min_vm_pu == pytest.approx(0.9975, abs=1e-4)
    # Realistic ratings here, unlike the IEEE cases.
    assert 0 < pf.max_loading_pct < 100
