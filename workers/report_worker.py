import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

class ReportWorker:
    def __init__(self, base_dir: str):
        self.reports_dir = os.path.join(base_dir, "reports")
        self.observations_dir = os.path.join(base_dir, "observations")
        self.logs_dir = os.path.join(base_dir, "logs")

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        params = action.get("params", {})
        observation_data = params.get("observation_data", {})
        
        timestamp = datetime.now(timezone.utc).isoformat()
        observation_data["timestamp"] = timestamp
        
        # Write latest observation
        latest_obs_path = os.path.join(self.observations_dir, "latest_observation.json")
        try:
            with open(latest_obs_path, "w", encoding="utf-8") as f:
                json.dump(observation_data, f, indent=2)
        except Exception as e:
            return {"status": "failed", "error": f"Failed to write observation: {e}"}

        # Write latest run log
        latest_log_path = os.path.join(self.logs_dir, "latest_run.json")
        try:
            with open(latest_log_path, "w", encoding="utf-8") as f:
                json.dump(observation_data, f, indent=2)
            
            # Append to history
            history_path = os.path.join(self.logs_dir, "run_history.jsonl")
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(observation_data) + "\n")
        except Exception as e:
            pass
            
        # Write Markdown Report
        report_path = os.path.join(self.reports_dir, "latest_report.md")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"# Run Report - {timestamp}\n\n")
                f.write(f"**Objective:** {observation_data.get('objective_id', 'Unknown')}\n")
                f.write(f"**Plan ID:** {observation_data.get('plan_id', 'Unknown')}\n")
                f.write(f"**Status:** {observation_data.get('status', 'Unknown')}\n\n")
                
                f.write("## Actions\n")
                f.write(f"- Executed: {len(observation_data.get('actions_executed', []))}\n")
                f.write(f"- Blocked: {len(observation_data.get('actions_blocked', []))}\n\n")
                
                f.write("## Details\n")
                f.write(f"- Files Read: {len(observation_data.get('files_read', []))}\n")
                f.write(f"- Files Changed: {len(observation_data.get('files_changed', []))}\n")
                f.write(f"- Commands Run: {len(observation_data.get('commands_run', []))}\n")
                f.write(f"- Errors: {len(observation_data.get('errors', []))}\n\n")
                
                f.write("## Next Recommendation\n")
                f.write(f"{observation_data.get('next_recommendation', 'None')}\n")
                
            return {"status": "success", "data": {"report_path": report_path, "observation_path": latest_obs_path}}
        except Exception as e:
            return {"status": "failed", "error": f"Failed to write report: {e}"}
