import os
import urllib.request
import json
from datetime import datetime, timezone
from typing import Dict, Any
from .base_provider import BaseModelProvider
from .provider_errors import ProviderRateLimitError, ProviderContextLengthError, ProviderError

class OpenAICompatibleProvider(BaseModelProvider):
    name = "openai_compatible"

    def is_configured(self) -> bool:
        if not super().is_configured():
            return False
        api_key_env = self.config.get("api_key_env", "OPENAI_API_KEY")
        return os.environ.get(api_key_env) is not None

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
                "error": "Provider not fully configured or API key missing.",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        api_key_env = self.config.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env)
        base_url = self.config.get("base_url", "https://api.openai.com/v1")
        model = self.config.get("model", "gpt-4-turbo")
        timeout = self.config.get("timeout_seconds", 90)

        url = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
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
