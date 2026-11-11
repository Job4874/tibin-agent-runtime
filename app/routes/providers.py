from flask import Blueprint, render_template, request, jsonify
import os
import sys
import glob

providers_bp = Blueprint('providers', __name__)

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@providers_bp.route('/api/providers/open_login', methods=['POST'])
def open_login():
    from flask import request
    from utils.provider_links import load_brain_config, open_url_in_system_browser
    data = request.get_json(silent=True) or {}
    provider_id = data.get('provider', 'boodlebox')
    cfg = load_brain_config().get("providers", {})
    prov = cfg.get(provider_id, {})
    url = prov.get('login_url') or prov.get('url', '')
    if not url:
        return jsonify({"status": "error", "error": f"No URL for {provider_id}"}), 400
    opened = open_url_in_system_browser(url)
    return jsonify({"status": "success", "url": url, "opened_browser": opened})

@providers_bp.route('/providers')
def providers_page():
    from model_providers.provider_registry import ProviderRegistry
    from model_providers.provider_errors import ProviderConfigError
    from brain.openrouter_brain import get_brain_status
    from utils.provider_links import load_brain_config

    config_error = None
    try:
        reg = ProviderRegistry(get_base_dir())
        active_name = reg.get_active_provider_name()
        all_providers = reg.config.get("providers", {})
    except ProviderConfigError as exc:
        # Render the page with a clear error state instead of a 500.
        reg = None
        active_name = "unavailable"
        all_providers = {}
        config_error = str(exc)
    
    status = {}
    try:
        status_path = os.path.join(get_base_dir(), "state", "provider_status.json")
        if os.path.exists(status_path):
            with open(status_path, "r", encoding="utf-8") as f:
                import json
                status = json.load(f)
    except Exception:
        pass

    # Latest prompt
    latest_prompt = ""
    prompt_path = os.path.join(get_base_dir(), "outbox", "model_prompts", "latest_prompt.md")
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                latest_prompt = f.read()
        except Exception:
            pass

    # Latest raw response
    latest_response = ""
    resp_dir = os.path.join(get_base_dir(), "inbox", "provider_responses")
    os.makedirs(resp_dir, exist_ok=True)
    resp_files = glob.glob(os.path.join(resp_dir, "*"))
    if resp_files:
        resp_files.sort(key=os.path.getmtime, reverse=True)
        try:
            with open(resp_files[0], "r", encoding="utf-8") as f:
                latest_response = f.read()
        except Exception:
            pass

    # Plan counts
    def count_files(subdir):
        d = os.path.join(get_base_dir(), "inbox", subdir)
        os.makedirs(d, exist_ok=True)
        return len(glob.glob(os.path.join(d, "*.json")))

    candidate_plans = count_files("candidate_plans")
    rejected_plans = count_files("rejected_plans")
    validated_plans = count_files("validated_plans")

    return render_template('providers.html',
                           active_name=active_name,
                           all_providers=all_providers,
                           config_error=config_error,
                           status=status,
                           latest_prompt=latest_prompt,
                           latest_response=latest_response,
                           candidate_plans=candidate_plans,
                           rejected_plans=rejected_plans,
                           validated_plans=validated_plans,
                           external_providers=load_brain_config().get("providers", {}),
                           brain=get_brain_status(get_base_dir()))

@providers_bp.route('/api/providers/status', methods=['POST'])
def check_status():
    from model_providers.provider_registry import ProviderRegistry
    reg = ProviderRegistry(get_base_dir())
    active_prov = reg.get_active_provider()
    res = active_prov.health_check()
    
    import json
    os.makedirs(os.path.join(get_base_dir(), "state"), exist_ok=True)
    with open(os.path.join(get_base_dir(), "state", "provider_status.json"), "w") as f:
        json.dump({"active": reg.get_active_provider_name(), "status": res}, f)
        
    return jsonify({"status": "success", "health": res})

@providers_bp.route('/api/providers/run_next', methods=['POST'])
def run_next():
    try:
        from runtime import do_run_next
        result = do_run_next()
        if result is False:
            return jsonify({
                "status": "no_plans",
                "error": "No validated plans found in inbox/validated_plans/.",
            }), 404
        if result == "pending_approval":
            return jsonify({
                "status": "pending_approval",
                "message": "Plan requires approval before it can run. See the Approvals page.",
            })
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
