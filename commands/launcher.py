#!/usr/bin/env python3
"""
Tibin Agent Runtime desktop launcher.

Uses the shared process manager — one dashboard, one install root.
"""

import json
import os
import subprocess
import sys
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.env_loader import load_dotenv
from utils.process_manager import (
    dashboard_health,
    ensure_single_dashboard,
    get_process_status,
    read_pid_file,
    stop_all,
    DASHBOARD_PID_FILE,
)

load_dotenv(ROOT)


def get_brain_status():
    from brain.openrouter_brain import get_brain_status as _status
    return _status(ROOT)


class TibinLauncher:
    def __init__(self):
        self.root = ROOT
        self.server_proc = None

    def start_dashboard(self):
        if dashboard_health():
            pid = read_pid_file(DASHBOARD_PID_FILE, self.root)
            return {
                "status": "already_running",
                "process_id": pid,
                "url": "http://127.0.0.1:5000/",
                "install_root": self.root,
            }

        prep = ensure_single_dashboard(base_dir=self.root)
        server_script = os.path.join(self.root, "commands", "run_server.py")
        if not os.path.exists(server_script):
            server_script = os.path.join(self.root, "run_server.py")
        self.server_proc = subprocess.Popen(
            [sys.executable, server_script],
            cwd=self.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "status": "starting",
            "process_id": self.server_proc.pid,
            "url": "http://127.0.0.1:5000/",
            "install_root": self.root,
            "prep": prep,
        }

    def stop_dashboard(self):
        return stop_all(self.root)

    def open_browser(self, path="/dashboard"):
        webbrowser.open(f"http://127.0.0.1:5000{path}")

    def run_gui(self):
        import tkinter as tk
        from tkinter import ttk

        brain = get_brain_status()
        proc = get_process_status(self.root)
        install = proc.get("install", {})

        root = tk.Tk()
        root.title("Tibin Agent Runtime")
        root.geometry("480x320")
        root.resizable(False, False)

        ttk.Label(root, text="Tibin Agent Runtime", font=("Segoe UI", 14, "bold")).pack(pady=(16, 8))
        ttk.Label(root, text=f"Brain: {brain['label']} ({brain['status']})").pack(pady=2)
        ttk.Label(root, text=f"Branch: {install.get('git_branch', '?')} @ {install.get('git_commit', '?')}", font=("Segoe UI", 9)).pack(pady=2)
        ttk.Label(root, text=f"Root: {self.root}", font=("Segoe UI", 8), wraplength=440).pack(pady=2)
        status_var = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=status_var).pack(pady=4)

        def launch():
            status_var.set("Starting dashboard...")
            res = self.start_dashboard()
            status_var.set(f"{res['status']} — {res['url']}")

        def stop():
            res = self.stop_dashboard()
            status_var.set(f"Stopped — killed {res.get('dashboard', {}).get('killed_pids', [])}")

        def open_dash():
            self.open_browser("/dashboard")

        def open_boodlebox():
            from utils.provider_links import open_url_in_system_browser
            open_url_in_system_browser("https://box.boodle.ai/launch/")

        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=16)
        ttk.Button(btn_frame, text="Launch Dashboard", command=launch).grid(row=0, column=0, padx=6, pady=6)
        ttk.Button(btn_frame, text="Stop All", command=stop).grid(row=0, column=1, padx=6, pady=6)
        ttk.Button(btn_frame, text="Open Browser", command=open_dash).grid(row=1, column=0, padx=6, pady=6)
        ttk.Button(btn_frame, text="Open BoodleBox", command=open_boodlebox).grid(row=1, column=1, padx=6, pady=6)

        root.mainloop()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--no-gui":
        res = TibinLauncher().start_dashboard()
        print(json.dumps(res, indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--stop":
        print(json.dumps(stop_all(ROOT), indent=2))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps(get_process_status(ROOT), indent=2))
        return
    TibinLauncher().run_gui()


if __name__ == "__main__":
    main()
