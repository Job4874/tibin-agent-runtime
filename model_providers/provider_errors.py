import os

class ProviderError(Exception):
    """Base exception for provider errors. Ensures secrets are redacted."""
    def __init__(self, message):
        self.message = self._redact(message)
        super().__init__(self.message)

    def _redact(self, message):
        if not isinstance(message, str):
            return message
            
        secrets = []
        for key in ["OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"]:
            val = os.environ.get(key)
            if val and len(val) > 4:
                secrets.append(val)
                
        for secret in secrets:
            message = message.replace(secret, "***REDACTED***")
        return message

class ProviderConfigError(ProviderError):
    pass

class ProviderRateLimitError(ProviderError):
    pass

class ProviderContextLengthError(ProviderError):
    pass

class ProviderConnectionError(ProviderError):
    pass
