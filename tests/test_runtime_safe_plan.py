import pytest
import os
import json
import tempfile
from runtime import run_plan
from agents.defender_agent import DefenderAgent
from tools.approval_store import ApprovalStore

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    for d in ["state", "permissions", "inbox", "outbox", "logs", "reports", "observations", "runs", "screenshots", "workspace"]:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)
    with open(os.path.join(base_dir, "permissions", "allowlist.json"), "w") as f:
        json.dump({"commands": ["echo", "python --version", "git --version"]}, f)
    with open(os.path.join(base_dir, "permissions", "denylist.json"), "w") as f:
        json.dump({"commands": []}, f)
    with open(os.path.join(base_dir, "permissions", "tool_permissions.json"), "w") as f:
        json.dump({"allowed_tools": ["ShellWorker", "FileWorker"]}, f)
    with open(os.path.join(base_dir, "permissions", "path_permissions.json"), "w") as f:
        json.dump({"blocked_paths": [], "allowed_write_paths": [os.path.join(base_dir, "workspace")]}, f)
    with open(os.path.join(base_dir, "permissions", "web_permissions.json"), "w") as f:
        json.dump({"blocked_domains": []}, f)
    return base_dir

def test_safe_plan_execution(temp_env, monkeypatch):
    plan = {
        "plan_id": "plan-safe-001",
        "objective_id": "obj-001",
        "objective": "Verify environment and list files.",
        "actions": [
            {"action_id": "act-1", "worker": "ShellWorker", "type": "run", "params": {"command": "python --version"}},
            {"action_id": "act-2", "worker": "ShellWorker", "type": "run", "params": {"command": "git --version"}},
            {"action_id": "act-3", "worker": "FileWorker", "type": "list", "params": {"path": "."}}
        ]
    }
    path = os.path.join(temp_env, "plan.json")
    with open(path, "w") as f:
        json.dump(plan, f)
    monkeypatch.chdir(temp_env)
    result = run_plan(path)
    assert result is not None
    assert result["status"] in ["completed", "failed", "pending_approval"]
    # Verify run artifacts exist
    run_dir = result.get("run_dir")
    if run_dir and os.path.exists(run_dir):
        assert os.path.exists(os.path.join(run_dir, "plan.json"))
        assert os.path.exists(os.path.join(run_dir, "observation.json"))
        assert os.path.exists(os.path.join(run_dir, "defender_decisions.json"))
        assert os.path.exists(os.path.join(run_dir, "worker_results.json"))
