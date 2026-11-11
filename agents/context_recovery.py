import os
from typing import Dict, Any

class ContextRecovery:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def build_recovery_packet(self, objective: str, current_status: str, memory: Dict[str, Any], latest_obs: Dict[str, Any], latest_report: str) -> str:
        errors = ""
        action_results = latest_obs.get("worker_results", [])
        if action_results:
            for ar in action_results:
                if ar.get("status") == "failed":
                    errors += f"\nACTION ID: {ar.get('action_id')}\nERROR: {ar.get('error')}\n"
                    data = ar.get("data", {})
                    if "stdout" in data and data["stdout"]:
                        errors += f"STDOUT: {data['stdout'][-1000:]}\n"
                    if "stderr" in data and data["stderr"]:
                        errors += f"STDERR: {data['stderr'][-1000:]}\n"
                        
        template = f"""You are continuing a long-running agent task.

The previous context may be incomplete, so use this recovery packet.

ORIGINAL OBJECTIVE:
{objective}

CURRENT STATUS:
{current_status}

WHAT HAS BEEN TRIED:
{chr(10).join(memory.get('what_was_tried', []))}

WHAT WORKED:
{chr(10).join(memory.get('what_worked', []))}

WHAT FAILED:
{chr(10).join(memory.get('what_failed', []))}

BLOCKERS:
{chr(10).join(memory.get('blocked_actions', []))}

LATEST OBSERVATION:
{latest_obs.get('manager_summary', 'None')}

EXACT FAILURE LOGS:
{errors}

LATEST REPORT:
{latest_report}

OPEN QUESTIONS:
None currently recorded.

KNOWN CONSTRAINTS:
- Keep changes small
- Do not bypass safety

SAFETY RULES:
- Do not bypass website blocks, CAPTCHAs, paywalls, or access controls.
- Do not perform destructive actions without approval.
- Do not fake execution.
- Ask for missing information when necessary.

Your job:
1. Recover the full task state.
2. Identify the next smallest useful action.
3. Produce a valid plan.json for the runtime.
4. Include verification.
5. Include rollback.
6. If blocked, say exactly what input is needed.
"""
        
        ctx_path = os.path.join(self.base_dir, "state", "continuation_context.md")
        with open(ctx_path, "w", encoding="utf-8") as f:
            f.write(template)
            
        return ctx_path
