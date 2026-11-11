# AGENTS.md

Guidance for agents working in this workspace.

## Cursor Cloud specific instructions

### Python and PATH

Linux VMs ship with `python3` only. Tibin shell workers and example plans invoke `python`. Before running plans or workers:

```bash
mkdir -p "$HOME/.local/bin"
ln -sf /usr/bin/python3 "$HOME/.local/bin/python"
export PATH="$HOME/.local/bin:$PATH"
```

`pip install --user` installs scripts under `~/.local/bin`; keep that on `PATH`.

### Install

```bash
cd /workspace
pip install --user -r requirements.txt pytest
python3 -m playwright install chromium   # optional; doctor warns without browsers
```

Create `logs/` and `screenshots/` if doctor reports them missing. Copy `config/env.example` → `.env`; `OPENROUTER_API_KEY` is only needed for autonomous mode.

### Common commands

| Action | Command |
|--------|---------|
| Doctor | `python3 tibin.py cli --doctor` |
| Tests | `python3 -m pytest -q` |
| Plan replay (no API) | `python3 tibin.py cli --run-loop examples/safe_code_plan.json --max-turns 10` |
| Dashboard | `python3 tibin.py server` → http://127.0.0.1:5000/ |
| Lint (syntax) | `python3 -m compileall -q .` |
| Health API | `curl http://127.0.0.1:5000/health` |
| Stop all | `python3 tibin.py cli --stop-all` |

### Expected offline behavior

These states are normal in a fresh dev environment and do not indicate bugs:

- `[FAIL] App binds to 127.0.0.1` — start the server first before running doctor if that check matters.
- `[FAIL] brain:openrouter configured` — expected when `OPENROUTER_API_KEY` is absent. Autonomous tasks require the key; plan replay and the dashboard work without it.
- Brain shows "NOT SET" in sidebar — normal without the API key; the dashboard remains fully functional.
- Process manager shows "STOPPED" — normal when the server is not running.

### API authentication

All mutating (non-GET) `/api/*` routes require a token via `X-Tibin-Token` or `Authorization: Bearer`. The dashboard UI injects it automatically. For curl/scripts, set `TIBIN_API_TOKEN` in the environment before starting the server and send the same value in the header. Requests without the token fail closed with 401.

Tested by `tests/test_api_auth.py` and `tests/test_finish_integration.py::test_http_smoke`.

### Provider config

Provider settings live in `config/model_providers.json`. Inline secrets (e.g. an `api_key` value) are rejected at load; use `*_env` references (e.g. `api_key_env`) and put keys in `.env` / environment variables only. If the config is invalid, `/providers` renders an error state instead of a 500.

