import os
import urllib.request
import json
from datetime import datetime, timezone
from typing import Dict, Any
from .base_provider import BaseModelProvider
from .provider_errors import ProviderRateLimitError, ProviderContextLengthError, ProviderError

class GeminiProvider(BaseModelProvider):
    name = "gemini"

    def is_configured(self) -> bool:
        if not super().is_configured():
            return False
        return os.environ.get("GEMINI_API_KEY") is not None

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"status": "not_configured"}
        return {"status": "ok"}

    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "provider": self.name,
                "status": "not_configured",
                "raw_text": "",
                "usage": {},
                "error": "Provider not configured or GEMINI_API_KEY missing.",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        api_key = os.environ.get("GEMINI_API_KEY")
        model = self.config.get("model", "gemini-1.5-pro")
        timeout = self.config.get("timeout_seconds", 90)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            content = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            return {
                "provider": self.name,
                "status": "success",
                "raw_text": content,
                "usage": {},
                "error": "",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return self._handle_request_error(e, api_key)
