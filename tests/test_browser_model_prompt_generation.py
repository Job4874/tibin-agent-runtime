"""
Tests for browser model prompt generation.
"""

import unittest
import json
import os
import tempfile
import shutil
from model_providers.browser_llm_provider import BrowserLLMProvider


class TestBrowserModelPromptGeneration(unittest.TestCase):
    """Test browser model prompt generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.test_dir, "state")
        self.config_dir = os.path.join(self.test_dir, "config")

        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_prompt_file_generated(self):
        """Test that prompt file is generated."""
        provider = BrowserLLMProvider({}, self.test_dir)

        prompt_text = "You are a coding agent. Generate a plan to fix the bug."
        result = provider.generate_prompt_file(prompt_text)

        self.assertEqual(result["status"], "success")
        self.assertIn("prompt_file", result)

        prompt_path = result["prompt_file"]
        self.assertTrue(os.path.exists(prompt_path))

        with open(prompt_path, "r") as f:
            content = f.read()
        self.assertEqual(content, prompt_text)

    def test_prompt_has_handoff_instructions(self):
        """Test that prompt generation includes handoff instructions."""
        provider = BrowserLLMProvider({}, self.test_dir)

        prompt_text = "Test prompt"
        result = provider.generate_prompt_file(prompt_text)

        self.assertIn("instructions", result)
        instructions = result["instructions"]

        # Manual mode should include copy/paste instructions
        if result.get("mode") == "manual_handoff":
            self.assertIn("copy", instructions.lower())
            self.assertIn("paste", instructions.lower())

    def test_prompt_file_location(self):
        """Test that prompt is saved to correct location."""
        provider = BrowserLLMProvider({}, self.test_dir)

        prompt_text = "Generate a test plan"
        result = provider.generate_prompt_file(prompt_text)

        expected_path = os.path.join(self.state_dir, "model_prompt.md")
        self.assertEqual(result["prompt_file"], expected_path)


if __name__ == "__main__":
    unittest.main()
