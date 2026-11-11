from flask import Blueprint, render_template, request, jsonify
import os
import sys

# Ensure tools can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.approval_store import ApprovalStore

approvals_bp = Blueprint('approvals', __name__)

def get_approval_store():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return ApprovalStore(base_dir)

@approvals_bp.route('/approvals')
def approvals_page():
    store = get_approval_store()
    all_approvals = store.list_approvals()
    
    # Read latest observation to find currently blocked actions
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    obs_file = os.path.join(base_dir, "observations", "latest_observation.json")
    blocked_actions = []
    
    import json
    if os.path.exists(obs_file):
        try:
            with open(obs_file, "r") as f:
                obs = json.load(f)
            if obs.get("status") == "pending_approval":
                plan_id = obs.get("plan_id")
                for action in obs.get("action_results", []):
                    if action.get("status") == "pending_approval":
                        blocked_actions.append({
                            "plan_id": plan_id,
                            "action_id": action.get("action_id"),
                            "error": action.get("error")
                        })
        except Exception:
            pass
            
    return render_template('approvals.html', approvals=all_approvals, blocked=blocked_actions)

@approvals_bp.route('/api/approvals/approve', methods=['POST'])
def approve_action():
    data = request.json
    plan_id = data.get('plan_id')
    action_id = data.get('action_id')
    reason = data.get('reason', 'User approved from UI')
    risk_level = data.get('risk_level', 'medium')
    
    if not plan_id or not action_id:
        return jsonify({"error": "plan_id and action_id required"}), 400
        
    store = get_approval_store()
    record = store.create_approval(plan_id, action_id, "approved", reason, risk_level)
    return jsonify({"status": "success", "record": record})

@approvals_bp.route('/api/approvals/reject', methods=['POST'])
def reject_action():
    data = request.json
    plan_id = data.get('plan_id')
    action_id = data.get('action_id')
    reason = data.get('reason', 'User rejected from UI')
    
    if not plan_id or not action_id:
        return jsonify({"error": "plan_id and action_id required"}), 400
        
    store = get_approval_store()
    record = store.reject_approval(plan_id, action_id, reason)
    return jsonify({"status": "success", "record": record})
