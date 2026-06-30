import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from reefiki_core import harvest_commit


def test_harvest_commit_payload_blocks_outside_target_wiki(monkeypatch, tmp_path):
    monkeypatch.setattr(harvest_commit, "git_staged_paths", lambda repo, env=None: [])
    monkeypatch.setattr(harvest_commit, "git_status_paths", lambda repo: [])

    code, payload = harvest_commit.harvest_commit_payload(
        tmp_path,
        "reefiki",
        ["projects/reefiki/notes.md"],
        "Harvest notes",
        validate=False,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "path_outside_target_wiki"
    assert payload["blocking_paths"] == ["projects/reefiki/notes.md"]


def test_harvest_commit_payload_blocks_already_staged_target_path(monkeypatch, tmp_path):
    target = "projects/reefiki/wiki/synthesis/harvest.md"
    monkeypatch.setattr(harvest_commit, "git_staged_paths", lambda repo, env=None: [target])
    monkeypatch.setattr(harvest_commit, "git_status_paths", lambda repo: [target, "README.md"])

    code, payload = harvest_commit.harvest_commit_payload(
        tmp_path,
        "reefiki",
        [target],
        "Harvest synthesis",
        validate=False,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "target_paths_already_staged"
    assert payload["blocking_paths"] == [target]
    assert payload["excluded_dirty_paths"] == ["README.md"]


def test_harvest_commit_payload_requires_message_and_path(tmp_path):
    with pytest.raises(SystemExit, match="commit message is required"):
        harvest_commit.harvest_commit_payload(tmp_path, "reefiki", ["projects/reefiki/wiki/a.md"], "", False)
    with pytest.raises(SystemExit, match="at least one --path is required"):
        harvest_commit.harvest_commit_payload(tmp_path, "reefiki", [], "Harvest", False)


def test_harvest_commit_payload_blocks_when_project_lock_is_held(tmp_path):
    lock_dir = tmp_path / ".reefiki" / "locks"
    lock_dir.mkdir(parents=True)
    (lock_dir / "reefiki.lock").write_text("busy\n", encoding="utf-8")

    code, payload = harvest_commit.harvest_commit_payload(
        tmp_path,
        "reefiki",
        ["projects/reefiki/wiki/skills/locked.md"],
        "Harvest locked",
        validate=False,
        lock_timeout_seconds=0,
    )

    assert code == 1
    assert payload["outcome"] == "block"
    assert payload["reason"] == "project_lock_timeout"
