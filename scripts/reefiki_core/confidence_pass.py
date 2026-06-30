from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .doctor import doctor_payload
from .git_utils import run_git
from .orchestration_check import orchestration_check_payload
from .process_utils import SUBPROCESS_TIMEOUT_SECONDS
from .project_paths import find_project
from .publish_task import publish_task_payload
from .review_queues import review_queue_scan, review_queue_summary


PayloadFn = Callable[..., dict[str, object]]
PublishTaskFn = Callable[..., tuple[int, dict[str, object]]]
PytestFn = Callable[[Path, list[str]], dict[str, object]]
MemoryGoldenFn = Callable[[Path, str], dict[str, object]]


def _command(*parts: str) -> list[str]:
    return list(parts)


def _tail(text: str, limit: int = 20) -> list[str]:
    lines = text.splitlines()
    return lines[-limit:]


def _step(
    name: str,
    outcome: str,
    *,
    command: list[str],
    payload: dict[str, object] | None = None,
    reason: str | None = None,
    required: bool = True,
) -> dict[str, object]:
    return {
        "name": name,
        "outcome": outcome,
        "required": required,
        "command": " ".join(command),
        "reason": reason,
        "payload": payload or {},
    }


def _payload_outcome(payload: dict[str, object]) -> str:
    value = payload.get("outcome", payload.get("status", "pass"))
    return str(value)


def _gate_outcome(payload: dict[str, object]) -> str:
    outcome = _payload_outcome(payload)
    return "pass" if outcome in {"pass", "ok"} else "block"


def _git_status_payload(repo: Path) -> dict[str, object]:
    completed = run_git(repo, ["status", "--short", "--branch"])
    return {
        "outcome": "pass" if completed.returncode == 0 else "block",
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _run_pytest(repo: Path, pytest_args: list[str]) -> dict[str, object]:
    args = [sys.executable, "-m", "pytest", *pytest_args]
    completed = subprocess.run(
        args,
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    return {
        "outcome": "pass" if completed.returncode == 0 else "block",
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def confidence_pass_payload(
    repo: Path,
    *,
    project_name: str = "reefiki",
    base: str = "origin/main",
    include_pytest: bool = False,
    pytest_args: list[str] | None = None,
    memory_golden_fn: MemoryGoldenFn,
    git_status_fn: PayloadFn = _git_status_payload,
    doctor_fn: PayloadFn = doctor_payload,
    orchestration_fn: PayloadFn = orchestration_check_payload,
    publish_task_fn: PublishTaskFn = publish_task_payload,
    pytest_fn: PytestFn = _run_pytest,
) -> dict[str, object]:
    repo = repo.resolve()
    project = find_project(repo, project_name)
    pytest_args = pytest_args or []

    steps: list[dict[str, object]] = []

    git_status = git_status_fn(repo)
    steps.append(_step("git-status", _gate_outcome(git_status), command=_command("git", "status", "--short", "--branch"), payload=git_status))

    orchestration = orchestration_fn(repo, base=base)
    steps.append(
        _step(
            "orchestration-check",
            _gate_outcome(orchestration),
            command=_command("python", "scripts/reefiki.py", "orchestration-check", "--base", base, "--format", "json"),
            payload=orchestration,
        )
    )

    doctor = doctor_fn(project)
    steps.append(
        _step(
            "doctor",
            _gate_outcome(doctor),
            command=_command("python", "scripts/reefiki.py", "--project", f"projects/{project.name}", "doctor", "--format", "json"),
            payload=doctor,
        )
    )

    queues = review_queue_summary(review_queue_scan(project), limit=5)
    queues_outcome = "pass" if int(queues.get("total", 0) or 0) == 0 else "block"
    steps.append(
        _step(
            "review-queues",
            queues_outcome,
            command=_command(
                "python",
                "scripts/reefiki.py",
                "--project",
                f"projects/{project.name}",
                "review-queues",
                "--summary",
                "--format",
                "json",
            ),
            payload=queues,
        )
    )

    golden = memory_golden_fn(repo, project.name)
    steps.append(
        _step(
            "memory-golden",
            _gate_outcome(golden.get("eval", {}) if isinstance(golden.get("eval"), dict) else golden),
            command=_command("python", "scripts/reefiki.py", "memory", "golden", "--project", project.name, "--format", "json"),
            payload=golden,
        )
    )

    if include_pytest:
        pytest_payload = pytest_fn(repo, pytest_args)
        steps.append(
            _step(
                "pytest",
                _gate_outcome(pytest_payload),
                command=[sys.executable, "-m", "pytest", *pytest_args],
                payload=pytest_payload,
            )
        )
    else:
        steps.append(
            _step(
                "pytest",
                "skipped",
                command=[sys.executable, "-m", "pytest", *pytest_args],
                reason="use --include-pytest for a complete local confidence pass",
                required=False,
            )
        )

    _publish_code, publish = publish_task_fn(
        repo,
        base=base,
        private_remote="origin",
        public_remote="public",
        dry_run=True,
        cleanup=True,
        public_snapshot=False,
    )
    steps.append(
        _step(
            "publish-dry-run",
            _gate_outcome(publish),
            command=_command("python", "scripts/reefiki.py", "publish-task", "--base", base, "--dry-run", "--cleanup", "--format", "json"),
            payload=publish,
        )
    )

    manual_steps = [
        {
            "name": "read-only-verifier",
            "outcome": "manual_required",
            "reason": "CLI cannot spawn or certify delegated verifier agents; TeamLead closeout still requires verifier evidence when policy triggers apply.",
        }
    ]
    blocked_steps = [step["name"] for step in steps if step["outcome"] == "block"]
    skipped_steps = [step["name"] for step in steps if step["outcome"] == "skipped"]
    outcome = "block" if blocked_steps else "review" if skipped_steps else "pass"
    return {
        "schema_version": "reefiki.confidence-pass.v1",
        "repo": str(repo),
        "project": project.name,
        "base": base,
        "outcome": outcome,
        "steps": steps,
        "blocked_steps": blocked_steps,
        "skipped_steps": skipped_steps,
        "manual_steps": manual_steps,
        "side_effects": [
            "does not stage, commit, push, publish, or cleanup the current task worktree",
            "publish-task dry-run may create and remove a temporary public snapshot worktree",
        ],
        "recipe": [
            step["command"]
            for step in steps
            if isinstance(step.get("command"), str)
        ],
    }


def print_confidence_pass(
    repo: Path,
    *,
    project_name: str,
    base: str,
    include_pytest: bool,
    pytest_args: list[str],
    fmt: str,
    memory_golden_fn: MemoryGoldenFn,
) -> int:
    payload = confidence_pass_payload(
        repo,
        project_name=project_name,
        base=base,
        include_pytest=include_pytest,
        pytest_args=pytest_args,
        memory_golden_fn=memory_golden_fn,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"outcome: {payload['outcome']}")
        print(f"project: {payload['project']}")
        print(f"base: {payload['base']}")
        print("steps:")
        for item in payload["steps"]:
            assert isinstance(item, dict)
            print(f"- {item['name']}: {item['outcome']}")
            if item.get("reason"):
                print(f"  reason: {item['reason']}")
        print("side_effects:")
        for item in payload["side_effects"]:
            print(f"- {item}")
        if payload["manual_steps"]:
            print("manual_steps:")
            for item in payload["manual_steps"]:
                print(f"- {item['name']}: {item['outcome']} ({item['reason']})")
    return 1 if payload["outcome"] == "block" else 0
