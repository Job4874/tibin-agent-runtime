"""Load environment variables from .env without external dependencies."""

import os
from pathlib import Path


def load_dotenv(base_dir: str = None) -> bool:
    """Load KEY=VALUE pairs from .env in base_dir. Returns True if file was found."""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = Path(base_dir) / ".env"
    if not env_path.exists():
        return False
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return False
    return True
