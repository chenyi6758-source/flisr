"""Plain-text and JSON reporting of restoration results."""

from __future__ import annotations

import json

from .restore import RestorationResult
from .topology import switch_label


def _shed_buses(result: RestorationResult) -> list[int]:
    """Buses whose load was shed during restoration, 1-based, sorted."""
    shed: set[int] = set()
    for step in result.steps:
        if step.accepted:
            shed |= set(step.shed_buses)
    return sorted(shed)


def format_report(net, result: RestorationResult) -> str:
    """Full human-readable report for one restoration run."""
    iso = result.isolation
    fault_labels = [
        switch_label(net, f.line) if f.line is not None else f"bus {f.bus + 1}"
        for f in result.faults
    ]
    lines = [
        f"{result.case or 'network'} restoration: "
        f"{result.restored_load_mw:.3f} / {result.total_load_mw:.3f} MW "
        f"restored ({result.restored_pct:.1f}% of system, "
        f"{result.restored_of_outage_pct:.1f}% of outage load "
        f"{result.outage_load_mw:.3f} MW)",
        f"fault: {', '.join(fault_labels)}",
        f"isolated: switches opened "
        f"{', '.join(str(i + 1) for i in iso.opened_lines)}; "
        f"de-energized buses {iso.deenergized_buses_1based}",
        f"loss:        {result.base_loss_kw:9.2f} kW (healthy) -> "
        f"{result.isolated_loss_kw:9.2f} kW (isolated) -> "
        f"{result.final_loss_kw:9.2f} kW (restored)",
        f"min voltage: {result.base_min_vm_pu:.4f} p.u. (healthy) -> "
        f"{result.isolated_min_vm_pu:.4f} p.u. (isolated) -> "
        f"{result.final_min_vm_pu:.4f} p.u. (restored)",
        f"max voltage: {result.final_max_vm_pu:.4f} p.u.; "
        f"max loading: {result.final_max_loading_pct:.1f}% "
        f"(limits {result.v_min:.2f}-{result.v_max:.2f} p.u., "
        f"<={result.max_loading_pct:.0f}%)",
        f"operations: {result.n_operations} tie closure(s); "
        f"load shed: {result.shed_load_mw:.3f} MW at buses {_shed_buses(result)}; "
        f"unrestored: {result.unrestored_load_mw:.3f} MW at buses "
        f"{result.unserved_buses_1based}",
        "switching sequence:",
    ]
    if not result.steps:
        lines.append("  (no tie switch could be closed)")
    for n, step in enumerate(result.steps, 1):
        if not step.accepted:
            continue
        lines.append(
            f"  {n}. close tie {step.tie_1based} "
            f"{switch_label(net, step.tie)}: restores buses "
            f"{step.restored_buses} "
            f"({step.restored_load_mw:.3f} MW)"
            + (
                f", sheds buses {step.shed_buses} ({step.shed_load_mw:.3f} MW)"
                if step.shed_buses
                else ""
            )
            + f"; min voltage {step.min_vm_pu:.4f} p.u., "
            f"max loading {step.max_loading_pct:.1f}%, "
            f"loss {step.loss_kw:.2f} kW [{step.reason}]"
        )
    if result.skipped:
        lines.append("skipped ties:")
        for step in result.skipped:
            lines.append(
                f"  - tie {step.tie_1based} "
                f"{switch_label(net, step.tie)}: {step.reason}"
            )
    lines.append(f"elapsed: {result.elapsed_s:.1f} s")
    return "\n".join(lines)


def result_to_dict(result: RestorationResult) -> dict:
    """JSON-serialisable view of a result."""
    iso = result.isolation
    return {
        "case": result.case,
        "faults": [
            {
                "line_1based": (f.line + 1) if f.line is not None else None,
                "bus_1based": (f.bus + 1) if f.bus is not None else None,
            }
            for f in result.faults
        ],
        "opened_lines_1based": iso.opened_lines_1based if iso else [],
        "deenergized_buses_1based": iso.deenergized_buses_1based if iso else [],
        "total_load_mw": result.total_load_mw,
        "outage_load_mw": result.outage_load_mw,
        "restored_load_mw": result.restored_load_mw,
        "restored_pct": result.restored_pct,
        "restored_of_outage_pct": result.restored_of_outage_pct,
        "shed_load_mw": result.shed_load_mw,
        "shed_buses_1based": _shed_buses(result),
        "unrestored_load_mw": result.unrestored_load_mw,
        "unrestored_buses_1based": result.unrestored_buses_1based,
        "base_loss_kw": result.base_loss_kw,
        "base_min_vm_pu": result.base_min_vm_pu,
        "isolated_loss_kw": result.isolated_loss_kw,
        "isolated_min_vm_pu": result.isolated_min_vm_pu,
        "final_loss_kw": result.final_loss_kw,
        "final_min_vm_pu": result.final_min_vm_pu,
        "final_max_vm_pu": result.final_max_vm_pu,
        "final_max_loading_pct": result.final_max_loading_pct,
        "v_min": result.v_min,
        "v_max": result.v_max,
        "max_loading_pct": result.max_loading_pct,
        "n_operations": result.n_operations,
        "elapsed_s": result.elapsed_s,
        "steps": [
            {
                "tie_1based": s.tie_1based,
                "accepted": s.accepted,
                "restored_buses_1based": s.restored_buses,
                "restored_load_mw": s.restored_load_mw,
                "shed_buses_1based": s.shed_buses,
                "shed_load_mw": s.shed_load_mw,
                "min_vm_pu": s.min_vm_pu,
                "max_loading_pct": s.max_loading_pct,
                "loss_kw": s.loss_kw,
                "reason": s.reason,
            }
            for s in result.steps
        ],
        "skipped": [
            {
                "tie_1based": s.tie_1based,
                "reason": s.reason,
            }
            for s in result.skipped
        ],
    }


def result_to_json(result: RestorationResult) -> str:
    """Return the result as a JSON string."""
    return json.dumps(result_to_dict(result), indent=2)
