from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

try:
    from reefiki_memory import AccessBoundaryContext, PolicySafetyLayer
except ModuleNotFoundError:  # pragma: no cover - used when imported as scripts.reefiki_core in tests
    from scripts.reefiki_memory import AccessBoundaryContext, PolicySafetyLayer

from .file_utils import numbered_path, slugify, write_new_text
from .project_paths import relative


IMPORT_SCHEMA_VERSION = "reefiki.import.v1"
IMPORT_SOURCE_KINDS = ("markdown", "obsidian", "logseq")
DEFAULT_MAX_FILES = 100
MAX_IMPORT_FILE_BYTES = 1_000_000
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".obsidian",
    ".trash",
    ".cache",
    "__pycache__",
    "node_modules",
    "vendor",
    "build",
    "dist",
    "target",
}


def _display_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _project_problem(project: Path) -> str | None:
    if not project.exists():
        return "project_missing"
    if not project.is_dir():
        return "project_not_directory"
    for required in ["inbox", "wiki"]:
        if not (project / required).is_dir():
            return f"project_missing_{required}"
    return None


def _source_problem(source: Path) -> str | None:
    if not source.exists():
        return "source_missing"
    if not (source.is_dir() or source.is_file()):
        return "source_not_supported"
    if source.is_file() and source.suffix.lower() != ".md":
        return "source_not_markdown"
    return None


def _iter_markdown_candidates(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    candidates: list[Path] = []
    for path in sorted(source.rglob("*.md")):
        if not path.is_file():
            continue
        try:
            relative_path = path.relative_to(source)
        except ValueError:
            continue
        if any(part.lower() in SKIP_DIRS for part in relative_path.parts[:-1]):
            continue
        candidates.append(path)
    return candidates


def _relative_source_path(path: Path, source_root: Path) -> str:
    try:
        return path.relative_to(source_root).as_posix()
    except ValueError:
        return path.name


def _destination_for(project: Path, source_relative: str, reserved: set[str]) -> Path:
    stem = slugify(Path(source_relative).with_suffix("").as_posix())
    base = project / "inbox" / f"{stem}.md"
    counter = 1
    while True:
        candidate = numbered_path(base, counter)
        normalized = candidate.relative_to(project).as_posix()
        if not candidate.exists() and normalized not in reserved:
            reserved.add(normalized)
            return candidate
        counter += 1


def _policy_result(content: str, source_relative: str) -> tuple[bool, str | None]:
    boundary = AccessBoundaryContext(
        project="import",
        allowed_scopes=[],
        forbidden_scopes=[],
        visibility="private",
    )
    result = PolicySafetyLayer().preflight(
        boundary,
        operation="import",
        content=content,
        paths=[source_relative],
    )
    if result.outcome == "pass":
        return True, None
    if "secret_like_content" in result.blocking_reasons:
        return False, "secret_like_content"
    if "secret_like_path" in result.blocking_reasons:
        return False, "secret_like_path"
    return False, result.blocking_reasons[0] if result.blocking_reasons else "blocked"


def _append_import_log(project: Path, source: Path, source_kind: str, imported_count: int, skipped_count: int) -> None:
    log = project / "wiki" / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"\n## [{date.today().isoformat()}] /import | {source_kind} {source.name} -> inbox "
            f"({imported_count} imported, {skipped_count} skipped)\n"
        )


def _next_actions(project: Path, skipped: list[dict[str, str]]) -> list[str]:
    actions: list[str] = []
    skipped_reasons = {item["reason"] for item in skipped}
    if skipped_reasons & {"secret_like_content", "secret_like_path"}:
        actions.append(
            "Create a redacted copy of secret-like notes before importing; do not import credentials or raw private logs."
        )
    if skipped:
        actions.append("Review skipped files before increasing the import scope.")
    actions.extend(
        [
            f"Run `reefiki --project {project} status`.",
            "Run `/process` or ask an agent to process the inbox before relying on these notes as durable wiki knowledge.",
        ]
    )
    return actions


def markdown_import_payload(
    project: Path,
    source: Path,
    *,
    source_kind: str = "markdown",
    dry_run: bool = False,
    max_files: int = DEFAULT_MAX_FILES,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    source = source.expanduser().resolve()
    if source_kind not in IMPORT_SOURCE_KINDS:
        return {
            "schema_version": IMPORT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "invalid_source_kind",
            "project": _display_path(project),
            "source": {"path": _display_path(source), "kind": source_kind},
            "dry_run": dry_run,
            "candidate_count": 0,
            "imported_count": 0,
            "skipped_count": 0,
            "imported": [],
            "skipped": [],
            "created_paths": [],
            "next_actions": [f"Use one of: {', '.join(IMPORT_SOURCE_KINDS)}."],
        }
    project_problem = _project_problem(project)
    if project_problem:
        return {
            "schema_version": IMPORT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": project_problem,
            "project": _display_path(project),
            "source": {"path": _display_path(source), "kind": source_kind},
            "dry_run": dry_run,
            "candidate_count": 0,
            "imported_count": 0,
            "skipped_count": 0,
            "imported": [],
            "skipped": [],
            "created_paths": [],
            "next_actions": ["Run reefiki init or choose an existing project root with inbox/ and wiki/."],
        }
    source_problem = _source_problem(source)
    if source_problem:
        return {
            "schema_version": IMPORT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": source_problem,
            "project": _display_path(project),
            "source": {"path": _display_path(source), "kind": source_kind},
            "dry_run": dry_run,
            "candidate_count": 0,
            "imported_count": 0,
            "skipped_count": 0,
            "imported": [],
            "skipped": [],
            "created_paths": [],
            "next_actions": ["Choose a markdown file or a folder containing .md files."],
        }
    source_root = source if source.is_dir() else source.parent
    candidates = _iter_markdown_candidates(source)
    if not candidates:
        return {
            "schema_version": IMPORT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "no_markdown_files",
            "project": _display_path(project),
            "source": {"path": _display_path(source), "kind": source_kind},
            "dry_run": dry_run,
            "candidate_count": 0,
            "imported_count": 0,
            "skipped_count": 0,
            "imported": [],
            "skipped": [],
            "created_paths": [],
            "next_actions": ["Point import at a markdown vault or a single .md file."],
        }
    if max_files < 1:
        return {
            "schema_version": IMPORT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "invalid_max_files",
            "project": _display_path(project),
            "source": {"path": _display_path(source), "kind": source_kind},
            "dry_run": dry_run,
            "candidate_count": len(candidates),
            "imported_count": 0,
            "skipped_count": 0,
            "imported": [],
            "skipped": [],
            "created_paths": [],
            "next_actions": ["Use --max-files with a positive integer."],
        }
    if len(candidates) > max_files:
        return {
            "schema_version": IMPORT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "too_many_files",
            "project": _display_path(project),
            "source": {"path": _display_path(source), "kind": source_kind},
            "dry_run": dry_run,
            "candidate_count": len(candidates),
            "max_files": max_files,
            "imported_count": 0,
            "skipped_count": 0,
            "imported": [],
            "skipped": [],
            "created_paths": [],
            "next_actions": ["Review the source folder, then rerun with a higher --max-files if this batch is intended."],
        }

    imported: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    created: list[Path] = []
    reserved_destinations: set[str] = set()
    for candidate in candidates:
        source_relative = _relative_source_path(candidate, source_root)
        if candidate.is_symlink():
            skipped.append({"source_path": source_relative, "reason": "symlink"})
            continue
        try:
            size = candidate.stat().st_size
        except OSError:
            skipped.append({"source_path": source_relative, "reason": "stat_failed"})
            continue
        if size > MAX_IMPORT_FILE_BYTES:
            skipped.append({"source_path": source_relative, "reason": "too_large"})
            continue
        content = candidate.read_text(encoding="utf-8", errors="replace")
        ok, reason = _policy_result(content, source_relative)
        if not ok:
            skipped.append({"source_path": source_relative, "reason": reason or "blocked"})
            continue
        destination = _destination_for(project, source_relative, reserved_destinations)
        imported.append(
            {
                "source_path": source_relative,
                "destination": relative(project, destination),
            }
        )
        if not dry_run:
            write_new_text(destination, content)
            created.append(destination)

    if not dry_run and imported:
        _append_import_log(project, source, source_kind, len(imported), len(skipped))
        created.append(project / "wiki" / "log.md")

    if imported:
        outcome = "warn" if skipped else "pass"
        reason = "some_files_skipped" if skipped else None
    else:
        outcome = "block"
        reason = skipped[0]["reason"] if skipped else "no_importable_files"
    return {
        "schema_version": IMPORT_SCHEMA_VERSION,
        "outcome": outcome,
        "reason": reason,
        "project": _display_path(project),
        "source": {"path": _display_path(source), "kind": source_kind},
        "dry_run": dry_run,
        "candidate_count": len(candidates),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped,
        "created_paths": sorted({relative(project, path) for path in created}),
        "next_actions": _next_actions(project, skipped),
    }


def print_markdown_import(
    project: Path,
    source: str,
    source_kind: str,
    dry_run: bool,
    max_files: int,
    fmt: str,
) -> int:
    payload = markdown_import_payload(
        project,
        Path(source),
        source_kind=source_kind,
        dry_run=dry_run,
        max_files=max_files,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"import: {payload['outcome']}")
        if payload.get("reason"):
            print(f"- reason: {payload['reason']}")
        print(f"- source: {payload['source']['path']}")
        print(f"- imported: {payload['imported_count']}")
        print(f"- skipped: {payload['skipped_count']}")
        for item in payload.get("imported", []):
            print(f"- saved: {item['source_path']} -> {item['destination']}")
        for item in payload.get("skipped", []):
            print(f"- skipped: {item['source_path']} ({item['reason']})")
        for action in payload["next_actions"]:
            print(f"- next: {action}")
    return 0 if payload["outcome"] in {"pass", "warn"} else 1
