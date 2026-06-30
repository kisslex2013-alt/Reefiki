from __future__ import annotations

import ast
import json
import tomllib
from collections import Counter, defaultdict
from pathlib import Path


PYTEST_BUILTIN_MARKERS = {
    "filterwarnings",
    "parametrize",
    "skip",
    "skipif",
    "tryfirst",
    "trylast",
    "usefixtures",
    "xfail",
}


def _registered_markers(pyproject_path: Path) -> dict[str, str]:
    config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    markers = config.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
    registry: dict[str, str] = {}
    for entry in markers:
        name, _, description = entry.partition(":")
        marker = name.strip()
        if marker:
            registry[marker] = description.strip()
    return registry


def _is_pytest_mark(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _is_pytest_mark(node.func)
    if not isinstance(node, ast.Attribute):
        return None
    value = node.value
    if (
        isinstance(value, ast.Attribute)
        and value.attr == "mark"
        and isinstance(value.value, ast.Name)
        and value.value.id == "pytest"
    ):
        return node.attr
    return None


def _markers_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    markers: set[str] = set()
    for node in ast.walk(tree):
        marker = _is_pytest_mark(node)
        if marker:
            markers.add(marker)
    return markers


def _test_files(repo: Path) -> list[Path]:
    tests_root = repo / "tests"
    if not tests_root.exists():
        return []
    return sorted(
        path
        for path in tests_root.rglob("*.py")
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    )


def _relative(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def build_test_observability_payload(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    registry = _registered_markers(repo / "pyproject.toml")
    registered = set(registry)
    marker_usage: Counter[str] = Counter()
    builtin_usage: Counter[str] = Counter()
    unknown_usage: defaultdict[str, list[str]] = defaultdict(list)
    file_markers: dict[str, list[str]] = {}
    unmarked_files: list[str] = []
    parse_errors: list[dict[str, str]] = []

    for path in _test_files(repo):
        relative_path = _relative(repo, path)
        try:
            markers = _markers_in_file(path)
        except SyntaxError as exc:
            parse_errors.append(
                {
                    "path": relative_path,
                    "error": f"{exc.__class__.__name__}: {exc.msg}",
                }
            )
            continue

        custom_markers = sorted(marker for marker in markers if marker in registered)
        builtin_markers = sorted(marker for marker in markers if marker in PYTEST_BUILTIN_MARKERS)
        unknown_markers = sorted(markers - registered - PYTEST_BUILTIN_MARKERS)

        file_markers[relative_path] = custom_markers
        if not custom_markers:
            unmarked_files.append(relative_path)
        marker_usage.update(custom_markers)
        builtin_usage.update(builtin_markers)
        for marker in unknown_markers:
            unknown_usage[marker].append(relative_path)

    unknown_markers = {
        marker: sorted(paths)
        for marker, paths in sorted(unknown_usage.items())
    }
    outcome = "block" if unknown_markers or parse_errors else "pass"

    recommended_commands = [
        {
            "name": "full",
            "command": "python -m pytest -q",
            "use_when": "release or broad core changes",
        },
        {
            "name": "fast",
            "command": 'python -m pytest -q -m "not slow"',
            "use_when": "normal inner-loop verification",
        },
        *[
            {
                "name": marker,
                "command": f"python -m pytest -q -m {marker}",
                "use_when": registry[marker] or f"{marker} lane",
            }
            for marker in sorted(registry)
        ],
        {
            "name": "durations",
            "command": "python -m pytest -q --durations=20",
            "use_when": "slow-test visibility without a coverage dependency",
        },
    ]

    return {
        "outcome": outcome,
        "registered_markers": [
            {"name": marker, "description": registry[marker]}
            for marker in sorted(registry)
        ],
        "marker_usage": dict(sorted(marker_usage.items())),
        "builtin_marker_usage": dict(sorted(builtin_usage.items())),
        "unmarked_files": sorted(unmarked_files),
        "unknown_markers": unknown_markers,
        "parse_errors": parse_errors,
        "file_markers": dict(sorted(file_markers.items())),
        "recommended_commands": recommended_commands,
        "coverage": {
            "default_gate": False,
            "reason": "Coverage is intentionally not a default gate; marker lanes and durations keep QA observable without adding pytest-cov.",
        },
        "summary": {
            "test_files": len(file_markers) + len(parse_errors),
            "registered_marker_count": len(registry),
            "unmarked_file_count": len(unmarked_files),
            "unknown_marker_count": len(unknown_markers),
            "parse_error_count": len(parse_errors),
        },
    }


def print_test_observability(repo: Path, fmt: str) -> int:
    payload = build_test_observability_payload(repo)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload["summary"]
        assert isinstance(summary, dict)
        print(f"outcome: {payload['outcome']}")
        print(f"test_files: {summary['test_files']}")
        print(f"registered_markers: {summary['registered_marker_count']}")
        print(f"unmarked_files: {summary['unmarked_file_count']}")
        print(f"unknown_markers: {summary['unknown_marker_count']}")
        print("marker_usage:")
        marker_usage = payload["marker_usage"]
        assert isinstance(marker_usage, dict)
        if marker_usage:
            for marker, count in marker_usage.items():
                print(f"  {marker}: {count}")
        else:
            print("  none")
        if payload["unknown_markers"]:
            print("unknown_marker_files:")
            unknown_markers = payload["unknown_markers"]
            assert isinstance(unknown_markers, dict)
            for marker, paths in unknown_markers.items():
                print(f"  {marker}: {', '.join(paths)}")
        print("coverage_default_gate: false")
        print("next: use marker lanes or --durations=20 before adding new test dependencies")
    return 1 if payload["outcome"] == "block" else 0
