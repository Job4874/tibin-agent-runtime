import json
from pathlib import Path
from typing import Any, Dict, List


class ModelRouter:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.catalog_path = self.base_dir / "config" / "model_catalog.json"
        self.catalog = self._load_catalog()

    def select_for_task(
        self,
        task: str,
        provider_health: Dict[str, Dict[str, Any]],
        browser_status: Dict[str, Any],
        evidence_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        task_key = self._task_key(task)
        profile = self.catalog.get("task_profiles", {}).get(task_key, {})
        preferred = profile.get("preferred_models", [])
        model_by_id = {m.get("id"): m for m in self.catalog.get("models", [])}

        ranked: List[Dict[str, Any]] = []
        for model_id in preferred:
            model = model_by_id.get(model_id)
            if model:
                ranked.append(self._score_model(model, provider_health, browser_status))

        direct_ready = [
            self._score_model(model, provider_health, browser_status)
            for model in self.catalog.get("models", [])
            if model.get("access_mode") == "direct_api"
            and provider_health.get(model.get("provider"), {}).get("status") == "ok"
        ]
        direct_ready.sort(key=lambda item: item["score"], reverse=True)
        ranked.sort(key=lambda item: item["score"], reverse=True)

        enough_evidence = evidence_summary.get("training_rows", 0) >= 20 and evidence_summary.get("eval_rows", 0) >= 20

        return {
            "task": task,
            "task_profile": task_key,
            "recommended_model": ranked[0] if ranked else None,
            "direct_api_ready_model": direct_ready[0] if direct_ready else None,
            "ranked_models": ranked,
            "training_selection_ready": enough_evidence,
            "training_selection_reason": (
                "enough local examples to begin empirical model selection"
                if enough_evidence
                else "not enough validated model I/O rows yet; collect more prompt/response/run outcomes first"
            ),
        }

    def _score_model(
        self,
        model: Dict[str, Any],
        provider_health: Dict[str, Dict[str, Any]],
        browser_status: Dict[str, Any],
    ) -> Dict[str, Any]:
        score = 0
        strengths = set(model.get("strengths", []))
        provider = model.get("provider", "")
        access_mode = model.get("access_mode", "")

        score += 3 * len(strengths.intersection({"coding", "multi_step_planning", "agentic_systems"}))
        score += 2 * len(strengths.intersection({"debugging", "reliability", "reasoning"}))

        access_status = "not_ready"
        if access_mode == "direct_api":
            health = provider_health.get(provider, {})
            access_status = "ready" if health.get("status") == "ok" else health.get("status", "not_configured")
            if access_status == "ready":
                score += 10
        elif provider == "boodlebox":
            if browser_status.get("reachable"):
                access_status = "manual_handoff_ready"
                score += 5
            if browser_status.get("system_profile_auth_expected"):
                access_status = "existing_system_browser_profile_expected"
                score += 2
            if browser_status.get("login_required") and not browser_status.get("system_profile_auth_expected"):
                access_status = "login_required_manual_handoff"

        return {
            "id": model.get("id"),
            "display_name": model.get("display_name"),
            "provider": provider,
            "access_mode": access_mode,
            "access_status": access_status,
            "strengths": model.get("strengths", []),
            "score": score,
        }

    def _task_key(self, task: str) -> str:
        text = (task or "").lower()
        if any(token in text for token in ["build", "application", "app", "full-stack", "frontend", "backend", "coding"]):
            return "building_applications"
        return "building_applications"

    def _load_catalog(self) -> Dict[str, Any]:
        try:
            return json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except Exception:
            return {"task_profiles": {}, "models": []}
