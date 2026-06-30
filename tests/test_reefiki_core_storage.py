import tempfile
from pathlib import Path

import pytest

from scripts.reefiki_core.storage import SQLITE_BUSY_TIMEOUT_MS, index_lock, sqlite_connection


def test_sqlite_connection_sets_busy_timeout_commits_and_rolls_back() -> None:
    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "index.sqlite"

        with sqlite_connection(database, row_factory=True) as conn:
            timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            conn.execute("CREATE TABLE items (name TEXT)")
            conn.execute("INSERT INTO items VALUES ('ok')")
            row = conn.execute("SELECT name FROM items").fetchone()

        assert timeout_ms == SQLITE_BUSY_TIMEOUT_MS
        assert row["name"] == "ok"

        with pytest.raises(RuntimeError):
            with sqlite_connection(database) as conn:
                conn.execute("INSERT INTO items VALUES ('rolled-back')")
                raise RuntimeError("force rollback")

        with sqlite_connection(database) as conn:
            rows = conn.execute("SELECT name FROM items ORDER BY name").fetchall()

        assert [row[0] for row in rows] == ["ok"]


def test_index_lock_creates_project_local_lock_file() -> None:
    with tempfile.TemporaryDirectory() as temp:
        project = Path(temp) / "project"
        project.mkdir()

        with index_lock(project) as lock_path:
            assert lock_path == project / ".reefiki" / "index.lock"

        assert (project / ".reefiki" / "index.lock").exists()
        assert (project / ".reefiki" / "index.lock").read_bytes() == b"0"
