import json
import os
import sys
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from agents.complexity_engine import ComplexityEngine


class ManagerAgent:
    def __init__(self, base_dir: str, defender, workers: Dict[str, Any]):
        self.base_dir = base_dir
        self.defender = defender
        self.workers = workers
        self.complexity_engine = ComplexityEngine(base_dir)

    def _resolve_params(self, params: Any, context: Dict[str, Any]) -> Any:
        if isinstance(params, dict):
            return {k: self._resolve_params(v, context) for k, v in params.items()}
        elif isinstance(params, list):
            return [self._resolve_params(v, context) for v in params]
        elif isinstance(params, str):
            if params.startswith("$"):
                var_path = params[1:].split(".")
                if len(var_path) == 2:
                    act_id, key = var_path
                    if act_id in context and isinstance(context[act_id], dict) and key in context[act_id]:
                        return context[act_id][key]
            resolved_str = params
            for act_id, act_data in context.items():
                if isinstance(act_data, dict):
                    for k, v in act_data.items():
                        var_name = f"${act_id}.{k}"
                        if var_name in resolved_str:
                            resolved_str = resolved_str.replace(var_name, str(v))
            return resolved_str
        else:
            return params

    def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = plan.get("plan_id", "unknown")
        actions = plan.get("actions", [])

        # Generate run ID and artifact directory
        run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        run_id = f"run_{run_timestamp}_{plan_id}"
        run_dir = Path(self.base_dir) / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save plan snapshot
        (run_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

        # Capture stdout/stderr logs
        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"
        defender_decisions_path = run_dir / "defender_decisions.json"
        worker_results_path = run_dir / "worker_results.json"

        # ComplexityEngine: pre-execution analysis
        # Use the richest available description so the engine doesn't block valid plans.
        objective = (
            plan.get("objective")
            or plan.get("goal")
            or plan.get("title")
            or plan.get("objective_id")
            or f"Execute plan {plan_id}"
        )
        memory = self._load_memory()
        latest_obs = self._load_latest_observation()
        complexity_pre = self.complexity_engine.analyze_objective(objective, memory, latest_obs)
        if complexity_pre.get("context_quality") in ["insufficient", "contradictory"]:
            self._write_state_file("state/progress.md", f"Run {run_id}: Context insufficient. Halting.\n")
            return {
                "plan_id": plan_id,
                "run_id": run_id,
                "run_dir": str(run_dir),
                "status": "blocked",
                "action_results": [],
                "complexity_observation": complexity_pre,
            }

        # Determine next smallest action if vague
        if complexity_pre.get("next_smallest_action"):
            next_action_hint = complexity_pre["next_smallest_action"]
            actions = [a for a in actions if a.get("action_id") == next_action_hint] or actions

        results = []
        defender_decisions = []

        for action in actions:
            action_id = action.get("action_id", "unknown")
            worker_name = action.get("worker")

            if action.get("status") == "success":
                results.append({"action_id": action_id, "status": "success"})
                continue

            # 1. Ask Defender (structured decision)
            decision = self.defender.evaluate_action(action, plan_id)
            defender_decisions.append(decision)

            if decision["decision"] != "allow":
                if decision["decision"] == "approval_required":
                    result = {
                        "action_id": action_id,
                        "status": "pending_approval",
                        "error": f"Defender blocked action pending approval: {decision['reason']}",
                        "defender_decision": decision,
                    }
                    results.append(result)
                    action["status"] = "pending_approval"
                    break
                else:
                    result = {
                        "action_id": action_id,
                        "status": "blocked",
                        "error": f"Defender hard blocked action: {decision['reason']}",
                        "defender_decision": decision,
                    }
                    results.append(result)
                    action["status"] = "blocked"
                    break

            # 2. Route to Worker
            worker = self.workers.get(worker_name)
            if not worker:
                result = {
                    "action_id": action_id,
                    "status": "failed",
                    "error": f"Worker {worker_name} not found.",
                }
                results.append(result)
                break

            # Resolve variables
            context_map = {}
            for res in results:
                if res.get("status") == "success" and "data" in res:
                    context_map[res["action_id"]] = res["data"]
            action["params"] = self._resolve_params(action.get("params", {}), context_map)

            # 3. Execute
            try:
                worker_result = worker.execute(action)
                worker_result["action_id"] = action_id
                worker_result["defender_decision"] = decision

                # 4. Auto-verify successful actions via VerifierWorker
                if worker_result.get("status") == "success":
                    verification = self._auto_verify(action, worker_result)
                    worker_result["verification"] = verification
                    if verification.get("status") == "failed":
                        worker_result["status"] = "failed"
                        worker_result["error"] = f"Verification failed: {verification.get('reason', '')}"

                results.append(worker_result)
                action["status"] = worker_result.get("status")

                if worker_result.get("status") == "success":
                    self.defender.mark_approval_used(plan_id, action_id)

                if worker_result.get("status") in ["failed", "blocked"]:
                    break
            except Exception as e:
                results.append({
                    "action_id": action_id,
                    "status": "failed",
                    "error": str(e),
                })
                action["status"] = "failed"
                break

        # Post-execution complexity analysis
        complexity_post = self.complexity_engine.analyze_objective(objective, memory, latest_obs)
        if results:
            last_result = results[-1]
            if last_result.get("status") in ["failed", "blocked"]:
                complexity_post["context_quality"] = "hazy"
                complexity_post["blocked_by"] = [last_result.get("error", "")]

        # Write artifact files
        (run_dir / "worker_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        (run_dir / "defender_decisions.json").write_text(json.dumps(defender_decisions, indent=2, default=str), encoding="utf-8")

        # Git diff if available
        diff_path = run_dir / "diff.patch"
        try:
            diff = subprocess.run(["git", "diff"], capture_output=True, text=True, cwd=self.base_dir)
            if diff.stdout:
                diff_path.write_text(diff.stdout, encoding="utf-8")
        except Exception:
            pass

        # Build observation
        status = "failed"
        if all(r.get("status") == "success" for r in results):
            status = "completed"
        elif any(r.get("status") == "pending_approval" for r in results):
            status = "pending_approval"
        elif any(r.get("status") == "blocked" for r in results):
            status = "blocked"

        observation = {
            "observation_id": f"obs-{plan_id}",
            "run_id": run_id,
            "run_dir": str(run_dir),
            "plan_id": plan_id,
            "objective_id": plan.get("objective_id"),
            "status": status,
            "actions_executed": [r.get("action_id") for r in results if r.get("status") == "success"],
            "actions_blocked": [r.get("action_id") for r in results if r.get("status") == "blocked"],
            "actions_failed": [r.get("action_id") for r in results if r.get("status") == "failed"],
            "errors": [r.get("error") for r in results if r.get("error")],
            "commands_run": [r.get("data", {}).get("command") for r in results if isinstance(r.get("data"), dict) and r.get("data", {}).get("command")],
            "worker_results": results,
            "defender_decisions": defender_decisions,
            "complexity_observation": complexity_post,
        }

        # Save observation to run dir and latest
        (run_dir / "observation.json").write_text(json.dumps(observation, indent=2, default=str), encoding="utf-8")
        latest_obs_path = Path(self.base_dir) / "observations" / "latest_observation.json"
        latest_obs_path.parent.mkdir(parents=True, exist_ok=True)
        latest_obs_path.write_text(json.dumps(observation, indent=2, default=str), encoding="utf-8")

        # Save report to run dir and latest
        report_text = self._build_report(observation)
        (run_dir / "report.md").write_text(report_text, encoding="utf-8")
        latest_report_path = Path(self.base_dir) / "reports" / "latest_report.md"
        latest_report_path.parent.mkdir(parents=True, exist_ok=True)
        latest_report_path.write_text(report_text, encoding="utf-8")

        # Write ComplexityEngine state outputs
        self._write_state_file("state/progress.md", f"Run {run_id}: {status}\nExecuted: {observation['actions_executed']}\nBlocked: {observation['actions_blocked']}\nFailed: {observation['actions_failed']}\n")
        blockers_md = "\n".join(f"- {e}" for e in observation["errors"]) if observation["errors"] else "No blockers."
        self._write_state_file("state/blockers.md", blockers_md)
        if complexity_post.get("recommended_next_action"):
            self._write_state_file("state/next_prompt.md", f"# Next Recommended Action\n\n{complexity_post['recommended_next_action']}")
        if complexity_post.get("recommended_next_prompt"):
            self._write_state_file("state/continuation_context.md", complexity_post["recommended_next_prompt"])

        return observation

    def _auto_verify(self, action: Dict[str, Any], worker_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run a lightweight post-action verification using VerifierWorker if available."""
        verifier = self.workers.get("VerifierWorker")
        if not verifier:
            return {"status": "skipped", "reason": "VerifierWorker not registered"}

        worker_name = action.get("worker", "")
        params = action.get("params", {})
        data = worker_result.get("data", {})

        # Build a verification action based on the worker that just ran
        if worker_name == "FileWorker":
            action_type = action.get("type", "")
            if action_type in ("write", "append", "create_dir"):
                path = params.get("path") or params.get("dir_path", "")
                if path:
                    verify_action = {
                        "action_id": f"verify-{action.get('action_id', 'unknown')}",
                        "worker": "VerifierWorker",
                        "type": "file_exists",
                        "params": {"path": path},
                    }
                    return verifier.execute(verify_action)
        elif worker_name == "ShellWorker":
            # Verify the command exited without error (exit_code available in data)
            exit_code = data.get("exit_code")
            if exit_code is not None and exit_code != 0:
                return {"status": "failed", "reason": f"Shell command exited with code {exit_code}"}
        elif worker_name == "CoderWorker":
            action_type = action.get("type", "")
            if action_type == "write_code":
                path = data.get("path") or params.get("path", "")
                if path:
                    verify_action = {
                        "action_id": f"verify-{action.get('action_id', 'unknown')}",
                        "worker": "VerifierWorker",
                        "type": "file_exists",
                        "params": {"path": path},
                    }
                    return verifier.execute(verify_action)

        return {"status": "skipped", "reason": "No verification rule for this action"}

    def _load_memory(self) -> Dict[str, Any]:
        memory_path = Path(self.base_dir) / "state" / "memory.json"
        try:
            return json.loads(memory_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _load_latest_observation(self) -> Dict[str, Any]:
        obs_path = Path(self.base_dir) / "observations" / "latest_observation.json"
        try:
            return json.loads(obs_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_state_file(self, rel_path: str, content: str) -> None:
        path = Path(self.base_dir) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _build_report(self, observation: Dict[str, Any]) -> str:
        lines = [
            f"# Run Report - {datetime.now(timezone.utc).isoformat()}",
            "",
            f"**Objective:** {observation.get('objective_id', '')}",
            f"**Plan ID:** {observation.get('plan_id', '')}",
            f"**Run ID:** {observation.get('run_id', '')}",
            f"**Status:** {observation.get('status', '')}",
            "",
            "## Actions",
            f"- Executed: {len(observation.get('actions_executed', []))}",
            f"- Blocked: {len(observation.get('actions_blocked', []))}",
            f"- Failed: {len(observation.get('actions_failed', []))}",
            "",
            "## Details",
        ]
        for r in observation.get("worker_results", []):
            status = r.get("status")
            act_id = r.get("action_id")
            error = r.get("error", "")
            lines.append(f"- Action `{act_id}`: {status}" + (f" ({error})" if error else ""))
        if observation.get("errors"):
            lines.extend(["", "## Errors"])
            for e in observation["errors"]:
                lines.append(f"- {e}")
        lines.append("")
        return "\n".join(lines)
