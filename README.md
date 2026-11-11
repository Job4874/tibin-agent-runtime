# Tibin Full-Stack Agent Runtime

A **local, self-hosted runtime** for LLM-powered coding agents. The model thinks; this runtime validates a plan, enforces safety, and executes only approved actions on your machine. It is plain code: there is no hosted service and no bundled API keys. Anyone who runs it brings their own keys and providers (OpenAI, OpenRouter, or any OpenAI-compatible endpoint).

## Architecture

```
  LLM provider (your keys)          Local runtime
  -------------------------         ---------------------------------
  OpenAI / Codex API  ─┐            ManagerAgent  ─► workers
  OpenRouter          ─┼─ plan ──►  DefenderAgent ─► (allow / deny / ask)
  Browser handoff     ─┘            ComplexityEngine, memory, reports
```

1. A model (API or manual paste) produces a **candidate plan** (JSON).
2. The runtime **validates** the plan against schemas in `schemas/`.
3. **ManagerAgent** (`agents/manager_agent.py`) accepts a valid plan and dispatches work.
4. **DefenderAgent** (`agents/defender_agent.py`) checks every action against `permissions/` before it runs. Destructive or unapproved actions are blocked or queued for a signed approval.
5. **Workers** execute only approved actions:
   - `ShellWorker` — allowlisted shell commands
   - `FileWorker` — sandboxed file edits
   - `GitWorker` — git workflows (no unapproved pushes)
   - `BrowserWorker` — browser testing
   - `CoderWorker` — code generation helpers
   - `VerifierWorker` — result checks
   - `MemoryWorker` — lessons and context
   - `ReportWorker` — run reports and observations
   - `ResearchWorker` — research tasks
6. Evidence, run IDs, and reports stay on disk under `runs/`, `reports/`, and (optionally) `datasets/` on your machine. Those directories are gitignored so live traces are not committed.

Optional **browser handoff** (see `README_BROWSER_LLM.md`) lets you paste prompts into a web LLM workspace and feed the plan JSON back in, without scraping logins.

## Quick start (bring your own keys)

Requires Python 3.12+.

```bash
git clone <this-repo>
cd tibin-fullstack-agent-runtime

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
# optional, only if you use BrowserWorker:
# python3 -m playwright install chromium

cp config/env.example .env
# Edit .env and set at least one provider key (see below).

mkdir -p logs screenshots

# Health check (works without keys)
python3 tibin.py cli --doctor

# Tests (no keys or private data required)
python3 -m pytest -q

# Replay a safe example plan offline
python3 tibin.py cli --run-loop examples/safe_code_plan.json --max-turns 10

# Local dashboard (http://127.0.0.1:5000/)
python3 tibin.py server
```

### OpenRouter

Default autonomous configuration in `config/model_providers.json` and `config/brain.json` uses OpenRouter's OpenAI-compatible API (`https://openrouter.ai/api/v1`). Set in `.env`:

```bash
OPENROUTER_API_KEY=sk-or-...
```

Then:

```bash
python3 tibin.py cli --run-autonomous "List all .py files in the project root" --max-turns 10
```

Leave the key empty to disable autonomous API runs. Plan replay, tests, and the dashboard still work.

### OpenAI and Codex

The same `openai_compatible` provider talks to any Chat Completions endpoint. To use the official OpenAI API (including models you access with a Codex / OpenAI platform key):

1. Set `OPENAI_API_KEY` in `.env`.
2. In `config/model_providers.json`, point the `openai_compatible` provider at OpenAI, for example:

```json
"openai_compatible": {
  "enabled": true,
  "api_key_env": "OPENAI_API_KEY",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4.1",
  "timeout_seconds": 90
}
```

This runtime does not wrap the Codex IDE/CLI product itself; it uses the **OpenAI-compatible HTTP API**. You can also point `base_url` at Azure OpenAI or a local server. Provider configs must reference keys via `api_key_env` — inline `api_key` values are rejected at load.

## Safety

- Defender enforces allow/deny lists in `permissions/`.
- Some commands are never allowed; others need an explicit signed approval.
- Mutating dashboard `/api/*` routes require `X-Tibin-Token` or `Authorization: Bearer` (`TIBIN_API_TOKEN`).
- The dashboard binds to localhost by default (`TIBIN_ALLOWED_HOSTS` can add extras).
- Do not enable `TIBIN_DEBUG=1` in any exposed process.

See [SECURITY.md](SECURITY.md) to report a vulnerability.

## Project layout

| Path | Role |
|------|------|
| `tibin.py`, `runtime.py` | CLI and runtime entry points |
| `agents/` | Manager, Defender, complexity / recovery |
| `workers/` | Tool workers listed above |
| `model_providers/` | OpenAI-compatible, OpenRouter, file, manual, browser-handoff |
| `model_loop/` | Prompt build, plan validation, evidence |
| `permissions/`, `schemas/` | Safety policy and JSON schemas |
| `app/` | Local Flask dashboard |
| `examples/` | Offline plans for replay and tests |
| `config/env.example` | BYOK template (copy to `.env`) |

## License

[MIT](LICENSE) © 2026 Abdulwahab Tibin. Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
