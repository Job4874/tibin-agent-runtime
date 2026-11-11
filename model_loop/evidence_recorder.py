import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class EvidenceRecorder:
    """Persist prompt and model-response evidence for evals and future tuning."""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.datasets_dir = self.base_dir / "datasets"
        self.prompt_dir = self.datasets_dir / "prompts"
        self.request_dir = self.datasets_dir / "requests"
        self.training_dir = self.datasets_dir / "training"
        self.eval_dir = self.datasets_dir / "eval"

        for directory in [
            self.datasets_dir,
            self.prompt_dir,
            self.request_dir,
            self.training_dir,
            self.eval_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def record_prompt_snapshot(
        self,
        request_id: str,
        objective: str,
        prompt_text: str,
        request_packet: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt_path = self.prompt_dir / f"{request_id}.md"
        request_path = self.request_dir / f"{request_id}.json"

        prompt_path.write_text(prompt_text, encoding="utf-8")
        request_path.write_text(json.dumps(request_packet, indent=2, default=str), encoding="utf-8")

        record = {
            "event": "prompt_snapshot",
            "request_id": request_id,
            "objective": objective,
            "prompt_path": self._rel(prompt_path),
            "request_path": self._rel(request_path),
            "prompt_sha256": self._sha256(prompt_text),
            "created_at": self._now(),
        }
        self._append_jsonl(self.datasets_dir / "prompt_versions.jsonl", record)
        return record

    def record_model_exchange(
        self,
        *,
        response_text: str,
        parse_status: str,
        parse_error: str = "",
        candidate_plan: Optional[Dict[str, Any]] = None,
        raw_response_archive: Optional[str] = None,
        candidate_plan_path: Optional[str] = None,
        rejected_plan_path: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt_text = self._read_text(self.base_dir / "outbox" / "model_prompts" / "latest_prompt.md")
        request_packet = self._read_json(self.base_dir / "outbox" / "model_requests" / "latest_model_request.json")
        request_id = request_id or request_packet.get("request_id") or f"unknown_{int(datetime.now(timezone.utc).timestamp())}"

        record = {
            "event": "model_exchange",
            "request_id": request_id,
            "prompt_sha256": self._sha256(prompt_text) if prompt_text else "",
            "response_sha256": self._sha256(response_text),
            "parse_status": parse_status,
            "parse_error": parse_error,
            "candidate_plan": candidate_plan or None,
            "candidate_plan_path": self._rel(candidate_plan_path),
            "rejected_plan_path": self._rel(rejected_plan_path),
            "raw_response_archive": self._rel(raw_response_archive),
            "prompt_text": prompt_text,
            "response_text": response_text,
            "created_at": self._now(),
        }
        self._append_jsonl(self.datasets_dir / "model_io.jsonl", record)
        return record

    def export_training_data(self) -> Dict[str, Any]:
        exchanges = list(self._read_jsonl(self.datasets_dir / "model_io.jsonl"))
        train_rows: List[Dict[str, Any]] = []
        eval_rows: List[Dict[str, Any]] = []

        for row in exchanges:
            parse_status = row.get("parse_status", "")
            candidate_plan = row.get("candidate_plan")
            prompt_text = row.get("prompt_text", "")
            is_training_eligible, validation_error = self._is_training_eligible_plan(candidate_plan)

            eval_rows.append(
                {
                    "request_id": row.get("request_id"),
                    "prompt_sha256": row.get("prompt_sha256"),
                    "response_sha256": row.get("response_sha256"),
                    "parse_status": parse_status,
                    "has_candidate_plan": bool(candidate_plan),
                    "training_eligible": is_training_eligible,
                    "validation_error": validation_error,
                    "parse_error": row.get("parse_error", ""),
                    "created_at": row.get("created_at"),
                }
            )

            if parse_status == "parsed" and is_training_eligible and prompt_text:
                train_rows.append(
                    {
                        "messages": [
                            {
                                "role": "system",
                                "content": "You generate safe Tibin runtime plan JSON only.",
                            },
                            {"role": "user", "content": prompt_text},
                            {
                                "role": "assistant",
                                "content": json.dumps(candidate_plan, indent=2, sort_keys=True),
                            },
                        ],
                        "metadata": {
                            "request_id": row.get("request_id"),
                            "prompt_sha256": row.get("prompt_sha256"),
                            "response_sha256": row.get("response_sha256"),
                        },
                    }
                )

        training_path = self.training_dir / "model_plan_sft.jsonl"
        eval_path = self.eval_dir / "plan_parse_eval.jsonl"
        self._write_jsonl(training_path, train_rows)
        self._write_jsonl(eval_path, eval_rows)

        return {
            "status": "success",
            "model_io_rows": len(exchanges),
            "training_rows": len(train_rows),
            "eval_rows": len(eval_rows),
            "training_path": self._rel(training_path),
            "eval_path": self._rel(eval_path),
            "created_at": self._now(),
        }

    def _append_jsonl(self, path: Path, row: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def _write_jsonl(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, default=str) + "\n")

    def _read_jsonl(self, path: Path) -> Iterable[Dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _read_json(self, path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _rel(self, path: Optional[Any]) -> Optional[str]:
        if not path:
            return None
        try:
            return os.path.relpath(str(path), str(self.base_dir))
        except ValueError:
            return str(path)

    def _sha256(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _is_training_eligible_plan(self, plan: Optional[Dict[str, Any]]) -> tuple[bool, str]:
        if not isinstance(plan, dict):
            return False, "candidate plan missing"

        required = ["plan_id", "objective_id", "title", "actions", "complexity"]
        missing = [key for key in required if key not in plan]
        if missing:
            return False, f"missing required fields: {', '.join(missing)}"

        actions = plan.get("actions")
        if not isinstance(actions, list) or not actions:
            return False, "actions must be a non-empty list"
        for index, action in enumerate(actions):
            if not isinstance(action, dict):
                return False, f"action {index} is not an object"
            for key in ["action_id", "worker", "type"]:
                if key not in action:
                    return False, f"action {index} missing {key}"

        complexity = plan.get("complexity")
        if not isinstance(complexity, dict):
            return False, "complexity must be an object"

        problem_type = complexity.get("problem_type")
        if problem_type not in {"coding", "research", "browser", "debugging", "planning", "mixed"}:
            return False, f"unsupported complexity.problem_type: {problem_type}"

        estimated_depth = complexity.get("estimated_depth")
        if estimated_depth not in {"simple", "medium", "deep", "unknown"}:
            return False, f"unsupported complexity.estimated_depth: {estimated_depth}"

        return True, ""
