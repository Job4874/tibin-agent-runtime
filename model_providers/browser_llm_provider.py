"""
Browser LLM Provider

Allows the Tibin runtime to use browser-accessible LLMs (e.g., BoodleBox) as the model brain.
The local runtime remains the execution body.

Modes:
- manual_handoff: User copy/pastes prompt into browser, copy/pastes response back
- browser_assisted_handoff: Runtime uses BrowserWorker to inject prompt, monitor response
- supervised_browser_loop: Autonomous loop with Defender validation and safe execution

Safety:
- Never bypass login or captcha
- Never read browser passwords
- Never read browser cookies or profile databases
- Raw model response never executes directly
- All responses parsed and validated as candidate plan JSON
- DefenderAgent approves every action before execution
"""

import os
import json
import glob
import subprocess
import webbrowser
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path
from .base_provider import BaseModelProvider
from .response_parser import ResponseParser
from model_loop.evidence_recorder import EvidenceRecorder


class BrowserLLMProvider(BaseModelProvider):
    """
    Provider for browser-accessible LLMs.

    Orchestrates:
    1. Prompt generation and display
    2. User/browser handoff to LLM
    3. Response ingestion and validation
    4. Candidate plan extraction
    """

    name = "browser_llm"

    def __init__(self, config: Dict[str, Any], base_dir: str):
        super().__init__(config)
        self.base_dir = base_dir
        self.browser_config_path = os.path.join(base_dir, "config", "browser_llm_providers.json")
        self.browser_config = self._load_browser_config()

        # Setup directories
        self.inbox_dir = os.path.join(base_dir, "inbox", "provider_responses")
        self.archive_dir = os.path.join(base_dir, "inbox", "provider_responses", "archive")
        self.candidate_plans_dir = os.path.join(base_dir, "inbox", "candidate_plans")
        self.validated_plans_dir = os.path.join(base_dir, "inbox", "validated_plans")
        self.rejected_plans_dir = os.path.join(base_dir, "inbox", "rejected_plans")
        self.state_dir = os.path.join(base_dir, "state")

        for dir_path in [self.inbox_dir, self.archive_dir, self.candidate_plans_dir, 
                         self.validated_plans_dir, self.rejected_plans_dir, self.state_dir]:
            os.makedirs(dir_path, exist_ok=True)

    def _load_browser_config(self) -> Dict[str, Any]:
        """Load browser LLM provider configuration."""
        try:
            if os.path.exists(self.browser_config_path):
                with open(self.browser_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            pass

        # Return default config if file not found
        return {
            "active_browser_provider": "boodlebox",
            "providers": {
                "boodlebox": {
                    "name": "BoodleBox",
                    "url": "https://box.boodle.ai/launch/chat",
                    "mode": "manual_handoff",
                    "auth_strategy": "existing_system_browser_profile",
                    "system_profile_auth_expected": True,
                    "preferred_system_browsers": ["chrome", "msedge"],
                    "requires_user_login": True,
                    "allow_browser_automation": False,
                    "notes": "Open in the user's existing Chrome/Edge profile. Do not read cookies, passwords, or profile databases."
                }
            },
            "safety": {
                "never_bypass_login": True,
                "never_bypass_captcha": True,
                "never_read_passwords": True,
                "never_read_cookies": True,
                "raw_response_never_executes": True
            }
        }

    def get_active_provider_config(self) -> Dict[str, Any]:
        """Get the active browser provider configuration."""
        active_name = self.browser_config.get("active_browser_provider", "boodlebox")
        providers = self.browser_config.get("providers", {})
        return providers.get(active_name, {})

    def get_provider_status(self) -> Dict[str, Any]:
        """Get current status of the browser LLM provider."""
        active_config = self.get_active_provider_config()
        active_name = self.browser_config.get("active_browser_provider", "boodlebox")

        # Check for pending response
        pending_responses = glob.glob(os.path.join(self.inbox_dir, "*.txt")) + \
                           glob.glob(os.path.join(self.inbox_dir, "*.md")) + \
                           glob.glob(os.path.join(self.inbox_dir, "*.json"))

        # Exclude archived files
        pending_responses = [f for f in pending_responses if not f.endswith(".processed")]

        # Check for pending candidate plans
        pending_plans = glob.glob(os.path.join(self.candidate_plans_dir, "*.json"))

        return {
            "provider": self.name,
            "active_provider": active_name,
            "active_config": active_config,
            "mode": active_config.get("mode", "manual_handoff"),
            "auth_strategy": active_config.get("auth_strategy", "manual_login"),
            "system_profile_auth_expected": active_config.get("system_profile_auth_expected", False),
            "preferred_system_browsers": active_config.get("preferred_system_browsers", []),
            "requires_user_login": active_config.get("requires_user_login", True),
            "allow_browser_automation": active_config.get("allow_browser_automation", False),
            "url": active_config.get("url", ""),
            "pending_responses": len(pending_responses),
            "pending_candidate_plans": len(pending_plans),
            "response_inbox_path": self.inbox_dir,
            "candidate_plans_path": self.candidate_plans_dir,
            "validated_plans_path": self.validated_plans_dir,
            "rejected_plans_path": self.rejected_plans_dir,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    def generate_prompt_file(self, prompt: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate and save a model prompt file for manual or assisted handoff.

        Returns info about where the prompt is saved and how to use it.
        """
        try:
            prompt_path = os.path.join(self.state_dir, "model_prompt.md")

            # Write prompt to file
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(prompt)

            active_config = self.get_active_provider_config()
            mode = active_config.get("mode", "manual_handoff")
            provider_url = active_config.get("url", "")

            return {
                "provider": self.name,
                "status": "success",
                "action": "prompt_generated",
                "prompt_file": prompt_path,
                "provider_url": provider_url,
                "mode": mode,
                "instructions": self._get_handoff_instructions(mode, provider_url),
                "next_step": "Copy prompt to browser LLM or use --open-browser-provider",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "provider": self.name,
                "status": "failed",
                "error": f"Failed to generate prompt file: {e}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

    def _get_handoff_instructions(self, mode: str, provider_url: str) -> str:
        """Get handoff instructions based on mode."""
        if mode == "manual_handoff":
            return (
                f"1. Open {provider_url}\n"
                f"2. Log in with your credentials\n"
                f"3. Copy the prompt from state/model_prompt.md\n"
                f"4. Paste into the BoodleBox chat\n"
                f"5. Wait for the model response\n"
                f"6. Copy the full JSON response\n"
                f"7. Save to a file in inbox/provider_responses/\n"
                f"8. Run: python runtime.py --ingest-browser-model-response"
            )
        elif mode == "browser_assisted_handoff":
            return (
                f"1. The runtime will open {provider_url}\n"
                f"2. Ensure you are logged in\n"
                f"3. Run: python runtime.py --browser-model-cycle-once\n"
                f"4. The runtime will handle prompt injection and response capture"
            )
        elif mode == "supervised_browser_loop":
            return (
                f"1. Ensure you are logged into {provider_url}\n"
                f"2. Run: python runtime.py --supervised-browser-loop\n"
                f"3. The runtime will execute autonomous cycles with full Defender checks\n"
                f"4. Watch for approval_required stops"
            )
        return "Unknown mode"

    def open_provider_page(self) -> Dict[str, Any]:
        """
        Open the browser-accessible LLM provider page.

        Safety:
        - Does not bypass login
        - Does not bypass captcha
        - Does not use cookies to auto-login
        - Requires user to handle login/captcha manually
        """
        try:
            active_config = self.get_active_provider_config()
            provider_url = active_config.get("url", "")
            preferred_browsers = active_config.get("preferred_system_browsers", [])

            if not provider_url:
                return {
                    "provider": self.name,
                    "status": "failed",
                    "error": "No provider URL configured",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

            opened_browser = self._open_existing_system_browser(provider_url, preferred_browsers)

            return {
                "provider": self.name,
                "status": "success",
                "action": "provider_page_opened",
                "url": provider_url,
                "opened_browser": opened_browser,
                "auth_strategy": active_config.get("auth_strategy", "manual_login"),
                "system_profile_auth_expected": active_config.get("system_profile_auth_expected", False),
                "instructions": "Browser opened in the existing system profile if available. Use the already signed-in tab, then copy/paste the model response when ready.",
                "next_step": "Paste response to inbox/provider_responses/ and run --ingest-browser-model-response",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "provider": self.name,
                "status": "failed",
                "error": f"Failed to open provider page: {e}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

    def _open_existing_system_browser(self, url: str, preferred_browsers: Optional[list] = None) -> str:
        """Open URL in a normal user browser profile without reading browser data."""
        for browser_name in preferred_browsers or []:
            try:
                if browser_name in ["chrome", "msedge", "edge"]:
                    exe = "msedge" if browser_name in ["msedge", "edge"] else "chrome"
                    subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return exe
            except Exception:
                continue

        webbrowser.open(url)
        return "default"

    def ingest_response_file(self) -> Dict[str, Any]:
        """
        Ingest the newest response file from inbox/provider_responses/.

        Process:
        1. Find newest response file
        2. Archive raw response
        3. Extract candidate plan JSON
        4. Validate plan
        5. Route to validated_plans/ or rejected_plans/
        """
        try:
            # Find newest response file
            response_files = glob.glob(os.path.join(self.inbox_dir, "*.txt")) + \
                           glob.glob(os.path.join(self.inbox_dir, "*.md")) + \
                           glob.glob(os.path.join(self.inbox_dir, "*.json"))

            # Exclude archived files
            response_files = [f for f in response_files if not f.endswith(".processed")]

            if not response_files:
                return {
                    "provider": self.name,
                    "status": "failed",
                    "error": "No response file found in inbox/provider_responses/",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

            response_files.sort(key=os.path.getmtime, reverse=True)
            response_file = response_files[0]

            # Read response
            with open(response_file, "r", encoding="utf-8") as f:
                raw_response = f.read()

            # Archive raw response
            archive_name = f"{Path(response_file).stem}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
            archive_path = os.path.join(self.archive_dir, archive_name)
            with open(archive_path, "w", encoding="utf-8") as f:
                f.write(raw_response)

            # Mark original as processed
            os.rename(response_file, response_file + ".processed")

            # Parse candidate plan from response
            parser = ResponseParser()
            parse_status, candidate_plan, parse_error = parser.parse(raw_response)

            if not candidate_plan:
                # Save as rejected
                rejected_name = f"rejected_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
                rejected_path = os.path.join(self.rejected_plans_dir, rejected_name)
                with open(rejected_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "status": "rejected",
                        "reason": "No valid JSON plan found in response",
                        "raw_response_archive": archive_path,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }, f, indent=2)

                self._record_exchange(
                    raw_response,
                    parse_status,
                    parse_error,
                    None,
                    archive_path,
                    rejected_plan_path=rejected_path,
                )

                return {
                    "provider": self.name,
                    "status": "failed",
                    "action": "plan_rejected",
                    "reason": "No valid JSON plan found in response",
                    "rejected_plan_path": rejected_path,
                    "raw_response_archive": archive_path,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

            # Save candidate plan
            candidate_name = f"candidate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            candidate_path = os.path.join(self.candidate_plans_dir, candidate_name)
            with open(candidate_path, "w", encoding="utf-8") as f:
                json.dump(candidate_plan, f, indent=2)

            self._record_exchange(
                raw_response,
                parse_status,
                parse_error,
                candidate_plan,
                archive_path,
                candidate_plan_path=candidate_path,
            )

            return {
                "provider": self.name,
                "status": "success",
                "action": "response_ingested",
                "raw_response_archive": archive_path,
                "candidate_plan_path": candidate_path,
                "next_step": "Validate and approve plan before execution",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            return {
                "provider": self.name,
                "status": "failed",
                "error": f"Failed to ingest response: {e}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

    def _record_exchange(
        self,
        raw_response: str,
        parse_status: str,
        parse_error: str,
        candidate_plan: Optional[Dict[str, Any]],
        archive_path: str,
        candidate_plan_path: Optional[str] = None,
        rejected_plan_path: Optional[str] = None,
    ) -> None:
        """Best-effort evidence capture; ingestion should not fail if logging fails."""
        try:
            EvidenceRecorder(self.base_dir).record_model_exchange(
                response_text=raw_response,
                parse_status=parse_status,
                parse_error=parse_error,
                candidate_plan=candidate_plan,
                raw_response_archive=archive_path,
                candidate_plan_path=candidate_plan_path,
                rejected_plan_path=rejected_plan_path,
            )
        except Exception:
            pass

    def validate_candidate_plan(self, plan_path: str) -> Dict[str, Any]:
        """Validate a candidate plan against schema."""
        try:
            if not os.path.exists(plan_path):
                return {
                    "status": "failed",
                    "error": f"Plan file not found: {plan_path}"
                }

            with open(plan_path, "r", encoding="utf-8") as f:
                plan = json.load(f)

            is_valid, validation_error = EvidenceRecorder(self.base_dir)._is_training_eligible_plan(plan)
            if not is_valid:
                return {
                    "status": "failed",
                    "error": validation_error
                }

            return {
                "status": "valid",
                "plan_id": plan.get("plan_id"),
                "action_count": len(plan.get("actions", []))
            }

        except json.JSONDecodeError as e:
            return {
                "status": "failed",
                "error": f"Invalid JSON: {e}"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Validation error: {e}"
            }

    def generate(self, prompt: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate (in this context, prepare for handoff to browser LLM).

        This method is called by the standard provider interface.
        For browser LLM, it prepares the prompt and returns handoff instructions.
        """
        return self.generate_prompt_file(prompt, metadata)
