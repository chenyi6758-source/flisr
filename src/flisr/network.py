"""Built-in test networks, all returned as pandapower networks.

Every line is a switchable branch: ``in_service=True`` means the
switch is closed, ``in_service=False`` means it is an open tie switch.
Bus numbers in reports are 1-based (pandapower index + 1).

Cases
-----
case33 : IEEE 33-bus (Baran & Wu 1989), ``pandapower.networks.case33bw``.
case69 : IEEE 69-bus (Baran & Wu 1989), built from MATPOWER ``case69.m``
    plus the five tie lines of Savier & Das (2007). The builder is
    adapted from the sibling project ``dnrflow`` (``networks.py`` /
    ``data.py``); the 69-bus tables live in :mod:`flisr.data` with
    attribution.
small : a synthetic 10-bus teaching feeder with two feeders off one
    slack and two tie switches, built for the exhaustive-enumeration
    optimality check and for the priority-shedding tests. It is not a
    literature system; its data are stated in full in
    :func:`synthetic_feeder`.
"""

from __future__ import annotations

import pandapower as pp
import pandapower.networks as pn

from . import data

CASES = ("case33", "case69", "small")
ALIASES = {
    "33": "case33",
    "33-bus": "case33",
    "case33bw": "case33",
    "69": "case69",
    "69-bus": "case69",
    "synthetic": "small",
}

SOURCES = {
    "case33": "Baran & Wu (1989), via pandapower.networks.case33bw",
    "case69": "Baran & Wu (1989), MATPOWER case69.m; ties: Savier & Das (2007)",
    "small": "synthetic teaching feeder (see flisr.network.synthetic_feeder)",
}


def available_cases() -> list[str]:
    """Names of the built-in cases."""
    return list(CASES)


def _build_from_tables(bus, branch, vn_kv, ties=None):
    """Build a single-slack network from MATPOWER-style tables.

    Parameters
    ----------
    bus:
        Array with columns (bus_i, type, Pd_kW, Qd_kVAr).
    branch:
        Array with columns (f_bus, t_bus, R_ohm, X_ohm[, status]).
    vn_kv:
        Base voltage, in kV.
    ties:
        Optional array with columns (f_bus, t_bus, R_ohm, X_ohm) of
        normally open tie lines.

    """
    net = pp.create_empty_network(sn_mva=1.0)
    bus_map: dict[int, int] = {}
    for row in bus:
        number, typ, pd, qd = int(row[0]), int(row[1]), row[2], row[3]
        idx = pp.create_bus(net, vn_kv=vn_kv, name=f"bus {number}")
        bus_map[number] = idx
        if typ == 3:
            pp.create_ext_grid(net, idx, vm_pu=1.0, va_degree=0.0)
        if pd != 0 or qd != 0:
            pp.create_load(
                net, idx, p_mw=pd / 1000.0, q_mvar=qd / 1000.0, name=f"load {number}"
            )
    for row in branch:
        status = int(row[4]) if len(row) > 4 else 1
        pp.create_line_from_parameters(
            net,
            bus_map[int(row[0])],
            bus_map[int(row[1])],
            length_km=1.0,
            r_ohm_per_km=row[2],
            x_ohm_per_km=row[3],
            c_nf_per_km=0.0,
            max_i_ka=999.0,
            in_service=bool(status),
        )
    if ties is not None:
        for row in ties:
            pp.create_line_from_parameters(
                net,
                bus_map[int(row[0])],
                bus_map[int(row[1])],
                length_km=1.0,
                r_ohm_per_km=row[2],
                x_ohm_per_km=row[3],
                c_nf_per_km=0.0,
                max_i_ka=999.0,
                in_service=False,
            )
    return net


def case33():
    """IEEE 33-bus radial distribution system (Baran & Wu 1989)."""
    return pn.case33bw()


def case69():
    """IEEE 69-bus radial distribution system (Baran & Wu 1989)."""
    return _build_from_tables(
        data.CASE69_BUS,
        data.CASE69_BRANCH,
        data.CASE69_VN_KV,
        ties=data.CASE69_TIES,
    )


def synthetic_feeder():
    """Synthetic 10-bus teaching feeder with two ties.

    One slack (bus 1, 12.66 kV) feeds two radial feeders:

    * feeder A: 1-2-3-4-5-6, loads 100/200/150/150/100 kW at buses
      2-6 (power factor 0.95);
    * feeder B: 1-7-8-9-10, loads 150/200/150/100 kW at buses 7-10.

    Tie switches: T1 = line 10 (6-10, 0.5 + j0.25 ohm), T2 = line 11
    (4-8, 0.3 + j0.15 ohm), both normally open. Branch impedances are
    0.2 + j0.10 ohm on feeder A and 0.2 + j0.10 ohm on feeder B, except
    the first branch of each feeder (0.1 + j0.05 ohm). Every line is
    rated 0.5 kA, a realistic distribution rating (unlike the IEEE
    cases shipped with ``max_i_ka = 99999``, which makes the loading
    check vacuous there -- see the README).

    The feeder is small enough that every tie-switch combination can
    be enumerated exactly, which is what the optimality test uses.
    """
    net = pp.create_empty_network(sn_mva=1.0)
    vn_kv = 12.66
    bus_map = {
        n: pp.create_bus(net, vn_kv=vn_kv, name=f"bus {n}") for n in range(1, 11)
    }
    pp.create_ext_grid(net, bus_map[1], vm_pu=1.0, va_degree=0.0)
    loads_kw = {2: 100, 3: 200, 4: 150, 5: 150, 6: 100, 7: 150, 8: 200, 9: 150, 10: 100}
    for number, p_kw in loads_kw.items():
        pp.create_load(
            net,
            bus_map[number],
            p_mw=p_kw / 1000.0,
            q_mvar=(p_kw / 1000.0) * 0.3287,  # pf 0.95
            name=f"load {number}",
        )
    branches = [
        (1, 2, 0.1, 0.05),
        (2, 3, 0.2, 0.10),
        (3, 4, 0.2, 0.10),
        (4, 5, 0.2, 0.10),
        (5, 6, 0.2, 0.10),
        (1, 7, 0.1, 0.05),
        (7, 8, 0.2, 0.10),
        (8, 9, 0.2, 0.10),
        (9, 10, 0.2, 0.10),
    ]
    for f, t, r, x in branches:
        pp.create_line_from_parameters(
            net,
            bus_map[f],
            bus_map[t],
            length_km=1.0,
            r_ohm_per_km=r,
            x_ohm_per_km=x,
            c_nf_per_km=0.0,
            max_i_ka=0.5,
            in_service=True,
        )
    for f, t, r, x in [(6, 10, 0.5, 0.25), (4, 8, 0.3, 0.15)]:
        pp.create_line_from_parameters(
            net,
            bus_map[f],
            bus_map[t],
            length_km=1.0,
            r_ohm_per_km=r,
            x_ohm_per_km=x,
            c_nf_per_km=0.0,
            max_i_ka=0.5,
            in_service=False,
        )
    return net


_BUILDERS = {
    "case33": case33,
    "case69": case69,
    "small": synthetic_feeder,
}


def load_case(name: str):
    """Load a built-in case by name (aliases ``33``/``69``/``case33bw``)."""
    key = ALIASES.get(name, name)
    if key not in _BUILDERS:
        raise ValueError(f"unknown case {name!r}; available: {', '.join(CASES)}")
    return _BUILDERS[key]()


def normalize_case(name: str) -> str:
    """Canonical case name (``33`` -> ``case33``), or raise ``ValueError``."""
    key = ALIASES.get(name, name)
    if key not in _BUILDERS:
        raise ValueError(f"unknown case {name!r}; available: {', '.join(CASES)}")
    return key


def case_source(name: str) -> str:
    """Literature source of a built-in case."""
    key = ALIASES.get(name, name)
    return SOURCES[key]
