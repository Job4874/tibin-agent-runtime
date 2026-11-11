import json
import os
from typing import Dict, Any

class BrowserObserver:
    def __init__(self, base_dir: str):
        self.obs_dir = os.path.join(base_dir, "observations", "browser")
        os.makedirs(self.obs_dir, exist_ok=True)

    def build_browser_observation(self, session_id: str, action_result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "session_id": session_id,
            "page_state": {}, # Would be populated by capturing DOM
            "action_result": action_result
        }

    def write_browser_observation(self, observation: Dict[str, Any]):
        session_id = observation.get("session_id", "unknown")
        import time
        filename = f"{session_id}_{int(time.time())}.json"
        path = os.path.join(self.obs_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(observation, f, indent=2)
