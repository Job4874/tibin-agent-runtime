import sys
import os
import json
import argparse
from typing import Dict, Any

from utils.env_loader import load_dotenv

load_dotenv(os.path.dirname(os.path.abspath(__file__)))

from agents.defender_agent import DefenderAgent
from agents.manager_agent import ManagerAgent
from workers.shell_worker import ShellWorker
from workers.file_worker import FileWorker
from workers.git_worker import GitWorker
from workers.coder_worker import CoderWorker
from workers.research_worker import ResearchWorker
from workers.verifier_worker import VerifierWorker
from workers.memory_worker import MemoryWorker
from workers.report_worker import ReportWorker
from tools.redaction import RedactionTool

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
    _RICH = True
    _console = Console()
except ImportError:
    _RICH = False
    _console = None


def _print(msg: str, style: str = ""):
    if _RICH and _console:
        _console.print(msg, style=style)
    else:
        print(msg)


def _print_panel(title: str, content: str, style: str = "blue"):
    if _RICH:
        _console.print(Panel(content, title=title, border_style=style))
    else:
        print(f"\n=== {title} ===\n{content}\n")


def get_base_dir():
    return os.path.dirname(os.path.abspath(__file__))

def init_runtime():
    base_dir = get_base_dir()
    
    defender = DefenderAgent(base_dir)
    redaction = RedactionTool()
    
    workers = {
        "ShellWorker": ShellWorker(),
        "FileWorker": FileWorker(base_dir, redaction),
        "GitWorker": GitWorker(os.path.join(base_dir, "workspace", "repos")),
        "CoderWorker": CoderWorker(base_dir),
        "ResearchWorker": ResearchWorker(base_dir),
        "VerifierWorker": VerifierWorker(base_dir),
        "MemoryWorker": MemoryWorker(base_dir),
        "ReportWorker": ReportWorker(base_dir),
        "BrowserWorker": None  # Initialised below if Playwright is available
    }
    
    # Initialize Browser modules
    try:
        from browser.new_browser import NewBrowserManager
        from tools.browser_tool import BrowserTool
        from tools.browser_observer import BrowserObserver
        from tools.browser_safety import BrowserSafety
        from workers.browser_worker import BrowserWorker
        
        browser_manager = NewBrowserManager(base_dir)
        browser_safety = BrowserSafety(defender.web_permissions)
        browser_tool = BrowserTool(browser_manager, browser_safety)
        browser_observer = BrowserObserver(base_dir)
        
        workers["BrowserWorker"] = BrowserWorker(browser_tool, browser_observer)
    except ImportError:
        pass
    
    manager = ManagerAgent(base_dir, defender, workers)
    return manager

def run_once():
    _print("[bold cyan]Running Tibin Agent Runtime --once[/bold cyan]")
    manager = init_runtime()
    base_dir = get_base_dir()
    inbox_validated = os.path.join(base_dir, "inbox", "validated_plans")
    if os.path.isdir(inbox_validated):
        plans = [f for f in os.listdir(inbox_validated) if f.endswith(".json")]
        if plans:
            next_plan = os.path.join(inbox_validated, sorted(plans)[0])
            _print(f"[green]Found plan:[/green] {next_plan}")
            run_plan(next_plan)
            return
    _print("[yellow]No validated plans in inbox. Runtime initialized successfully.[/yellow]")

def status():
    base_dir = get_base_dir()
    runs_dir = os.path.join(base_dir, "runs")
    run_count = len(os.listdir(runs_dir)) if os.path.isdir(runs_dir) else 0
    obs_dir = os.path.join(base_dir, "observations")
    obs_count = len([f for f in os.listdir(obs_dir) if f.endswith(".json")]) if os.path.isdir(obs_dir) else 0

    if _RICH:
        table = Table(title="Tibin Runtime Status", border_style="blue")
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        table.add_row("Base Dir", base_dir)
        table.add_row("Total Runs", str(run_count))
        table.add_row("Observations", str(obs_count))
        table.add_row("Status", "[green]Active[/green]")
        _console.print(table)
    else:
        print("Tibin Full-Stack Agent Runtime")
        print("Status: Active")
        print(f"Base Dir: {base_dir}")
        print(f"Total Runs: {run_count}")
        print(f"Observations: {obs_count}")

def validate_plan(path):
    from model_loop.plan_validator import PlanValidator
    _print(f"[cyan]Validating plan:[/cyan] {path}")
    if not os.path.exists(path):
        _print(f"[red]File not found:[/red] {path}")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except Exception as e:
        _print(f"[red]Invalid JSON:[/red] {e}")
        return

    validator = PlanValidator(get_base_dir())
    is_valid, reason = validator.validate_plan(plan)
    if is_valid:
        actions = plan.get("actions", [])
        _print(f"[green]Plan is valid.[/green] {len(actions)} action(s) found.")
        if _RICH:
            table = Table(border_style="green")
            table.add_column("Action ID", style="cyan")
            table.add_column("Worker")
            table.add_column("Type")
            for a in actions:
                table.add_row(
                    a.get("action_id", "?"),
                    a.get("worker", "?"),
                    a.get("type", "?"),
                )
            _console.print(table)
    else:
        _print(f"[red]Plan is invalid:[/red] {reason}")

def approve_plan(path):
    _print(f"[cyan]Approving plan:[/cyan] {path}")
    from tools.approval_store import ApprovalStore
    base_dir = get_base_dir()
    store = ApprovalStore(base_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        plan_id = plan.get("plan_id", os.path.basename(path))
        record = store.create_approval(
            plan_id=plan_id,
            action_id="*",
            decision="approved",
            reason="Approved via CLI (--approve)",
            risk_level="medium",
        )
        _print(f"[green]Plan '{plan_id}' approved for all actions.[/green] Approval ID: {record['approval_id']}")
    except Exception as e:
        _print(f"[red]Approval failed:[/red] {e}")

def run_plan(path):
    _print(f"[bold cyan]Running plan:[/bold cyan] {path}")
    if not os.path.exists(path):
        _print(f"[red]File not found:[/red] {path}")
        return None
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)

        # Validate before executing
        from model_loop.plan_validator import PlanValidator
        validator = PlanValidator(get_base_dir())
        is_valid, reason = validator.validate_plan(plan)
        if not is_valid:
            _print(f"[red]Plan validation failed:[/red] {reason}")
            return None

        manager = init_runtime()

        if _RICH:
            with _console.status("[bold green]Executing plan...[/bold green]", spinner="dots"):
                result = manager.execute_plan(plan)
        else:
            result = manager.execute_plan(plan)

        # Only write state back for inbox plans, not examples
        if os.sep + "examples" + os.sep not in path and "examples/" not in path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)
            
        plan_status = result.get("status", "unknown")
        status_color = {"completed": "green", "failed": "red", "blocked": "yellow"}.get(plan_status, "white")

        if _RICH:
            table = Table(title=f"Plan Result — {plan_status.upper()}", border_style=status_color)
            table.add_column("Action ID", style="cyan")
            table.add_column("Status")
            table.add_column("Detail")
            for r in result.get("worker_results", []):
                act_status = r.get("status", "?")
                color = {"success": "green", "failed": "red", "blocked": "yellow"}.get(act_status, "white")
                detail = r.get("error", "") or str(r.get("data", {}).get("message", ""))
                table.add_row(
                    r.get("action_id", "?"),
                    f"[{color}]{act_status}[/{color}]",
                    detail[:80],
                )
            _console.print(table)
            if result.get("errors"):
                _console.print("[red]Errors:[/red]")
                for e in result["errors"]:
                    _console.print(f"  • {e}", style="red")
        else:
            print(f"Status: {plan_status}")
            print(json.dumps(result, indent=2, default=str))

        # Trigger report worker only if finished
        if plan_status in ["completed", "failed"]:
            report_worker = manager.workers.get("ReportWorker")
            if report_worker:
                observation = {
                    "observation_id": f"obs-{plan.get('plan_id', 'unknown')}",
                    "plan_id": plan.get("plan_id"),
                    "objective_id": plan.get("objective_id"),
                    "status": plan_status,
                    "actions_executed": [r.get("action_id") for r in result.get("worker_results", []) if r.get("status") == "success"],
                    "actions_blocked": [r.get("action_id") for r in result.get("worker_results", []) if r.get("status") == "blocked"],
                    "errors": [r.get("error") for r in result.get("worker_results", []) if r.get("error")],
                    "worker_results": result.get("worker_results", [])
                }
                report_worker.execute({"params": {"observation_data": observation}})
                
        return result
            
    except Exception as e:
        _print(f"[red]Execution failed:[/red] {e}")
        return None

def do_doctor():
    import subprocess
    import tempfile

    _print("[bold cyan]Running doctor checks...[/bold cyan]")
    checks = []
    base = get_base_dir()

    # 1. Python version
    py_version = sys.version_info
    checks.append(("Python >= 3.10", py_version >= (3, 10), f"{py_version.major}.{py_version.minor}.{py_version.micro}"))

    # 2. Required packages
    for pkg in ["requests", "flask", "rich", "jsonschema"]:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "?")
            checks.append((f"Package {pkg}", True, ver))
        except ImportError:
            checks.append((f"Package {pkg}", False, "not installed"))

    # 3. Playwright
    try:
        import playwright
        ver = getattr(playwright, "__version__", "?")
        checks.append(("Playwright installed", True, ver))
    except ImportError:
        checks.append(("Playwright installed", False, "pip install playwright"))

    # 4. Browser drivers
    try:
        result = subprocess.run([sys.executable, "-m", "playwright", "install", "--help"], capture_output=True, timeout=10)
        checks.append(("Playwright CLI", result.returncode == 0, "ok" if result.returncode == 0 else "run: python3 -m playwright install chromium"))
    except Exception:
        checks.append(("Playwright CLI", False, "playwright not available"))

    # 5. Git
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
        ver = result.stdout.strip() if result.returncode == 0 else "?"
        checks.append(("Git available", result.returncode == 0, ver))
    except Exception:
        checks.append(("Git available", False, "not found"))

    # 6. Required directories (runtime dirs are auto-created; gitignored ones
    # are missing on fresh checkouts, which is not an error)
    for d in ["state", "permissions", "inbox", "outbox", "logs", "reports", "observations", "runs", "screenshots"]:
        path = os.path.join(base, d)
        created = False
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
                created = True
            except OSError:
                pass
        exists = os.path.exists(path)
        checks.append((f"Dir: {d}", exists, "created" if created else ("ok" if exists else f"mkdir {d}")))

    # 7. Config files
    for f in ["config/runtime.json", "config/brain.json", "config/browser.json", "config/workers.json"]:
        exists = os.path.exists(os.path.join(base, f))
        checks.append((f"Config: {f}", exists, "ok" if exists else "missing"))

    # 8. Schema files
    for f in ["schemas/plan.schema.json", "schemas/action.schema.json", "schemas/observation.schema.json"]:
        exists = os.path.exists(os.path.join(base, f))
        checks.append((f"Schema: {f}", exists, "ok" if exists else "missing"))

    # 9. Write permissions
    try:
        tmp = tempfile.TemporaryFile(dir=base)
        tmp.close()
        checks.append(("Write permission: base dir", True, "ok"))
    except Exception:
        checks.append(("Write permission: base dir", False, "check permissions"))

    # 10. App binds to localhost only
    server_path = os.path.join(base, "commands", "run_server.py")
    if not os.path.exists(server_path):
        server_path = os.path.join(base, "run_server.py")
    try:
        with open(server_path, "r", encoding="utf-8") as f:
            server_src = f.read()
        binds_local = "host=\"127.0.0.1\"" in server_src or "host='127.0.0.1'" in server_src
        checks.append(("App binds to 127.0.0.1", binds_local, "ok" if binds_local else "start server first"))
    except Exception:
        checks.append(("App binds to 127.0.0.1", False, "server not found"))

    # 11. OpenRouter brain
    try:
        from brain.openrouter_brain import OpenRouterBrain
        brain = OpenRouterBrain(base)
        configured = brain.is_configured()
        checks.append(("brain:openrouter configured", configured, "ok" if configured else "set OPENROUTER_API_KEY in .env"))
    except Exception:
        checks.append(("brain:openrouter configured", False, "set OPENROUTER_API_KEY in .env"))

    # 12. CoderWorker and ResearchWorker
    checks.append(("CoderWorker available", os.path.exists(os.path.join(base, "workers", "coder_worker.py")), "ok"))
    checks.append(("ResearchWorker available", os.path.exists(os.path.join(base, "workers", "research_worker.py")), "ok"))

    failures = sum(1 for _, passed, _ in checks if not passed)

    if _RICH:
        table = Table(title="Doctor Checks", border_style="cyan")
        table.add_column("Check", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Detail", style="dim")
        for name, passed, detail in checks:
            status_str = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            table.add_row(name, status_str, detail)
        _console.print(table)
        overall = "[green]All checks passed![/green]" if failures == 0 else f"[red]{failures} check(s) failed[/red]"
        _console.print(f"\nDoctor: {overall}")
    else:
        for name, passed, detail in checks:
            print(f"[{'PASS' if passed else 'FAIL'}] {name} — {detail}")
        print(f"\nDoctor: {'PASS' if failures == 0 else f'FAIL ({failures} issues)'}")

def do_audit():
    import subprocess
    import datetime

    print("Running full safety audit...")
    base = get_base_dir()
    env = os.environ.copy()
    env["PYTHONPATH"] = base

    lines = [
        "# Tibin Runtime Audit Report",
        f"Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        "",
    ]

    def run_cmd(cmd_list, label):
        print(f"Running: {label}")
        lines.append(f"## {label}")
        try:
            result = subprocess.run(cmd_list, capture_output=True, text=True, cwd=base, env=env, timeout=120)
            rc = result.returncode
            out = result.stdout.strip()
            err = result.stderr.strip()
            lines.append(f"- Command: `{' '.join(cmd_list)}`")
            lines.append(f"- Return code: {rc}")
            if out:
                lines.append("```")
                lines.append(out)
                lines.append("```")
            if err and rc != 0:
                lines.append("**Stderr:**")
                lines.append("```")
                lines.append(err)
                lines.append("```")
            lines.append(f"- **Status:** {'PASS' if rc == 0 else 'FAIL'}")
            return rc == 0, out + "\n" + err
        except Exception as exc:
            lines.append(f"- Exception: {exc}")
            lines.append("- **Status:** FAIL")
            return False, str(exc)

    # 1. Doctor
    ok, _ = run_cmd([sys.executable, "runtime.py", "--doctor"], "Doctor Checks")

    # 2. Status
    ok2, _ = run_cmd([sys.executable, "runtime.py", "--status"], "Runtime Status")

    # 3. Validate example plans
    examples_dir = os.path.join(base, "examples")
    validated = 0
    failed_plans = []
    for fname in os.listdir(examples_dir):
        if fname.endswith(".json"):
            path = os.path.join(examples_dir, fname)
            ok_p, _ = run_cmd([sys.executable, "runtime.py", "--validate", path], f"Validate {fname}")
            if ok_p:
                validated += 1
            else:
                failed_plans.append(fname)

    # 4. Run safe plan
    safe_plan = os.path.join(base, "examples", "safe_code_plan.json")
    ok_safe = False
    if os.path.exists(safe_plan):
        ok_safe, _ = run_cmd([sys.executable, "runtime.py", "--run-plan", safe_plan], "Run Safe Plan")

    # 5. Run blocked dangerous plan
    blocked_plan = os.path.join(base, "examples", "blocked_dangerous_plan.json")
    ok_blocked = False
    if os.path.exists(blocked_plan):
        ok_blocked, _ = run_cmd([sys.executable, "runtime.py", "--run-plan", blocked_plan], "Run Blocked Dangerous Plan")

    # 6. Pytest
    ok_pytest, pytest_out = run_cmd([sys.executable, "-m", "pytest", "tests/", "-q"], "Pytest Suite")

    # Summary table
    lines.extend([
        "",
        "## Summary",
        "",
        "| Check        | Status |",
        "|--------------|--------|",
        f"| Doctor       | {'PASS' if ok else 'FAIL'} |",
        f"| Status       | {'PASS' if ok2 else 'FAIL'} |",
        f"| Validated plans ({validated}) | {'PASS' if not failed_plans else 'FAIL'} |",
        f"| Safe plan    | {'PASS' if ok_safe else 'FAIL'} |",
        f"| Blocked plan | {'PASS' if ok_blocked else 'FAIL'} |",
        f"| Pytest       | {'PASS' if ok_pytest else 'FAIL'} |",
        "",
        "## Remaining Stubs",
        "- BrowserWorker: stubbed if Playwright not installed",
        "- ComplexityEngine: basic analysis implemented",
        "",
        "## Next Implementation Step",
        "- Continue model loop integration",
    ])

    # Write report
    report_dir = os.path.join(base, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "audit_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nAudit report saved to {report_path}")

def do_next_prompt():
    from model_loop.prompt_builder import PromptBuilder
    pb = PromptBuilder(get_base_dir())
    p, r = pb.build_prompt()
    print(f"Prompt generated at: {p}")

def do_ingest_plan(path):
    from model_loop.plan_validator import PlanValidator
    pv = PlanValidator(get_base_dir())
    val_dir = os.path.join(get_base_dir(), "inbox", "validated_plans")
    rej_dir = os.path.join(get_base_dir(), "inbox", "rejected_plans")
    os.makedirs(val_dir, exist_ok=True)
    os.makedirs(rej_dir, exist_ok=True)
    is_valid, msg = pv.ingest_candidate(path, val_dir, rej_dir)
    print(f"Ingest plan {path}: {'Valid' if is_valid else 'Invalid'} - {msg}")

def do_run_next():
    import glob
    import shutil
    val_dir = os.path.join(get_base_dir(), "inbox", "validated_plans")
    done_dir = os.path.join(get_base_dir(), "inbox", "completed_plans")
    os.makedirs(val_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)
    plans = glob.glob(os.path.join(val_dir, "*.json"))
    if not plans:
        print("No validated plans found.")
        return False
    plans.sort(key=os.path.getmtime, reverse=True)
    path = plans[0]
    print(f"Running newest validated plan: {path}")
    
    res = run_plan(path)
    if res and res.get("status") in ["completed", "failed"]:
        # Move it out of validated_plans
        shutil.move(path, os.path.join(done_dir, os.path.basename(path)))
        return True
    elif res and res.get("status") == "pending_approval":
        print("Plan requires approval. Sleeping...")
        return "pending_approval"
    return False

def do_model_loop_once():
    do_next_prompt()
    print("Model loop paused. Waiting for manual handoff...")
    print("Paste model response plan into inbox/candidate_plans/ and run --ingest-plan, then --run-next.")

def do_provider_status():
    from model_providers.provider_registry import ProviderRegistry
    reg = ProviderRegistry(get_base_dir())
    active_name = reg.get_active_provider_name()
    active_prov = reg.get_active_provider()
    status = active_prov.health_check()
    print(f"Active Provider: {active_name}")
    print(f"Health Status: {status}")
    os.makedirs(os.path.join(get_base_dir(), "state"), exist_ok=True)
    with open(os.path.join(get_base_dir(), "state", "provider_status.json"), "w") as f:
        json.dump({"active": active_name, "status": status}, f)

def do_generate_with_provider():
    from model_loop.prompt_builder import PromptBuilder
    from model_providers.provider_registry import ProviderRegistry
    from model_providers.response_parser import ResponseParser
    import json
    
    pb = PromptBuilder(get_base_dir())
    prompt_path, _ = pb.build_prompt()
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()
        
    reg = ProviderRegistry(get_base_dir())
    prov = reg.get_active_provider()
    
    print(f"Generating with {prov.name}...")
    result = prov.generate(prompt)
    print(f"Status: {result['status']}")
    
    if result['status'] == 'not_configured':
        print("Provider not configured.")
        return result
        
    if result['status'] == 'rate_limited':
        print("Provider rate limited. Writing blocker and checkpoint.")
        return result
        
    if result['status'] == 'context_length_exceeded':
        print("Context too large. Triggering compact prompt generation...")
        return result
    
    if result['status'] == 'success':
        if prov.name == 'file' or prov.name == 'manual':
            return result
            
        parser = ResponseParser()
        status, plan, err = parser.parse(result['raw_text'])
        print(f"Parse status: {status}")
        
        if status == 'parsed':
            import time
            cand_dir = os.path.join(get_base_dir(), "inbox", "candidate_plans")
            os.makedirs(cand_dir, exist_ok=True)
            cand_path = os.path.join(cand_dir, f"plan_{int(time.time())}.json")
            with open(cand_path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)
            print(f"Candidate plan saved to {cand_path}")
        else:
            print("Output is invalid. Reject and generate a repair prompt.")
    return result

def do_ingest_provider_response():
    from model_providers.provider_registry import ProviderRegistry
    reg = ProviderRegistry(get_base_dir())
    file_prov = reg.get_provider("file")
    result = file_prov.generate("")
    print(f"File ingest status: {result['status']}")
    return result

def do_export_training_data():
    from model_loop.evidence_recorder import EvidenceRecorder
    recorder = EvidenceRecorder(get_base_dir())
    result = recorder.export_training_data()
    print(json.dumps(result, indent=2))
    return result

def _probe_boodlebox_access():
    import urllib.request
    from datetime import datetime, timezone

    url = "https://box.boodle.ai/launch/chat"
    result = {
        "url": url,
        "reachable": False,
        "login_required": True,
        "http_status": None,
        "error": "",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TibinRuntime/1.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read(200000).decode("utf-8", errors="ignore")
            body_lower = body.lower()
            result["http_status"] = response.status
            result["reachable"] = 200 <= response.status < 400
            result["login_required"] = any(
                token in body_lower
                for token in ["sign in", "sign up", "log in", "login", "password"]
            )
    except Exception as exc:
        result["error"] = str(exc)
    return result

def do_model_access_audit(task="Building applications"):
    from datetime import datetime, timezone
    from model_loop.evidence_recorder import EvidenceRecorder
    from model_loop.model_router import ModelRouter
    from model_providers.browser_llm_provider import BrowserLLMProvider
    from model_providers.provider_registry import ProviderRegistry

    base = get_base_dir()
    reg = ProviderRegistry(base)
    provider_health = {}
    for provider_name in reg.config.get("providers", {}).keys():
        try:
            provider_health[provider_name] = reg.get_provider(provider_name).health_check()
        except Exception as exc:
            provider_health[provider_name] = {"status": "failed", "error": str(exc)}

    browser_provider = BrowserLLMProvider({}, base)
    browser_provider_status = browser_provider.get_provider_status()
    boodlebox_access = _probe_boodlebox_access()
    public_login_gate = bool(boodlebox_access.get("login_required"))
    system_profile_auth = bool(browser_provider_status.get("system_profile_auth_expected"))
    if browser_provider_status.get("requires_user_login") and not system_profile_auth:
        boodlebox_access["login_required"] = True
    boodlebox_access["public_login_gate"] = public_login_gate
    boodlebox_access["system_profile_auth_expected"] = system_profile_auth
    boodlebox_access["effective_auth_status"] = (
        "existing_system_browser_profile_expected"
        if system_profile_auth
        else "manual_login_required"
        if boodlebox_access.get("login_required")
        else "unknown"
    )

    recorder = EvidenceRecorder(base)
    evidence_summary = recorder.export_training_data()
    selection = ModelRouter(base).select_for_task(
        task,
        provider_health,
        boodlebox_access,
        evidence_summary,
    )

    audit = {
        "status": "ready_for_system_browser_handoff" if system_profile_auth and boodlebox_access.get("reachable") else "ready_for_manual_browser_handoff" if boodlebox_access.get("reachable") else "blocked",
        "task": task,
        "active_provider": reg.get_active_provider_name(),
        "provider_health": provider_health,
        "browser_provider_status": browser_provider_status,
        "boodlebox_access": boodlebox_access,
        "model_selection": selection,
        "evidence_summary": evidence_summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    state_dir = os.path.join(base, "state")
    os.makedirs(state_dir, exist_ok=True)
    json_path = os.path.join(state_dir, "model_access_status.json")
    md_path = os.path.join(state_dir, "model_access_status.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)

    recommended = selection.get("recommended_model") or {}
    direct = selection.get("direct_api_ready_model") or {}
    lines = [
        "# Model Access Status",
        "",
        f"Updated: {audit['created_at']}",
        f"Task: {task}",
        f"Active provider: `{audit['active_provider']}`",
        "",
        "## BoodleBox",
        f"- URL: {boodlebox_access['url']}",
        f"- Reachable: {boodlebox_access['reachable']}",
        f"- Public login gate: {boodlebox_access.get('public_login_gate')}",
        f"- System profile auth expected: {boodlebox_access.get('system_profile_auth_expected')}",
        f"- Effective auth status: {boodlebox_access.get('effective_auth_status')}",
        f"- Pending responses: {browser_provider_status.get('pending_responses')}",
        "",
        "## Provider Reality",
    ]
    for name, health in provider_health.items():
        lines.append(f"- `{name}`: {health.get('status')}")
    lines.extend([
        "",
        "## Recommended Model For Task",
        f"- Model: `{recommended.get('display_name', 'None')}`",
        f"- Access status: `{recommended.get('access_status', 'not_ready')}`",
        f"- Direct API ready model: `{direct.get('display_name', 'None')}`",
        "",
        "## Training Evidence",
        f"- Model I/O rows: {evidence_summary.get('model_io_rows')}",
        f"- Training rows: {evidence_summary.get('training_rows')}",
        f"- Eval rows: {evidence_summary.get('eval_rows')}",
        f"- Selection ready: {selection.get('training_selection_ready')}",
        f"- Reason: {selection.get('training_selection_reason')}",
        "",
        "## Next Command",
        "```bash",
        "python runtime.py --generate-browser-model-prompt",
        "python runtime.py --open-browser-provider",
        "python runtime.py --ingest-browser-model-response",
        "python runtime.py --export-training-data",
        "python runtime.py --run-next",
        "```",
    ])
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(json.dumps(audit, indent=2))
    print(f"Status written to: {md_path}")
    return audit

def do_validate_candidate_plans():
    from model_loop.plan_validator import PlanValidator
    import glob
    pv = PlanValidator(get_base_dir())
    cand_dir = os.path.join(get_base_dir(), "inbox", "candidate_plans")
    val_dir = os.path.join(get_base_dir(), "inbox", "validated_plans")
    rej_dir = os.path.join(get_base_dir(), "inbox", "rejected_plans")
    os.makedirs(val_dir, exist_ok=True)
    os.makedirs(rej_dir, exist_ok=True)
    
    for path in glob.glob(os.path.join(cand_dir, "*.json")):
        is_valid, msg = pv.ingest_candidate(path, val_dir, rej_dir)
        print(f"{os.path.basename(path)}: {'Valid' if is_valid else 'Invalid'} - {msg}")

def do_model_cycle_once():
    print("Starting Model Cycle...")
    res = do_generate_with_provider()
    if res and res.get('status') == 'success':
        do_validate_candidate_plans()
        return do_run_next()
    return False

# ===================== Browser LLM Provider Commands =====================

def do_browser_provider_status():
    """Show the status of the browser LLM provider."""
    try:
        from model_providers.browser_llm_provider import BrowserLLMProvider
        config = {}
        provider = BrowserLLMProvider(config, get_base_dir())
        status = provider.get_provider_status()
        print(json.dumps(status, indent=2))
    except Exception as e:
        print(f"Error: {e}")

def do_generate_browser_model_prompt():
    """Generate a model prompt for browser-based LLM handoff."""
    try:
        from model_loop.prompt_builder import PromptBuilder
        from model_providers.browser_llm_provider import BrowserLLMProvider

        pb = PromptBuilder(get_base_dir())
        prompt, report = pb.build_prompt()

        # Read the generated prompt
        with open(prompt, "r", encoding="utf-8") as f:
            prompt_text = f.read()

        # Use browser LLM provider to save and display instructions
        provider = BrowserLLMProvider({}, get_base_dir())
        result = provider.generate_prompt_file(prompt_text)

        print(json.dumps(result, indent=2))
        print(f"\n{'='*60}")
        print("NEXT STEPS:")
        print(f"{'='*60}")
        print(result.get("instructions", ""))

    except Exception as e:
        print(f"Error: {e}")

def do_open_browser_provider():
    """Open the browser-based LLM provider page."""
    try:
        from model_providers.browser_llm_provider import BrowserLLMProvider
        provider = BrowserLLMProvider({}, get_base_dir())
        result = provider.open_provider_page()
        print(json.dumps(result, indent=2))
        print(f"\nInstructions: {result.get('instructions', '')}")
    except Exception as e:
        print(f"Error: {e}")

def do_ingest_browser_model_response():
    """Ingest response from browser-based LLM provider."""
    try:
        from model_providers.browser_llm_provider import BrowserLLMProvider
        provider = BrowserLLMProvider({}, get_base_dir())

        result = provider.ingest_response_file()
        print(json.dumps(result, indent=2))

        if result.get("status") == "success":
            # Validate the candidate plan
            plan_path = result.get("candidate_plan_path")
            if plan_path:
                validation = provider.validate_candidate_plan(plan_path)
                print(f"\nCandidate Plan Validation: {json.dumps(validation, indent=2)}")

                # Move to validated_plans if valid
                if validation.get("status") == "valid":
                    import shutil
                    validated_path = os.path.join(get_base_dir(), "inbox", "validated_plans", 
                                                  os.path.basename(plan_path))
                    shutil.copy(plan_path, validated_path)
                    print(f"\nPlan moved to: {validated_path}")
    except Exception as e:
        print(f"Error: {e}")

def do_browser_model_cycle_once():
    """Run one safe cycle of the browser model loop."""
    try:
        print("Starting Browser Model Cycle...")
        print("\n1. Generating prompt...")
        do_generate_browser_model_prompt()

        print("\n2. Opening browser provider...")
        do_open_browser_provider()

        print("\n3. Waiting for user to paste response...")
        print("   When ready, save response to inbox/provider_responses/ and run:")
        print("   python runtime.py --ingest-browser-model-response")

    except Exception as e:
        print(f"Error: {e}")

def do_supervised_browser_loop(max_cycles=1):
    """Run supervised autonomous browser model loop."""
    import time
    import glob

    print(f"Starting Supervised Browser Loop (max_cycles={max_cycles})")
    print("Safety: All Defender checks enabled, approval required for risky actions")

    cycle = 0
    while cycle < max_cycles:
        cycle += 1
        print(f"\n{'='*60}")
        print(f"CYCLE {cycle}/{max_cycles}")
        print(f"{'='*60}")

        # Check for stop file
        stop_file = os.path.join(get_base_dir(), "state", "loop_stop.txt")
        if os.path.exists(stop_file):
            print("Stop file detected. Exiting loop.")
            os.remove(stop_file)
            break

        try:
            # Generate prompt
            print("\n[1/5] Generating browser model prompt...")
            from model_loop.prompt_builder import PromptBuilder
            pb = PromptBuilder(get_base_dir())
            prompt_path, _ = pb.build_prompt()

            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read()

            # Open provider or show instructions
            print("\n[2/5] Opening browser LLM provider...")
            from model_providers.browser_llm_provider import BrowserLLMProvider
            provider = BrowserLLMProvider({}, get_base_dir())
            provider.open_provider_page()

            # Wait for response
            print("\n[3/5] Waiting for user to submit response...")
            print("      Save response to: inbox/provider_responses/response.txt")
            print("      Press Ctrl+C to cancel or create loop_stop.txt to exit")

            # Ingest response when available
            response_found = False
            for attempt in range(60):  # Wait up to 60 seconds
                response_files = glob.glob(os.path.join(get_base_dir(), "inbox", "provider_responses", "*.txt"))
                response_files = [f for f in response_files if not f.endswith(".processed")]

                if response_files:
                    response_found = True
                    break

                if attempt % 10 == 0:
                    print(f"      Waiting... ({attempt}s)")
                time.sleep(1)

            if not response_found:
                print("      No response received. Continuing to next cycle...")
                continue

            # Ingest and validate
            print("\n[4/5] Ingesting and validating model response...")
            ingest_result = provider.ingest_response_file()

            if ingest_result.get("status") != "success":
                print(f"      Ingestion failed: {ingest_result.get('error', 'unknown')}")
                continue

            # Validate candidate plan
            plan_path = ingest_result.get("candidate_plan_path")
            if plan_path:
                validation = provider.validate_candidate_plan(plan_path)
                if validation.get("status") != "valid":
                    print(f"      Validation failed: {validation.get('error', 'unknown')}")
                    continue

                # Move to validated plans
                import shutil
                validated_path = os.path.join(get_base_dir(), "inbox", "validated_plans", 
                                             os.path.basename(plan_path))
                shutil.copy(plan_path, validated_path)

            # Run the plan
            print("\n[5/5] Executing validated plan with Defender checks...")
            do_run_next()

        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            break
        except Exception as e:
            print(f"Error in cycle: {e}")
            continue

        if cycle < max_cycles:
            print("\nWaiting before next cycle...")
            time.sleep(2)

    print(f"\n{'='*60}")
    print("Supervised Browser Loop completed")
    print(f"{'='*60}")

# ===================== End Browser LLM Commands =====================

def do_run_loop(plan_path: str, max_turns: int = 10):
    from model_loop.agent_loop import run_plan_loop
    result = run_plan_loop(plan_path, get_base_dir(), max_turns=max_turns)
    print(json.dumps(result, indent=2))
    return result

def do_run_autonomous(goal: str, max_turns: int = 10):
    from model_loop.agent_loop import run_autonomous
    result = run_autonomous(goal, get_base_dir(), max_turns=max_turns)
    print(json.dumps(result, indent=2))
    return result

def do_stop_all():
    from utils.process_manager import stop_all, get_process_status
    result = stop_all(get_base_dir())
    print(json.dumps({"stopped": result, "status": get_process_status(get_base_dir())}, indent=2))
    return result

def do_audit_install():
    import subprocess
    script = os.path.join(get_base_dir(), "scripts", "audit_install.py")
    subprocess.run([sys.executable, script], cwd=get_base_dir())

def do_watch(max_loops=10, use_agent=False):
    import time
    import glob
    import os
    from utils.process_manager import register_watcher_pid, clear_pid_file, WATCHER_PID_FILE

    base_dir = get_base_dir()
    register_watcher_pid(os.getpid(), base_dir)
    print(f"Starting Watcher Daemon (max_loops={max_loops}, pid={os.getpid()})")
    
    if use_agent:
        import threading
        from commands.agent_daemon import AgentDaemon
        base_dir = get_base_dir()
        agent = AgentDaemon(base_dir)
        agent_thread = threading.Thread(target=agent.run, args=(max_loops,), daemon=True)
        agent_thread.start()
        print("Spawned AgentDaemon in background thread.")
        
    val_dir = os.path.join(get_base_dir(), "inbox", "validated_plans")
    state_dir = os.path.join(get_base_dir(), "state")
    os.makedirs(state_dir, exist_ok=True)
    status_file = os.path.join(state_dir, "daemon_status.json")
    
    def set_status(state, message=""):
        with open(status_file, "w") as f:
            json.dump({"status": state, "message": message, "timestamp": time.time()}, f)
            
    # Allow the daemon to be stopped by setting status to stopped in the file
    def check_stopped():
        try:
            if os.path.exists(status_file):
                with open(status_file, "r") as f:
                    data = json.load(f)
                    if data.get("status") == "stopped":
                        return True
        except:
            pass
        return False

    loops = 0
    while loops < max_loops:
        if check_stopped():
            print("Daemon stopped by user.")
            break
            
        print(f"--- Watcher Loop {loops+1}/{max_loops} ---")
        set_status("running", f"Loop {loops+1}")
        
        # 1. Any validated plans to run?
        plans = glob.glob(os.path.join(val_dir, "*.json"))
        if plans:
            set_status("running", "Executing validated plan")
            res = do_run_next()
            if res == "pending_approval":
                set_status("paused", "Waiting for approval")
                print("Sleeping for 10 seconds waiting for approval...")
                time.sleep(10)
                continue
            elif res == True:
                # Execution finished, generate next prompt
                set_status("running", "Generating next prompt after execution")
                do_next_prompt()
            else:
                print("Failed to run plan.")
                time.sleep(5)
        else:
            # 2. No validated plans. Try to run model cycle.
            set_status("running", "Running model cycle")
            res = do_model_cycle_once()
            if res == "pending_approval":
                continue
            
            # If no success, maybe we are rate limited or wait for user
            print("Sleeping for 5 seconds...")
            time.sleep(5)
            
        loops += 1
        
    set_status("stopped", "Max loops reached or stopped")
    print("Watcher Daemon finished.")
    clear_pid_file(WATCHER_PID_FILE, base_dir)

def main():
    parser = argparse.ArgumentParser(description="Tibin Full-Stack AI Coding Agent Runtime")
    parser.add_argument("--once", action="store_true", help="Run one cycle of the coding agent loop")
    parser.add_argument("--watch", action="store_true", help="Run continuously")
    parser.add_argument("--agent", action="store_true", help="Run the Agent LLM loop in a background thread")
    parser.add_argument("--max-loops", type=int, default=10, help="Max iterations for watch mode")
    parser.add_argument("--status", action="store_true", help="Show runtime status")
    parser.add_argument("--validate", type=str, help="Validate a plan JSON file")
    parser.add_argument("--approve", type=str, help="Approve a plan JSON file")
    parser.add_argument("--run-approved", action="store_true", help="Run approved plans")
    parser.add_argument("--run-plan", type=str, help="Run a specific plan JSON file")
    
    # Phase 8 Commands
    parser.add_argument("--doctor", action="store_true", help="Run doctor health checks")
    parser.add_argument("--audit", action="store_true", help="Run full safety audit")
    parser.add_argument("--next-prompt", action="store_true", help="Generate next model prompt")
    parser.add_argument("--model-loop-once", action="store_true", help="Run model loop once")
    parser.add_argument("--ingest-plan", type=str, help="Ingest a specific candidate plan")
    parser.add_argument("--run-next", action="store_true", help="Run the next validated plan")

    # Phase 9 Commands
    parser.add_argument("--provider-status", action="store_true", help="Check provider status")
    parser.add_argument("--generate-with-provider", action="store_true", help="Generate with active provider")
    parser.add_argument("--ingest-provider-response", action="store_true", help="Ingest manually pasted response")
    parser.add_argument("--validate-candidate-plans", action="store_true", help="Validate all candidates")
    parser.add_argument("--run-next-validated", action="store_true", help="Alias for run-next")
    parser.add_argument("--model-cycle-once", action="store_true", help="Run full cycle")
    parser.add_argument("--export-training-data", action="store_true", help="Export model I/O JSONL for eval and future tuning")
    parser.add_argument("--model-access-audit", action="store_true", help="Audit provider reachability, model routing, and training evidence")
    parser.add_argument("--task", type=str, default="Building applications", help="Task description for model routing")

    # Browser LLM Provider Commands
    parser.add_argument("--browser-provider-status", action="store_true", help="Check browser LLM provider status")
    parser.add_argument("--generate-browser-model-prompt", action="store_true", help="Generate prompt for browser LLM")
    parser.add_argument("--open-browser-provider", action="store_true", help="Open browser LLM provider page")
    parser.add_argument("--ingest-browser-model-response", action="store_true", help="Ingest browser LLM response")
    parser.add_argument("--browser-model-cycle-once", action="store_true", help="Run one browser model cycle (manual)")
    parser.add_argument("--supervised-browser-loop", action="store_true", help="Run supervised browser model loop")
    parser.add_argument("--max-browser-cycles", type=int, default=1, help="Max cycles for supervised loop")

    # Autonomous / plan loop
    parser.add_argument("--run-loop", type=str, help="Run a plan JSON through the agent loop (no API key needed)")
    parser.add_argument("--run-autonomous", type=str, help="Run autonomous mode with OpenRouter (requires OPENROUTER_API_KEY)")
    parser.add_argument("--max-turns", type=int, default=10, help="Max turns for autonomous/loop modes")
    parser.add_argument("--stop-all", action="store_true", help="Stop dashboard, watcher, and port 5000 listeners")
    parser.add_argument("--audit-install", action="store_true", help="Audit install root and process registry")

    args = parser.parse_args()

    if args.once:
        run_once()
    elif args.status:
        status()
    elif args.validate:
        validate_plan(args.validate)
    elif args.approve:
        approve_plan(args.approve)
    elif args.run_approved:
        print("Running approved plans...")
        run_once()
    elif args.run_plan:
        run_plan(args.run_plan)
    elif args.doctor:
        do_doctor()
    elif args.audit:
        do_audit()
    elif args.next_prompt:
        do_next_prompt()
    elif args.model_loop_once:
        do_model_loop_once()
    elif args.ingest_plan:
        do_ingest_plan(args.ingest_plan)
    elif args.run_next or args.run_next_validated:
        do_run_next()
    elif args.provider_status:
        do_provider_status()
    elif args.generate_with_provider:
        do_generate_with_provider()
    elif args.ingest_provider_response:
        do_ingest_provider_response()
    elif args.export_training_data:
        do_export_training_data()
    elif args.model_access_audit:
        do_model_access_audit(args.task)
    elif args.validate_candidate_plans:
        do_validate_candidate_plans()
    elif args.model_cycle_once:
        do_model_cycle_once()
    elif args.browser_provider_status:
        do_browser_provider_status()
    elif args.generate_browser_model_prompt:
        do_generate_browser_model_prompt()
    elif args.open_browser_provider:
        do_open_browser_provider()
    elif args.ingest_browser_model_response:
        do_ingest_browser_model_response()
    elif args.browser_model_cycle_once:
        do_browser_model_cycle_once()
    elif args.supervised_browser_loop:
        do_supervised_browser_loop(args.max_browser_cycles)
    elif args.run_loop:
        do_run_loop(args.run_loop, max_turns=args.max_turns)
    elif args.run_autonomous:
        do_run_autonomous(args.run_autonomous, max_turns=args.max_turns)
    elif args.stop_all:
        do_stop_all()
    elif args.audit_install:
        do_audit_install()
    elif args.watch:
        do_watch(args.max_loops, use_agent=args.agent)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
