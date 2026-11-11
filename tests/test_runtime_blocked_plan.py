import pytest
import os
import json
from runtime import run_plan

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    for d in ["state", "permissions", "inbox", "outbox", "logs", "reports", "observations", "runs", "screenshots", "workspace"]:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)
    with open(os.path.join(base_dir, "permissions", "allowlist.json"), "w") as f:
        json.dump({"commands": ["echo"]}, f)
    with open(os.path.join(base_dir, "permissions", "denylist.json"), "w") as f:
        json.dump({"commands": []}, f)
    with open(os.path.join(base_dir, "permissions", "tool_permissions.json"), "w") as f:
        json.dump({"allowed_tools": ["ShellWorker"]}, f)
    with open(os.path.join(base_dir, "permissions", "path_permissions.json"), "w") as f:
        json.dump({"blocked_paths": [], "allowed_write_paths": []}, f)
    with open(os.path.join(base_dir, "permissions", "web_permissions.json"), "w") as f:
        json.dump({"blocked_domains": []}, f)
    return base_dir

def test_blocked_dangerous_plan(temp_env, monkeypatch):
    plan = {
        "plan_id": "plan-bad-001",
        "objective_id": "obj-bad-001",
        "objective": "Bad plan objective.",
        "actions": [
            {"action_id": "act-b1", "worker": "ShellWorker", "type": "run", "params": {"command": "rm -rf /"}}
        ]
    }
    path = os.path.join(temp_env, "plan.json")
    with open(path, "w") as f:
        json.dump(plan, f)
    monkeypatch.chdir(temp_env)
    result = run_plan(path)
    assert result is not None
    assert result["status"] == "blocked"
    assert any(r.get("status") == "blocked" for r in result.get("worker_results", []))
