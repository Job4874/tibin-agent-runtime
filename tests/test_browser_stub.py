import pytest
from workers.browser_worker import BrowserWorker

class FakeBrowserTool:
    def open_url(self, session_id, url):
        return {"status": "success", "data": {"url": url, "title": "Test Page", "text": "Hello world"}}
    def get_title(self, session_id):
        return {"status": "success", "data": {"title": "Test Page"}}
    def extract_text(self, session_id):
        return {"status": "success", "data": {"text": "Hello world"}}
    def screenshot(self, session_id, name):
        return {"status": "success", "data": {"screenshot": f"{name}.png"}}
    def evaluate(self, session_id, js_code):
        return {"status": "success", "data": {"result": 42}}
    def close_page(self, session_id):
        return {"status": "success"}
    def get_page_info(self, session_id):
        return {"url": "https://example.com", "title": "Example", "text": "Example domain"}

class FakeObserver:
    def build_browser_observation(self, session_id, result):
        return result
    def write_browser_observation(self, obs):
        pass

def test_browser_blocked_states():
    tool = FakeBrowserTool()
    observer = FakeObserver()
    bw = BrowserWorker(tool, observer)

    class CaptchaTool(FakeBrowserTool):
        def get_page_info(self, session_id):
            return {"url": "https://example.com", "title": "Captcha", "text": "Please complete the captcha below"}

    bw2 = BrowserWorker(CaptchaTool(), observer)
    result = bw2.execute({"type": "open_url", "params": {"session_id": "s1", "url": "https://example.com"}})
    assert result["status"] == "blocked"
    assert result.get("blocked_reason") == "captcha"

def test_browser_success():
    tool = FakeBrowserTool()
    observer = FakeObserver()
    bw = BrowserWorker(tool, observer)
    result = bw.execute({"type": "open_url", "params": {"session_id": "s1", "url": "https://example.com"}})
    assert result["status"] == "success"
