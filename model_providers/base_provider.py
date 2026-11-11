from typing import Dict, Any
from datetime import datetime, timezone
import urllib.error
from .provider_errors import ProviderRateLimitError, ProviderContextLengthError, ProviderError

class BaseModelProvider:
    name: str = "base"

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def is_configured(self) -> bool:
        return self.config.get("enabled", False)

    def health_check(self) -> Dict[str, Any]:
        return {"status": "ok" if self.is_configured() else "not_configured"}

    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        raise NotImplementedError("Provider must implement generate()")

    def _handle_request_error(self, e: Exception, api_key: str = None) -> Dict[str, Any]:
        err_msg = ""
        if isinstance(e, urllib.error.HTTPError):
            try:
                err_msg = e.read().decode('utf-8')
            except Exception:
                err_msg = str(e)
            if not err_msg.strip():
                err_msg = str(e)
        else:
            err_msg = str(e)

        if api_key and api_key in err_msg:
            err_msg = err_msg.replace(api_key, "***REDACTED***")

        status = "failed"
        if "429" in err_msg:
            status = "rate_limited"
            err_obj = ProviderRateLimitError(err_msg)
        elif "length" in err_msg.lower():
            status = "context_length_exceeded"
            err_obj = ProviderContextLengthError(err_msg)
        else:
            err_obj = ProviderError(err_msg)

        return {
            "provider": self.name,
            "status": status,
            "raw_text": "",
            "usage": {},
            "error": str(err_obj),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
