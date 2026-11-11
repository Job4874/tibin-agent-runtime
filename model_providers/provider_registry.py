from typing import Dict, Any, Type
from .base_provider import BaseModelProvider
from .manual_provider import ManualProvider
from .file_provider import FileProvider
from .openai_compatible_provider import OpenAICompatibleProvider
from .gemini_provider import GeminiProvider
from .anthropic_provider import AnthropicProvider
from .browser_llm_provider import BrowserLLMProvider
from .provider_config import ProviderConfig

class ProviderRegistry:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.config_manager = ProviderConfig(base_dir)
        self.config = self.config_manager.config

        self._providers: Dict[str, Type[BaseModelProvider]] = {
            "manual": ManualProvider,
            "file": FileProvider,
            "openai_compatible": OpenAICompatibleProvider,
            "gemini": GeminiProvider,
            "anthropic": AnthropicProvider,
            "browser_llm": BrowserLLMProvider
        }

    def get_active_provider_name(self) -> str:
        return self.config_manager.get_active_provider_name()

    def get_provider(self, name: str) -> BaseModelProvider:
        provider_class = self._providers.get(name)
        if not provider_class:
            return ManualProvider({"enabled": True}, self.base_dir)

        provider_config = self.config_manager.get_provider_config(name)

        if name in ["manual", "file", "browser_llm"]:
            return provider_class(provider_config, self.base_dir)

        return provider_class(provider_config)

    def get_active_provider(self) -> BaseModelProvider:
        return self.get_provider(self.get_active_provider_name())
