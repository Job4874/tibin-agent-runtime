import pytest
import os
from agents.complexity_engine import ComplexityEngine

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    os.makedirs(os.path.join(base_dir, "state"), exist_ok=True)
    return base_dir

def test_analyze_clear_context(temp_env):
    ce = ComplexityEngine(temp_env)
    result = ce.analyze_objective("Run tests and report results.", {}, {})
    assert result["context_quality"] == "clear"
    assert result["recommended_next_action"] == "execute_next_worker_task"

def test_analyze_insufficient_context(temp_env):
    ce = ComplexityEngine(temp_env)
    result = ce.analyze_objective("", {}, {})
    assert result["context_quality"] == "insufficient"
    assert result["missing_context"]

def test_next_prompt_generation(temp_env):
    ce = ComplexityEngine(temp_env)
    path = ce.create_next_prompt_for_model()
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Continue" in content

def test_checkpoint_report(temp_env):
    ce = ComplexityEngine(temp_env)
    path = ce.create_checkpoint_report()
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Checkpoint" in content
