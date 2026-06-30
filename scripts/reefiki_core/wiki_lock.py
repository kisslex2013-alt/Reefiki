from __future__ import annotations

import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class WikiLockTimeout(RuntimeError):
    def __init__(self, lock_path: Path) -> None:
        super().__init__(f"timed out waiting for lock: {lock_path}")
        self.lock_path = lock_path


def _lock_name(target_project: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", target_project.strip()).strip("-")
    return safe or "project"


def _is_busy_lock_error(exc: OSError, lock_path: Path) -> bool:
    if isinstance(exc, FileExistsError):
        return True
    # On Windows, a concurrent O_CREAT | O_EXCL open can surface as
    # PermissionError while another process still owns the path.
    return isinstance(exc, PermissionError) and lock_path.exists()


@contextmanager
def project_lock(
    repo: Path,
    target_project: str,
    operation: str,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.1,
) -> Iterator[Path]:
    lock_dir = repo / ".reefiki" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{_lock_name(target_project)}.lock"
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    acquired = False
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"operation: {operation}\n")
                handle.write(f"pid: {os.getpid()}\n")
                handle.write(f"created_at: {time.time():.6f}\n")
            acquired = True
            break
        except OSError as exc:
            if not _is_busy_lock_error(exc, lock_path):
                raise
            if timeout_seconds <= 0 or time.monotonic() >= deadline:
                raise WikiLockTimeout(lock_path) from exc
            time.sleep(max(0.01, poll_seconds))
    try:
        yield lock_path
    finally:
        if acquired:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
