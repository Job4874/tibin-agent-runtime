from flask import Blueprint, render_template, jsonify
import os
import json

dashboard_bp = Blueprint('dashboard', __name__)

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def dashboard_page():
    from brain.openrouter_brain import get_brain_status
    brain = get_brain_status(get_base_dir())
    return render_template('dashboard.html', brain=brain)

@dashboard_bp.route('/api/brain')
def api_brain():
    from brain.openrouter_brain import get_brain_status
    return jsonify(get_brain_status(get_base_dir()))

@dashboard_bp.route('/api/status')
def api_status():
    base_dir = get_base_dir()
    status_file = os.path.join(base_dir, "state", "daemon_status.json")
    
    if not os.path.exists(status_file):
        return jsonify({"status": "stopped", "message": "Daemon is not running."})
        
    try:
        with open(status_file, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@dashboard_bp.route('/api/stats')
def api_stats():
    base_dir = get_base_dir()
    val_dir = os.path.join(base_dir, "inbox", "validated_plans")
    rej_dir = os.path.join(base_dir, "inbox", "rejected_plans")
    obs_dir = os.path.join(base_dir, "observations")
    
    def count_files(d):
        return len(os.listdir(d)) if os.path.exists(d) else 0
        
    return jsonify({
        "validated_plans": count_files(val_dir),
        "rejected_plans": count_files(rej_dir),
        "observations": count_files(obs_dir)
    })
