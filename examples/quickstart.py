"""Quickstart: restore the IEEE 33-bus and 69-bus systems after a fault.

Runs a mid-feeder single fault on case33 (line 6, buses 6-7) and a
single fault on case69 (line 6, buses 6-7), and prints the restoration
report for each.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flisr.isolate import Fault
from flisr.network import load_case
from flisr.report import format_report
from flisr.restore import plan_restoration


def main() -> None:
    for case, fault_line in (("case33", 6), ("case69", 6)):
        net = load_case(case)
        result = plan_restoration(net, [Fault(line=fault_line - 1)])
        result.case = case
        print(format_report(net, result))
        print()


if __name__ == "__main__":
    main()
