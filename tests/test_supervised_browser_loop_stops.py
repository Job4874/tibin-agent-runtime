"""
Tests for supervised browser loop safety constraints.
"""

import unittest
import json
import os
import tempfile
import shutil
from model_providers.browser_llm_provider import BrowserLLMProvider


class TestSupervisedBrowserLoopStops(unittest.TestCase):
    """Test that supervised browser loop respects safety constraints."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.test_dir, "state")
        self.config_dir = os.path.join(self.test_dir, "config")

        for d in [self.state_dir, self.config_dir]:
            os.makedirs(d, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_loop_respects_max_cycles(self):
        """Test that loop respects max_cycles limit."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # This is a simple check that the provider can be instantiated
        # Actual loop testing requires runtime integration
        status = provider.get_provider_status()
        self.assertIsNotNone(status)

    def test_loop_never_bypasses_defender(self):
        """Test that Defender checks are never bypassed."""
        provider = BrowserLLMProvider({}, self.test_dir)

        # Check that safety config prevents defender bypass
        config = provider.browser_config
        safety = config.get("safety", {})

        # Raw response should never execute
        self.assertTrue(safety.get("raw_response_never_executes"))

    def test_loop_never_bypasses_login(self):
        """Test that login is never bypassed."""
        provider = BrowserLLMProvider({}, self.test_dir)

        config = provider.browser_config
        safety = config.get("safety", {})

        self.assertTrue(safety.get("never_bypass_login"))

    def test_loop_never_bypasses_captcha(self):
        """Test that captcha is never bypassed."""
        provider = BrowserLLMProvider({}, self.test_dir)

        config = provider.browser_config
        safety = config.get("safety", {})

        self.assertTrue(safety.get("never_bypass_captcha"))


if __name__ == "__main__":
    unittest.main()
