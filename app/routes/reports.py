from flask import Blueprint, render_template
from pathlib import Path
import json
import glob
import os

reports_bp = Blueprint('reports', __name__)

def get_base_dir() -> Path:
    return Path(__file__).resolve().parents[2]

def read_text(path: Path, limit: int = 8000) -> str:
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:limit] + ("..." if len(text) > limit else "")
    except Exception as exc:
        return f"[read error: {exc}]"

@reports_bp.route('/reports')
def reports_page():
    base = get_base_dir()
    data = {
        "latest_report": read_text(base / "reports" / "latest_report.md"),
        "latest_observation": read_text(base / "observations" / "latest_observation.json"),
    }
    return render_template('reports.html', **data)
