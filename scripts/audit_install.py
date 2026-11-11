#!/usr/bin/env python3
"""Scan for duplicate Tibin install folders and stale port-5000 listeners."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.process_manager import get_process_status, dashboard_health, get_install_info


def main():
    info = get_install_info(ROOT)
    proc = get_process_status(ROOT)
    report = {
        "canonical_install_root": ROOT,
        "git_branch": info.get("git_branch"),
        "git_commit": info.get("git_commit"),
        "dashboard_health": dashboard_health(),
        "processes": proc,
        "warnings": [],
    }

    dash = proc.get("dashboard", {})
    if dash.get("install_root") and dash.get("install_root") != ROOT:
        report["warnings"].append(
            f"Stale dashboard.pid points to {dash['install_root']} but this scan is from {ROOT}"
        )

    if dash.get("status") == "running" and not report["dashboard_health"]:
        report["warnings"].append("dashboard.pid says running but /health failed — stale PID file")

    print(json.dumps(report, indent=2))
    if report["warnings"]:
        print("\nRun: python runtime.py --stop-all", file=sys.stderr)
        sys.exit(1)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
