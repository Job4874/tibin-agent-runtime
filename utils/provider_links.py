"""Shared helpers for opening provider URLs in the user's default browser."""

import json
import os
import subprocess
import webbrowser
from typing import Any, Dict, List, Optional


def get_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_brain_config() -> Dict[str, Any]:
    path = os.path.join(get_base_dir(), "config", "brain.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"providers": {}}


def open_url_in_system_browser(url: str, preferred_browsers: Optional[List[str]] = None) -> str:
    """Open URL in Chrome/Edge on Windows, or default browser elsewhere."""
    for browser_name in preferred_browsers or ["chrome", "msedge", "edge"]:
        try:
            if browser_name in ["chrome", "msedge", "edge"]:
                exe = "msedge" if browser_name in ["msedge", "edge"] else "chrome"
                subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return exe
        except Exception:
            continue
    webbrowser.open(url)
    return "default"
