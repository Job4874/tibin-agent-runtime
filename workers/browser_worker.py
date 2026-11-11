from typing import Dict, Any
import os

class BrowserWorker:
    def __init__(self, browser_tool, observer):
        self.browser_tool = browser_tool
        self.observer = observer

    def _detect_blocked_state(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """Detect whether the page shows a blocked state. Returns dict with blocked, reason, screenshot_recommended."""
        text = (page_info.get("text") or "").lower()
        title = (page_info.get("title") or "").lower()
        url = (page_info.get("url") or "").lower()

        blocked_states = [
            (("captcha" in text or "recaptcha" in text or "i'm not a robot" in text), "captcha"),
            (("access denied" in text or "access denied" in title), "access_denied"),
            (("403 forbidden" in text or "forbidden" in title), "forbidden"),
            (("login required" in text or "sign in" in title or "log in" in title), "login_required"),
            (("paywall" in text or "subscription required" in text or "subscribe to continue" in text), "paywall"),
            (("rate limit" in text or "too many requests" in text or "429" in text), "rate_limited"),
            (("cloudflare" in text and "challenge" in text), "cloudflare_challenge"),
            (("cf-turnstile" in text), "cloudflare_challenge"),
        ]

        for condition, reason in blocked_states:
            if condition:
                return {"blocked": True, "reason": reason, "screenshot_recommended": True}
        return {"blocked": False, "reason": "", "screenshot_recommended": False}

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type")
        params = action.get("params", {})
        session_id = params.get("session_id")

        result = {"status": "failed", "error": "Unknown action"}

        try:
            if action_type == "launch_temporary_session":
                session_id = self.browser_tool.browser_manager.launch_temporary_session(headed=params.get("headed", False))
                result = {"status": "success", "data": {"session_id": session_id}}
                obs = self.observer.build_browser_observation(session_id, result)
                self.observer.write_browser_observation(obs)
                return result

            # For actions that require a session_id
            session_id = params.get("session_id")

            if action_type == "open_url":
                result = self.browser_tool.open_url(session_id, params.get("url"))
            elif action_type == "get_title":
                result = self.browser_tool.get_title(session_id)
            elif action_type == "extract_text":
                result = self.browser_tool.extract_text(session_id)
            elif action_type == "screenshot":
                result = self.browser_tool.screenshot(session_id, params.get("name", "screenshot"))
            elif action_type == "click":
                result = self.browser_tool.click(session_id, params.get("selector"))
            elif action_type == "fill":
                result = self.browser_tool.fill(session_id, params.get("selector"), params.get("text", ""))
            elif action_type == "press":
                result = self.browser_tool.press(session_id, params.get("key"))
            elif action_type == "scroll":
                result = self.browser_tool.scroll(session_id, params.get("direction", "down"), params.get("amount", 500))
            elif action_type == "wait_for_selector":
                result = self.browser_tool.wait_for_selector(session_id, params.get("selector"), params.get("timeout", 30000))
            elif action_type == "evaluate":
                result = self.browser_tool.evaluate(session_id, params.get("js_code"))
            elif action_type == "close_page":
                result = self.browser_tool.close_page(session_id)
            else:
                result = {"status": "failed", "error": f"Unsupported browser action: {action_type}"}

            # Safety: detect blocked states after actions that change page content
            if action_type in ["open_url", "evaluate", "click", "fill", "press"]:
                try:
                    page_info = self.browser_tool.get_page_info(session_id)
                    blocked_check = self._detect_blocked_state(page_info)
                    if blocked_check["blocked"]:
                        # Screenshot and stop
                        ss_result = self.browser_tool.screenshot(session_id, f"blocked_{blocked_check['reason']}")
                        blocked_obs = self.observer.build_browser_observation(session_id, ss_result)
                        self.observer.write_browser_observation(blocked_obs)
                        result = {
                            "status": "blocked",
                            "error": f"Browser blocked: {blocked_check['reason']}. Do not bypass. Recommend alternate path or user input.",
                            "blocked_reason": blocked_check["reason"],
                            "screenshot_recommended": True,
                        }
                except Exception:
                    pass

            obs = self.observer.build_browser_observation(session_id, result)
            self.observer.write_browser_observation(obs)

            return result
        except Exception as e:
            if "Browser tool not configured" in str(e):
                return {"status": "failed", "error": str(e)}
            return {"status": "failed", "error": str(e)}
