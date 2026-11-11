"""
Tests for the Browser LLM Provider module.
"""

import unittest
import json
import os
import tempfile
import shutil
from model_providers.browser_llm_provider import BrowserLLMProvider


class TestBrowserLLMProvider(unittest.TestCase):
    """Test Browser LLM Provider functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, "config")
        self.state_dir = os.path.join(self.test_dir, "state")
        self.inbox_dir = os.path.join(self.test_dir, "inbox", "provider_responses")

        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.inbox_dir, exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "inbox", "provider_responses", "archive"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "inbox", "candidate_plans"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "inbox", "validated_plans"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "inbox", "rejected_plans"), exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_browser_config_loads(self):
        """Test that browser LLM provider config loads."""
        provider = BrowserLLMProvider({}, self.test_dir)
        config = provider.get_active_provider_config()

        self.assertIn("name", config)
        self.assertEqual(config["name"], "BoodleBox")
        self.assertIn("url", config)
        self.assertIn("mode", config)

    def test_provider_status(self):
        """Test provider status reporting."""
        provider = BrowserLLMProvider({}, self.test_dir)
        status = provider.get_provider_status()

        self.assertEqual(status["provider"], "browser_llm")
        self.assertEqual(status["active_provider"], "boodlebox")
        self.assertIn("mode", status)
        self.assertIn("url", status)
        self.assertIn("pending_responses", status)

    def test_safety_rules_present(self):
        """Test that safety rules are loaded."""
        provider = BrowserLLMProvider({}, self.test_dir)
        config = provider.browser_config

        safety = config.get("safety", {})
        self.assertTrue(safety.get("never_bypass_login"))
        self.assertTrue(safety.get("never_bypass_captcha"))
        self.assertTrue(safety.get("never_read_passwords"))
        self.assertTrue(safety.get("never_read_cookies", True))
        self.assertTrue(safety.get("raw_response_never_executes"))

    def test_existing_system_profile_auth_status(self):
        """Test that existing Chrome/Edge profile handoff is exposed in status."""
        config_path = os.path.join(self.config_dir, "browser_llm_providers.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(
                {
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
                        }
                    },
                    "safety": {
                        "never_bypass_login": True,
                        "never_bypass_captcha": True,
                        "never_read_passwords": True,
                        "never_read_cookies": True,
                        "raw_response_never_executes": True,
                    },
                },
                f,
            )

        status = BrowserLLMProvider({}, self.test_dir).get_provider_status()

        self.assertEqual(status["auth_strategy"], "existing_system_browser_profile")
        self.assertTrue(status["system_profile_auth_expected"])
        self.assertEqual(status["preferred_system_browsers"], ["chrome", "msedge"])

    def test_generate_prompt_file(self):
        """Test prompt file generation."""
        provider = BrowserLLMProvider({}, self.test_dir)
        test_prompt = "Generate a test plan"

        result = provider.generate_prompt_file(test_prompt)

        self.assertEqual(result["status"], "success")
        self.assertIn("prompt_file", result)

        # Verify file was created
        prompt_file = result["prompt_file"]
        self.assertTrue(os.path.exists(prompt_file))

        # Verify content
        with open(prompt_file, "r") as f:
            content = f.read()
        self.assertEqual(content, test_prompt)

    def test_ingest_response_file_no_file(self):
        """Test ingest when no response file exists."""
        provider = BrowserLLMProvider({}, self.test_dir)
        result = provider.ingest_response_file()

        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)

    def test_ingest_response_file_invalid_json(self):
        """Test ingest of response with no JSON plan."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # Create a response file with no JSON
        response_file = os.path.join(self.inbox_dir, "response.txt")
        with open(response_file, "w") as f:
            f.write("This is just text, no JSON")

        result = provider.ingest_response_file()

        # Should be rejected
        self.assertEqual(result["status"], "failed")
        self.assertIn("rejected_plan_path", result)

    def test_validate_candidate_plan_valid(self):
        """Test validation of a valid candidate plan."""
        provider = BrowserLLMProvider({}, self.test_dir)

        plan = {
            "plan_id": "test-plan-001",
            "objective_id": "obj-001",
            "title": "Test plan",
            "actions": [
                {
                    "action_id": "act-1",
                    "worker": "ShellWorker",
                    "type": "run",
                    "params": {"command": "echo 'test'"}
                }
            ],
            "complexity": {
                "problem_type": "coding",
                "estimated_depth": "simple"
            }
        }

        plan_file = os.path.join(self.test_dir, "test_plan.json")
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        validation = provider.validate_candidate_plan(plan_file)

        self.assertEqual(validation["status"], "valid")
        self.assertEqual(validation["plan_id"], "test-plan-001")
        self.assertEqual(validation["action_count"], 1)

    def test_validate_candidate_plan_missing_fields(self):
        """Test validation of plan with missing required fields."""
        provider = BrowserLLMProvider({}, self.test_dir)

        plan = {
            "plan_id": "test-plan-001"
            # Missing "actions"
        }

        plan_file = os.path.join(self.test_dir, "test_plan.json")
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        validation = provider.validate_candidate_plan(plan_file)

        self.assertEqual(validation["status"], "failed")

    def test_validate_candidate_plan_invalid_json(self):
        """Test validation of invalid JSON file."""
        provider = BrowserLLMProvider({}, self.test_dir)

        plan_file = os.path.join(self.test_dir, "invalid.json")
        with open(plan_file, "w") as f:
            f.write("{ invalid json }")

        validation = provider.validate_candidate_plan(plan_file)

        self.assertEqual(validation["status"], "failed")
        self.assertIn("Invalid JSON", validation["error"])


if __name__ == "__main__":
    unittest.main()
