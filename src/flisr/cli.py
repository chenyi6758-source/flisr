"""Command-line interface: ``flisr demo`` and ``flisr restore ...``."""

from __future__ import annotations

import argparse
import sys

from .isolate import Fault
from .network import available_cases, case_source, load_case, normalize_case
from .report import format_report, result_to_json
from .restore import (
    DEFAULT_MAX_LOADING_PCT,
    DEFAULT_V_MAX,
    DEFAULT_V_MIN,
    plan_restoration,
)

#: Demo fault: IEEE 33-bus, line 6 (1-based) between buses 6 and 7 --
#: a mid-feeder fault that de-energizes buses 7-18.
DEMO_CASE = "case33"
DEMO_FAULT_LINE_1BASED = 6


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="flisr",
        description="Distribution-network fault isolation and service "
        "restoration: isolate a faulted section, then restore load by "
        "closing tie switches, one power-flow-checked step at a time.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    demo = sub.add_parser(
        "demo",
        help="run the built-in demo: IEEE 33-bus, mid-feeder single fault",
    )
    demo.add_argument(
        "--json", default=None, metavar="FILE", help="write the result as JSON to FILE"
    )

    restore = sub.add_parser(
        "restore",
        help="restore load after fault(s) on a built-in case",
    )
    restore.add_argument(
        "--case",
        default="case33",
        help=f"built-in case: {', '.join(available_cases())} "
        "(also 33 / 69 / case33bw; default: case33)",
    )
    restore.add_argument(
        "--fault-line",
        type=int,
        action="append",
        default=[],
        metavar="N",
        help="faulted line, 1-based (repeatable for multiple faults)",
    )
    restore.add_argument(
        "--fault-bus",
        type=int,
        action="append",
        default=[],
        metavar="N",
        help="faulted bus, 1-based (repeatable for multiple faults)",
    )
    restore.add_argument(
        "--priority",
        action="append",
        default=[],
        metavar="BUS:WEIGHT",
        help="load priority, e.g. --priority 18:10 for a critical load "
        "at bus 18 (repeatable; default weight 1.0)",
    )
    restore.add_argument(
        "--v-min",
        type=float,
        default=DEFAULT_V_MIN,
        help=f"lower voltage limit in p.u. (default: {DEFAULT_V_MIN})",
    )
    restore.add_argument(
        "--v-max",
        type=float,
        default=DEFAULT_V_MAX,
        help=f"upper voltage limit in p.u. (default: {DEFAULT_V_MAX})",
    )
    restore.add_argument(
        "--max-loading",
        type=float,
        default=DEFAULT_MAX_LOADING_PCT,
        help="line-loading limit in percent (default: 100)",
    )
    restore.add_argument(
        "--json", default=None, metavar="FILE", help="write the result as JSON to FILE"
    )
    return p


def _parse_priorities(specs: list[str]) -> dict[int, float]:
    """Parse ``BUS:WEIGHT`` specs (1-based buses) to 0-based weights."""
    priorities: dict[int, float] = {}
    for spec in specs:
        try:
            bus, weight = spec.split(":")
            priorities[int(bus) - 1] = float(weight)
        except ValueError:
            raise ValueError(
                f"bad --priority {spec!r}; expected BUS:WEIGHT, e.g. 18:10"
            ) from None
    return priorities


def _run_restore(args) -> int:
    try:
        net = load_case(args.case)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    faults = [Fault(line=n - 1) for n in args.fault_line]
    faults += [Fault(bus=n - 1) for n in args.fault_bus]
    if not faults:
        print(
            "no fault given: use --fault-line N and/or --fault-bus N", file=sys.stderr
        )
        return 2
    for fault in faults:
        if fault.line is not None and not 0 <= fault.line < len(net.line):
            print(f"no line {fault.line + 1} in {args.case}", file=sys.stderr)
            return 2
        if fault.bus is not None and not 0 <= fault.bus < len(net.bus):
            print(f"no bus {fault.bus + 1} in {args.case}", file=sys.stderr)
            return 2
    try:
        priorities = _parse_priorities(args.priority)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{args.case}: {case_source(args.case)}")
    try:
        result = plan_restoration(
            net,
            faults,
            priorities=priorities,
            v_min=args.v_min,
            v_max=args.v_max,
            max_loading_pct=args.max_loading,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    result.case = normalize_case(args.case)
    print(format_report(net, result))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(result_to_json(result) + "\n")
        print(f"wrote {args.json}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        demo_args = argparse.Namespace(
            case=DEMO_CASE,
            fault_line=[DEMO_FAULT_LINE_1BASED],
            fault_bus=[],
            priority=[],
            v_min=DEFAULT_V_MIN,
            v_max=DEFAULT_V_MAX,
            max_loading=DEFAULT_MAX_LOADING_PCT,
            json=args.json,
        )
        return _run_restore(demo_args)
    return _run_restore(args)


if __name__ == "__main__":
    raise SystemExit(main())
