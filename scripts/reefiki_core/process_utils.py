from __future__ import annotations

import os
import subprocess
from pathlib import Path


SUBPROCESS_TIMEOUT_SECONDS = int(os.environ.get("REEFIKI_SUBPROCESS_TIMEOUT", "120"))


def git_repo_root(path: Path) -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path.resolve(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"Git repo not found: {path}"
        raise SystemExit(detail)
    return Path(completed.stdout.strip()).resolve()
