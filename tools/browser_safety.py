class BrowserSafety:
    def __init__(self, web_permissions: dict):
        self.allowed_domains = web_permissions.get("allowed_domains", [])
        self.blocked_domains = web_permissions.get("blocked_domains", [])

    def check_url_allowed(self, url: str) -> bool:
        for blocked in self.blocked_domains:
            if blocked in url:
                return False
        return True

    def block_sensitive_actions(self, action: str) -> bool:
        blocked_actions = ["delete_account", "transfer_funds", "purchase"]
        return action in blocked_actions
