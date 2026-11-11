import os
import json
from .provider_errors import ProviderConfigError

# Config keys that would hold an inline secret value. Keys that merely *reference*
# an environment variable (e.g. "api_key_env") are explicitly allowed.
_SECRET_KEY_NAMES = {"api_key", "apikey", "key", "secret", "token", "access_token", "password"}

class ProviderConfig:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.config_path = os.path.join(base_dir, "config", "model_providers.json")
        self.config = self._load_config()
        
    def _load_config(self):
        if not os.path.exists(self.config_path):
            return {"active_provider": "manual", "providers": {}}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # Reject inline secrets; allow *_env references to environment variables.
            for prov_name, prov_conf in config.get("providers", {}).items():
                for k in prov_conf.keys():
                    name = str(k).lower()
                    if name.endswith("_env"):
                        continue
                    if name in _SECRET_KEY_NAMES:
                        raise ProviderConfigError(
                            f"Provider '{prov_name}' stores a secret under '{k}' in model_providers.json. "
                            "Use an environment variable reference (e.g. api_key_env) instead."
                        )
            return config
        except Exception as e:
            if isinstance(e, ProviderConfigError):
                raise
            return {"active_provider": "manual", "providers": {}}

    def get_active_provider_name(self):
        return self.config.get("active_provider", "manual")
        
    def get_provider_config(self, name):
        return self.config.get("providers", {}).get(name, {})
        
    def get_api_key(self, env_var_name):
        key = os.environ.get(env_var_name)
        if not key:
            raise ProviderConfigError(f"API key not found in environment variable: {env_var_name}")
        return key
