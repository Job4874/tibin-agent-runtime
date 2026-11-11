#!/usr/bin/env python3
"""Start the Tibin dashboard on port 5000 (single instance enforced)."""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.env_loader import load_dotenv
from utils.process_manager import (
    ensure_single_dashboard,
    get_process_status,
    register_dashboard_pid,
    stop_all,
)

load_dotenv(ROOT)


def main():
    parser = argparse.ArgumentParser(description="Tibin dashboard server")
    parser.add_argument("--stop", action="store_true", help="Stop dashboard, watcher, and port 5000 listeners")
    parser.add_argument("--status", action="store_true", help="Show process registry")
    args = parser.parse_args()

    if args.stop:
        import json
        print(json.dumps(stop_all(ROOT), indent=2))
        return

    if args.status:
        import json
        print(json.dumps(get_process_status(ROOT), indent=2))
        return

    prep = ensure_single_dashboard(base_dir=ROOT)
    if prep.get("status") == "already_running":
        print(f"Dashboard already running (pid {prep['pid']}): {prep['url']}")
        return

    if prep.get("killed_pids"):
        print(f"Cleared stale processes on port 5000: {prep['killed_pids']}")

    from app.app import app
    register_dashboard_pid(os.getpid(), ROOT)
    debug = os.environ.get("TIBIN_DEBUG", "0") == "1"
    print("Dashboard: http://127.0.0.1:5000/")
    print(f"Install root: {ROOT}")
    try:
        app.run(host="127.0.0.1", port=5000, debug=debug, use_reloader=False)
    finally:
        from utils.process_manager import clear_pid_file, DASHBOARD_PID_FILE
        clear_pid_file(DASHBOARD_PID_FILE, ROOT)


if __name__ == "__main__":
    main()
