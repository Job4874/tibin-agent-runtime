import pytest
import os
import json
from workers.memory_worker import MemoryWorker

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    os.makedirs(os.path.join(base_dir, "state"), exist_ok=True)
    return base_dir

def test_memory_updates_after_success(temp_env):
    mw = MemoryWorker(temp_env)
    mw.execute({"params": {"update_type": "what_worked", "data": "plan-001"}})
    with open(os.path.join(temp_env, "state", "memory.json"), "r") as f:
        data = json.load(f)
    assert "plan-001" in data.get("what_worked", [])

def test_memory_appends_failed_patterns(temp_env):
    mw = MemoryWorker(temp_env)
    mw.execute({"params": {"update_type": "what_failed", "data": "Connection refused"}})
    mw.execute({"params": {"update_type": "what_failed", "data": "Connection refused"}})
    with open(os.path.join(temp_env, "state", "memory.json"), "r") as f:
        data = json.load(f)
    failures = data.get("what_failed", [])
    assert len(failures) >= 1
