from flask import Blueprint, render_template, jsonify, request
import os
import json

browser_bp = Blueprint('browser', __name__)

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _load_providers():
    path = os.path.join(get_base_dir(), "config", "brain.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("providers", {})
    return {}

@browser_bp.route('/browser')
def browser_ui():
    from brain.openrouter_brain import get_brain_status
    providers = _load_providers()
    brain = get_brain_status(get_base_dir())
    return render_template('browser.html', providers=providers, brain=brain)

@browser_bp.route('/api/browser/open', methods=['POST'])
def open_in_browser():
    from utils.provider_links import open_url_in_system_browser
    data = request.get_json(silent=True) or {}
    provider_id = data.get('provider', 'boodlebox')
    providers = _load_providers()
    prov = providers.get(provider_id, {})
    url = data.get('url') or prov.get('login_url') or prov.get('url', '')
    if not url:
        return jsonify({"status": "error", "error": f"No URL for provider: {provider_id}"}), 400
    opened = open_url_in_system_browser(url, ["chrome", "msedge", "edge"])
    return jsonify({"status": "success", "url": url, "opened_browser": opened})

@browser_bp.route('/api/browser/playwright', methods=['POST'])
def open_playwright():
    """Launch headed Chromium for manual provider login (Playwright)."""
    base = get_base_dir()
    data = request.get_json(silent=True) or {}
    provider_id = data.get('provider', 'boodlebox')
    providers = _load_providers()
    prov = providers.get(provider_id, {})
    url = prov.get('login_url') or prov.get('url', 'https://box.boodle.ai/launch/')
    try:
        from browser.new_browser import NewBrowserManager
        mgr = NewBrowserManager(base)
        session_id = mgr.launch_temporary_session(headed=True)
        page = mgr.get_page(session_id)
        if page:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        return jsonify({"status": "success", "url": url, "mode": "playwright_headed", "session_id": session_id})
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500

@browser_bp.route('/api/browser/feed')
def browser_feed():
    from flask import send_file
    base_dir = get_base_dir()
    screenshot_path = os.path.join(base_dir, "screenshots", "current_page.png")
    if os.path.exists(screenshot_path):
        return send_file(screenshot_path, mimetype='image/png', max_age=0)
    return "No screenshot available", 404


@browser_bp.route('/api/browser/feed/status')
def browser_feed_status():
    """Lightweight availability probe so the UI can poll without 404 noise."""
    base_dir = get_base_dir()
    screenshot_path = os.path.join(base_dir, "screenshots", "current_page.png")
    available = os.path.exists(screenshot_path)
    payload = {"available": available}
    if available:
        payload["updated_at"] = os.path.getmtime(screenshot_path)
    return jsonify(payload)
