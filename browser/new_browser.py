import os
import uuid
import threading
from playwright.sync_api import sync_playwright
from .browser_config import BrowserConfig
from .browser_profile_manager import BrowserProfileManager
from .browser_session_store import BrowserSessionStore

class NewBrowserManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.config = BrowserConfig(base_dir)
        self.profiles = BrowserProfileManager(base_dir, self.config.get("profiles_dir"))
        self.sessions = BrowserSessionStore(base_dir)
        self.playwright_context = None
        self.playwright_engine = None
        self._lock = threading.Lock()
        self.active_contexts = {} # session_id -> (browser_context, page)

    def _start_playwright(self):
        if not self.playwright_context:
            self.playwright_context = sync_playwright().start()
            browser_type = self.config.get("default_browser", "chromium")
            if browser_type == "chromium":
                self.playwright_engine = self.playwright_context.chromium
            elif browser_type == "firefox":
                self.playwright_engine = self.playwright_context.firefox
            else:
                self.playwright_engine = self.playwright_context.webkit

    def create_profile(self, profile_name: str):
        self.profiles.create_profile(profile_name)

    def launch_profile(self, profile_name: str, headed: bool = True) -> str:
        with self._lock:
            self._start_playwright()
            profile_path = self.profiles.get_profile_path(profile_name)
            
            context = self.playwright_engine.launch_persistent_context(
                user_data_dir=profile_path,
                headless=not headed,
                downloads_path=os.path.join(self.base_dir, self.config.get("downloads_dir"))
            )
            page = context.new_page() if not context.pages else context.pages[0]
            
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            self.active_contexts[session_id] = (context, page)
            
            self.sessions.register_session(session_id, {
                "profile": profile_name,
                "headed": headed,
                "temporary": False
            })
            return session_id

    def launch_temporary_session(self, headed: bool = True) -> str:
        with self._lock:
            self._start_playwright()
            browser = self.playwright_engine.launch(headless=not headed)
            context = browser.new_context()
            page = context.new_page()
            
            session_id = f"session_tmp_{uuid.uuid4().hex[:8]}"
            self.active_contexts[session_id] = (context, page, browser)
            
            self.sessions.register_session(session_id, {
                "profile": None,
                "headed": headed,
                "temporary": True
            })
            return session_id

    def get_page(self, session_id: str):
        if session_id in self.active_contexts:
            return self.active_contexts[session_id][1]
        return None

    def close_session(self, session_id: str):
        with self._lock:
            if session_id in self.active_contexts:
                ctx_tuple = self.active_contexts.pop(session_id)
                # tuple can be (context, page) or (context, page, browser)
                ctx_tuple[0].close()
                if len(ctx_tuple) == 3:
                    ctx_tuple[2].close()
                self.sessions.mark_closed(session_id)

    def list_sessions(self) -> list:
        return self.sessions.list_active_sessions()

    def get_session_info(self, session_id: str) -> dict:
        return self.sessions.sessions["active"].get(session_id, {})

    def cleanup_temporary_sessions(self):
        with self._lock:
            temp_sessions = [sid for sid, meta in self.sessions.sessions["active"].items() if meta.get("temporary")]
            for sid in temp_sessions:
                self.close_session(sid)
