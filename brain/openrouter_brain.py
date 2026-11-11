"""
OpenRouter brain for autonomous mode.

Autonomous tasks use OpenRouter API only — never BoodleBox browser scraping.
BoodleBox remains the premium manual-handoff workspace for complex work.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tools.redaction import RedactionTool
from utils.env_loader import load_dotenv

LOGIN_PAGE_MARKERS = [
    "sign in",
    "sign up",
    "log in",
    "login",
    "create account",
    "cookie",
    "accept cookies",
    "password",
    "forgot password",
    "verify your email",
]

DEFAULT_MODEL = "openrouter/free"
FALLBACK_MODELS = [
    "openrouter/free",
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "qwen/qwen-2.5-7b-instruct:free",
]


class OpenRouterBrain:
    name = "openrouter"

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        load_dotenv(base_dir)
        self.redaction = RedactionTool()
        self._config = self._load_config()
        openrouter_cfg = self._config.get("providers", {}).get("openrouter", {})
        self.api_key_env = openrouter_cfg.get("api_key_env", "OPENROUTER_API_KEY")
        self.base_url = openrouter_cfg.get("base_url", "https://openrouter.ai/api/v1").rstrip("/")
        self.default_model = openrouter_cfg.get("default_model", "openrouter/free")
        self.timeout = 90

    def _load_config(self) -> Dict[str, Any]:
        path = os.path.join(self.base_dir, "config", "brain.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def is_configured(self) -> bool:
        return bool(os.environ.get(self.api_key_env, "").strip())

    def get_status(self) -> Dict[str, Any]:
        configured = self.is_configured()
        return {
            "brain": self.name,
            "label": "OpenRouter (free-tier models)",
            "configured": configured,
            "model": self.default_model if configured else None,
            "status": "ready" if configured else "not_configured",
            "message": (
                "Autonomous mode ready."
                if configured
                else "Set OPENROUTER_API_KEY in .env to enable autonomous mode."
            ),
        }

    @staticmethod
    def is_login_page(text: str) -> bool:
        if not text or len(text) < 20:
            return False
        lower = text.lower()
        # HTML-heavy short responses are almost always login walls, not agent answers.
        if "<html" in lower or "<!doctype" in lower:
            hits = sum(1 for m in LOGIN_PAGE_MARKERS if m in lower)
            return hits >= 2
        hits = sum(1 for m in LOGIN_PAGE_MARKERS if m in lower)
        return hits >= 3

    def complete(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "failed_no_brain",
                "provider": self.name,
                "error": (
                    "OPENROUTER_API_KEY is not set. "
                    "Add it to .env or export it, then retry. "
                    "Autonomous mode does not fall back to BoodleBox."
                ),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        safe_prompt = self.redaction.redact(prompt)
        safe_system = self.redaction.redact(system) if system else ""

        models_to_try = [model or self.default_model] + [
            m for m in FALLBACK_MODELS if m != (model or self.default_model)
        ]

        last_error = ""
        for attempt_model in models_to_try:
            result = self._call_api(safe_prompt, safe_system, attempt_model)
            if result["status"] == "success":
                raw = result.get("raw_text", "")
                if self.is_login_page(raw):
                    return {
                        "status": "blocked_login_page",
                        "provider": self.name,
                        "model": attempt_model,
                        "error": "Response looks like a login/signup page, not a model answer.",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                result["model"] = attempt_model
                return result
            last_error = result.get("error", "unknown")
            if result.get("status") == "rate_limited":
                continue

        return {
            "status": "failed",
            "provider": self.name,
            "error": last_error or "All models failed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _call_api(self, prompt: str, system: str, model: str) -> Dict[str, Any]:
        api_key = os.environ[self.api_key_env]
        url = f"{self.base_url}/chat/completions"
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/Job4874/tibin-fullstack-agent-runtime",
            "X-Title": "Tibin Agent Runtime",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "status": "success",
                "provider": self.name,
                "raw_text": content,
                "usage": body.get("usage", {}),
                "error": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            if exc.code == 429:
                return {
                    "status": "rate_limited",
                    "provider": self.name,
                    "error": f"Rate limited (429): {err_body[:200]}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            return {
                "status": "failed",
                "provider": self.name,
                "error": f"HTTP {exc.code}: {err_body[:300]}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "provider": self.name,
                "error": str(exc),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }


def get_brain_status(base_dir: str) -> Dict[str, Any]:
    return OpenRouterBrain(base_dir).get_status()
