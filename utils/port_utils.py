"""Cross-platform helpers for freeing a TCP port before starting the dashboard."""

import os
import subprocess
import sys


def kill_processes_on_port(port: int = 5000) -> list[int]:
    """Kill processes listening on port. Returns list of PIDs that were targeted."""
    killed = []
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.splitlines():
                if "LISTENING" not in line:
                    continue
                # Match :5000 but not :50001 (Windows netstat)
                if not any(token.endswith(f":{port}") for token in line.split()):
                    continue
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) != os.getpid():
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True,
                                timeout=10,
                            )
                            killed.append(int(pid))
        except Exception:
            pass
    else:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for pid_str in result.stdout.strip().split():
                if pid_str.isdigit():
                    pid = int(pid_str)
                    if pid != os.getpid():
                        try:
                            os.kill(pid, 9)
                            killed.append(pid)
                        except OSError:
                            pass
        except Exception:
            pass
    return killed
