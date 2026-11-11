import os
import json
from typing import Dict, Any

class BrowserSessionStore:
    def __init__(self, base_dir: str):
        self.state_file = os.path.join(base_dir, "state", "browser_sessions.json")
        self.sessions = self.load_from_disk()

    def load_from_disk(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"active": {}, "closed": {}}

    def save_to_disk(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, indent=2)

    def register_session(self, session_id: str, metadata: Dict[str, Any]):
        self.sessions["active"][session_id] = metadata
        self.save_to_disk()

    def update_session(self, session_id: str, metadata: Dict[str, Any]):
        if session_id in self.sessions["active"]:
            self.sessions["active"][session_id].update(metadata)
            self.save_to_disk()

    def mark_closed(self, session_id: str):
        if session_id in self.sessions["active"]:
            metadata = self.sessions["active"].pop(session_id)
            self.sessions["closed"][session_id] = metadata
            self.save_to_disk()

    def list_active_sessions(self) -> list:
        return list(self.sessions["active"].keys())
        
    def list_all_sessions(self) -> Dict[str, Any]:
        return self.sessions
