import os
import json
from datetime import datetime, timezone
from model_loop.evidence_recorder import EvidenceRecorder

class PromptBuilder:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.outbox_requests_dir = os.path.join(base_dir, "outbox", "model_requests")
        self.outbox_prompts_dir = os.path.join(base_dir, "outbox", "model_prompts")
        os.makedirs(self.outbox_requests_dir, exist_ok=True)
        os.makedirs(self.outbox_prompts_dir, exist_ok=True)

    def _read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def _truncate(self, text: str, max_len: int = 8000) -> str:
        if not text or len(text) <= max_len:
            return text
        half = (max_len // 2) - 20
        return text[:half] + "\n\n...<TRUNCATED>...\n\n" + text[-half:]

    def build_prompt(self, objective: str = "Continue next steps for the current plan") -> tuple[str, str]:
        # Gather state
        obs_path = os.path.join(self.base_dir, "observations", "latest_observation.json")
        rep_path = os.path.join(self.base_dir, "reports", "latest_report.md")
        ctx_path = os.path.join(self.base_dir, "state", "continuation_context.md")
        
        obs_content = self._read_file(obs_path)
        rep_content = self._read_file(rep_path)
        ctx_content = self._read_file(ctx_path)

        now = datetime.now(timezone.utc)
        request_id = f"model_request_{now.strftime('%Y%m%dT%H%M%S%fZ')}"

        packet = {
            "request_id": request_id,
            "objective": objective,
            "latest_status": "Ready",
            "latest_observation_summary": self._truncate(obs_content) if obs_content else "None",
            "latest_report_summary": self._truncate(rep_content) if rep_content else "None",
            "blockers": [],
            "open_questions": [],
            "required_output": "valid plan.json only",
            "schema_path": "schemas/plan.schema.json",
            "safety_rules": [
                "Include approvals for risky actions",
                "Do not bypass safety",
                "Do not repeat completed actions",
                "Produce valid plan JSON only"
            ],
            "next_smallest_action": "Evaluate the state and emit a single next step",
            "created_at": now.isoformat()
        }

        prompt = f"""# System Prompt
Continue from the latest verified state.
Do not repeat completed actions.
Produce valid plan JSON only.
Include verification.
Include rollback.
Include approvals for risky actions.
Do not bypass safety.
If blocked, ask for needed input.

# Context
{ctx_content}

# Observation
{obs_content}

# Report
{rep_content}

# Objective
{objective}
"""
        evidence = EvidenceRecorder(self.base_dir)
        snapshot = evidence.record_prompt_snapshot(request_id, objective, prompt, packet)
        packet["evidence"] = snapshot

        # Write Request JSON
        request_path = os.path.join(self.outbox_requests_dir, "latest_model_request.json")
        with open(request_path, "w", encoding="utf-8") as f:
            json.dump(packet, f, indent=2)

        # Write Prompt Markdown
        prompt_path = os.path.join(self.outbox_prompts_dir, "latest_prompt.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
            
        # Also write state/next_prompt.md (or model_prompt.md) as requested by other parts
        state_prompt_path = os.path.join(self.base_dir, "state", "model_prompt.md")
        os.makedirs(os.path.dirname(state_prompt_path), exist_ok=True)
        with open(state_prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        return prompt_path, request_path
