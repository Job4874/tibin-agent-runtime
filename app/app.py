import os
import secrets
import sys
from datetime import datetime, timezone
from uuid import uuid4

from flask import Flask, jsonify, request, render_template

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_APP_DIR)
for p in (_APP_DIR, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.env_loader import load_dotenv
load_dotenv(_ROOT)

app = Flask(__name__)

# Runtime directories the dashboard and workers read/write. Created up front so
# fresh checkouts don't 404/fail on missing paths.
for _d in ("observations", "logs", "screenshots", "runs", "state",
           os.path.join("inbox", "candidate_plans"),
           os.path.join("inbox", "validated_plans"),
           os.path.join("inbox", "rejected_plans"),
           os.path.join("inbox", "provider_responses"),
           os.path.join("outbox", "model_prompts"),
           os.path.join("outbox", "model_requests")):
    os.makedirs(os.path.join(_ROOT, _d), exist_ok=True)

# ---------------------------------------------------------------------------
# API access control
# ---------------------------------------------------------------------------
API_TOKEN = os.environ.get("TIBIN_API_TOKEN") or secrets.token_hex(32)
app.config["API_TOKEN"] = API_TOKEN

_DEFAULT_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "127.0.0.1:5000", "localhost:5000"}


def _allowed_hosts():
    extra = os.environ.get("TIBIN_ALLOWED_HOSTS", "")
    hosts = set(_DEFAULT_ALLOWED_HOSTS)
    hosts.update(h.strip() for h in extra.split(",") if h.strip())
    return hosts


def _request_token():
    token = request.headers.get("X-Tibin-Token", "")
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return ""


@app.before_request
def _enforce_access_controls():
    if request.host not in _allowed_hosts():
        return jsonify({"error": "forbidden_host"}), 403

    if request.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
        supplied = _request_token()
        if not supplied or not secrets.compare_digest(supplied, app.config["API_TOKEN"]):
            return jsonify({"error": "unauthorized", "detail": "Missing or invalid API token."}), 401


@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy",
                            "geolocation=(), microphone=(), camera=()")
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'",
    )
    return resp


# ---------------------------------------------------------------------------
# Template context — injected into every render_template call
# ---------------------------------------------------------------------------
def _get_system_context():
    """Return lightweight system state for template injection.

    Runs on every page request; kept fast (file I/O only, no network).
    """
    try:
        from utils.process_manager import get_process_status
        ps = get_process_status(_ROOT)
        dashboard_health_ok = ps.get("dashboard_health", False)
        dashboard_status    = (ps.get("dashboard", {}) or {}).get("status", "stopped")
        watcher_status      = (ps.get("watcher", {}) or {}).get("status", "stopped")
        runtime_running     = bool(dashboard_health_ok or dashboard_status == "running")
        watcher_running     = watcher_status == "running"
    except Exception:
        runtime_running = False
        watcher_running = False

    try:
        from brain.openrouter_brain import get_brain_status
        brain = get_brain_status(_ROOT)
        brain_configured = bool(brain.get("configured", False))
        brain_label      = brain.get("label", "Unknown")
        brain_status_str = brain.get("status", "not_configured")
    except Exception:
        brain_configured = False
        brain_label      = "Unknown"
        brain_status_str = "not_configured"

    return {
        "api_token":           app.config["API_TOKEN"],
        "sys_runtime_running": runtime_running,
        "sys_watcher_running": watcher_running,
        "sys_brain_configured":brain_configured,
        "sys_brain_label":     brain_label,
        "sys_brain_status":    brain_status_str,
    }


@app.context_processor
def _inject_common_context():
    return _get_system_context()


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    ctx = _get_system_context()
    ctx.update({
        "request_path":  request.path,
        "request_id":    uuid4().hex[:8],
        "error_time":    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    })
    return render_template("404.html", **ctx), 404


@app.errorhandler(500)
def internal_error(e):
    ctx = _get_system_context()
    ctx.update({
        "request_path": request.path,
        "request_id":   uuid4().hex[:8],
        "error_time":   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "error_detail": "An unexpected server error occurred.",
    })
    return render_template("404.html",
                           error_code=500,
                           error_title="Internal Server Error",
                           **ctx), 500


# ---------------------------------------------------------------------------
# Blueprint registration
# ---------------------------------------------------------------------------
from routes.approvals import approvals_bp
from routes.model_loop import model_loop_bp
from routes.providers import providers_bp
from routes.dashboard import dashboard_bp
from routes.browser import browser_bp
from routes.workers import workers_bp
from routes.complexity import complexity_bp
from routes.memory import memory_bp
from routes.reports import reports_bp
from routes.plans import plans_bp
from routes.tasks import tasks_bp
from routes.timeline import timeline_bp

app.register_blueprint(approvals_bp)
app.register_blueprint(model_loop_bp)
app.register_blueprint(providers_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(browser_bp)
app.register_blueprint(workers_bp)
app.register_blueprint(complexity_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(timeline_bp)


@app.route('/health')
def health():
    from utils.process_manager import get_install_info
    info = get_install_info(_ROOT)
    return {
        "status": "ok",
        "service": "tibin-fullstack-agent-runtime",
        "host": "127.0.0.1",
        "port": 5000,
        "install_root": _ROOT,
        "git_branch": info.get("git_branch"),
        "git_commit": info.get("git_commit"),
    }


@app.route('/api/system/status')
def system_status():
    from utils.process_manager import get_process_status
    from brain.openrouter_brain import get_brain_status

    runs_dir = os.path.join(_ROOT, "runs")
    try:
        runs = len([d for d in os.listdir(runs_dir)
                    if os.path.isdir(os.path.join(runs_dir, d))])
    except OSError:
        runs = 0

    processes = get_process_status(_ROOT)
    processes["runs"] = runs
    return {
        "processes": processes,
        "brain": get_brain_status(_ROOT),
    }


if __name__ == '__main__':
    _server = os.path.join(_ROOT, "commands", "run_server.py")
    print(f"Use: python {_server}  (single-instance dashboard)")
    print(f"Stop: python {_server} --stop  OR  python tibin.py server --stop")
    os.execv(sys.executable, [sys.executable, _server])
