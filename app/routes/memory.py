from flask import Blueprint, render_template
from pathlib import Path
import json
import glob
import os

memory_bp = Blueprint('memory', __name__)

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

@memory_bp.route('/memory')
def memory_page():
    base = get_base_dir()
    memory_path = base / "state" / "memory.json"
    lessons_path = base / "state" / "lessons.md"
    data = {
        "memory_json": read_text(memory_path),
        "lessons": read_text(lessons_path),
    }
    return render_template('memory.html', **data)
