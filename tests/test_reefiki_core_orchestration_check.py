from datetime import date

from scripts.reefiki_core import orchestration_check


def test_ledger_entry_issues_require_owner_scope_milestone_and_fresh_lease() -> None:
    entry = {
        "branch": "codex/task",
        "created_at": "2026-05-01",
        "coordination_files": [],
    }

    issues = orchestration_check.ledger_entry_issues(entry, max_lease_days=14, today=date(2026, 6, 13))

    assert issues == ["missing_owner", "missing_scope", "missing_milestone", "lease_expired"]


def test_coordination_conflicts_require_single_integration_owner() -> None:
    entries = [
        {
            "branch": "codex/a",
            "owner": "thread-a",
            "status": "active",
            "coordination_files": ["TASKS.md"],
        },
        {
            "branch": "codex/b",
            "owner": "thread-b",
            "status": "review",
            "coordination_files": ["TASKS.md"],
        },
    ]

    conflicts = orchestration_check.coordination_conflicts(entries)

    assert conflicts == [
        {
            "path": "TASKS.md",
            "holders": [
                {"branch": "codex/a", "owner": "thread-a", "integration_owner": "", "status": "active"},
                {"branch": "codex/b", "owner": "thread-b", "integration_owner": "", "status": "review"},
            ],
            "reason": "coordination_file_without_single_owner",
        }
    ]


def test_coordination_conflicts_allow_shared_integration_owner() -> None:
    entries = [
        {
            "branch": "codex/a",
            "owner": "thread-a",
            "integration_owner": "lead",
            "status": "active",
            "coordination_files": ["projects/reefiki/wiki/log.md"],
        },
        {
            "branch": "codex/b",
            "owner": "thread-b",
            "integration_owner": "lead",
            "status": "review",
            "coordination_files": ["projects/reefiki/wiki/log.md"],
        },
    ]

    assert orchestration_check.coordination_conflicts(entries) == []


def test_global_config_scan_blocks_unsafe_patterns(tmp_path) -> None:
    rules = tmp_path / "default.rules"
    rules.write_text("allow = 'git reset --hard'\n", encoding="utf-8")

    payload = orchestration_check.global_config_scan_payload([rules])

    assert payload["outcome"] == "block"
    assert payload["findings"] == [
        {
            "path": str(rules),
            "pattern": "git reset --hard",
            "reason": "unsafe_or_secret_like_global_rule",
        }
    ]


def test_remote_task_branches_marks_merged_branches_for_deletion(monkeypatch, tmp_path) -> None:
    def fake_run_git(_repo, args):
        class Result:
            returncode = 0
            stderr = ""

            if args[:3] == ["branch", "-r", "--list"]:
                stdout = "origin/codex/merged\norigin/codex/open\n"
            elif args == ["merge-base", "--is-ancestor", "origin/codex/merged", "origin/main"]:
                stdout = ""
                returncode = 0
            else:
                stdout = ""
                returncode = 1

        return Result()

    monkeypatch.setattr(orchestration_check, "run_git", fake_run_git)

    payload = orchestration_check.remote_task_branches_payload(tmp_path, "origin/main", "origin")

    assert payload["delete_candidates"] == ["origin/codex/merged"]
    assert payload["branches"][1]["recommendation"] == "keep_or_review"


def test_orchestration_check_blocks_ledger_issues_and_conflicts(monkeypatch, tmp_path) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        """{
  "schema_version": "reefiki.worktree-ledger.v1",
  "entries": [
    {"branch": "codex/a", "owner": "a", "scope": "docs", "milestone": "m1", "created_at": "2026-06-13", "status": "active", "coordination_files": ["TASKS.md"]},
    {"branch": "codex/b", "owner": "b", "scope": "docs", "milestone": "m1", "created_at": "2026-06-13", "status": "active", "coordination_files": ["TASKS.md"]}
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        orchestration_check,
        "worktree_status_payload",
        lambda repo, base, scopes=None: {
            "repo": str(repo),
            "base": base,
            "scopes": scopes or [],
            "shared_checkout_dirty": False,
            "shared_checkout_behind": False,
            "excluded_dirty_paths": [],
            "scope_conflicts": [],
            "recommendation": "keep",
            "shared_checkout": None,
            "worktrees": [],
        },
    )
    monkeypatch.setattr(
        orchestration_check,
        "remote_task_branches_payload",
        lambda repo, base, remote: {"remote": remote, "base": base, "branches": [], "delete_candidates": []},
    )
    monkeypatch.setattr(orchestration_check, "ci_policy_payload", lambda repo: {"local_ci_present": True})
    monkeypatch.setattr(orchestration_check, "git_status_paths", lambda repo: [])

    payload = orchestration_check.orchestration_check_payload(tmp_path, ledger_path=ledger, max_lease_days=30)

    assert payload["outcome"] == "block"
    assert payload["blockers"] == ["coordination_conflicts"]
    assert payload["coordination_conflicts"][0]["path"] == "TASKS.md"


def test_orchestration_check_blocks_current_dirty_worktree(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        orchestration_check,
        "worktree_status_payload",
        lambda repo, base, scopes=None: {
            "repo": str(repo),
            "base": base,
            "scopes": scopes or [],
            "shared_checkout_dirty": False,
            "shared_checkout_behind": False,
            "excluded_dirty_paths": [],
            "scope_conflicts": [],
            "recommendation": "keep",
            "shared_checkout": None,
            "worktrees": [],
        },
    )
    monkeypatch.setattr(
        orchestration_check,
        "remote_task_branches_payload",
        lambda repo, base, remote: {"remote": remote, "base": base, "branches": [], "delete_candidates": []},
    )
    monkeypatch.setattr(orchestration_check, "ci_policy_payload", lambda repo: {"local_ci_present": True})
    monkeypatch.setattr(orchestration_check, "git_status_paths", lambda repo: ["README.md"])

    payload = orchestration_check.orchestration_check_payload(tmp_path)

    assert payload["outcome"] == "block"
    assert payload["blockers"] == ["current_worktree_dirty"]
    assert payload["current_worktree_dirty_paths"] == ["README.md"]
