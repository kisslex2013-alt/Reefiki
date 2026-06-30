import argparse
from pathlib import Path

import pytest

from scripts.reefiki_core.project_commands import ProjectCommandDeps, dispatch_project_command


def test_dispatch_index_uses_injected_dependencies(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    args = argparse.Namespace(cmd="index")

    result = dispatch_project_command(
        args,
        project,
        ProjectCommandDeps(
            build_index=lambda path: 3,
            db_path=lambda path: path / ".reefiki" / "index.sqlite",
            relative=lambda base, path: ".reefiki/index.sqlite",
        ),
    )

    assert result == 0
    assert capsys.readouterr().out == "Indexed 3 page(s): .reefiki/index.sqlite\n"


def test_dispatch_review_queue_write_report_uses_injected_writer(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    calls = []
    args = argparse.Namespace(cmd="review-queues", write_report=True, stale_days=30)

    def fake_write_report(project_path: Path, stale_days: int) -> Path:
        calls.append((project_path, stale_days))
        return project_path / "plans" / "review-queues.md"

    result = dispatch_project_command(
        args,
        project,
        ProjectCommandDeps(
            write_review_queue_report=fake_write_report,
            relative=lambda base, path: "plans/review-queues.md",
        ),
    )

    assert result == 0
    assert calls == [(project, 30)]
    assert capsys.readouterr().out == "plans/review-queues.md\n"


def test_dispatch_promote_apply_uses_injected_apply(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    calls = []
    args = argparse.Namespace(
        cmd="promote-dry-run",
        apply_draft="draft.md",
        write_draft=False,
        yes=True,
    )

    def fake_apply(project_path: Path, draft_path: str, yes: bool) -> Path:
        calls.append((project_path, draft_path, yes))
        return project_path / "wiki" / "decisions" / "accepted.md"

    result = dispatch_project_command(
        args,
        project,
        ProjectCommandDeps(
            apply_promotion_draft=fake_apply,
            relative=lambda base, path: "wiki/decisions/accepted.md",
        ),
    )

    assert result == 0
    assert calls == [(project, "draft.md", True)]
    assert capsys.readouterr().out == "wiki/decisions/accepted.md\n"


def test_dispatch_status_passes_format_to_dependency(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    calls = []
    args = argparse.Namespace(cmd="status", format="json")

    def fake_status(project_path: Path, fmt: str) -> int:
        calls.append((project_path, fmt))
        return 0

    result = dispatch_project_command(args, project, ProjectCommandDeps(status=fake_status))

    assert result == 0
    assert calls == [(project, "json")]


def test_dispatch_timeline_passes_limit_and_format_to_dependency(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    calls = []
    args = argparse.Namespace(cmd="timeline", limit=3, format="json")

    def fake_timeline(project_path: Path, limit: int, fmt: str) -> int:
        calls.append((project_path, limit, fmt))
        return 0

    result = dispatch_project_command(args, project, ProjectCommandDeps(timeline=fake_timeline))

    assert result == 0
    assert calls == [(project, 3, "json")]


def test_dispatch_unknown_command_returns_2(tmp_path: Path) -> None:
    args = argparse.Namespace(cmd="unknown")

    assert dispatch_project_command(args, tmp_path, ProjectCommandDeps()) == 2
