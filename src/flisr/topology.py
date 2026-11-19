"""Topology helpers: switch identification, radiality, energized sets.

A distribution network is radial when its closed branches form a tree
(or, after a fault has islanded part of the feeder, a forest: every
energized component is a tree fed from a slack bus, and no closed
branch forms a loop). Every line is a switchable branch:
``in_service=True`` means the switch is closed, ``in_service=False``
means it is open. Bus numbers in reports are 1-based (pandapower
index + 1), matching the IEEE numbering used in the literature.

Unlike the sibling project ``dnrflow`` (which requires the whole
network to stay connected and uses networkx), the helpers here are
pure Python and tolerate islanded buses: after fault isolation part of
the feeder is deliberately de-energized, so connectivity to a slack is
checked per bus, not for the network as a whole.
"""

from __future__ import annotations

import numpy as np


def slack_buses(net) -> list[int]:
    """0-based pandapower bus indices that host an external grid."""
    return sorted(int(b) for b in net.ext_grid.bus.values)


def line_indices(net) -> list[int]:
    """All 0-based pandapower line indices, in order."""
    return list(net.line.index)


def closed_line_indices(net) -> list[int]:
    """0-based line indices with ``in_service=True``."""
    return [int(i) for i, s in net.line.in_service.items() if bool(s)]


def open_line_indices(net) -> list[int]:
    """0-based line indices with ``in_service=False`` (the open switches)."""
    return [int(i) for i, s in net.line.in_service.items() if not bool(s)]


def line_endpoints(net) -> dict[int, tuple[int, int]]:
    """Map 0-based line index -> (from_bus, to_bus), 0-based bus indices."""
    return {int(i): (int(r.from_bus), int(r.to_bus)) for i, r in net.line.iterrows()}


def adjacency(net, closed: set[int] | None = None) -> dict[int, list[tuple[int, int]]]:
    """Adjacency of the closed-branch graph: bus -> [(neighbour, line)]."""
    if closed is None:
        closed = set(closed_line_indices(net))
    endpoints = line_endpoints(net)
    adj: dict[int, list[tuple[int, int]]] = {b: [] for b in range(len(net.bus))}
    for idx in sorted(closed):
        f, t = endpoints[idx]
        adj[f].append((t, idx))
        adj[t].append((f, idx))
    return adj


def _component(adj: dict[int, list[tuple[int, int]]], start: int) -> set[int]:
    """Buses reachable from ``start`` through closed branches (BFS)."""
    seen = {start}
    stack = [start]
    while stack:
        bus = stack.pop()
        for neighbour, _ in adj[bus]:
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def components(net, closed: set[int] | None = None) -> list[set[int]]:
    """Return the connected components of the closed-branch graph."""
    adj = adjacency(net, closed)
    seen: set[int] = set()
    result: list[set[int]] = []
    for bus in range(len(net.bus)):
        if bus in seen:
            continue
        comp = _component(adj, bus)
        seen |= comp
        result.append(comp)
    return result


def energized_buses(net, closed: set[int] | None = None) -> set[int]:
    """Buses with a closed-branch path to a slack bus."""
    adj = adjacency(net, closed)
    energized: set[int] = set()
    for slack in slack_buses(net):
        energized |= _component(adj, slack)
    return energized


def deenergized_buses(net, closed: set[int] | None = None) -> set[int]:
    """Buses with no closed-branch path to a slack bus (the outage area)."""
    return set(range(len(net.bus))) - energized_buses(net, closed)


def downstream_buses(net, line_idx: int) -> set[int]:
    """Buses on the far side of ``line_idx`` from the slack.

    The line is removed from the closed graph; the returned set is the
    component that no longer reaches a slack bus. On a radial feeder
    this is exactly the subtree fed through the faulted branch.
    """
    closed = set(closed_line_indices(net))
    closed.discard(int(line_idx))
    return deenergized_buses(net, closed)


def is_radial_forest(net, closed: set[int] | None = None) -> tuple[bool, str]:
    """Check that the closed branches contain no loop.

    Returns a ``(radial, reason)`` pair. Every connected component of
    the closed-branch graph must be a tree (edges = nodes - 1); a loop
    makes some component over-edged. Islanded (de-energized) components
    are allowed -- they are trees too, just not fed from a slack -- so
    this check is valid both before and after fault isolation, unlike a
    whole-network connectivity check.
    """
    if closed is None:
        closed = set(closed_line_indices(net))
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for bus in range(len(net.bus)):
        parent[bus] = bus
    endpoints = line_endpoints(net)
    for idx in sorted(closed):
        f, t = endpoints[idx]
        rf, rt = find(f), find(t)
        if rf == rt:
            return False, f"loop: closing line {idx + 1} ({f + 1}-{t + 1})"
        parent[rf] = rt
    return True, "radial (no loops)"


def load_by_bus(net) -> dict[int, float]:
    """Total active load per 0-based bus index, in MW."""
    result: dict[int, float] = {}
    for _, row in net.load.iterrows():
        bus = int(row.bus)
        result[bus] = result.get(bus, 0.0) + float(row.p_mw)
    return result


def total_load_mw(net) -> float:
    """Total active load of the network, in MW."""
    return float(np.sum(net.load.p_mw.values)) if len(net.load) else 0.0


def switch_label(net, line_idx: int) -> str:
    """Human-readable ``"line N (from-to)"`` label, 1-based buses."""
    f, t = line_endpoints(net)[int(line_idx)]
    return f"line {int(line_idx) + 1} ({f + 1}-{t + 1})"
