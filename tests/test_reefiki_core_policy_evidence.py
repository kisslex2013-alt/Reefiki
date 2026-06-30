import json
from pathlib import Path

from scripts import reefiki
from scripts.reefiki_core.policy_evidence import policy_evidence_matrix


def test_policy_evidence_matrix_reports_guard_publish_cleanup_pass() -> None:
    payload = policy_evidence_matrix(
        [
            (
                {
                    "outcome": "pass",
                    "target_project": "reefiki",
                    "mode": "code/docs",
                    "allowed_prefix": "code/docs-profile:projects/reefiki",
                    "staged_paths": ["scripts/reefiki.py"],
                    "blocking_paths": [],
                    "violations": [],
                },
                "guard.json",
            ),
            (
                {
                    "outcome": "pass",
                    "reason": None,
                    "diff_class": "mixed",
                    "changed_paths": ["TASKS.md", "projects/reefiki/wiki/log.md"],
                    "checked_paths": ["TASKS.md"],
                    "blocking_paths": [],
                    "public_snapshot_intent": "diff-class:mixed",
                    "public_snapshot_exclusions": ["projects/reefiki"],
                    "private_projects": ["reefiki"],
                    "actions": ["push_task_branch", "push_private_main", "push_public_snapshot"],
                    "base": "origin/main",
                    "base_is_ancestor": True,
                    "head": "abc123",
                },
                "publish.json",
            ),
            (
                {
                    "outcome": "pass",
                    "worktree": "D:/Projects/_worktrees/REEFIKI-task",
                    "branch": "codex/task",
                    "head": "abc123",
                    "base": "origin/main",
                    "dirty_paths": [],
                    "head_reachable_from_base": True,
                    "branch_delete_allowed": True,
                    "actions": ["remove_worktree", "delete_local_branch"],
                },
                "cleanup.json",
            ),
        ]
    )

    assert payload["outcome"] == "pass"
    assert payload["explanatory_only"] is True
    assert "cannot approve" in payload["decision_authority"]
    check_ids = {row["check_id"] for row in payload["rows"]}
    assert {"guard.target_project", "guard.scope", "publish.public_snapshot", "publish.secret_scan", "cleanup.reachability"} <= check_ids
    assert any(row["evidence_pointer"] == "guard.json#/target_project" for row in payload["rows"])
    assert any(row["evidence_pointer"] == "publish.json#/public_snapshot_intent" for row in payload["rows"])


def test_policy_evidence_matrix_reports_guard_block_rows() -> None:
    payload = policy_evidence_matrix(
        [
            (
                {
                    "outcome": "block",
                    "target_project": "reefiki",
                    "mode": "process",
                    "allowed_prefix": "process-profile:projects/reefiki",
                    "staged_paths": ["projects/reefiki/raw/source.md", "projects/metrica/wiki/log.md"],
                    "blocking_paths": ["projects/reefiki/raw/source.md", "projects/metrica/wiki/log.md"],
                    "violations": [
                        {"path": "projects/reefiki/raw/source.md", "reason": "raw_modify_delete_forbidden"},
                        {"path": "projects/metrica/wiki/log.md", "reason": "outside_mode_scope"},
                    ],
                },
                "guard-block.json",
            )
        ]
    )

    assert payload["outcome"] == "block"
    raw_row = next(row for row in payload["rows"] if row["check_id"] == "guard.raw")
    mode_row = next(row for row in payload["rows"] if row["check_id"] == "guard.mode")
    assert raw_row["outcome"] == "block"
    assert mode_row["outcome"] == "block"
    assert raw_row["evidence_pointer"] == "guard-block.json#/violations"


def test_policy_evidence_matrix_reports_publish_secret_block() -> None:
    payload = policy_evidence_matrix(
        [
            (
                {
                    "outcome": "block",
                    "reason": "secret_like_content",
                    "diff_class": "public-safe",
                    "changed_paths": ["README.md"],
                    "checked_paths": ["README.md"],
                    "blocking_paths": ["README.md"],
                    "public_snapshot_intent": "diff-class:public-safe",
                    "public_snapshot_exclusions": [],
                    "private_projects": ["reefiki"],
                    "actions": [],
                    "base": "origin/main",
                    "base_is_ancestor": True,
                    "head": "abc123",
                },
                "publish-secret.json",
            )
        ]
    )

    assert payload["outcome"] == "block"
    secret_row = next(row for row in payload["rows"] if row["check_id"] == "publish.secret_scan")
    assert secret_row["outcome"] == "block"
    assert secret_row["evidence_pointer"] == "publish-secret.json#/blocking_paths"
    assert secret_row["facts"]["blocking_paths"] == ["README.md"]


def test_policy_evidence_matrix_reports_cleanup_unmerged_block() -> None:
    payload = policy_evidence_matrix(
        [
            (
                {
                    "outcome": "block",
                    "reason": "unmerged_worktree_head",
                    "worktree": "D:/Projects/_worktrees/REEFIKI-task",
                    "branch": "codex/task",
                    "head": "abc123",
                    "base": "origin/main",
                    "dirty_paths": [],
                    "head_reachable_from_base": False,
                    "branch_delete_allowed": False,
                },
                "cleanup-block.json",
            )
        ]
    )

    assert payload["outcome"] == "block"
    reachability = next(row for row in payload["rows"] if row["check_id"] == "cleanup.reachability")
    assert reachability["outcome"] == "block"
    assert reachability["evidence_pointer"] == "cleanup-block.json#/head_reachable_from_base"


def test_policy_evidence_matrix_reports_worktree_status_scope_conflict() -> None:
    payload = policy_evidence_matrix(
        [
            (
                {
                    "outcome": "pass",
                    "repo": "D:/Projects/REEFIKI",
                    "base": "origin/main",
                    "shared_checkout_dirty": True,
                    "shared_checkout_behind": False,
                    "excluded_dirty_paths": ["README.md"],
                    "scope_conflicts": ["projects/reefiki/wiki/log.md"],
                    "recommendation": "blocked_by_dirty_target_scope",
                    "shared_checkout": {},
                    "worktrees": [],
                },
                "worktree-status.json",
            )
        ]
    )

    assert payload["outcome"] == "block"
    row = next(row for row in payload["rows"] if row["check_id"] == "worktree.scope")
    assert row["outcome"] == "block"
    assert row["evidence_pointer"] == "worktree-status.json#/recommendation"
    assert row["facts"]["scope_conflicts"] == ["projects/reefiki/wiki/log.md"]


def test_policy_evidence_cli_reads_json_inputs(tmp_path, capsys) -> None:
    guard = tmp_path / "guard.json"
    guard.write_text(
        json.dumps(
            {
                "outcome": "pass",
                "target_project": "reefiki",
                "mode": "code/docs",
                "allowed_prefix": "code/docs-profile:projects/reefiki",
                "staged_paths": ["scripts/reefiki.py"],
                "blocking_paths": [],
                "violations": [],
            }
        ),
        encoding="utf-8",
    )

    code = reefiki.main(["policy-evidence", "--input", str(guard), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["outcome"] == "pass"
    assert payload["rows"][0]["tool"] == "guard-staged"
    assert str(guard).replace("\\", "/") in payload["rows"][0]["evidence_pointer"]


def test_policy_evidence_docs_explain_explanatory_only_contract() -> None:
    commands = Path("COMMANDS.md").read_text(encoding="utf-8")

    assert "reefiki.py policy-evidence" in commands
    assert "не обходит" in commands
