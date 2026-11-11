import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

class DefenderAgent:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.permissions_dir = os.path.join(base_dir, "permissions")
        self.allowlist = self._load_json("allowlist.json")
        self.denylist = self._load_json("denylist.json")
        self.path_permissions = self._load_json("path_permissions.json")
        self.tool_permissions = self._load_json("tool_permissions.json")
        self.web_permissions = self._load_json("web_permissions.json")

        # Load active approvals via ApprovalStore
        from tools.approval_store import ApprovalStore
        self.approval_store = ApprovalStore(base_dir)

        # Compile dangerous command patterns for cross-platform detection
        self.dangerous_patterns = [
            (r"\brm\s+-rf\b", "rm -rf recursive deletion"),
            (r"Remove-Item\s+-Recurse", "PowerShell recursive deletion"),
            (r"\bdel\s+/[fqsw]*\b", "Windows mass deletion"),
            (r"\brmdir\s+/s\b", "Windows directory deletion"),
            (r"shutil\.rmtree", "Python shutil deletion"),
            (r"fs\.rmSync", "Node.js fs deletion"),
            (r"\bformat\b", "disk format"),
            (r"\bdiskpart\b", "disk partition manipulation"),
            (r"reg\s+delete", "registry deletion"),
            (r"curl\s+.*\|\s*(sh|bash|cmd|powershell|pwsh)", "curl pipe shell"),
            (r"Invoke-WebRequest\s+.*\|\s*iex", "PowerShell web request pipe execution"),
            (r"Invoke-Expression", "PowerShell expression execution"),
            (r"\.git\b.*(?:rm|del|remove|delete)", ".git deletion"),
            (r"(?:home|users|appdata|local|documents|downloads).*\b(?:rm|del|remove|delete|rmdir|format)", "user home deletion"),
            (r"cookie|password|credential|secret", "credential exfiltration pattern"),
            (r"(?:chrome|firefox|edge|browser).*\b(cookie|password|login|credential)", "browser credential access"),
        ]

        self._precompile()

    def _precompile(self):
        self.compiled_patterns = []
        for pattern, desc in self.dangerous_patterns:
            try:
                self.compiled_patterns.append((re.compile(pattern, re.IGNORECASE), desc))
            except re.error:
                pass

    def _load_json(self, filename: str) -> Dict[str, Any]:
        filepath = os.path.join(self.permissions_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _make_decision(
        self,
        action_id: str,
        decision: str,
        reason: str,
        matched_rule: str,
        risk_level: str,
    ) -> Dict[str, Any]:
        return {
            "action_id": action_id,
            "decision": decision,
            "reason": reason,
            "matched_rule": matched_rule,
            "risk_level": risk_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def evaluate_action(self, action: Dict[str, Any], plan_id: str) -> Dict[str, Any]:
        """Return a structured decision dict with keys: action_id, decision, reason, matched_rule, risk_level, timestamp."""
        worker = action.get("worker", "")
        action_type = action.get("type", "")
        params = action.get("params", {}) or {}
        action_id = action.get("action_id", "")

        # 1. Check tool permissions
        allowed_tools = self.tool_permissions.get("allowed_tools", [])
        if allowed_tools and worker not in allowed_tools:
            return self._make_decision(
                action_id, "block",
                f"Worker {worker} is not in allowed_tools list.",
                "tool_permissions", "high"
            )

        # 2. Dangerous command detection for ShellWorker (broad, cross-platform)
        if worker == "ShellWorker":
            cmd = params.get("command", "")
            if action_type in ["check_status", "kill_process"]:
                return self._make_decision(action_id, "allow", "Action allowed.", "allowlist", "low")

            # Check denylist exact substrings first
            for denied in self.denylist.get("commands", []):
                if denied in cmd:
                    return self._make_decision(
                        action_id, "block",
                        f"Command contains blocked pattern: {denied}",
                        "denylist", "critical"
                    )

            # Check compiled dangerous patterns
            for compiled, desc in self.compiled_patterns:
                if compiled.search(cmd):
                    # If this is a destructive pattern, always block regardless of approval
                    if desc in (
                        "rm -rf recursive deletion",
                        ".git deletion",
                        "user home deletion",
                        "disk format",
                        "disk partition manipulation",
                        "PowerShell recursive deletion",
                        "Python shutil deletion",
                    ):
                        return self._make_decision(
                            action_id, "block",
                            f"Destructive command detected: {desc}",
                            "dangerous_pattern", "critical"
                        )
                    # Others may be approved
                    if not self.approval_store.find_valid_approval(plan_id, action_id):
                        return self._make_decision(
                            action_id, "approval_required",
                            f"Dangerous command requires approval: {desc}",
                            "dangerous_pattern", "high"
                        )

            # Require explicit approval for anything not in allowlist
            is_allowed_cmd = any(cmd.startswith(allowed) for allowed in self.allowlist.get("commands", []))
            if not is_allowed_cmd:
                if not self.approval_store.find_valid_approval(plan_id, action_id):
                    return self._make_decision(
                        action_id, "approval_required",
                        f"Command requires explicit signed approval: {cmd}",
                        "allowlist", "medium"
                    )

        # 3. FileWorker safety
        elif worker == "FileWorker":
            path = params.get("path", "")
            if path:
                path = os.path.abspath(os.path.normpath(path))

                for blocked in self.path_permissions.get("blocked_paths", []):
                    blocked_abs = os.path.abspath(os.path.normpath(blocked))
                    try:
                        if os.path.commonpath([path, blocked_abs]) == blocked_abs:
                            return self._make_decision(
                                action_id, "block",
                                f"Path is blocked: {blocked}",
                                "path_permissions", "high"
                            )
                    except ValueError:
                        pass

                if action_type in ["write", "append", "delete", "replace_content", "create_dir"]:
                    allowed_writes = self.path_permissions.get("allowed_write_paths", [])
                    is_allowed_write = False
                    for allowed in allowed_writes:
                        allowed_abs = os.path.abspath(os.path.normpath(allowed))
                        try:
                            if os.path.commonpath([path, allowed_abs]) == allowed_abs:
                                is_allowed_write = True
                                break
                        except ValueError:
                            pass
                    if not is_allowed_write:
                        if not self.approval_store.find_valid_approval(plan_id, action_id):
                            return self._make_decision(
                                action_id, "approval_required",
                                f"Path not in allowed_write_paths: {path} (Requires explicit signed approval)",
                                "path_permissions", "medium"
                            )

                if action_type == "delete":
                    if not self.approval_store.find_valid_approval(plan_id, action_id):
                        return self._make_decision(
                            action_id, "approval_required",
                            "File deletion requires explicit signed approval.",
                            "path_permissions", "high"
                        )

        # 4. GitWorker safety
        elif worker == "GitWorker":
            if action_type in ["push", "commit", "pull", "checkout"]:
                if not self.approval_store.find_valid_approval(plan_id, action_id):
                    return self._make_decision(
                        action_id, "approval_required",
                        f"Git {action_type} requires explicit signed approval.",
                        "git_permissions", "medium"
                    )

        # 5. BrowserWorker safety
        elif worker == "BrowserWorker":
            url = params.get("url", "")
            if url:
                for blocked in self.web_permissions.get("blocked_domains", []):
                    if blocked in url:
                        return self._make_decision(
                            action_id, "block",
                            f"Domain is blocked: {blocked}",
                            "web_permissions", "high"
                        )

            if action_type in ["upload", "submit_form", "post", "evaluate"]:
                if not self.approval_store.find_valid_approval(plan_id, action_id):
                    return self._make_decision(
                        action_id, "approval_required",
                        f"Browser action {action_type} requires explicit signed approval.",
                        "web_permissions", "medium"
                    )

        return self._make_decision(action_id, "allow", "Action allowed.", "allow", "low")

    def check_action(self, action: Dict[str, Any], plan_id: str) -> tuple[bool, str]:
        """Backward-compatible (bool, reason) wrapper."""
        decision = self.evaluate_action(action, plan_id)
        if decision["decision"] == "allow":
            return True, decision["reason"]
        return False, decision["reason"]

    def mark_approval_used(self, plan_id: str, action_id: str) -> bool:
        approval = self.approval_store.find_valid_approval(plan_id, action_id)
        if approval:
            return self.approval_store.mark_used(approval["approval_id"])
        return False
