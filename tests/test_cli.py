"""End-to-end CLI tests."""

import json

import pytest

from flisr.cli import main


def test_demo(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "1.075 / 3.715 MW" in out
    assert "100.0% of outage" in out
    assert "close tie 35" in out


def test_restore_case33(capsys):
    assert main(["restore", "--case", "33", "--fault-line", "6"]) == 0
    out = capsys.readouterr().out
    assert "case33 restoration" in out
    assert "close tie 35" in out


def test_restore_with_priority_and_json(tmp_path, capsys):
    target = tmp_path / "result.json"
    assert (
        main(
            [
                "restore",
                "--case",
                "69",
                "--fault-line",
                "6",
                "--priority",
                "61:10",
                "--json",
                str(target),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "2.043 / 3.802 MW" in out
    assert f"wrote {target}" in out
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["restored_load_mw"] == pytest.approx(2.043, abs=1e-3)
    assert data["shed_buses_1based"] == [11, 12, 21, 64]
    assert 61 not in data["shed_buses_1based"]


def test_restore_multi_fault(capsys):
    assert (
        main(
            [
                "restore",
                "--case",
                "33",
                "--fault-line",
                "6",
                "--fault-line",
                "18",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "0.345 / 3.715 MW" in out


def test_unknown_case_returns_2(capsys):
    assert main(["restore", "--case", "nope", "--fault-line", "6"]) == 2
    assert "unknown case" in capsys.readouterr().err


def test_no_fault_returns_2(capsys):
    assert main(["restore", "--case", "33"]) == 2
    assert "no fault given" in capsys.readouterr().err


def test_bad_priority_returns_2(capsys):
    assert (
        main(
            [
                "restore",
                "--case",
                "33",
                "--fault-line",
                "6",
                "--priority",
                "18",
            ]
        )
        == 2
    )
    assert "bad --priority" in capsys.readouterr().err


def test_demo_json(tmp_path, capsys):
    target = tmp_path / "demo.json"
    assert main(["demo", "--json", str(target)]) == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["restored_of_outage_pct"] == pytest.approx(100.0, abs=1e-9)
