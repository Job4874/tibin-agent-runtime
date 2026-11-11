import os
import requests
from typing import Dict, Any

class VerifierWorker:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        params = action.get("params", {})
        verification_type = params.get("verification_type")
        
        status = "failed"
        message = ""
        
        try:
            if verification_type == "file_exists":
                path = params.get("path")
                if os.path.exists(path):
                    status = "success"
                    message = f"File exists: {path}"
                else:
                    message = f"File not found: {path}"
                    
            elif verification_type == "text_exists":
                path = params.get("path")
                text = params.get("text")
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        if text in f.read():
                            status = "success"
                            message = f"Text found in {path}"
                        else:
                            message = f"Text not found in {path}"
                else:
                    message = f"File not found: {path}"
                    
            elif verification_type == "url_reachable":
                url = params.get("url")
                resp = requests.get(url, timeout=10)
                if resp.status_code < 400:
                    status = "success"
                    message = f"URL reachable: {url}"
                else:
                    message = f"URL returned status {resp.status_code}"
                    
            elif verification_type == "manual_review":
                status = "needs_manual_review"
                message = "Manual review requested."
                
            else:
                message = f"Unknown verification type: {verification_type}"
                
            return {
                "status": status,
                "data": {"message": message}
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
