import pytest
import os
import json
from agents.defender_agent import DefenderAgent
from tools.approval_store import ApprovalStore

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    os.makedirs(os.path.join(base_dir, "state"))
    os.makedirs(os.path.join(base_dir, "permissions"))
    
    # Mock permissions
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

def test_exact_action_enforcement(temp_env):
    defender = DefenderAgent(temp_env)
    store = ApprovalStore(temp_env)
    
    # Use a command that is not allowed but not unconditionally blocked
    action = {
        "worker": "ShellWorker",
        "type": "run",
        "action_id": "a1",
        "params": {"command": "npm test"},
        "requires_approval": True
    }
    
    # Blocked without approval
    allowed, msg = defender.check_action(action, "p1")
    assert not allowed
    
    # Approve it
    store.create_approval("p1", "a1", "approved", "Test", "high")
    
    # Allowed with approval
    allowed, msg = defender.check_action(action, "p1")
    assert allowed
    
    # Blocked for wrong plan
    allowed, msg = defender.check_action(action, "p2")
    assert not allowed

def test_destructive_always_blocked(temp_env):
    defender = DefenderAgent(temp_env)
    store = ApprovalStore(temp_env)
    
    action = {
        "worker": "ShellWorker",
        "type": "run",
        "action_id": "a2",
        "params": {"command": "rm -rf /"}
    }
    
    # Blocked unconditionally
    allowed, msg = defender.check_action(action, "p1")
    assert not allowed
    assert "destructive" in msg.lower() or "blocked" in msg.lower()
    
    # Approval does NOT help for destructive commands
    store.create_approval("p1", "a2", "approved", "Test", "critical")
    allowed, msg = defender.check_action(action, "p1")
    assert not allowed

def test_structured_decision_fields(temp_env):
    defender = DefenderAgent(temp_env)
    action = {
        "worker": "ShellWorker",
        "type": "run",
        "action_id": "a3",
        "params": {"command": "echo hello"}
    }
    decision = defender.evaluate_action(action, "p1")
    assert "action_id" in decision
    assert "decision" in decision
    assert "reason" in decision
    assert "matched_rule" in decision
    assert "risk_level" in decision
    assert "timestamp" in decision
    assert decision["decision"] == "allow"
