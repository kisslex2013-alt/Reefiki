from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


SQLITE_BUSY_TIMEOUT_MS = int(os.environ.get("REEFIKI_SQLITE_BUSY_TIMEOUT_MS", "5000"))


@contextmanager
def sqlite_connection(database: Path, row_factory: bool = False):
    conn = sqlite3.connect(database, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    if row_factory:
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def unlock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def index_lock(project: Path):
    state = project / ".reefiki"
    state.mkdir(exist_ok=True)
    lock_path = state / "index.lock"
    with lock_path.open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.truncate()
        handle.flush()
        lock_file(handle)
        try:
            yield lock_path
        finally:
            unlock_file(handle)
