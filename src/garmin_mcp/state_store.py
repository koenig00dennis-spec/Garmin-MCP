"""Optional on-disk state so a restart doesn't log everything out.

Off by default. Set ``GARMIN_MCP_STATE_DIR`` to a directory on a
persistent volume (on Railway: attach a volume, e.g. mounted at /data, and
set ``GARMIN_MCP_STATE_DIR=/data``) and the remote server keeps two small
files there:

- ``oauth_state.json`` — registered clients plus the access/refresh tokens
  this server issued, so claude.ai stays connected across a redeploy
  instead of asking you to reconnect the connector.
- ``garmin_tokens.json`` — the unofficial-API session tokens (never your
  Garmin password). The garminconnect library rewrites this file itself
  whenever it refreshes the tokens, so a saved session doesn't go stale
  the way a one-off copy in an environment variable can.

Both files are written atomically with owner-only permissions (0600, in
a 0700 directory). Whoever can read them can use your connector or read
your Garmin data, so only point this at a volume that belongs to this
service.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

STATE_DIR_ENV_VAR = "GARMIN_MCP_STATE_DIR"


def state_dir() -> Path | None:
    """Return the configured state directory, or None when persistence is off."""
    value = os.environ.get(STATE_DIR_ENV_VAR, "").strip()
    return Path(value) if value else None


def state_file(name: str) -> Path | None:
    directory = state_dir()
    return directory / name if directory else None


def write_json(path: Path, data: Any) -> None:
    """Atomically write JSON with 0600 permissions inside a 0700 directory."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        path.parent.chmod(0o700)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        tmp.replace(path)
    except Exception:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def read_json(path: Path) -> Any | None:
    """Return parsed JSON, or None if the file is missing or unreadable."""
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None
