"""
Single-instance process registry for Tibin runtime.

Prevents duplicate dashboard servers and watcher daemons on port 5000.
"""

import json
import os
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.port_utils import kill_processes_on_port

DASHBOARD_PID_FILE = "dashboard.pid"
WATCHER_PID_FILE = "watcher.pid"
REGISTRY_FILE = "process_registry.json"


def get_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _state_dir(base_dir: str = None) -> str:
    d = os.path.join(base_dir or get_base_dir(), "state")
    os.makedirs(d, exist_ok=True)
    return d


def _pid_path(name: str, base_dir: str = None) -> str:
    return os.path.join(_state_dir(base_dir), name)


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return str(pid) in result.stdout and "No tasks" not in result.stdout
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def read_pid_file(filename: str, base_dir: str = None) -> Optional[int]:
    path = _pid_path(filename, base_dir)
    if not os.path.exists(path):
        return None
    try:
        data = json.loads(open(path, "r", encoding="utf-8").read())
        return int(data.get("pid", 0)) or None
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def write_pid_file(filename: str, pid: int, role: str, base_dir: str = None, extra: Dict = None) -> None:
    path = _pid_path(filename, base_dir)
    payload = {
        "pid": pid,
        "role": role,
        "install_root": base_dir or get_base_dir(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    _update_registry(base_dir)


def clear_pid_file(filename: str, base_dir: str = None) -> None:
    path = _pid_path(filename, base_dir)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    _update_registry(base_dir)


def kill_pid(pid: int) -> bool:
    if not is_pid_alive(pid):
        return False
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=10)
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def dashboard_health(port: int = 5000, timeout: float = 1.5) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def get_install_info(base_dir: str = None) -> Dict[str, Any]:
    base = base_dir or get_base_dir()
    info = {
        "install_root": base,
        "python": sys.executable,
        "platform": sys.platform,
    }
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=base,
            timeout=5,
        )
        if result.returncode == 0:
            info["git_branch"] = result.stdout.strip()
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=base,
            timeout=5,
        )
        if result.returncode == 0:
            info["git_commit"] = result.stdout.strip()
    except Exception:
        pass
    return info


def _update_registry(base_dir: str = None) -> None:
    base = base_dir or get_base_dir()
    registry_path = os.path.join(_state_dir(base), REGISTRY_FILE)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "install": get_install_info(base),
        "dashboard": _read_pid_record(DASHBOARD_PID_FILE, base),
        "watcher": _read_pid_record(WATCHER_PID_FILE, base),
        "dashboard_health": dashboard_health(),
    }
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _read_pid_record(filename: str, base_dir: str) -> Dict[str, Any]:
    path = _pid_path(filename, base_dir)
    if not os.path.exists(path):
        return {"status": "stopped"}
    try:
        data = json.loads(open(path, "r", encoding="utf-8").read())
        pid = int(data.get("pid", 0))
        alive = is_pid_alive(pid)
        root_match = data.get("install_root") == base_dir
        return {
            "status": "running" if alive else "stale",
            "pid": pid,
            "role": data.get("role"),
            "install_root": data.get("install_root"),
            "install_root_match": root_match,
            "started_at": data.get("started_at"),
        }
    except (json.JSONDecodeError, ValueError, OSError):
        return {"status": "unknown"}


def get_process_status(base_dir: str = None) -> Dict[str, Any]:
    base = base_dir or get_base_dir()
    _update_registry(base)
    registry_path = os.path.join(_state_dir(base), REGISTRY_FILE)
    with open(registry_path, "r", encoding="utf-8") as f:
        return json.load(f)


def stop_dashboard(base_dir: str = None, port: int = 5000) -> Dict[str, Any]:
    base = base_dir or get_base_dir()
    killed: List[int] = []
    pid = read_pid_file(DASHBOARD_PID_FILE, base)
    if pid and kill_pid(pid):
        killed.append(pid)
    clear_pid_file(DASHBOARD_PID_FILE, base)
    for p in kill_processes_on_port(port):
        if p not in killed:
            killed.append(p)
    _update_registry(base)
    return {"status": "stopped", "killed_pids": killed}


def stop_watcher(base_dir: str = None) -> Dict[str, Any]:
    base = base_dir or get_base_dir()
    killed: List[int] = []
    pid = read_pid_file(WATCHER_PID_FILE, base)
    if pid and kill_pid(pid):
        killed.append(pid)
    clear_pid_file(WATCHER_PID_FILE, base)
    status_file = os.path.join(_state_dir(base), "daemon_status.json")
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump({"status": "stopped", "message": "Stopped by process manager"}, f)
    _update_registry(base)
    return {"status": "stopped", "killed_pids": killed}


def stop_all(base_dir: str = None, port: int = 5000) -> Dict[str, Any]:
    w = stop_watcher(base_dir)
    d = stop_dashboard(base_dir, port)
    return {"watcher": w, "dashboard": d}


def ensure_single_dashboard(port: int = 5000, base_dir: str = None) -> Dict[str, Any]:
    """If another dashboard is healthy on this install, refuse to start a duplicate."""
    base = base_dir or get_base_dir()
    existing = read_pid_file(DASHBOARD_PID_FILE, base)
    if existing and is_pid_alive(existing):
        if dashboard_health(port):
            return {"status": "already_running", "pid": existing, "url": f"http://127.0.0.1:{port}/"}
        kill_pid(existing)
        clear_pid_file(DASHBOARD_PID_FILE, base)

    # Stale listeners on port from other copies / crashed servers
    killed = kill_processes_on_port(port)
    if killed:
        return {"status": "cleared_stale", "killed_pids": killed}
    return {"status": "ready"}


def register_dashboard_pid(pid: int, base_dir: str = None) -> None:
    write_pid_file(DASHBOARD_PID_FILE, pid, "dashboard", base_dir)


def register_watcher_pid(pid: int, base_dir: str = None) -> None:
    write_pid_file(WATCHER_PID_FILE, pid, "watcher", base_dir)
