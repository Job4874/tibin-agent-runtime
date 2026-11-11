import pytest
import os
from workers.report_worker import ReportWorker

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    for d in ["reports", "observations", "logs"]:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)
    return base_dir

def test_report_generation(temp_env):
    rw = ReportWorker(temp_env)
    observation = {
        "plan_id": "plan-001",
        "objective_id": "obj-001",
        "status": "completed",
        "actions_executed": ["a1", "a2"],
        "actions_blocked": [],
        "errors": []
    }
    rw.execute({"params": {"observation_data": observation}})
    report_path = os.path.join(temp_env, "reports", "latest_report.md")
    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "plan-001" in content
    assert "completed" in content
