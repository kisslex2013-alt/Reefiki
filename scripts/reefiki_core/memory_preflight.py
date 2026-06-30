from __future__ import annotations

import json

try:
    from reefiki_memory import AccessBoundaryContext, PolicySafetyLayer
except ModuleNotFoundError:  # pragma: no cover - package import fallback for tests
    from scripts.reefiki_memory import AccessBoundaryContext, PolicySafetyLayer


def memory_preflight(
    project: str,
    visibility: str,
    operation: str,
    content: str,
    paths: list[str],
) -> dict[str, object]:
    cross_project_forbidden = [
        scope for scope in ["projects/metrica", "projects/hermes"]
        if scope != f"projects/{project}"
    ]
    boundary = AccessBoundaryContext(
        project=project,
        allowed_scopes=[f"projects/{project}"],
        forbidden_scopes=[*cross_project_forbidden, "secrets", "raw"],
        visibility=visibility,
    )
    return PolicySafetyLayer().preflight(
        boundary,
        operation=operation,
        content=content,
        paths=paths,
    ).to_dict()


def memory_global_strict_preflight(
    project: str,
    visibility: str,
    operation: str,
    content: str,
    paths: list[str],
) -> dict[str, object]:
    boundary = AccessBoundaryContext(
        project=project,
        allowed_scopes=[f"projects/{project}"],
        forbidden_scopes=["projects/metrica", "projects/hermes", "secrets", "raw"],
        visibility=visibility,
    )
    return PolicySafetyLayer().preflight(
        boundary,
        operation=operation,
        content=content,
        paths=paths,
    ).to_dict()


def print_memory_preflight(
    project: str,
    visibility: str,
    operation: str,
    content: str,
    paths: list[str],
    fmt: str,
) -> int:
    result = memory_preflight(
        project=project,
        visibility=visibility,
        operation=operation,
        content=content,
        paths=paths,
    )
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"outcome: {result['outcome']}")
        if result["blocking_reasons"]:
            print(f"blocking_reasons: {', '.join(result['blocking_reasons'])}")
        if result["warnings"]:
            print(f"warnings: {', '.join(result['warnings'])}")
    return 1 if result["outcome"] == "block" else 0
