import json
import os
from typing import Dict, Any

class BrowserConfig:
    def __init__(self, base_dir: str):
        self.config_path = os.path.join(base_dir, "config", "browser.json")
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "default_browser": "chromium",
            "headless_default": False,
            "profiles_dir": "browser_profiles",
            "downloads_dir": "workspace/downloads",
            "screenshots_dir": "screenshots/browser",
            "allow_persistent_profiles": True,
            "allow_temporary_profiles": True,
            "require_approval_for_logged_in_sites": True,
            "default_timeout_ms": 30000
        }
        
    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
