from flask import Blueprint, render_template
import glob
import os
from pathlib import Path

plans_bp = Blueprint('plans', __name__)

def get_base_dir() -> Path:
    return Path(__file__).resolve().parents[2]

@plans_bp.route('/plans')
def plans_page():
    base = get_base_dir()
    def list_json(directory: str):
        d = base / "inbox" / directory
        d.mkdir(parents=True, exist_ok=True)
        return [p.name for p in d.glob("*.json")]

    data = {
        "validated_plans": list_json("validated_plans"),
        "candidate_plans": list_json("candidate_plans"),
        "rejected_plans": list_json("rejected_plans"),
    }
    return render_template('plans.html', **data)
