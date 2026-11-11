import json
import os
from typing import Dict, Any

class MemoryWorker:
    def __init__(self, base_dir: str):
        self.state_dir = os.path.join(base_dir, "state")
        self.memory_file = os.path.join(self.state_dir, "memory.json")

    def _load_memory(self) -> Dict[str, Any]:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "current_objective": "",
            "current_milestone": "",
            "what_was_tried": [],
            "what_worked": [],
            "what_failed": [],
            "lessons_learned": [],
            "blocked_actions": [],
            "recurring_commands": [],
            "environment_notes": [],
            "worker_success_failure_counts": {}
        }

    def _save_memory(self, memory: Dict[str, Any]):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2)

    def _append_to_md(self, filename: str, content: str):
        path = os.path.join(self.state_dir, filename)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        params = action.get("params", {})
        update_type = params.get("update_type")
        data = params.get("data")
        
        memory = self._load_memory()
        
        try:
            if update_type == "objective":
                memory["current_objective"] = data
            elif update_type == "milestone":
                memory["current_milestone"] = data
            elif update_type in ["what_was_tried", "what_worked", "what_failed", "lessons_learned", "blocked_actions"]:
                if data not in memory[update_type]:
                    memory[update_type].append(data)
                
                # Also log to corresponding markdown files
                if update_type == "lessons_learned":
                    self._append_to_md("lessons.md", f"- {data}")
                elif update_type == "what_failed":
                    self._append_to_md("failures.md", f"- {data}")
                elif update_type == "blocked_actions":
                    self._append_to_md("blockers.md", f"- {data}")
                    
            elif update_type == "decision":
                self._append_to_md("decisions.md", f"- {data}")
            elif update_type == "progress":
                self._append_to_md("progress.md", f"- {data}")
            else:
                return {"status": "failed", "error": f"Unknown update type: {update_type}"}
                
            self._save_memory(memory)
            return {"status": "success", "data": {"message": "Memory updated"}}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
