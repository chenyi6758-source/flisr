"""Tests for the restoration report (text and JSON)."""

import json

import pytest

from flisr.isolate import Fault
from flisr.network import load_case
from flisr.report import format_report, result_to_dict, result_to_json
from flisr.restore import plan_restoration


def _demo_result():
    net = load_case("case33")
    result = plan_restoration(net, [Fault(line=5)])
    result.case = "case33"
    return net, result


def test_json_round_trip():
    net, result = _demo_result()
    data = json.loads(result_to_json(result))
    assert data == result_to_dict(result)
    assert data["case"] == "case33"
    assert data["restored_load_mw"] == pytest.approx(1.075, abs=1e-9)
    assert data["restored_of_outage_pct"] == pytest.approx(100.0, abs=1e-9)
    assert data["shed_load_mw"] == 0.0
    assert data["steps"][0]["tie_1based"] == 35
    assert data["steps"][0]["restored_buses_1based"] == list(range(7, 19))
    assert data["faults"] == [{"line_1based": 6, "bus_1based": None}]
    assert data["deenergized_buses_1based"] == list(range(7, 19))


def test_text_report_contains_key_numbers():
    net, result = _demo_result()
    text = format_report(net, result)
    assert "1.075 / 3.715 MW" in text
    assert "100.0% of outage" in text
    assert "line 6 (6-7)" in text
    assert "close tie 35" in text
    assert "202.68 kW (healthy)" in text
    assert "168.20 kW (restored)" in text
    assert "0.9263 p.u. (restored)" in text


def test_text_report_lists_shedding_and_skips():
    net = load_case("case69")
    result = plan_restoration(net, [Fault(line=5)])
    result.case = "case69"
    text = format_report(net, result)
    assert "sheds buses [61]" in text
    assert "1.244 MW" in text
    assert "unrestored: 1.244 MW at buses [61]" in text
