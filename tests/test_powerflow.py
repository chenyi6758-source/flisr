"""Tests for power-flow evaluation and the constraint checker."""

import pytest

from flisr.isolate import Fault, isolate_fault
from flisr.network import load_case, synthetic_feeder
from flisr.powerflow import PowerFlowResult, check_constraints, solve_power_flow


def _result(*, converged=True, min_vm=0.95, max_vm=1.0, loading=50.0):
    pf = PowerFlowResult()
    pf.converged = converged
    pf.min_vm_pu = min_vm
    pf.max_vm_pu = max_vm
    pf.min_vm_bus = 18
    pf.max_loading_pct = loading
    return pf


def test_checker_accepts_healthy_result():
    ok, violations = check_constraints(_result())
    assert ok and violations == []


def test_checker_rejects_low_voltage():
    ok, violations = check_constraints(_result(min_vm=0.89))
    assert not ok
    assert any("0.8900" in v and "below 0.90" in v for v in violations)


def test_checker_rejects_high_voltage():
    ok, violations = check_constraints(_result(max_vm=1.06))
    assert not ok
    assert any("above 1.05" in v for v in violations)


def test_checker_rejects_overloading():
    ok, violations = check_constraints(_result(loading=120.0))
    assert not ok
    assert any("120.0%" in v for v in violations)


def test_checker_rejects_non_converged():
    ok, violations = check_constraints(_result(converged=False))
    assert not ok
    assert violations == ["power flow did not converge"]


def test_checker_uses_given_band():
    # 0.93 p.u. fails a 0.95 floor but passes the 0.90 emergency floor.
    assert not check_constraints(_result(min_vm=0.93), v_min=0.95)[0]
    assert check_constraints(_result(min_vm=0.93), v_min=0.90)[0]


def test_power_flow_converges_on_islanded_network():
    net = load_case("case33")
    work, _ = isolate_fault(net, Fault(line=5))
    pf = solve_power_flow(work)
    assert pf.converged
    # Loss counts in-service load only: 3.715 MW total minus the 1.075 MW
    # outage leaves 2.640 MW served; the isolated loss is 93.09 kW.
    assert pf.loss_kw == pytest.approx(93.09, abs=0.05)
    assert pf.min_vm_pu == pytest.approx(0.9382, abs=1e-4)


def test_power_flow_on_synthetic_feeder():
    net = synthetic_feeder()
    pf = solve_power_flow(net)
    assert pf.converged
    assert pf.min_vm_pu == pytest.approx(0.9975, abs=1e-4)
