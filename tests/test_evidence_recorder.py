import json
import os

from model_loop.evidence_recorder import EvidenceRecorder
from model_loop.prompt_builder import PromptBuilder
from model_providers.browser_llm_provider import BrowserLLMProvider


def test_prompt_builder_versions_prompt_and_request(tmp_path):
    base_dir = str(tmp_path)
    for rel in ["observations", "reports", "state", "outbox/model_prompts", "outbox/model_requests"]:
        os.makedirs(os.path.join(base_dir, rel), exist_ok=True)

    prompt_path, request_path = PromptBuilder(base_dir).build_prompt("Fix the failing browser loop")

    assert os.path.exists(prompt_path)
    assert os.path.exists(request_path)

    with open(request_path, "r", encoding="utf-8") as f:
        request = json.load(f)

    evidence = request["evidence"]
    assert os.path.exists(os.path.join(base_dir, evidence["prompt_path"]))
    assert os.path.exists(os.path.join(base_dir, evidence["request_path"]))
    assert len(evidence["prompt_sha256"]) == 64


def test_browser_ingest_records_model_exchange_and_exports_training_data(tmp_path):
    base_dir = str(tmp_path)
    for rel in [
        "config",
        "state",
        "outbox/model_prompts",
        "outbox/model_requests",
        "inbox/provider_responses",
        "inbox/provider_responses/archive",
        "inbox/candidate_plans",
        "inbox/validated_plans",
        "inbox/rejected_plans",
    ]:
        os.makedirs(os.path.join(base_dir, rel), exist_ok=True)

    PromptBuilder(base_dir).build_prompt("Create a safe echo plan")

    plan = {
        "plan_id": "plan-evidence-001",
        "objective_id": "obj-evidence-001",
        "title": "Safe echo",
        "actions": [
            {
                "action_id": "act-1",
                "worker": "ShellWorker",
                "type": "run",
                "params": {"command": "echo evidence"},
            }
        ],
        "complexity": {"problem_type": "planning", "estimated_depth": "simple"},
    }
    response_path = os.path.join(base_dir, "inbox", "provider_responses", "response.txt")
    with open(response_path, "w", encoding="utf-8") as f:
        f.write("```json\n" + json.dumps(plan) + "\n```")

    result = BrowserLLMProvider({}, base_dir).ingest_response_file()
    assert result["status"] == "success"

    model_io_path = os.path.join(base_dir, "datasets", "model_io.jsonl")
    assert os.path.exists(model_io_path)

    export = EvidenceRecorder(base_dir).export_training_data()
    assert export["training_rows"] == 1
    assert export["eval_rows"] == 1
    assert os.path.exists(os.path.join(base_dir, export["training_path"]))
    assert os.path.exists(os.path.join(base_dir, export["eval_path"]))


def test_export_keeps_schema_drift_out_of_training_rows(tmp_path):
    base_dir = str(tmp_path)
    recorder = EvidenceRecorder(base_dir)
    recorder.record_model_exchange(
        response_text="{}",
        parse_status="parsed",
        candidate_plan={
            "plan_id": "bad-schema",
            "objective_id": "obj",
            "title": "Bad schema",
            "actions": [
                {
                    "action_id": "act-1",
                    "worker": "ShellWorker",
                    "type": "run",
                }
            ],
            "complexity": {"problem_type": "scripting", "estimated_depth": "shallow"},
        },
    )

    export = recorder.export_training_data()
    assert export["training_rows"] == 0
    assert export["eval_rows"] == 1

    with open(os.path.join(base_dir, export["eval_path"]), "r", encoding="utf-8") as f:
        row = json.loads(f.readline())
    assert row["training_eligible"] is False
    assert "unsupported complexity.problem_type" in row["validation_error"]
