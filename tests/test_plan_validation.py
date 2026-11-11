import pytest
import os
import json
import tempfile

from model_loop.plan_validator import PlanValidator

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    os.makedirs(os.path.join(base_dir, "inbox", "validated_plans"))
    os.makedirs(os.path.join(base_dir, "inbox", "rejected_plans"))
    return base_dir

def test_valid_plan(temp_env):
    pv = PlanValidator(temp_env)
    plan = {
        "plan_id": "plan-001",
        "objective_id": "obj-001",
        "objective": "Test objective",
        "actions": [
            {"action_id": "a1", "worker": "ShellWorker", "type": "run", "params": {"command": "echo hi"}}
        ]
    }
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, dir=temp_env)
    json.dump(plan, tmp)
    tmp.close()
    is_valid, msg = pv.ingest_candidate(tmp.name, os.path.join(temp_env, "inbox", "validated_plans"), os.path.join(temp_env, "inbox", "rejected_plans"))
    assert is_valid, msg

def test_missing_actions(temp_env):
    pv = PlanValidator(temp_env)
    plan = {
        "plan_id": "plan-002",
        "objective_id": "obj-002",
        "objective": "Test objective",
        "actions": []
    }
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, dir=temp_env)
    json.dump(plan, tmp)
    tmp.close()
    is_valid, msg = pv.ingest_candidate(tmp.name, os.path.join(temp_env, "inbox", "validated_plans"), os.path.join(temp_env, "inbox", "rejected_plans"))
    assert not is_valid

def test_missing_plan_id(temp_env):
    pv = PlanValidator(temp_env)
    plan = {
        "objective_id": "obj-003",
        "objective": "Test objective",
        "actions": [{"action_id": "a1", "worker": "ShellWorker", "type": "run", "params": {"command": "echo hi"}}]
    }
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, dir=temp_env)
    json.dump(plan, tmp)
    tmp.close()
    is_valid, msg = pv.ingest_candidate(tmp.name, os.path.join(temp_env, "inbox", "validated_plans"), os.path.join(temp_env, "inbox", "rejected_plans"))
    assert not is_valid
