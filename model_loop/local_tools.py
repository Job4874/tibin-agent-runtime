"""Local tool helpers for autonomous mode when the LLM response is weak."""

import glob
import os
from typing import Any, Dict, List, Optional


def _is_weak_brain_answer(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return True
    lower = text.lower().strip()
    weak_phrases = [
        "user safety",
        "i cannot",
        "i can't",
        "as an ai",
        "i'm unable",
    ]
    if len(text) < 80 and any(p in lower for p in weak_phrases):
        return True
    if lower in ("safe", "ok", "done"):
        return True
    return False


def _list_py_files(base_dir: str, root_only: bool) -> List[str]:
    if root_only:
        pattern = os.path.join(base_dir, "*.py")
    else:
        pattern = os.path.join(base_dir, "**", "*.py")
    return sorted(os.path.relpath(p, base_dir) for p in glob.glob(pattern, recursive=not root_only))


def detect_list_files_goal(goal: str) -> Optional[Dict[str, Any]]:
    """Return tool spec if goal looks like a file-listing request."""
    lower = goal.lower()
    list_markers = ["list", "show", "find", "enumerate"]
    file_markers = [".py", "python", "files", "file"]
    if not any(m in lower for m in list_markers):
        return None
    if not any(m in lower for m in file_markers):
        return None

    root_only = any(x in lower for x in ["project root", "root", "top level", "root directory"])
    ext = ".py" if ".py" in lower or "python" in lower else None
    return {"kind": "list_files", "root_only": root_only, "ext": ext}


def run_local_tool_for_goal(base_dir: str, goal: str, defender, shell_worker) -> Optional[Dict[str, Any]]:
    """Run a safe local tool when the goal maps to a known read-only operation."""
    spec = detect_list_files_goal(goal)
    if not spec:
        return None

    if spec.get("ext") in (".py", None) and spec.get("kind") == "list_files":
        files = _list_py_files(base_dir, spec.get("root_only", True))
        return {
            "status": "success",
            "tool": "FileWorker/list",
            "output": "\n".join(files),
        }

    # Generic shell listing for other extensions (simple commands only)
    ext = spec.get("ext", "*")
    if os.name == "nt":
        cmd = f'dir /b *{ext}' if ext != "*" else "dir /b"
    else:
        cmd = f'ls -1 *{ext} 2>/dev/null || true'

    action = {
        "action_id": "auto-tool-1",
        "worker": "ShellWorker",
        "type": "execute",
        "reason": "list_files_goal",
        "params": {"command": cmd, "cwd": base_dir},
        "risk_level": "low",
        "requires_approval": False,
    }

    decision = defender.evaluate_action(action, plan_id="autonomous-local")
    if decision.get("decision") != "allow":
        return {"status": "blocked", "error": decision.get("reason", "Defender blocked command")}

    result = shell_worker.execute(action)
    if result.get("status") != "success":
        return result

    stdout = result.get("data", {}).get("stdout", "")
    return {
        "status": "success",
        "tool": "ShellWorker",
        "command": cmd,
        "output": stdout.strip(),
    }
