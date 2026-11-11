import os
import glob
import json
import shutil
from datetime import datetime, timezone
from typing import Dict, Any
from .base_provider import BaseModelProvider
from .response_parser import ResponseParser

class FileProvider(BaseModelProvider):
    name = "file"

    def __init__(self, config: Dict[str, Any], base_dir: str):
        super().__init__(config)
        self.base_dir = base_dir
        self.inbox_dir = os.path.join(base_dir, "inbox", "provider_responses")
        self.val_dir = os.path.join(base_dir, "inbox", "validated_plans")
        self.rej_dir = os.path.join(base_dir, "inbox", "rejected_plans")
        os.makedirs(self.inbox_dir, exist_ok=True)
        os.makedirs(self.val_dir, exist_ok=True)
        os.makedirs(self.rej_dir, exist_ok=True)

    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        files = glob.glob(os.path.join(self.inbox_dir, "*.txt")) + \
                glob.glob(os.path.join(self.inbox_dir, "*.md")) + \
                glob.glob(os.path.join(self.inbox_dir, "*.json"))
                
        if not files:
            return {
                "provider": self.name,
                "status": "failed",
                "raw_text": "",
                "usage": {},
                "error": "No response file found in inbox/provider_responses/",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        
        files.sort(key=os.path.getmtime, reverse=True)
        newest = files[0]
        
        try:
            with open(newest, "r", encoding="utf-8") as f:
                content = f.read()
                
            proc_path = newest + ".processed"
            shutil.move(newest, proc_path)
            
            return {
                "provider": self.name,
                "status": "success",
                "raw_text": content,
                "usage": {},
                "error": "",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            return {
                "provider": self.name,
                "status": "failed",
                "raw_text": "",
                "usage": {},
                "error": f"Error reading file: {e}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
