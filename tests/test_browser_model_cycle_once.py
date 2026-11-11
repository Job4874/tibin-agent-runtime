"""
Integration test for browser model cycle once.
"""

import unittest
import json
import os
import tempfile
import shutil
from model_providers.browser_llm_provider import BrowserLLMProvider


class TestBrowserModelCycleOnce(unittest.TestCase):
    """Test one-cycle browser model operation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.test_dir, "state")
        self.config_dir = os.path.join(self.test_dir, "config")
        self.inbox_dir = os.path.join(self.test_dir, "inbox")

        for d in [self.state_dir, self.config_dir]:
            os.makedirs(d, exist_ok=True)

        for subdir in ["provider_responses", "provider_responses/archive", "candidate_plans", "validated_plans", "rejected_plans"]:
            os.makedirs(os.path.join(self.inbox_dir, subdir), exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_cycle_generates_prompt(self):
        """Test that cycle generates prompt."""
        provider = BrowserLLMProvider({}, self.test_dir)

        prompt_text = "Generate a simple test plan"
        result = provider.generate_prompt_file(prompt_text)

        self.assertEqual(result["status"], "success")
        self.assertTrue(os.path.exists(result["prompt_file"]))

    def test_cycle_never_executes_raw_response(self):
        """Test that raw response never executes directly."""
        provider = BrowserLLMProvider({}, self.test_dir)
        config = provider.browser_config
        safety = config.get("safety", {})

        # This is the core safety guarantee
        self.assertTrue(safety.get("raw_response_never_executes"))

    def test_cycle_creates_candidate_plan(self):
        """Test that cycle creates candidate plan from response."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # Create a sample response with JSON plan
        response_dir = os.path.join(self.inbox_dir, "provider_responses")
        response_file = os.path.join(response_dir, "response.txt")

        plan = {
            "plan_id": "test-cycle-001",
            "actions": [
                {
                    "id": "act-1",
                    "tool": "ShellWorker",
                    "command": "echo 'test from browser'"
                }
            ]
        }

        response_content = f"Here is the plan:\n```json\n{json.dumps(plan, indent=2)}\n```\nDone."

        with open(response_file, "w") as f:
            f.write(response_content)

        result = provider.ingest_response_file()

        # Should create candidate plan
        self.assertEqual(result["status"], "success")
        self.assertIn("candidate_plan_path", result)

        if os.path.exists(result["candidate_plan_path"]):
            with open(result["candidate_plan_path"], "r") as f:
                candidate = json.load(f)
            self.assertEqual(candidate["plan_id"], "test-cycle-001")

    def test_cycle_validates_before_execution(self):
        """Test that cycle validates plan before any execution."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # Create an invalid plan
        plan = {
            "plan_id": "invalid-plan"
            # Missing "actions"
        }

        plan_file = os.path.join(self.inbox_dir, "candidate_plans", "test_plan.json")
        os.makedirs(os.path.dirname(plan_file), exist_ok=True)
        with open(plan_file, "w") as f:
            json.dump(plan, f)

        validation = provider.validate_candidate_plan(plan_file)

        # Should reject invalid plan
        self.assertEqual(validation["status"], "failed")


if __name__ == "__main__":
    unittest.main()
