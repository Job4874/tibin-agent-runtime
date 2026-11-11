from typing import Dict, Any
import os

class BrowserTool:
    def __init__(self, browser_manager, safety):
        self.browser_manager = browser_manager
        self.safety = safety

    def open_url(self, session_id: str, url: str) -> Dict[str, Any]:
        if not self.safety.check_url_allowed(url):
            return {"status": "failed", "error": f"URL not allowed: {url}"}
            
        page = self.browser_manager.get_page(session_id)
        if not page:
            # Lazy init for MVP testing
            new_id = self.browser_manager.launch_temporary_session(headed=False)
            # Swap session_id mapping hack for MVP
            self.browser_manager.active_contexts[session_id] = self.browser_manager.active_contexts.pop(new_id)
            page = self.browser_manager.get_page(session_id)
            
        try:
            page.goto(url)
            return {"status": "success", "data": {"url": page.url, "title": page.title()}}
        except Exception as e:
            # Handle playwright not installed
            if "playwright" in str(e).lower() or "executable doesn't exist" in str(e).lower():
                return {"status": "failed", "error": "Browser tool not configured.\nInstall with:\npip install playwright\npython -m playwright install"}
            return {"status": "failed", "error": str(e)}

    def get_title(self, session_id: str) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        return {"status": "success", "data": {"title": page.title()}}

    def extract_text(self, session_id: str) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        text = page.locator("body").inner_text()
        return {"status": "success", "data": {"text": text}}

    def screenshot(self, session_id: str, name: str) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
            
        screenshots_dir = self.browser_manager.config.get("screenshots_dir")
        full_dir = os.path.join(self.browser_manager.base_dir, screenshots_dir)
        os.makedirs(full_dir, exist_ok=True)
        path = os.path.join(full_dir, f"{name}.png")
        page.screenshot(path=path)
        return {"status": "success", "data": {"screenshot_path": path}}

    def click(self, session_id: str, selector: str) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        page.click(selector)
        return {"status": "success", "data": {"clicked": selector}}

    def close_page(self, session_id: str) -> Dict[str, Any]:
        self.browser_manager.close_session(session_id)
        return {"status": "success", "data": {"message": "Session closed"}}

    def fill(self, session_id: str, selector: str, text: str) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        page.fill(selector, text)
        return {"status": "success", "data": {"filled": selector}}

    def press(self, session_id: str, key: str) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        page.keyboard.press(key)
        return {"status": "success", "data": {"pressed": key}}

    def scroll(self, session_id: str, direction: str, amount: int) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        
        if direction == "down":
            page.mouse.wheel(0, amount)
        elif direction == "up":
            page.mouse.wheel(0, -amount)
        else:
            return {"status": "failed", "error": "Direction must be 'up' or 'down'"}
            
        return {"status": "success", "data": {"scrolled": direction, "amount": amount}}

    def wait_for_selector(self, session_id: str, selector: str, timeout: int = 30000) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        try:
            page.wait_for_selector(selector, timeout=timeout)
            return {"status": "success", "data": {"found": selector}}
        except Exception as e:
            return {"status": "failed", "error": f"Timeout waiting for selector: {selector}"}

    def evaluate(self, session_id: str, js_code: str) -> Dict[str, Any]:
        page = self.browser_manager.get_page(session_id)
        if not page:
            return {"status": "failed", "error": f"Session {session_id} not active"}
        try:
            result = page.evaluate(js_code)
            return {"status": "success", "data": {"result": result}}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
