from flask import Blueprint, render_template, request, jsonify
import os
import sys
import glob
import json

model_loop_bp = Blueprint('model_loop', __name__)

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

@model_loop_bp.route('/model_loop')
def model_loop_page():
    base_dir = get_base_dir()
    
    # Read latest observation summary
    obs_path = os.path.join(base_dir, "observations", "latest_observation.json")
    obs_summary = read_file(obs_path)
    if obs_summary:
        obs_summary = obs_summary[:1000] + ("..." if len(obs_summary) > 1000 else "")

    # Read latest prompt
    prompt_path = os.path.join(base_dir, "outbox", "model_prompts", "latest_prompt.md")
    latest_prompt = read_file(prompt_path)

    # Read latest request
    req_path = os.path.join(base_dir, "outbox", "model_requests", "latest_model_request.json")
    latest_request = read_file(req_path)

    # Get plans
    inbox_plans_dir = os.path.join(base_dir, "inbox", "candidate_plans")
    val_plans_dir = os.path.join(base_dir, "inbox", "validated_plans")
    rej_plans_dir = os.path.join(base_dir, "inbox", "rejected_plans")
    
    os.makedirs(inbox_plans_dir, exist_ok=True)
    os.makedirs(val_plans_dir, exist_ok=True)
    os.makedirs(rej_plans_dir, exist_ok=True)
    
    candidate_plans = [os.path.basename(p) for p in glob.glob(os.path.join(inbox_plans_dir, "*.json"))]
    validated_plans = [os.path.basename(p) for p in glob.glob(os.path.join(val_plans_dir, "*.json"))]
    rejected_plans = [os.path.basename(p) for p in glob.glob(os.path.join(rej_plans_dir, "*.json"))]
    
    # Read daemon status
    daemon_status = {"status": "stopped", "message": "Not running"}
    status_file = os.path.join(base_dir, "state", "daemon_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                daemon_status = json.load(f)
        except:
            pass

    return render_template('model_loop.html',
                           obs_summary=obs_summary,
                           latest_prompt=latest_prompt,
                           latest_request=latest_request,
                           candidate_plans=candidate_plans,
                           validated_plans=validated_plans,
                           rejected_plans=rejected_plans,
                           daemon_status=daemon_status)

@model_loop_bp.route('/api/model_loop/generate_prompt', methods=['POST'])
def generate_prompt():
    from model_loop.prompt_builder import PromptBuilder
    pb = PromptBuilder(get_base_dir())
    prompt_path, req_path = pb.build_prompt()
    return jsonify({"status": "success", "prompt_path": prompt_path, "req_path": req_path})

@model_loop_bp.route('/api/daemon/start', methods=['POST'])
def start_daemon():
    import subprocess
    base = get_base_dir()
    status_file = os.path.join(base, "state", "daemon_status.json")

    from utils.process_manager import (
        read_pid_file,
        is_pid_alive,
        register_watcher_pid,
        WATCHER_PID_FILE,
    )

    existing = read_pid_file(WATCHER_PID_FILE, base)
    if existing and is_pid_alive(existing):
        return jsonify({"error": "Watcher already running.", "pid": existing}), 400

    p = subprocess.Popen(
        [sys.executable, "runtime.py", "--watch", "--max-loops", "50"],
        cwd=base,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    register_watcher_pid(p.pid, base)

    os.makedirs(os.path.dirname(status_file), exist_ok=True)
    with open(status_file, "w") as f:
        json.dump({"status": "running", "message": "Starting...", "pid": p.pid}, f)

    return jsonify({"status": "success", "pid": p.pid})

@model_loop_bp.route('/api/daemon/stop', methods=['POST'])
def stop_daemon():
    from utils.process_manager import stop_watcher
    result = stop_watcher(get_base_dir())
    return jsonify({"status": "success", **result})
