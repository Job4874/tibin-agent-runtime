import pytest
import os
import json
from model_loop.plan_validator import PlanValidator
from agents.defender_agent import DefenderAgent

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    os.makedirs(os.path.join(base_dir, "state"))
    os.makedirs(os.path.join(base_dir, "permissions"))
    os.makedirs(os.path.join(base_dir, "inbox", "candidate_plans"))
    os.makedirs(os.path.join(base_dir, "inbox", "validated_plans"))
    os.makedirs(os.path.join(base_dir, "inbox", "rejected_plans"))
    
    with open(os.path.join(base_dir, "permissions", "allowlist.json"), "w") as f:
        json.dump({"commands": ["ls"]}, f)
    with open(os.path.join(base_dir, "permissions", "tool_permissions.json"), "w") as f:
        json.dump({"allowed_tools": ["ShellWorker"]}, f)
    
    return base_dir

def test_model_cycle_safety_enforcement(temp_env):
    # Simulates provider generating a plan with a dangerous command
    dangerous_plan = {
        "plan_id": "p_danger",
        "actions": [{
            "action_id": "a1",
            "worker": "ShellWorker",
            "type": "run",
            "params": {"command": "rm -rf /"},
            "requires_approval": True
        }]
    }
    
    cand_path = os.path.join(temp_env, "inbox", "candidate_plans", "danger.json")
    with open(cand_path, "w") as f:
        json.dump(dangerous_plan, f)
        
    pv = PlanValidator(temp_env)
    val_dir = os.path.join(temp_env, "inbox", "validated_plans")
    rej_dir = os.path.join(temp_env, "inbox", "rejected_plans")
    
    # 1. Validation passes (it's valid JSON format)
    is_valid, msg = pv.ingest_candidate(cand_path, val_dir, rej_dir)
    assert is_valid
    
    # 2. Defender blocks it during runtime (requires approval)
    defender = DefenderAgent(temp_env)
    val_path = os.path.join(val_dir, "danger.json")
    with open(val_path, "r") as f:
        plan = json.load(f)
        
    allowed, msg = defender.check_action(plan["actions"][0], plan["plan_id"])
    assert not allowed
    assert "destructive" in msg.lower() or "blocked" in msg.lower()
