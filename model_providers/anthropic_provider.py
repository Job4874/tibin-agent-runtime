import os
import urllib.request
import json
from datetime import datetime, timezone
from typing import Dict, Any
from .base_provider import BaseModelProvider
from .provider_errors import ProviderRateLimitError, ProviderContextLengthError, ProviderError

class AnthropicProvider(BaseModelProvider):
    name = "anthropic"

    def is_configured(self) -> bool:
        if not super().is_configured():
            return False
        return os.environ.get("ANTHROPIC_API_KEY") is not None

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
                "error": "Provider not configured or ANTHROPIC_API_KEY missing.",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        model = self.config.get("model", "claude-3-opus-20240229")
        timeout = self.config.get("timeout_seconds", 90)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            content = ""
            for block in result.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
                    
            usage = result.get("usage", {})
            
            return {
                "provider": self.name,
                "status": "success",
                "raw_text": content,
                "usage": usage,
                "error": "",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return self._handle_request_error(e, api_key)
