from flask import Blueprint, render_template, jsonify, request
import os
import json
import glob
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__)

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@tasks_bp.route('/tasks')
def tasks_page():
    from brain.openrouter_brain import get_brain_status
    brain = get_brain_status(get_base_dir())
    return render_template('tasks.html', brain=brain)

@tasks_bp.route('/api/tasks/brain')
def api_brain():
    from brain.openrouter_brain import get_brain_status
    return jsonify(get_brain_status(get_base_dir()))

@tasks_bp.route('/api/tasks/run_loop', methods=['POST'])
def api_run_loop():
    data = request.get_json(silent=True) or {}
    plan = data.get('plan', 'examples/safe_code_plan.json')
    try:
        max_turns = max(1, min(int(data.get('max_turns', 10)), 50))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": "max_turns must be an integer"}), 400
    base = os.path.realpath(get_base_dir())
    # Plans must be JSON files inside the install root — no absolute paths or traversal.
    plan_path = os.path.realpath(os.path.join(base, plan))
    if not plan_path.startswith(base + os.sep) or not plan_path.endswith(".json"):
        return jsonify({"status": "error", "error": "Plan must be a .json file inside the project"}), 400
    if not os.path.exists(plan_path):
        return jsonify({"status": "error", "error": f"Plan not found: {plan}"}), 404
    if not plan_path.endswith('.json'):
        return jsonify({"status": "error", "error": "Plan file must be a .json file."}), 400
    try:
        from model_loop.agent_loop import run_plan_loop
        result = run_plan_loop(plan_path, base, max_turns=max_turns)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500

@tasks_bp.route('/api/tasks/run_autonomous', methods=['POST'])
def api_run_autonomous():
    data = request.get_json(silent=True) or {}
    goal = (data.get('goal') or '').strip()
    try:
        max_turns = max(1, min(int(data.get('max_turns', 10)), 50))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "error": "max_turns must be an integer"}), 400
    if not goal:
        return jsonify({"status": "error", "error": "Goal is required"}), 400
    if len(goal) > 2000:
        return jsonify({"status": "error", "error": "Goal must be 2000 characters or fewer."}), 400
    from brain.openrouter_brain import OpenRouterBrain
    brain = OpenRouterBrain(get_base_dir())
    if not brain.is_configured():
        return jsonify({
            "status": "failed_no_brain",
            "error": "OPENROUTER_API_KEY is not configured. Add it to .env to run autonomous tasks.",
        }), 400
    try:
        from model_loop.agent_loop import run_autonomous
        result = run_autonomous(goal, get_base_dir(), max_turns=max_turns)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
