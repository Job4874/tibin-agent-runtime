import os
import pytest
from model_providers.provider_config import ProviderConfig, ProviderConfigError
from model_providers.provider_errors import ProviderError
from model_providers.manual_provider import ManualProvider
from model_providers.file_provider import FileProvider

def test_provider_error_redaction(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret_key_12345")
    
    class FakeProviderError(ProviderError):
        pass
        
    err = FakeProviderError("Connection failed with token secret_key_12345")
    assert "secret_key_12345" not in err.message
    assert "***REDACTED***" in err.message

def test_provider_config_rejects_keys(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "model_providers.json"
    
    # Write a bad config
    config_file.write_text('{"providers": {"test": {"api_key": "123"}}}', encoding="utf-8")
    
    with pytest.raises(ProviderConfigError):
        ProviderConfig(str(tmp_path))


def test_provider_config_allows_env_references(tmp_path):
    """api_key_env references an environment variable and must be accepted."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "model_providers.json"

    config_file.write_text(
        '{"active_provider": "test", "providers": {"test": {"enabled": true, "api_key_env": "MY_KEY_ENV"}}}',
        encoding="utf-8",
    )

    cfg = ProviderConfig(str(tmp_path))
    assert cfg.get_active_provider_name() == "test"
    assert cfg.get_provider_config("test")["api_key_env"] == "MY_KEY_ENV"


def test_default_repo_config_loads():
    """The committed config/model_providers.json must load without errors."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = ProviderConfig(root)
    assert cfg.get_active_provider_name()
    assert cfg.config.get("providers")

def test_manual_provider_generate(tmp_path):
    prov = ManualProvider({"enabled": True}, str(tmp_path))
    res = prov.generate("Test prompt")
    
    assert res["status"] == "manual_handoff"
    assert "inbox/provider_responses/" in res["error"]
    
    # Ensure prompt was written
    prompt_file = tmp_path / "outbox" / "model_prompts" / "latest_prompt.md"
    assert prompt_file.exists()
    assert prompt_file.read_text(encoding="utf-8") == "Test prompt"

def test_file_provider_empty(tmp_path):
    prov = FileProvider({"enabled": True}, str(tmp_path))
    res = prov.generate("")
    assert res["status"] == "failed"
    assert "No response file" in res["error"]
