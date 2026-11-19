"""Fault isolation: open the switches bounding the faulted section.

Given a faulted branch (line index) or a faulted bus, the faulted
section is isolated by opening the faulted branch itself -- every
line is a sectionalizing switch in this model -- or, for a bus fault,
every closed line incident to the faulted bus. The de-energized set is
every bus that loses its closed-branch path to a slack bus.

Safety invariant: a faulted branch is recorded in ``forbidden_lines``
and is never closed again by the restoration planner. Isolation
returns a new network; the input is not modified.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .topology import (
    closed_line_indices,
    deenergized_buses,
    downstream_buses,
    line_endpoints,
)


@dataclass
class Fault:
    """One fault, as given by the user (0-based indices).

    Exactly one of ``line`` / ``bus`` must be set. ``line`` is a
    faulted branch; ``bus`` is a faulted bus (all incident closed
    lines are opened).
    """

    line: int | None = None
    bus: int | None = None

    def __post_init__(self) -> None:
        if (self.line is None) == (self.bus is None):
            raise ValueError("exactly one of line / bus must be set")


@dataclass
class IsolationResult:
    """Outcome of isolating one or more faults.

    All bus/line numbers in the human-readable fields are 1-based;
    the ``*_0based`` sets are 0-based pandapower indices.
    """

    faults: list[Fault] = field(default_factory=list)
    opened_lines: list[int] = field(default_factory=list)  # 0-based
    forbidden_lines: list[int] = field(default_factory=list)  # 0-based
    isolated_buses: set[int] = field(default_factory=set)  # 0-based
    deenergized_buses: set[int] = field(default_factory=set)  # 0-based

    @property
    def opened_lines_1based(self) -> list[int]:
        """Opened switches, 1-based line numbers."""
        return [i + 1 for i in self.opened_lines]

    @property
    def isolated_buses_1based(self) -> list[int]:
        """Isolated buses, 1-based, sorted."""
        return sorted(b + 1 for b in self.isolated_buses)

    @property
    def deenergized_buses_1based(self) -> list[int]:
        """De-energized buses, 1-based, sorted."""
        return sorted(b + 1 for b in self.deenergized_buses)


def _set_outage_state(net) -> None:
    """Mark de-energized buses (and their loads) out of service.

    pandapower excludes out-of-service buses from the power flow, so
    the energized part still solves. This is a state flag only; the
    branches stay as they are.
    """
    dead = deenergized_buses(net)
    for bus in dead:
        net.bus.at[bus, "in_service"] = False
    for idx, row in net.load.iterrows():
        if int(row.bus) in dead:
            net.load.at[idx, "in_service"] = False


def isolate_fault(net, fault: Fault) -> tuple[object, IsolationResult]:
    """Isolate a single fault; return ``(working net, result)``.

    The input network is not modified.
    """
    work = copy.deepcopy(net)
    result = IsolationResult(faults=[fault])
    endpoints = line_endpoints(work)
    if fault.line is not None:
        line = int(fault.line)
        if line not in endpoints:
            raise ValueError(f"unknown line index {line}")
        if not bool(work.line.at[line, "in_service"]):
            raise ValueError(
                f"line {line + 1} is already open; cannot fault an open switch"
            )
        result.isolated_buses = downstream_buses(work, line)
        work.line.at[line, "in_service"] = False
        result.opened_lines = [line]
        result.forbidden_lines = [line]
    else:
        bus = int(fault.bus)
        if bus < 0 or bus >= len(work.bus):
            raise ValueError(f"unknown bus index {bus}")
        incident = [i for i in closed_line_indices(work) if bus in endpoints[i]]
        if not incident:
            raise ValueError(f"bus {bus + 1} has no closed incident line to open")
        for line in incident:
            work.line.at[line, "in_service"] = False
        result.opened_lines = sorted(incident)
        result.forbidden_lines = sorted(incident)
        # Everything fed through the faulted bus loses its path to a
        # slack; it is recomputed from the post-isolation state below.
    result.deenergized_buses = deenergized_buses(work)
    result.isolated_buses = set(result.deenergized_buses)
    _set_outage_state(work)
    return work, result


def isolate_faults(net, faults: list[Fault]) -> tuple[object, IsolationResult]:
    """Isolate several faults in sequence; return ``(net, result)``.

    Faults are applied one at a time on the working network, so a
    second fault inside an already dead zone still counts as isolated
    and its branch is still forbidden from re-closing.
    """
    work = copy.deepcopy(net)
    combined = IsolationResult(faults=list(faults))
    for fault in faults:
        work, one = isolate_fault(work, fault)
        combined.opened_lines.extend(one.opened_lines)
        combined.forbidden_lines.extend(one.forbidden_lines)
        combined.isolated_buses |= one.isolated_buses
    combined.opened_lines = sorted(set(combined.opened_lines))
    combined.forbidden_lines = sorted(set(combined.forbidden_lines))
    combined.deenergized_buses = deenergized_buses(work)
    combined.isolated_buses = set(combined.deenergized_buses)
    _set_outage_state(work)
    return work, combined
