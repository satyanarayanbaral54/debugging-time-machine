from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: str | Path | None = None) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a .env file without overriding env vars."""
    env_path = Path(path or os.getenv("DTM_ENV_FILE", ".env"))
    if not env_path.exists() or not env_path.is_file():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _clean_env_value(value.strip())
        if not key or key in os.environ:
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded


def _clean_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
