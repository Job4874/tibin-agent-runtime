"""The --approve CLI path must create a signed approval record."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def test_approve_plan_creates_signed_record(tmp_path, monkeypatch):
    import runtime
    from tools.approval_store import ApprovalStore

    plan = {"plan_id": "test_plan_approve", "actions": []}
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    monkeypatch.setattr(runtime, "get_base_dir", lambda: str(tmp_path))
    runtime.approve_plan(str(plan_path))

    store = ApprovalStore(str(tmp_path))
    record = store.find_valid_approval("test_plan_approve", "*")
    assert record is not None
    assert record["decision"] == "approved"
    assert record["signature"]
