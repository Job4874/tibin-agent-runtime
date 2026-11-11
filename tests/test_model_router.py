from model_loop.model_router import ModelRouter


def test_model_router_recommends_app_building_model(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "model_catalog.json").write_text(
        """
{
  "task_profiles": {
    "building_applications": {
      "preferred_models": ["claude-4.6-sonnet", "codestral"]
    }
  },
  "models": [
    {
      "id": "claude-4.6-sonnet",
      "provider": "boodlebox",
      "display_name": "Claude 4.6 Sonnet",
      "access_mode": "browser_manual",
      "strengths": ["coding", "multi_step_planning", "agentic_systems"]
    },
    {
      "id": "codestral",
      "provider": "boodlebox",
      "display_name": "Codestral",
      "access_mode": "browser_manual",
      "strengths": ["coding", "debugging"]
    }
  ]
}
""",
        encoding="utf-8",
    )

    selection = ModelRouter(str(tmp_path)).select_for_task(
        "Building applications",
        provider_health={},
        browser_status={"reachable": True, "login_required": True},
        evidence_summary={"training_rows": 0, "eval_rows": 0},
    )

    assert selection["task_profile"] == "building_applications"
    assert selection["recommended_model"]["id"] == "claude-4.6-sonnet"
    assert selection["training_selection_ready"] is False


def test_model_router_labels_existing_system_profile_auth(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "model_catalog.json").write_text(
        """
{
  "task_profiles": {
    "building_applications": {
      "preferred_models": ["claude-4.6-sonnet"]
    }
  },
  "models": [
    {
      "id": "claude-4.6-sonnet",
      "provider": "boodlebox",
      "display_name": "Claude 4.6 Sonnet",
      "access_mode": "browser_manual",
      "strengths": ["coding", "multi_step_planning"]
    }
  ]
}
""",
        encoding="utf-8",
    )

    selection = ModelRouter(str(tmp_path)).select_for_task(
        "Building applications",
        provider_health={},
        browser_status={
            "reachable": True,
            "login_required": True,
            "system_profile_auth_expected": True,
        },
        evidence_summary={"training_rows": 0, "eval_rows": 0},
    )

    assert selection["recommended_model"]["access_status"] == "existing_system_browser_profile_expected"


def test_model_router_prefers_ready_direct_api_when_available(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "model_catalog.json").write_text(
        """
{
  "task_profiles": {
    "building_applications": {
      "preferred_models": ["openai-compatible-configured"]
    }
  },
  "models": [
    {
      "id": "openai-compatible-configured",
      "provider": "openai_compatible",
      "display_name": "Configured OpenAI-compatible API model",
      "access_mode": "direct_api",
      "strengths": ["coding", "reasoning"]
    }
  ]
}
""",
        encoding="utf-8",
    )

    selection = ModelRouter(str(tmp_path)).select_for_task(
        "Building applications",
        provider_health={"openai_compatible": {"status": "ok"}},
        browser_status={"reachable": False, "login_required": True},
        evidence_summary={"training_rows": 30, "eval_rows": 30},
    )

    assert selection["direct_api_ready_model"]["id"] == "openai-compatible-configured"
    assert selection["training_selection_ready"] is True
