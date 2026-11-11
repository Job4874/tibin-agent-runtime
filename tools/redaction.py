import re

class RedactionTool:
    def __init__(self):
        # Basic patterns for common secrets
        self.patterns = {
            "aws_access_key": r"AKIA[0-9A-Z]{16}",
            "aws_secret_key": r"(?i)aws_secret_access_key\s*=\s*[a-zA-Z0-9/+=]{40}",
            "private_key": r"-----BEGIN [A-Z]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z]+ PRIVATE KEY-----",
            "bearer_token": r"Bearer [a-zA-Z0-9\-\._~+/]+",
            "generic_api_key": r"(?i)(api[_-]?key|secret|token|password)[\s:=]+[\"']?([a-zA-Z0-9\-\._~+/]{16,})[\"']?"
        }

    def redact(self, text: str) -> str:
        if not text:
            return text
        
        redacted_text = text
        for name, pattern in self.patterns.items():
            def replace_match(match):
                if len(match.groups()) > 0:
                    full_match = match.group(0)
                    secret = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                    if secret:
                        return full_match.replace(secret, "[REDACTED]")
                return f"[REDACTED {name.upper()}]"
            
            try:
                # If pattern has groups, only redact the captured part, else the whole match
                if "(" in pattern and name == "generic_api_key":
                    redacted_text = re.sub(pattern, replace_match, redacted_text)
                else:
                    redacted_text = re.sub(pattern, f"[REDACTED {name.upper()}]", redacted_text)
            except Exception:
                pass
                
        return redacted_text
