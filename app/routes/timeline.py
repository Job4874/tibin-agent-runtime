from flask import Blueprint, render_template, jsonify, abort
import os
import json

timeline_bp = Blueprint('timeline', __name__)

def get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@timeline_bp.route('/timeline')
def timeline_page():
    base = get_base_dir()
    runs_dir = os.path.join(base, "runs")
    runs = []
    if os.path.exists(runs_dir):
        for name in sorted(os.listdir(runs_dir), reverse=True):
            run_path = os.path.join(runs_dir, name)
            if not os.path.isdir(run_path):
                continue
            trace = os.path.join(run_path, "trace.jsonl")
            report = os.path.join(run_path, "report.md")
            plan = os.path.join(run_path, "plan.json")
            mtime = os.path.getmtime(run_path)
            status = "unknown"
            if os.path.exists(trace):
                try:
                    with open(trace, "r", encoding="utf-8") as f:
                        for line in f:
                            ev = json.loads(line)
                            if ev.get("event") == "loop_end":
                                status = ev.get("status", status)
                except Exception:
                    pass
            elif os.path.exists(plan):
                status = "plan_run"
            runs.append({
                "run_id": name,
                "status": status,
                "has_trace": os.path.exists(trace),
                "has_report": os.path.exists(report),
                "mtime": mtime,
            })
    return render_template('timeline.html', runs=runs[:50])

@timeline_bp.route('/timeline/<run_id>')
def timeline_detail(run_id):
    base = get_base_dir()
    run_path = os.path.join(base, "runs", run_id)
    if not os.path.isdir(run_path) or ".." in run_id:
        abort(404)
    trace_lines = []
    trace_path = os.path.join(run_path, "trace.jsonl")
    if os.path.exists(trace_path):
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    trace_lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    report = ""
    report_path = os.path.join(run_path, "report.md")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report = f.read()
    return render_template('timeline_detail.html', run_id=run_id, trace_lines=trace_lines, report=report)

@timeline_bp.route('/api/timeline/runs')
def api_runs():
    base = get_base_dir()
    runs_dir = os.path.join(base, "runs")
    runs = []
    if os.path.exists(runs_dir):
        for name in sorted(os.listdir(runs_dir), reverse=True)[:50]:
            run_path = os.path.join(runs_dir, name)
            if os.path.isdir(run_path):
                runs.append({"run_id": name, "path": run_path})
    return jsonify({"runs": runs})
