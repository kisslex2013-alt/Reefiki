from pathlib import Path

from scripts.reefiki_core.confidence_pass import confidence_pass_payload


def _repo(tmp_path: Path) -> Path:
    project = tmp_path / "projects" / "reefiki"
    (project / "wiki").mkdir(parents=True)
    return tmp_path


def _pass_payload(**extra: object) -> dict[str, object]:
    return {"outcome": "pass", **extra}


def _doctor(_project: Path) -> dict[str, object]:
    return _pass_payload(project="reefiki")


def _orchestration(_repo: Path, **_kwargs: object) -> dict[str, object]:
    return _pass_payload(schema_version="reefiki.orchestration-check.v1")


def _golden(_repo: Path, _project: str) -> dict[str, object]:
    return {"eval": {"outcome": "pass"}, "total": 1, "passed": 1, "failed": 0}


def _git_status(_repo: Path) -> dict[str, object]:
    return _pass_payload(stdout="## main...origin/main")


def _publish_pass(_repo: Path, **_kwargs: object) -> tuple[int, dict[str, object]]:
    return 0, _pass_payload(diff_class="public-safe")


def _pytest_pass(_repo: Path, _args: list[str]) -> dict[str, object]:
    return _pass_payload(returncode=0)


def test_confidence_pass_reports_review_until_pytest_is_included(tmp_path) -> None:
    payload = confidence_pass_payload(
        _repo(tmp_path),
        memory_golden_fn=_golden,
        git_status_fn=_git_status,
        doctor_fn=_doctor,
        orchestration_fn=_orchestration,
        publish_task_fn=_publish_pass,
    )

    assert payload["schema_version"] == "reefiki.confidence-pass.v1"
    assert payload["outcome"] == "review"
    assert payload["skipped_steps"] == ["pytest"]
    assert any(command.endswith("-m pytest") for command in payload["recipe"])
    assert payload["manual_steps"][0]["name"] == "read-only-verifier"
    assert "does not stage" in payload["side_effects"][0]
    assert "temporary public snapshot worktree" in payload["side_effects"][1]


def test_confidence_pass_passes_when_local_gates_and_pytest_pass(tmp_path) -> None:
    payload = confidence_pass_payload(
        _repo(tmp_path),
        include_pytest=True,
        pytest_args=["tests/test_example.py"],
        memory_golden_fn=_golden,
        git_status_fn=_git_status,
        doctor_fn=_doctor,
        orchestration_fn=_orchestration,
        publish_task_fn=_publish_pass,
        pytest_fn=_pytest_pass,
    )

    assert payload["outcome"] == "pass"
    assert payload["blocked_steps"] == []
    pytest_step = next(step for step in payload["steps"] if step["name"] == "pytest")
    assert pytest_step["outcome"] == "pass"
    assert pytest_step["command"].endswith("pytest tests/test_example.py")


def test_confidence_pass_blocks_when_publish_dry_run_blocks(tmp_path) -> None:
    def publish_block(_repo: Path, **_kwargs: object) -> tuple[int, dict[str, object]]:
        return 1, {"outcome": "block", "reason": "dirty_worktree"}

    payload = confidence_pass_payload(
        _repo(tmp_path),
        include_pytest=True,
        memory_golden_fn=_golden,
        git_status_fn=_git_status,
        doctor_fn=_doctor,
        orchestration_fn=_orchestration,
        publish_task_fn=publish_block,
        pytest_fn=_pytest_pass,
    )

    assert payload["outcome"] == "block"
    assert payload["blocked_steps"] == ["publish-dry-run"]
