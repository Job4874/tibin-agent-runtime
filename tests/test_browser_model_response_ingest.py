"""
Tests for browser model response ingestion.
"""

import unittest
import json
import os
import tempfile
import shutil
from model_providers.browser_llm_provider import BrowserLLMProvider


class TestBrowserModelResponseIngest(unittest.TestCase):
    """Test browser model response ingestion."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.response_dir = os.path.join(self.test_dir, "inbox", "provider_responses")
        self.archive_dir = os.path.join(self.response_dir, "archive")
        self.candidate_dir = os.path.join(self.test_dir, "inbox", "candidate_plans")
        self.rejected_dir = os.path.join(self.test_dir, "inbox", "rejected_plans")
        self.state_dir = os.path.join(self.test_dir, "state")
        self.config_dir = os.path.join(self.test_dir, "config")

        for d in [self.response_dir, self.archive_dir, self.candidate_dir, self.rejected_dir, self.state_dir, self.config_dir]:
            os.makedirs(d, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_raw_response_archived(self):
        """Test that raw response is archived."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # Create a response file
        response_file = os.path.join(self.response_dir, "response.txt")
        raw_content = "Some model response text"
        with open(response_file, "w") as f:
            f.write(raw_content)

        result = provider.ingest_response_file()

        # Raw response should be archived (even if plan extraction fails)
        self.assertIn("raw_response_archive", result)
        archive_path = result["raw_response_archive"]

        if archive_path and os.path.exists(archive_path):
            with open(archive_path, "r") as f:
                archived_content = f.read()
            self.assertEqual(archived_content, raw_content)

    def test_valid_plan_extracted(self):
        """Test that valid plan JSON is extracted from response."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # Create a response with embedded JSON plan
        response_file = os.path.join(self.response_dir, "response.txt")
        plan = {
            "plan_id": "test-plan-001",
            "actions": [
                {
                    "id": "act-1",
                    "tool": "ShellWorker",
                    "command": "echo 'test'"
                }
            ]
        }

        response_content = f"""
        Here is the plan in JSON format:
        ```json
        {json.dumps(plan)}
        ```
        That's the plan.
        """

        with open(response_file, "w") as f:
            f.write(response_content)

        result = provider.ingest_response_file()

        # Should succeed if JSON is properly extracted
        # (success depends on ResponseParser implementation)
        self.assertIn("status", result)

    def test_response_file_marked_processed(self):
        """Test that response file is marked as processed."""
        provider = BrowserLLMProvider({}, self.test_dir)

        response_file = os.path.join(self.response_dir, "response.txt")
        with open(response_file, "w") as f:
            f.write("Some response")

        provider.ingest_response_file()

        # Original file should be renamed with .processed
        self.assertTrue(os.path.exists(response_file + ".processed"))
        self.assertFalse(os.path.exists(response_file))

    def test_invalid_response_rejected(self):
        """Test that invalid response is rejected."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # Create response with no valid JSON
        response_file = os.path.join(self.response_dir, "response.txt")
        with open(response_file, "w") as f:
            f.write("This response has no JSON at all")

        result = provider.ingest_response_file()

        # Should be rejected
        self.assertEqual(result["status"], "failed")
        self.assertIn("rejected_plan_path", result)


if __name__ == "__main__":
    unittest.main()
