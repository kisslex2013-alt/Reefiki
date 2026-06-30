from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts.reefiki_core import public_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_public_snapshot_wrappers_delegate_with_expected_remote(monkeypatch) -> None:
    calls: list[tuple[Path, str | None, list[str]]] = []

    def fake_run(repo: Path, public_remote: str | None, private_projects: list[str]):
        calls.append((repo, public_remote, private_projects))
        return {"outcome": "pass"}

    monkeypatch.setattr(public_snapshot, "run_public_snapshot", fake_run)

    repo = Path("repo")
    assert public_snapshot.inspect_public_snapshot(repo, ["reefiki"]) == {"outcome": "pass"}
    assert public_snapshot.push_public_snapshot(repo, "public", ["reefiki"]) == {"outcome": "pass"}
    assert calls == [(repo, None, ["reefiki"]), (repo, "public", ["reefiki"])]


def test_cleanup_local_public_snapshot_branches_keeps_current(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_run(_repo: Path, args: list[str], env=None):  # noqa: ANN001
        if args[:2] == ["for-each-ref", "--format=%(refname:short)"]:
            return CompletedProcess(args, 0, "public-snapshot-old\npublic-snapshot-current\n", "")
        calls.append(args)
        return CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(public_snapshot, "run_git", fake_run)

    assert public_snapshot.cleanup_local_public_snapshot_branches(tmp_path, "public-snapshot-current") == [
        "public-snapshot-old"
    ]
    assert calls == [["branch", "-D", "public-snapshot-old"]]


def test_cleanup_local_public_snapshot_branches_is_best_effort(monkeypatch, tmp_path) -> None:
    def fake_run(_repo: Path, args: list[str], env=None):  # noqa: ANN001
        if args[:2] == ["for-each-ref", "--format=%(refname:short)"]:
            return CompletedProcess(args, 0, "public-snapshot-old\npublic-snapshot-current\n", "")
        return CompletedProcess(args, 1, "", "branch checked out elsewhere")

    monkeypatch.setattr(public_snapshot, "run_git", fake_run)

    assert public_snapshot.cleanup_local_public_snapshot_branches(tmp_path, "public-snapshot-current") == []


def _stub_public_snapshot_dependencies(monkeypatch, push_code: int = 0) -> None:
    monkeypatch.setattr(
        public_snapshot,
        "private_project_inventory_payload",
        lambda _repo: {"outcome": "pass", "private_projects": [], "public_projects": [], "reason": None},
    )
    monkeypatch.setattr(
        public_snapshot,
        "secret_content_scan_payload",
        lambda _snapshot, _paths, _operation: {"outcome": "pass", "reason": None, "checked_paths": [], "blocking_paths": []},
    )

    def fake_run(_repo: Path, args: list[str], env=None):  # noqa: ANN001
        if args == ["ls-files"]:
            return CompletedProcess(args, 0, "README.md\n", "")
        if args and args[0] == "push":
            return CompletedProcess(args, push_code, "", "push rejected" if push_code else "")
        return CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(public_snapshot, "run_git", fake_run)


def test_run_public_snapshot_cleans_local_branches_after_successful_push(monkeypatch, tmp_path) -> None:
    _stub_public_snapshot_dependencies(monkeypatch)
    cleanup_calls: list[str] = []
    monkeypatch.setattr(public_snapshot, "cleanup_local_public_snapshot_branches", lambda _repo, keep_branch: cleanup_calls.append(keep_branch))

    assert public_snapshot.run_public_snapshot(tmp_path, public_remote="public", private_projects=[]) is None

    assert len(cleanup_calls) == 1
    assert cleanup_calls[0].startswith("public-snapshot-")


def test_run_public_snapshot_does_not_cleanup_during_inspect(monkeypatch, tmp_path) -> None:
    _stub_public_snapshot_dependencies(monkeypatch)
    cleanup_calls: list[str] = []
    monkeypatch.setattr(public_snapshot, "cleanup_local_public_snapshot_branches", lambda _repo, keep_branch: cleanup_calls.append(keep_branch))

    payload = public_snapshot.run_public_snapshot(tmp_path, public_remote=None, private_projects=[])

    assert payload is not None
    assert payload["outcome"] == "pass"
    assert payload["staged_count"] == 1
    assert payload["excluded_count"] == 0
    assert payload["leaked_private_paths"] == []
    assert payload["secret_scan"]["outcome"] == "pass"

    assert cleanup_calls == []


def test_run_public_snapshot_does_not_cleanup_after_failed_push(monkeypatch, tmp_path) -> None:
    _stub_public_snapshot_dependencies(monkeypatch, push_code=1)
    cleanup_calls: list[str] = []
    monkeypatch.setattr(public_snapshot, "cleanup_local_public_snapshot_branches", lambda _repo, keep_branch: cleanup_calls.append(keep_branch))

    with pytest.raises(SystemExit, match="push rejected"):
        public_snapshot.run_public_snapshot(tmp_path, public_remote="public", private_projects=[])

    assert cleanup_calls == []


def test_run_public_snapshot_blocks_failed_private_inventory(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        public_snapshot,
        "private_project_inventory_payload",
        lambda _repo: {"outcome": "block", "reason": "private_project_inventory_missing"},
    )

    with pytest.raises(SystemExit, match="private_project_inventory_missing"):
        public_snapshot.run_public_snapshot(tmp_path, public_remote=None, private_projects=[])


def test_public_snapshot_exclude_patterns_skip_comments_and_blanks(tmp_path) -> None:
    config = tmp_path / "scripts" / "public-snapshot.exclude.txt"
    config.parent.mkdir()
    config.write_text(
        "\n# comment\n"
        "docs/Audit_*/**\n"
        " .obsidian/** \n",
        encoding="utf-8",
    )

    assert public_snapshot.public_snapshot_exclude_patterns(tmp_path) == [
        "docs/Audit_*/**",
        ".obsidian/**",
    ]


def test_public_snapshot_excluded_paths_match_curated_patterns() -> None:
    paths = [
        "README.md",
        "ROADMAP.md",
        "TASKS.md",
        "docs/Audit_07.06.26/report.md",
        "docs/CURRENT_STATE_QA_2026-06-23.md",
        "docs/CODEX_PLUGIN_PACKAGING_EVALUATION.md",
        "docs/GTM_READINESS_PACK.md",
        "docs/neagi/sidequests/002-publish-guard.md",
        "plans/leadops/worktree-ledger.json",
        ".obsidian/graph.json",
        ".agents/skills/local-agent-delegation/__pycache__/local_agent_delegate.pyc",
        "scripts/__pycache__/reefiki.cpython-311.pyc",
        "scripts/mobile-capture/README.md",
    ]
    patterns = [
        "docs/Audit_*/**",
        "docs/*QA*",
        "docs/CODEX_PLUGIN_PACKAGING_EVALUATION.md",
        "docs/GTM_READINESS_PACK.md",
        "ROADMAP.md",
        "TASKS.md",
        "plans/**",
        ".obsidian/**",
        "**/__pycache__/**",
        "*.pyc",
        "scripts/mobile-capture/**",
    ]

    assert public_snapshot.public_snapshot_excluded_paths(paths, patterns) == [
        ".agents/skills/local-agent-delegation/__pycache__/local_agent_delegate.pyc",
        ".obsidian/graph.json",
        "ROADMAP.md",
        "TASKS.md",
        "docs/Audit_07.06.26/report.md",
        "docs/CODEX_PLUGIN_PACKAGING_EVALUATION.md",
        "docs/CURRENT_STATE_QA_2026-06-23.md",
        "docs/GTM_READINESS_PACK.md",
        "plans/leadops/worktree-ledger.json",
        "scripts/__pycache__/reefiki.cpython-311.pyc",
        "scripts/mobile-capture/README.md",
    ]


def test_public_snapshot_curated_config_keeps_public_runtime_and_demo_files() -> None:
    patterns = public_snapshot.public_snapshot_exclude_patterns(ROOT)
    paths = [
        ".agents/skills/local-agent-delegation/scripts/local_agent_delegate.py",
        "scripts/mimo_memory_integration.py",
        "projects/reefiki-demo/golden-queries.yml",
        "docs/CODEX_PLUGIN_PACKAGING_EVALUATION.md",
        "docs/Audit_07.06.26/report.md",
        "scripts/__pycache__/reefiki.cpython-311.pyc",
    ]

    excluded = public_snapshot.public_snapshot_excluded_paths(paths, patterns)

    assert ".agents/skills/local-agent-delegation/scripts/local_agent_delegate.py" not in excluded
    assert "scripts/mimo_memory_integration.py" not in excluded
    assert "projects/reefiki-demo/golden-queries.yml" not in excluded
    assert "docs/CODEX_PLUGIN_PACKAGING_EVALUATION.md" in excluded
    assert "docs/Audit_07.06.26/report.md" in excluded
    assert "scripts/__pycache__/reefiki.cpython-311.pyc" in excluded
