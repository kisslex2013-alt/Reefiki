from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def memoir_store_path(
    environ: dict[str, str] | None = None,
    platform_name: str | None = None,
    home: Path | None = None,
) -> Path:
    env = environ if environ is not None else os.environ
    if env.get("REEFIKI_MEMOIR_STORE"):
        return Path(env["REEFIKI_MEMOIR_STORE"])
    if env.get("MEMOIR_STORE"):
        return Path(env["MEMOIR_STORE"])
    platform = platform_name or sys.platform
    home_dir = home or Path.home()
    codex_store = home_dir / ".codex" / "memoir-stores" / "reefiki"
    if codex_store.exists():
        return codex_store
    if platform == "win32":
        base = Path(env.get("LOCALAPPDATA") or home_dir / "AppData" / "Local")
    else:
        base = Path(env.get("XDG_DATA_HOME") or home_dir / ".local" / "share")
    return base / "memoir" / "reefiki"


def _memoir_base_command(store: Path) -> list[str]:
    return [
        "uvx",
        "--from",
        "memoir-ai",
        "memoir",
        "--json",
        "--store",
        str(store),
    ]


def _parse_memoir_json_output(output: str) -> dict[str, object]:
    text = output.strip()
    if not text:
        return {}

    candidates = [text]
    for index, char in enumerate(text):
        if char in "{[" and (index == 0 or text[index - 1] in "\r\n"):
            candidates.append(text[index:].strip())

    for candidate in reversed(candidates):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
        return {"payload": payload}

    raise SystemExit("Invalid memoir JSON output: no JSON payload found")


def run_memoir(store: Path, args: list[str], timeout_seconds: int) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        _memoir_base_command(store) + args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "memoir command failed"
        raise SystemExit(detail)
    return _parse_memoir_json_output(completed.stdout)
