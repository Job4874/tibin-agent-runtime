from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, render_template

complexity_bp = Blueprint("complexity", __name__)


def get_base_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def read_text(path: Path, limit: int = 8000) -> str:
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:limit] + ("..." if len(text) > limit else "")
    except Exception as exc:
        return f"[read error: {exc}]"


def read_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def summarize_observation(obs: dict[str, Any]) -> dict[str, Any]:
    if not obs:
        return {
            "status": "unknown",
            "context_quality": "unknown",
            "next_action": "",
            "blockers": [],
            "open_questions": [],
        }

    complexity = obs.get("complexity_observation", {}) or {}

    return {
        "status": obs.get("status", "unknown"),
        "plan_id": obs.get("plan_id", ""),
        "objective_id": obs.get("objective_id", ""),
        "manager_summary": obs.get("manager_summary", ""),
        "context_quality": complexity.get("context_quality", "unknown"),
        "next_action": complexity.get("recommended_next_action", ""),
        "next_prompt": complexity.get("recommended_next_prompt", ""),
        "blockers": complexity.get("blocked_by", []) or obs.get("actions_blocked", []),
        "open_questions": complexity.get("new_questions", []),
        "errors": obs.get("errors", []),
    }


@complexity_bp.route("/complexity")
def complexity_page():
    base = get_base_dir()

    latest_observation = read_json(base / "observations" / "latest_observation.json")
    observation_summary = summarize_observation(latest_observation)

    data = {
        "observation": latest_observation,
        "summary": observation_summary,
        "next_prompt": read_text(base / "state" / "next_prompt.md"),
        "model_prompt": read_text(base / "state" / "model_prompt.md"),
        "continuation_context": read_text(base / "state" / "continuation_context.md"),
        "progress": read_text(base / "state" / "progress.md"),
        "blockers": read_text(base / "state" / "blockers.md"),
        "open_questions": read_text(base / "state" / "open_questions.md"),
        "assumptions": read_text(base / "state" / "assumptions.md"),
        "latest_report": read_text(base / "reports" / "latest_report.md"),
    }

    return render_template("complexity.html", **data)


@complexity_bp.route("/api/complexity/generate_prompt", methods=["POST"])
def generate_prompt():
    base = get_base_dir()
    cmd = [sys.executable, "runtime.py", "--next-prompt"]

    result = subprocess.run(
        cmd,
        cwd=str(base),
        capture_output=True,
        text=True,
        timeout=60,
    )

    return jsonify(
        {
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )


@complexity_bp.route("/api/complexity/checkpoint", methods=["POST"])
def create_checkpoint():
    base = get_base_dir()
    checkpoints = base / "reports" / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)

    report = read_text(base / "reports" / "latest_report.md", limit=20000)
    observation = read_text(base / "observations" / "latest_observation.json", limit=20000)

    checkpoint_path = checkpoints / "manual_complexity_checkpoint.md"
    checkpoint_path.write_text(
        "# Manual Complexity Checkpoint\n\n"
        "## Latest Report\n\n"
        f"{report or 'No latest report found.'}\n\n"
        "## Latest Observation\n\n"
        f"```json\n{observation or '{}'}\n```\n",
        encoding="utf-8",
    )

    return jsonify({"status": "success", "checkpoint_path": str(checkpoint_path)})
