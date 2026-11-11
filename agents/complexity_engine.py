import os
import json
from datetime import datetime, timezone
from typing import Dict, Any

class ComplexityEngine:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def analyze_objective(self, objective: str, memory: Dict[str, Any], latest_observation: Dict[str, Any]) -> Dict[str, Any]:
        context_quality = "clear"
        missing = []
        blockers = []
        next_action = ""
        next_prompt = ""

        if not objective or len(objective) < 10:
            context_quality = "insufficient"
            missing.append("objective is too vague")

        if latest_observation:
            if latest_observation.get("status") in ["failed", "blocked"]:
                context_quality = "hazy"
                blockers.extend(latest_observation.get("errors", []))
            if latest_observation.get("actions_blocked"):
                context_quality = "hazy"
                blockers.append("Previous action blocked")

        failed_patterns = memory.get("failed_patterns", [])
        if len(failed_patterns) >= 3:
            context_quality = "contradictory"
            blockers.append("Repeated failures detected")

        if missing:
            next_action = "request_clarification"
            next_prompt = "The objective is missing context. Please provide more details."
        elif blockers:
            next_action = "resolve_blockers"
            next_prompt = f"Blocked by: {blockers}. Resolve before proceeding."
        elif objective:
            next_action = "execute_next_worker_task"
            next_prompt = "Proceed with next smallest action."

        progress_path = os.path.join(self.base_dir, "state", "progress.md")
        try:
            progress_text = open(progress_path, "r", encoding="utf-8").read()
        except Exception:
            progress_text = ""

        return {
            "status": "analyzed",
            "complexity": "medium",
            "context_quality": context_quality,
            "missing_context": missing,
            "blocked_by": blockers,
            "recommended_next_action": next_action,
            "recommended_next_prompt": next_prompt,
            "new_questions": missing,
            "progress_summary": progress_text[:500],
        }

    def decompose_goal(self, goal: str) -> list:
        return [f"Decomposed step for {goal}"]

    def detect_missing_context(self, plan: Dict[str, Any], observation: Dict[str, Any]) -> list:
        missing = []
        if not plan.get("objective"):
            missing.append("plan missing objective")
        if not plan.get("actions"):
            missing.append("plan missing actions")
        return missing

    def detect_hazy_context(self, memory: Dict[str, Any], observation: Dict[str, Any], report: str) -> bool:
        failed_count = len(memory.get("what_failed", []))
        if failed_count > 3:
            return True
        if observation and observation.get("status") in ["failed", "blocked"]:
            return True
        return False

    def detect_looping_behavior(self, run_history: list) -> bool:
        if not run_history or len(run_history) < 3:
            return False
        recent = run_history[-3:]
        failures = [r for r in recent if r.get("status") == "failed"]
        if len(failures) == 3:
            errors = set()
            for f in failures:
                action_results = f.get("action_results", [])
                for ar in action_results:
                    if ar.get("status") == "failed":
                        errors.add(ar.get("error", ""))
            if len(errors) == 1:
                return True
        return False

    def build_recovery_context(self) -> Dict[str, Any]:
        return {}

    def create_research_questions(self, goal: str, missing_info: list) -> list:
        return [f"Research: {info}" for info in missing_info]

    def create_next_prompt_for_model(self) -> str:
        prompt_path = os.path.join(self.base_dir, "state", "next_prompt.md")
        content = (
            "# System Prompt\n"
            "Continue from the latest verified state.\n"
            "Do not repeat completed actions.\n"
            "Produce valid plan JSON only.\n"
            "Include verification.\n"
            "Include rollback.\n"
            "Include approvals for risky actions.\n"
            "Do not bypass safety.\n"
            "If blocked, ask for needed input.\n"
        )
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(content)
        return prompt_path

    def create_checkpoint_report(self) -> str:
        report_path = os.path.join(self.base_dir, "reports", "checkpoints", "checkpoint.md")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Checkpoint\n\nContext saved.")
        return report_path

    def decide_next_move(self) -> str:
        return "execute_next_worker_task"
