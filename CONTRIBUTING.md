# Contributing

Thanks for helping improve this local agent runtime. This project is meant to stay a **plain, self-hosted codebase**: no hosted control plane, and no bundled API keys.

## Ground rules

- Bring-your-own-keys only. Never commit `.env`, tokens, cookies, private keys, or live session traces (`state/`, `runs/`, `observations/`, `inbox/`, `outbox/`, `datasets/model_io.jsonl`).
- Do not add trading-strategy, brokerage, or market-alpha code.
- Keep changes dependency-light. Prefer the existing stack (Python 3.12, Flask, pytest).
- Tests must pass without private data or API keys:

  ```bash
  cp config/env.example .env
  python3 -m pytest -q --tb=short
  ```

## Pull requests

1. Fork or branch from the default branch.
2. Add or update tests for behavior you change, especially Defender / approval / provider-config paths.
3. Run the test command above and `python3 -m compileall -q .`.
4. Describe the change and any config a runner must set (for example a new `*_API_KEY` env var).
5. If your change touches permissions or shell/file/git workers, say how safety is preserved.

## Issues

Please include OS, Python version, and the output of `python3 tibin.py cli --doctor` when reporting a bug. Redact any keys or personal paths before pasting logs.

## Security

See [SECURITY.md](SECURITY.md). Do not file public issues that include secrets.
