"""Tests for shell worker, local tools, dashboard routes, and launcher."""

import json
import os
import pytest


def test_shell_worker_accepts_run_alias():
    from workers.shell_worker import ShellWorker
    w = ShellWorker()
    result = w.execute({
        "type": "run",
        "params": {"command": "python --version"},
    })
    assert result["status"] in ("success", "failed")
    if result["status"] == "success":
        assert "Python" in result["data"].get("stdout", "") or result["data"].get("exit_code") == 0


def test_detect_list_files_goal():
    from model_loop.local_tools import detect_list_files_goal
    spec = detect_list_files_goal("List all .py files in the project root")
    assert spec is not None
    assert spec.get("kind") == "list_files"


def test_is_weak_brain_answer():
    from model_loop.local_tools import _is_weak_brain_answer
    assert _is_weak_brain_answer("User Safety: safe") is True
    assert _is_weak_brain_answer("runtime.py\napp.py\nlauncher.py") is False


def test_local_tool_list_py_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alpha.py").write_text("x", encoding="utf-8")
    (tmp_path / "beta.py").write_text("x", encoding="utf-8")

    from agents.defender_agent import DefenderAgent
    from workers.shell_worker import ShellWorker
    from model_loop.local_tools import run_local_tool_for_goal

    defender = DefenderAgent(str(tmp_path))
    shell = ShellWorker()
    result = run_local_tool_for_goal(str(tmp_path), "List all .py files in the project root", defender, shell)
    assert result is not None
    assert result["status"] == "success"
    assert "alpha.py" in result["output"]
    assert "beta.py" in result["output"]


def test_dashboard_routes():
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    from app.app import app

    client = app.test_client()
    for path in ["/health", "/dashboard", "/browser", "/tasks", "/timeline", "/api/brain", "/api/system/status"]:
        res = client.get(path)
        assert res.status_code == 200, f"{path} returned {res.status_code}"


def test_http_smoke():
    """Smoke test: all 13 UI routes, 404, security headers, and POST auth."""
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    from app.app import app

    client = app.test_client()

    # All main UI routes must return 200
    ui_routes = [
        "/", "/dashboard", "/tasks", "/timeline", "/plans",
        "/approvals", "/reports", "/memory", "/complexity",
        "/model_loop", "/providers", "/browser", "/workers",
    ]
    for path in ui_routes:
        res = client.get(path)
        assert res.status_code == 200, f"GET {path} returned {res.status_code}"

    # Unknown route must return 404 with the two-panel template
    res = client.get("/nonexistent-page-xyzzy")
    assert res.status_code == 404, f"GET /nonexistent-page-xyzzy returned {res.status_code}"
    body = res.data.decode()
    assert "Page Not Found" in body or "404" in body, "404 page missing expected content"

    # POST /api/* without token must return 401 (not 403)
    res = client.post("/api/tasks/run_loop",
                      json={},
                      headers={"Content-Type": "application/json"})
    assert res.status_code == 401, f"Unauthenticated POST returned {res.status_code}"

    # Security headers must be present on every response
    res = client.get("/")
    required_headers = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
    ]
    for hdr in required_headers:
        assert hdr in res.headers, f"Missing security header: {hdr}"


def test_port_utils_kill_no_crash():
    from utils.port_utils import kill_processes_on_port
    killed = kill_processes_on_port(59999)
    assert isinstance(killed, list)


def test_launcher_headless_start(monkeypatch):
    # Patch commands.launcher (the module whose globals start_dashboard uses);
    # patching the root-level `launcher` shim's re-exported bindings has no
    # effect on the underlying module and made this test fail whenever a real
    # dashboard was listening on port 5000.
    import launcher
    import commands.launcher as launcher_impl
    calls = []

    class FakePopen:
        def __init__(self, *a, **k):
            calls.append(True)
            self.pid = 12345
        def poll(self):
            return None
        def terminate(self):
            pass

    monkeypatch.setattr(launcher_impl, "dashboard_health", lambda port=5000: False)
    monkeypatch.setattr(launcher_impl, "ensure_single_dashboard", lambda **k: {"status": "ready"})
    monkeypatch.setattr(launcher_impl.subprocess, "Popen", FakePopen)
    result = launcher.TibinLauncher().start_dashboard()
    assert result["status"] == "starting"
    assert calls


def test_process_manager_stop_all(tmp_path, monkeypatch):
    import utils.process_manager as pm
    # stop_dashboard intentionally clears port-5000 listeners on the real
    # install; neutralize that here so the test never kills a live dev server.
    monkeypatch.setattr(pm, "kill_processes_on_port", lambda port: [])
    pm.write_pid_file(pm.DASHBOARD_PID_FILE, 999999, "dashboard", str(tmp_path))
    result = pm.stop_all(str(tmp_path))
    assert "dashboard" in result
    status = pm.get_process_status(str(tmp_path))
    assert status["dashboard"]["status"] in ("stopped", "stale")
