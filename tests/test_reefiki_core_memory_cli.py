import json
from pathlib import Path

import pytest

from scripts.reefiki_core.memory_cli import (
    print_memory_golden,
    print_memory_pack,
    print_memory_reflect,
    read_only_pack_quality,
)


def test_print_memory_golden_uses_injected_payload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    golden_path = tmp_path / "custom-golden.yml"
    calls = []

    def fake_run_golden_queries(root: Path, project_name: str, path: Path | None = None) -> dict[str, object]:
        calls.append((root, project_name, path))
        return {
            "project": project_name,
            "passed": 1,
            "total": 1,
            "failed": 0,
            "cases": [{"status": "pass", "id": "known"}],
        }

    assert (
        print_memory_golden(
            tmp_path,
            "reefiki",
            str(golden_path),
            "text",
            run_golden_queries_fn=fake_run_golden_queries,
        )
        == 0
    )

    assert calls == [(tmp_path, "reefiki", golden_path)]
    assert capsys.readouterr().out == (
        "project: reefiki\n"
        "golden: 1/1 passed\n"
        "  - pass: known\n"
    )


def test_print_memory_pack_uses_injected_payload_and_adds_strict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = []

    def fake_memory_pack(root: Path, project_name: str, task: str, limit: int = 8) -> dict[str, object]:
        calls.append((root, project_name, task, limit))
        return {
            "task": task,
            "project": project_name,
            "safety_outcome": "pass",
            "lookup_error": None,
            "contents": [],
            "quality": {"outcome": "pass", "violations": []},
            "golden": {"total": 1, "passed": 1, "failed": 0},
            "diff": {"total": 0},
            "open_queues": [],
            "exclusions": [],
        }

    assert (
        print_memory_pack(
            tmp_path,
            "reefiki",
            "continue REEFIKI roadmap development",
            3,
            True,
            "json",
            memory_pack_fn=fake_memory_pack,
        )
        == 0
    )

    assert calls == [(tmp_path, "reefiki", "continue REEFIKI roadmap development", 3)]
    output = json.loads(capsys.readouterr().out)
    assert output["strict"] == {"outcome": "pass", "blocking_reasons": []}


def test_read_only_pack_quality_uses_injected_pack(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    (project / ".reefiki").mkdir(parents=True)
    (project / ".reefiki" / "index.sqlite").write_bytes(b"")
    calls = []

    def fake_memory_pack(root: Path, project_name: str, task: str, limit: int = 8) -> dict[str, object]:
        calls.append((root, project_name, task, limit))
        return {
            "quality": {"outcome": "pass"},
            "golden": {"total": 1, "passed": 1, "failed": 0},
            "open_queues": [],
            "safety_outcome": "pass",
        }

    result = read_only_pack_quality(
        tmp_path,
        project,
        "continue roadmap",
        3,
        memory_pack_fn=fake_memory_pack,
    )

    assert calls == [(tmp_path, "reefiki", "continue roadmap", 8)]
    assert result["strict"] == {"outcome": "pass", "blocking_reasons": []}
    assert result["quality"] == {"outcome": "pass"}


def test_print_memory_reflect_uses_injected_payload_and_result_printer(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    calls = []

    def fake_memory_reflect(root: Path, project_name: str, since: str, task: str, limit: int = 5) -> dict[str, object]:
        calls.append((root, project_name, since, task, limit))
        return {"project": project_name, "since": since, "outcome": "ok", "candidate_actions": []}

    def fake_print_result(payload: dict[str, object], fmt: str) -> int:
        assert payload["project"] == "reefiki"
        assert fmt == "json"
        return 0

    assert (
        print_memory_reflect(
            tmp_path,
            "reefiki",
            "HEAD",
            "continue roadmap",
            4,
            False,
            "json",
            memory_reflect_fn=fake_memory_reflect,
            print_result_fn=fake_print_result,
        )
        == 0
    )

    assert calls == [(tmp_path, "reefiki", "HEAD", "continue roadmap", 4)]


def test_print_memory_reflect_write_report_branch_uses_injected_writer(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    payload = {"project": "reefiki", "since": "HEAD", "outcome": "blocked"}

    def fake_memory_reflect(*args: object, **kwargs: object) -> dict[str, object]:
        return payload

    def fake_write_report(project_path: Path, report_payload: dict[str, object]) -> Path:
        assert project_path == project
        assert report_payload is payload
        return project / "plans" / "reflection-2026-06-12.md"

    assert (
        print_memory_reflect(
            tmp_path,
            "reefiki",
            "HEAD",
            "continue roadmap",
            4,
            True,
            "json",
            memory_reflect_fn=fake_memory_reflect,
            write_report_fn=fake_write_report,
        )
        == 1
    )

    assert capsys.readouterr().out == "plans/reflection-2026-06-12.md\n"
