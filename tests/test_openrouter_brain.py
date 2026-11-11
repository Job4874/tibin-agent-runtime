"""Tests for OpenRouter brain and agent loop guards."""

import json
import os
import tempfile
import shutil
import pytest

from brain.openrouter_brain import OpenRouterBrain
from model_loop.agent_loop import run_autonomous, run_plan_loop


@pytest.fixture
def tmp_base(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / "examples").mkdir()
    plan = {
        "plan_id": "plan-test-001",
        "objective_id": "obj-001",
        "actions": [],
    }
    (tmp_path / "examples" / "safe_code_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return str(tmp_path)


def test_brain_not_configured_without_key(tmp_base):
    brain = OpenRouterBrain(tmp_base)
    assert not brain.is_configured()
    status = brain.get_status()
    assert status["status"] == "not_configured"


def test_brain_configured_with_key(tmp_base, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    brain = OpenRouterBrain(tmp_base)
    assert brain.is_configured()
    assert brain.get_status()["status"] == "ready"


def test_login_page_detection():
    html = "<html><body>Sign in to continue. Accept cookies. Password</body></html>"
    assert OpenRouterBrain.is_login_page(html) is True
    assert OpenRouterBrain.is_login_page("Here are the files: runtime.py, app.py") is False


def test_autonomous_fails_no_brain_without_key(tmp_base):
    result = run_autonomous("List files", tmp_base, max_turns=3)
    assert result["status"] == "failed_no_brain"
    assert "OPENROUTER_API_KEY" in result["error"]
    assert os.path.exists(result["trace_path"])


def test_run_loop_writes_trace(tmp_base):
    result = run_plan_loop(
        os.path.join(tmp_base, "examples", "safe_code_plan.json"),
        tmp_base,
        max_turns=5,
    )
    assert "trace_path" in result
    assert os.path.exists(result["trace_path"])
