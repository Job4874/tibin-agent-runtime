"""
Agent loop for plan replay and OpenRouter-driven autonomous tasks.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from brain.openrouter_brain import OpenRouterBrain
from model_loop.local_tools import _is_weak_brain_answer, run_local_tool_for_goal
from utils.env_loader import load_dotenv

AUTONOMOUS_SYSTEM = """You are Tibin Agent Runtime, a local coding agent.
You have workers: ShellWorker (run safe shell commands), FileWorker (read/list files).
When the user asks to list files, respond with the actual filenames from tool output if provided.
Do not return HTML, login pages, or vague safety-only replies — give a useful answer."""


def _write_trace(trace_path: str, event: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(trace_path), exist_ok=True)
    event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with open(trace_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def run_plan_loop(plan_path: str, base_dir: str, max_turns: int = 10) -> Dict[str, Any]:
    """Execute a validated plan JSON through the runtime (ReAct-style replay)."""
    load_dotenv(base_dir)

    if not os.path.exists(plan_path):
        return {"status": "failed", "error": f"Plan not found: {plan_path}"}

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    plan_id = plan.get("plan_id", "unknown")
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"run_{run_timestamp}_{plan_id}"
    run_dir = os.path.join(base_dir, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    trace_path = os.path.join(run_dir, "trace.jsonl")

    _write_trace(trace_path, {"event": "loop_start", "mode": "plan_replay", "plan_path": plan_path, "max_turns": max_turns})

    import sys
    sys.path.insert(0, base_dir)
    from runtime import run_plan

    _write_trace(trace_path, {"event": "plan_execute", "plan_id": plan_id})
    result = run_plan(plan_path)

    status = (result or {}).get("status", "failed")
    _write_trace(trace_path, {"event": "loop_end", "status": status, "result": result})

    return {
        "status": status,
        "run_id": run_id,
        "run_dir": run_dir,
        "trace_path": trace_path,
        "result": result,
    }


def run_autonomous(goal: str, base_dir: str, max_turns: int = 10) -> Dict[str, Any]:
    """Run a natural-language goal using OpenRouter + local tools (no BoodleBox fallback)."""
    load_dotenv(base_dir)
    brain = OpenRouterBrain(base_dir)

    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    safe_slug = "".join(c if c.isalnum() else "_" for c in goal[:40]).strip("_")
    run_id = f"run_{run_timestamp}_{safe_slug or 'autonomous'}"
    run_dir = os.path.join(base_dir, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    trace_path = os.path.join(run_dir, "trace.jsonl")

    _write_trace(trace_path, {
        "event": "loop_start",
        "mode": "autonomous",
        "goal": goal,
        "max_turns": max_turns,
        "brain": brain.get_status(),
    })

    if not brain.is_configured():
        outcome = {
            "status": "failed_no_brain",
            "error": (
                "OPENROUTER_API_KEY is not configured. "
                "Autonomous mode requires OpenRouter — it does not fall back to BoodleBox. "
                "Add OPENROUTER_API_KEY to .env or use: python runtime.py --run-loop examples/safe_code_plan.json"
            ),
            "run_id": run_id,
            "trace_path": trace_path,
        }
        _write_trace(trace_path, {"event": "loop_end", **outcome})
        return outcome

    import sys
    sys.path.insert(0, base_dir)
    from runtime import init_runtime

    manager = init_runtime()
    defender = manager.defender
    shell_worker = manager.workers.get("ShellWorker")

    tool_result = None
    if shell_worker:
        tool_result = run_local_tool_for_goal(base_dir, goal, defender, shell_worker)
        if tool_result:
            _write_trace(trace_path, {"event": "local_tool", "result": tool_result})

    tool_output = (tool_result or {}).get("output", "")
    final_text = ""

    for turn in range(1, max_turns + 1):
        prompt_parts = [f"Goal: {goal}", f"Turn {turn}/{max_turns}."]
        if tool_output:
            prompt_parts.append(f"Tool output from ShellWorker:\n{tool_output}")
            prompt_parts.append("Summarize the tool output to answer the goal. List filenames clearly.")
        else:
            prompt_parts.append("If the goal is to list files, respond with a clear list of filenames.")
        prompt = "\n\n".join(prompt_parts)

        _write_trace(trace_path, {"event": "brain_request", "turn": turn, "prompt_preview": prompt[:500]})

        result = brain.complete(prompt, system=AUTONOMOUS_SYSTEM)
        _write_trace(trace_path, {
            "event": "brain_response",
            "turn": turn,
            "result": {k: v for k, v in result.items() if k != "raw_text"},
            "text_preview": (result.get("raw_text") or "")[:500],
        })

        if result["status"] == "failed_no_brain":
            outcome = {"status": "failed_no_brain", "error": result.get("error"), "run_id": run_id, "trace_path": trace_path}
            _write_trace(trace_path, {"event": "loop_end", **outcome})
            return outcome

        if result["status"] == "blocked_login_page":
            outcome = {"status": "blocked_login_page", "error": result.get("error"), "run_id": run_id, "trace_path": trace_path}
            _write_trace(trace_path, {"event": "loop_end", **outcome})
            return outcome

        if result["status"] != "success":
            _write_trace(trace_path, {"event": "brain_error", "turn": turn, "error": result.get("error")})
            continue

        final_text = result.get("raw_text", "")

        # Prefer tool output when brain answer is weak but we have real data
        if tool_output and _is_weak_brain_answer(final_text):
            final_text = f"Files found:\n{tool_output}"

        if final_text.strip():
            outcome = {
                "status": "completed",
                "answer": final_text,
                "turns_used": turn,
                "run_id": run_id,
                "run_dir": run_dir,
                "trace_path": trace_path,
                "brain": "openrouter",
                "tool_used": bool(tool_output),
            }
            _write_trace(trace_path, {
                "event": "loop_end",
                **{k: v for k, v in outcome.items() if k != "answer"},
                "answer_preview": final_text[:500],
            })
            return outcome

    # Last resort: return tool output alone
    if tool_output:
        outcome = {
            "status": "completed",
            "answer": f"Files found:\n{tool_output}",
            "turns_used": max_turns,
            "run_id": run_id,
            "run_dir": run_dir,
            "trace_path": trace_path,
            "brain": "openrouter",
            "tool_used": True,
            "note": "Brain did not produce a useful answer; returned ShellWorker output.",
        }
        _write_trace(trace_path, {"event": "loop_end", **outcome})
        return outcome

    outcome = {
        "status": "max_turns_reached",
        "answer": final_text,
        "run_id": run_id,
        "trace_path": trace_path,
    }
    _write_trace(trace_path, {"event": "loop_end", **outcome})
    return outcome
