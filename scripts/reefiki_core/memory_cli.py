from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .memory_golden import print_memory_golden_result
from .memory_pack import memory_pack_strict_result, print_memory_pack_result
from .memory_reflect import (
    print_memory_reflect_result,
    read_only_pack_quality as memory_reflect_read_only_pack_quality,
    write_memory_reflection_report,
)
from .project_paths import find_project, relative


def print_memory_golden(
    root: Path,
    project_name: str,
    path: str | None,
    fmt: str,
    run_golden_queries_fn: Callable[..., dict[str, object]],
) -> int:
    result = run_golden_queries_fn(root, project_name, Path(path) if path else None)
    return print_memory_golden_result(result, fmt)


def print_memory_pack(
    root: Path,
    project_name: str,
    task: str,
    limit: int,
    strict: bool,
    fmt: str,
    memory_pack_fn: Callable[..., dict[str, object]],
) -> int:
    result = memory_pack_fn(root, project_name, task, limit=limit)
    result["strict"] = memory_pack_strict_result(result)
    return print_memory_pack_result(result, strict=strict, fmt=fmt)


def read_only_pack_quality(
    root: Path,
    project: Path,
    task: str,
    limit: int,
    memory_pack_fn: Callable[..., dict[str, object]],
) -> dict[str, object]:
    return memory_reflect_read_only_pack_quality(root, project, task, limit, pack_fn=memory_pack_fn)


def print_memory_reflect(
    root: Path,
    project_name: str,
    since: str,
    task: str,
    limit: int,
    write_report: bool,
    fmt: str,
    memory_reflect_fn: Callable[..., dict[str, object]],
    find_project_fn: Callable[..., Path] = find_project,
    write_report_fn: Callable[..., Path] = write_memory_reflection_report,
    relative_fn: Callable[..., str] = relative,
    print_result_fn: Callable[..., int] = print_memory_reflect_result,
) -> int:
    project = find_project_fn(root, project_name)
    payload = memory_reflect_fn(root, project.name, since=since, task=task, limit=limit)
    if write_report:
        report = write_report_fn(project, payload)
        print(relative_fn(project, report))
        return 1 if payload.get("outcome") == "blocked" else 0
    return print_result_fn(payload, fmt)
