"""Snapshot builder for the Ops Dashboard v2.

Pure-ish functions that turn a workspace + REEFIKI root into a serializable
dict. The frontend reads this via /api/snapshot and renders it.

Read-only by design. No writes to discovered projects, REEFIKI wiki, or raw/.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import stat
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reefiki_core.health import knowledge_health_payload
from reefiki_core.guided_tour import dashboard_guided_tour_payload
from reefiki_core.markdown import as_text
from reefiki_core.memory_status import memory_status, memory_status_has_open
from reefiki_core.process_utils import SUBPROCESS_TIMEOUT_SECONDS
from reefiki_core.review_queues import review_queue_scan, review_queue_summary
from reefiki_core.worktree_status import worktree_status_payload

SCHEMA_VERSION = "ops-dashboard.v2"


def _default_workspace_root() -> Path:
    configured = os.environ.get("REEFIKI_WORKSPACE_ROOT")
    if configured:
        return Path(configured)
    return Path.cwd().parent


def _default_reefiki_root() -> Path:
    configured = os.environ.get("REEFIKI_ROOT")
    if configured:
        return Path(configured)
    return Path.cwd()


DEFAULT_WORKSPACE_ROOT = _default_workspace_root()
DEFAULT_REEFIKI_ROOT = _default_reefiki_root()

FORBIDDEN_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "vendor",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "target",
    ".cache",
    ".vercel",
    "raw",
    "_wiki",
}
SECRET_NAME_PATTERNS = {
    ".env",
    ".env.*",
    "secrets.*",
    "secret.*",
    "credentials.*",
    "id_rsa",
    "id_rsa.pub",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    ".npmrc",
    ".netrc",
}
SECRET_PARTS = {".aws", ".ssh"}
SUSPICIOUS_SECRET_TOKENS = {"secret", "password", "token"}
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    ".java",
    ".cs",
    ".rb",
    ".php",
    ".md",
    ".mdx",
}
PACKAGE_MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
}
NODE_LOCKS = {"pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lockb"}
TEST_MARKER_NAMES = {
    "pytest.ini",
    "tox.ini",
    "vitest.config.ts",
    "vitest.config.js",
    "vitest.config.mjs",
    "jest.config.js",
    "jest.config.ts",
    "playwright.config.ts",
    "playwright.config.js",
}
MAX_METADATA_FILES = 5000
MAX_METADATA_DEPTH = 5


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Git helpers (read-only)
# ---------------------------------------------------------------------------

def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def _git_output(repo: Path, args: list[str]) -> str | None:
    completed = _run_git(repo, args)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = os.lstat(path).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


# ---------------------------------------------------------------------------
# Workspace + repo discovery
# ---------------------------------------------------------------------------

def _resolve_allowed_root(path: Path) -> tuple[Path, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    try:
        resolved = path.expanduser().resolve()
    except OSError as exc:
        raise SystemExit(f"Cannot resolve workspace root: {path}: {exc}") from exc
    if not resolved.exists() or not resolved.is_dir():
        raise SystemExit(f"Workspace root not found: {resolved}")
    return resolved, warnings


def _is_contained(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return resolved == root or root in resolved.parents


def _has_git_marker(path: Path) -> bool:
    return (path / ".git").exists()


def discover_git_repositories(workspace_root: Path) -> tuple[list[Path], list[dict[str, str]]]:
    root, warnings = _resolve_allowed_root(workspace_root)
    repos: list[Path] = []
    for child in sorted(
        (item for item in root.iterdir() if item.is_dir()),
        key=lambda item: item.name.lower(),
    ):
        if not _is_contained(child, root):
            warnings.append(
                {
                    "code": "skipped_outside_root_link",
                    "path": str(child),
                    "message": "Skipped workspace child because it resolves outside workspace root.",
                }
            )
            continue
        if _has_git_marker(child):
            repos.append(child)
    return repos, warnings


# ---------------------------------------------------------------------------
# File / stack detection
# ---------------------------------------------------------------------------

def _is_secret_like(rel_path: str) -> bool:
    parts = [part.lower() for part in rel_path.replace("\\", "/").split("/") if part]
    name = parts[-1] if parts else ""
    if any(part in SECRET_PARTS for part in parts):
        return True
    if any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_NAME_PATTERNS):
        return True
    if Path(name).suffix.lower() in SOURCE_EXTENSIONS:
        return False
    stem = Path(name).stem.lower()
    return any(token in stem for token in SUSPICIOUS_SECRET_TOKENS)


def scan_project_metadata(repo: Path) -> dict[str, Any]:
    files: list[str] = []
    dirs: list[str] = []
    skipped_secret_paths: list[str] = []
    skipped_dirs: Counter[str] = Counter()
    warnings: list[dict[str, str]] = []
    scanned_files = 0

    for dirpath, dirnames, filenames in os.walk(repo, topdown=True, followlinks=False):
        current = Path(dirpath)
        rel_current = current.relative_to(repo).as_posix() if current != repo else ""
        depth = 0 if not rel_current else len(rel_current.split("/"))
        if depth >= MAX_METADATA_DEPTH:
            dirnames[:] = []

        kept_dirs: list[str] = []
        for dirname in dirnames:
            full = current / dirname
            rel_dir = full.relative_to(repo).as_posix()
            if dirname in FORBIDDEN_DIR_NAMES or full.is_symlink() or _is_reparse_point(full):
                skipped_dirs[dirname] += 1
                continue
            dirs.append(rel_dir)
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            full = current / filename
            if full.is_symlink():
                continue
            rel = full.relative_to(repo).as_posix()
            if _is_secret_like(rel):
                skipped_secret_paths.append(rel)
                continue
            files.append(rel)
            scanned_files += 1
            if scanned_files >= MAX_METADATA_FILES:
                warnings.append(
                    {
                        "code": "metadata_file_limit_reached",
                        "message": f"Stopped metadata scan after {MAX_METADATA_FILES} files.",
                    }
                )
                dirnames[:] = []
                break

    return {
        "files": sorted(set(files)),
        "dirs": sorted(set(dirs)),
        "skipped_secret_paths": sorted(set(skipped_secret_paths)),
        "skipped_dirs": dict(sorted(skipped_dirs.items())),
        "warnings": warnings,
    }


def detect_stack(files: set[str], dirs: set[str]) -> list[str]:
    stack: list[str] = []
    if "pyproject.toml" in files or "requirements.txt" in files:
        stack.append("python")
    if "package.json" in files or files.intersection(NODE_LOCKS):
        stack.append("node")
    if "Cargo.toml" in files:
        stack.append("rust")
    if not stack and sum(1 for path in files if path.lower().endswith(".md")) >= 3:
        stack.append("docs-only")
    return stack or ["unknown"]


def detect_tests(files: set[str], dirs: set[str]) -> bool:
    if files.intersection(TEST_MARKER_NAMES):
        return True
    if "tests" in dirs or "test" in dirs:
        return True
    for path in files:
        name = Path(path).name
        parts = path.split("/")
        if "tests" in parts[:-1] or "test" in parts[:-1]:
            return True
        if name.endswith(
            (
                ".test.ts",
                ".test.tsx",
                ".test.js",
                ".test.jsx",
                ".spec.ts",
                ".spec.tsx",
                ".spec.js",
                ".spec.jsx",
                "_test.py",
                "_test.go",
            )
        ):
            return True
    return False


def detect_ci(files: set[str]) -> bool:
    return any(
        path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
        for path in files
    )


# ---------------------------------------------------------------------------
# Git status / inventory
# ---------------------------------------------------------------------------

def _parse_git_status_z(output: str) -> list[str]:
    paths: list[str] = []
    entries = output.split("\0") if output else []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:].replace("\\", "/") if len(entry) > 3 else ""
        if path:
            paths.append(path)
        if "R" in status or "C" in status:
            i += 1
    return sorted(set(paths))


def _git_inventory(repo: Path) -> dict[str, Any]:
    root_output = _git_output(repo, ["rev-parse", "--show-toplevel"])
    if not root_output:
        return {
            "is_git_repo": False,
            "branch": None,
            "head": None,
            "last_activity": None,
            "dirty": False,
            "dirty_paths_count": 0,
            "dirty_paths_sample": [],
            "ahead": None,
            "behind": None,
            "worktree_count": 0,
            "remotes": [],
            "warnings": [{"code": "git_root_missing", "message": "Git root lookup failed."}],
        }

    git_root = Path(root_output).resolve()
    status = _run_git(git_root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    dirty_paths = _parse_git_status_z(status.stdout if status.returncode == 0 else "")
    branch = _git_output(git_root, ["branch", "--show-current"]) or "HEAD"
    head = _git_output(git_root, ["rev-parse", "--short", "HEAD"])
    upstream = _git_output(
        git_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    )
    ahead: int | None = None
    behind: int | None = None
    if upstream and head:
        counts = _git_output(git_root, ["rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        if counts:
            parts = counts.split()
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                behind, ahead = int(parts[0]), int(parts[1])

    # New in v2: last commit timestamp + subject, no network calls.
    last_iso = _git_output(git_root, ["log", "-1", "--format=%cI"])
    last_subject = _git_output(git_root, ["log", "-1", "--format=%s"])
    last_activity: dict[str, str] | None = None
    if last_iso and head:
        last_activity = {
            "iso": last_iso,
            "short_sha": head,
            "subject": last_subject or "",
        }

    remotes_output = _git_output(git_root, ["remote", "-v"]) or ""
    remotes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in remotes_output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        key = (parts[0], parts[1])
        if key in seen:
            continue
        seen.add(key)
        remotes.append({"name": parts[0], "url": parts[1]})

    worktree_output = _git_output(git_root, ["worktree", "list", "--porcelain"]) or ""
    worktree_count = sum(
        1 for line in worktree_output.splitlines() if line.startswith("worktree ")
    )
    warnings = []
    if upstream is None:
        warnings.append({"code": "upstream_missing", "message": "No upstream branch configured."})
    if status.returncode != 0:
        warnings.append({"code": "git_status_failed", "message": "Git status lookup failed."})

    return {
        "is_git_repo": True,
        "branch": branch,
        "head": head,
        "last_activity": last_activity,
        "dirty": bool(dirty_paths),
        "dirty_paths_count": len(dirty_paths),
        "dirty_paths_sample": dirty_paths[:10],
        "ahead": ahead,
        "behind": behind,
        "worktree_count": worktree_count,
        "remotes": remotes,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# REEFIKI mapping
# ---------------------------------------------------------------------------

def _read_connection_marker(repo: Path) -> dict[str, str]:
    marker = repo / ".reefiki"
    if not marker.exists() or not marker.is_file():
        return {}
    try:
        if marker.stat().st_size > 16_384:
            return {"warning": "marker_too_large"}
        text = marker.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"warning": "marker_unreadable"}
    data: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        if key in {"project_name", "REEFIKI_path", "wiki_junction"}:
            data[key] = value.strip()
    return data


def _reefiki_projects(reefiki_root: Path) -> list[Path]:
    projects_dir = reefiki_root / "projects"
    if not projects_dir.exists():
        return []
    return sorted(
        (path for path in projects_dir.iterdir() if path.is_dir() and path.name != "_template"),
        key=lambda item: item.name.lower(),
    )


def _project_catalog(reefiki_root: Path) -> dict[str, Any]:
    projects = _reefiki_projects(reefiki_root)
    by_exact = {path.name: path for path in projects}
    by_lower: dict[str, list[Path]] = {}
    for path in projects:
        by_lower.setdefault(path.name.lower(), []).append(path)
    return {"projects": projects, "by_exact": by_exact, "by_lower": by_lower}


def _catalog_match(name: str, catalog: dict[str, Any]) -> tuple[str | None, Path | None]:
    by_exact: dict[str, Path] = catalog["by_exact"]
    if name in by_exact:
        return "exact", by_exact[name]
    matches = catalog["by_lower"].get(name.lower(), [])
    if len(matches) == 1:
        return "casefold", matches[0]
    if len(matches) > 1:
        return "ambiguous", None
    return None, None


def match_reefiki_mapping(
    project_name: str, marker: dict[str, str], catalog: dict[str, Any]
) -> dict[str, Any]:
    candidates: dict[str, dict[str, str]] = {}
    status, path = _catalog_match(project_name, catalog)
    if path is not None and status == "exact":
        candidates[path.name] = {"source": "exact_folder_name", "project": path.name}

    marker_project = marker.get("project_name", "")
    if marker_project:
        marker_status, marker_path = _catalog_match(marker_project, catalog)
        if marker_path is not None:
            candidates[marker_path.name] = {"source": "connection_marker", "project": marker_path.name}
        elif marker_status == "ambiguous":
            return {
                "mapping_status": "ambiguous",
                "project": None,
                "sources": ["connection_marker"],
                "reason": "marker project name matches multiple REEFIKI projects",
            }

    if len(candidates) > 1:
        return {
            "mapping_status": "ambiguous",
            "project": None,
            "sources": [item["source"] for item in candidates.values()],
            "reason": "workspace folder and connection marker point to different projects",
        }
    if len(candidates) == 1:
        item = next(iter(candidates.values()))
        return {
            "mapping_status": "connected",
            "project": item["project"],
            "sources": [item["source"]],
            "reason": "unique REEFIKI mapping found",
        }

    return {
        "mapping_status": "missing",
        "project": None,
        "sources": [],
        "reason": "no matching REEFIKI project or connection marker",
    }


# ---------------------------------------------------------------------------
# REEFIKI log + status reading
# ---------------------------------------------------------------------------

def _read_safe_text(path: Path, max_bytes: int = 256_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    if path.stat().st_size > max_bytes:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def latest_log_entries(log_path: Path, limit: int = 5) -> list[dict[str, Any]]:
    text = _read_safe_text(log_path, max_bytes=512_000)
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    iso_in_heading: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                if iso_in_heading is not None and "iso" not in current:
                    current["iso"] = iso_in_heading
                entries.append(current)
            heading = line.removeprefix("## ").strip()
            iso_match = re.search(r"\d{4}-\d{2}-\d{2}", heading)
            iso_in_heading = iso_match.group(0) if iso_match else None
            current = {"heading": heading, "lines": []}
            continue
        if current is not None and line.strip():
            current["lines"].append(line.strip())
    if current is not None:
        if iso_in_heading is not None and "iso" not in current:
            current["iso"] = iso_in_heading
        entries.append(current)
    return entries[-limit:]


def _read_connected_project_status(reefiki_root: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    project_name = mapping.get("project")
    if mapping.get("mapping_status") != "connected" or not project_name:
        return {
            "mapping_status": mapping.get("mapping_status"),
            "project": None,
            "wiki_index_exists": False,
            "wiki_log_exists": False,
            "domain_exists": False,
            "agents_md_exists": False,
        }
    project = reefiki_root / "projects" / as_text(project_name)
    return {
        "mapping_status": "connected",
        "project": project.name,
        "path": str(project),
        "wiki_index_exists": (project / "wiki" / "index.md").exists(),
        "wiki_log_exists": (project / "wiki" / "log.md").exists(),
        "domain_exists": (project / "_domain.md").exists(),
        "agents_md_exists": (project / "AGENTS.md").exists(),
    }


def _read_reefiki_project_log(
    reefiki_root: Path, project_name: str | None, limit: int = 5
) -> list[dict[str, Any]]:
    if not project_name:
        return []
    return latest_log_entries(reefiki_root / "projects" / project_name / "wiki" / "log.md", limit=limit)


# ---------------------------------------------------------------------------
# v2: explicit per-project view, KPI, ReefikiControl
# ---------------------------------------------------------------------------

def _activity_kind(project: dict[str, Any]) -> str:
    if project.get("is_codex_branch"):
        return "codex_branch"
    if project.get("dirty"):
        return "dirty"
    if project.get("last_activity"):
        return "active"
    if project.get("warnings"):
        return "warning"
    return "quiet"


def _safe_payload(name: str, fn: Any) -> dict[str, Any]:
    try:
        return {"outcome": "pass", "payload": fn()}
    except SystemExit as exc:
        return {"outcome": "error", "error": f"{name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - dashboard must report partial failures.
        return {"outcome": "error", "error": f"{name}: {exc}"}


def _reefiki_control(reefiki_root: Path) -> dict[str, Any]:
    tasks_text = _read_safe_text(reefiki_root / "TASKS.md", max_bytes=1_000_000)
    roadmap_text = _read_safe_text(reefiki_root / "ROADMAP.md", max_bytes=1_000_000)
    tasks = _parse_tasks_md(tasks_text)
    roadmap = _parse_roadmap_md(roadmap_text)
    reefiki_project = reefiki_root / "projects" / "reefiki"
    health = _safe_payload("health", lambda: knowledge_health_payload(reefiki_project))
    review = _safe_payload(
        "review-queues", lambda: review_queue_summary(review_queue_scan(reefiki_project), limit=5)
    )
    worktrees = _safe_payload(  # noqa: F841 - kept for future surfacing
        "worktree-status", lambda: worktree_status_payload(reefiki_root, "origin/main")
    )
    log_path = reefiki_project / "wiki" / "log.md"
    log_entries = latest_log_entries(log_path, limit=10)
    last_log = log_entries[-1] if log_entries else None
    return {
        "roadmap_phase": roadmap["current_phase"],
        "current_sprint": tasks["current_sprint"],
        "task_counts": tasks["task_counts"],
        "active_tasks": tasks["active_tasks"][:5],
        "next_tasks": tasks["next_tasks"][:5],
        "t111_status": (tasks["t111_package_split_status"] or {}).get("status"),
        "health_outcome": _health_outcome(health),
        "review_queue_top": (review.get("payload") or {}).get("items", [])[:5]
        if review.get("outcome") == "pass"
        else [],
        "memory_golden_outcome": "skipped",  # never call from dashboard
        "last_log_heading": (last_log or {}).get("heading"),
        "last_log_iso": (last_log or {}).get("iso"),
        "latest_log_entries": log_entries,
    }


def _memory_dashboard_status(reefiki_root: Path) -> dict[str, Any]:
    return _safe_payload(
        "memory-status",
        lambda: _memory_dashboard_payload(reefiki_root),
    )


def _memory_dashboard_payload(reefiki_root: Path) -> dict[str, Any]:
    payload = memory_status(reefiki_root, "reefiki")
    payload["has_open"] = memory_status_has_open(payload)
    payload["dashboard_limits"] = {
        "memory_golden": "skipped",
        "graphify_rebuild": "skipped",
        "provider_lookup": "skipped",
    }
    return payload


def _health_outcome(health: dict[str, Any]) -> str:
    if health.get("outcome") != "pass":
        return "unknown"
    payload = health.get("payload") or {}
    status = (payload.get("status") or "").lower()
    if status in ("ok", "pass", "healthy"):
        return "pass"
    if status in ("warn", "warning", "degraded"):
        return "warn"
    if status in ("fail", "error", "bad"):
        return "fail"
    return "unknown"


def _parse_tasks_md(text: str) -> dict[str, Any]:
    sprints: list[dict[str, Any]] = []
    current_sprint: dict[str, Any] | None = None
    current_task: dict[str, Any] | None = None
    task_counts = {"done": 0, "todo": 0, "active": 0}
    tasks_by_id: dict[str, dict[str, Any]] = {}

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## Sprint "):
            current_sprint = {"heading": line.removeprefix("## ").strip(), "tasks": []}
            sprints.append(current_sprint)
            current_task = None
            continue
        task_match = re.match(r"^- \[(?P<mark>[ x~])\] \*\*(?P<id>T-\d+)\*\* (?P<title>.+)$", line)
        if task_match:
            mark = task_match.group("mark")
            status = "done" if mark == "x" else "active" if mark == "~" else "todo"
            task_counts[status] += 1
            current_task = {
                "id": task_match.group("id"),
                "title": task_match.group("title").strip(),
                "status": status,
                "progress": [],
                "closeout": [],
            }
            tasks_by_id[current_task["id"]] = current_task
            if current_sprint is not None:
                current_sprint["tasks"].append(current_task)
            continue
        if current_task is not None and line.strip().startswith("- "):
            detail = line.strip().removeprefix("- ").strip()
            lowered = detail.lower()
            if "progress" in lowered:
                current_task["progress"].append(detail)
            if "closeout" in lowered:
                current_task["closeout"].append(detail)

    active_tasks = [task for task in tasks_by_id.values() if task["status"] == "active"]
    todo_tasks = [task for task in tasks_by_id.values() if task["status"] == "todo"]
    return {
        "task_counts": task_counts,
        "current_sprint": sprints[-1]["heading"] if sprints else None,
        "active_tasks": active_tasks[:5],
        "next_tasks": todo_tasks[:5],
        "t111_package_split_status": tasks_by_id.get("T-111"),
    }


def _parse_roadmap_md(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    current_phase: str | None = None
    summary_lines: list[str] = []
    for idx, line in enumerate(lines):
        if line.startswith("#### Phase ") and ("АКТИВНА" in line or "ACTIVE" in line.upper()):
            current_phase = line.removeprefix("#### ").strip()
            for follow in lines[idx + 1 : idx + 10]:
                stripped = follow.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    break
                summary_lines.append(stripped)
                if len(summary_lines) >= 3:
                    break
            break
    if current_phase is None:
        for line in lines:
            if line.startswith("#### Phase "):
                current_phase = line.removeprefix("#### ").strip()
                break
    return {
        "current_phase": current_phase,
        "current_stage_summary": " ".join(summary_lines)[:600] if summary_lines else "",
    }


# ---------------------------------------------------------------------------
# Project view
# ---------------------------------------------------------------------------

def inspect_workspace_project(
    repo: Path, reefiki_root: Path, catalog: dict[str, Any]
) -> dict[str, Any]:
    metadata = scan_project_metadata(repo)
    files = set(metadata["files"])
    dirs = set(metadata["dirs"])
    inventory = _git_inventory(repo)
    marker = _read_connection_marker(repo)
    mapping = match_reefiki_mapping(repo.name, marker, catalog)
    reefiki_status = _read_connected_project_status(reefiki_root, mapping)
    latest_entries = _read_reefiki_project_log(
        reefiki_root, as_text(mapping.get("project")) or None, limit=3
    )

    gates = {
        "agents_md": "AGENTS.md" in files,
        "ci": detect_ci(files),
        "tests": detect_tests(files, dirs),
        "package_manifest": bool(files.intersection(PACKAGE_MANIFESTS | NODE_LOCKS)),
    }

    is_codex = bool(inventory["branch"] and inventory["branch"].startswith("codex/"))

    warnings: list[dict[str, str]] = [*metadata["warnings"], *inventory["warnings"]]
    if metadata["skipped_secret_paths"]:
        warnings.append(
            {
                "code": "secret_like_paths_skipped",
                "message": f"Skipped {len(metadata['skipped_secret_paths'])} secret-like path(s).",
            }
        )
    if metadata["skipped_dirs"]:
        skipped_names = list(metadata["skipped_dirs"])[:10]
        skipped_suffix = (
            ""
            if len(metadata["skipped_dirs"]) <= 10
            else f" and {len(metadata['skipped_dirs']) - 10} more"
        )
        warnings.append(
            {
                "code": "forbidden_dirs_skipped",
                "message": f"Skipped forbidden directories: {', '.join(skipped_names)}{skipped_suffix}.",
            }
        )
    if mapping.get("mapping_status") == "ambiguous":
        warnings.append(
            {"code": "reefiki_mapping_ambiguous", "message": as_text(mapping.get("reason"))}
        )

    project = {
        "name": repo.name,
        "path": str(repo),
        "is_git_repo": inventory["is_git_repo"],
        "branch": inventory["branch"],
        "head": inventory["head"],
        "last_activity": inventory["last_activity"],
        "is_codex_branch": is_codex,
        "dirty": inventory["dirty"],
        "dirty_paths_count": inventory["dirty_paths_count"],
        "dirty_paths_sample": inventory["dirty_paths_sample"],
        "ahead": inventory["ahead"],
        "behind": inventory["behind"],
        "worktree_count": inventory["worktree_count"],
        "remotes": inventory["remotes"],
        "detected_stack": detect_stack(files, dirs),
        "gates": gates,
        "detected_files": {
            "manifests": sorted(
                path for path in files if Path(path).name in PACKAGE_MANIFESTS
                or Path(path).name in NODE_LOCKS
            ),
            "ci": sorted(path for path in files if path.startswith(".github/workflows/"))[:10],
            "test_markers": sorted(
                path
                for path in files
                if Path(path).name in TEST_MARKER_NAMES or "/tests/" in f"/{path}"
            )[:10],
            "agent": sorted(
                path
                for path in files
                if Path(path).name in {"AGENTS.md", "CLAUDE.md", ".cursorrules", ".clinerules"}
            )[:10],
        },
        "readiness": _readiness(inventory, gates, mapping, warnings),
        "reefiki_mapping": mapping,
        "reefiki_status": reefiki_status,
        "latest_log_entries": latest_entries,
        "warnings": warnings,
    }
    project["activity_kind"] = _activity_kind(project)
    return project


def _readiness(
    inventory: dict[str, Any],
    gates: dict[str, bool],
    mapping: dict[str, Any],
    warnings: list[dict[str, str]],
) -> str:
    notes: list[str] = []
    if inventory.get("dirty"):
        notes.append("dirty worktree")
    if not gates["agents_md"]:
        notes.append("missing AGENTS.md")
    if not gates["ci"]:
        notes.append("missing CI")
    if not gates["tests"]:
        notes.append("missing tests")
    if mapping.get("mapping_status") == "connected":
        notes.append("REEFIKI connected")
    if warnings:
        notes.append(f"{len(warnings)} warning(s)")
    return "; ".join(notes) if notes else "ready"


# ---------------------------------------------------------------------------
# KPI + activity feed (v2 selectors, pure)
# ---------------------------------------------------------------------------

def derive_kpi(projects: list[dict[str, Any]]) -> dict[str, int]:
    total = len(projects)
    clean = sum(1 for p in projects if not p.get("dirty"))
    dirty = sum(1 for p in projects if p.get("dirty"))
    codex_branches = sum(1 for p in projects if p.get("is_codex_branch"))
    connected = sum(
        1
        for p in projects
        if (p.get("reefiki_mapping") or {}).get("mapping_status") == "connected"
    )
    warnings = sum(1 for p in projects if p.get("warnings"))
    no_tests = sum(1 for p in projects if not (p.get("gates") or {}).get("tests"))
    no_agents_md = sum(1 for p in projects if not (p.get("gates") or {}).get("agents_md"))
    return {
        "total": total,
        "clean": clean,
        "dirty": dirty,
        "codex_branches": codex_branches,
        "connected": connected,
        "warnings": warnings,
        "no_tests": no_tests,
        "no_agents_md": no_agents_md,
    }


def derive_current_work(projects: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    def sort_key(p: dict[str, Any]) -> tuple[int, str]:
        la = p.get("last_activity") or {}
        iso = la.get("iso") or ""
        # Sort by iso desc; no iso → last (z'').
        return (0 if iso else 1, "-" + iso if iso else p["name"].lower())

    sorted_projects = sorted(
        [p for p in projects if p.get("last_activity") or p.get("dirty") or p.get("warnings")],
        key=sort_key,
    )
    return sorted_projects[:limit]


def derive_activity_feed(
    projects: list[dict[str, Any]],
    reefiki_log: list[dict[str, Any]],
    limit: int = 30,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for p in projects:
        la = p.get("last_activity") or {}
        if la.get("iso"):
            events.append(
                {
                    "kind": "commit",
                    "project": p["name"],
                    "iso": la["iso"],
                    "title": f"{la.get('short_sha', '?')} {la.get('subject', '')}".strip(),
                }
            )
        if p.get("dirty"):
            events.append(
                {
                    "kind": "dirty",
                    "project": p["name"],
                    "iso": la.get("iso") if la else None,
                    "title": f"Dirty worktree: {p.get('dirty_paths_count', 0)} path(s)",
                }
            )
        if p.get("is_codex_branch"):
            events.append(
                {
                    "kind": "codex_branch",
                    "project": p["name"],
                    "iso": la.get("iso") if la else None,
                    "title": f"Agent branch: {p.get('branch')}",
                }
            )
        for entry in p.get("latest_log_entries") or []:
            if entry.get("iso"):
                events.append(
                    {
                        "kind": "reefiki_log",
                        "project": p["name"],
                        "iso": entry["iso"],
                        "title": entry.get("heading", ""),
                    }
                )
        if p.get("warnings"):
            events.append(
                {
                    "kind": "warning",
                    "project": p["name"],
                    "iso": la.get("iso") if la else None,
                    "title": f"{len(p['warnings'])} warning(s): {p['warnings'][0]['code']}",
                }
            )
    for entry in reefiki_log:
        if entry.get("iso"):
            events.append(
                {
                    "kind": "reefiki_log",
                    "project": "reefiki",
                    "iso": entry["iso"],
                    "title": entry.get("heading", ""),
                }
            )
    events.sort(key=lambda e: e.get("iso") or "", reverse=True)
    return events[:limit]


def _is_synthetic_demo_workspace(root: Path) -> bool:
    return (root / ".reefiki-dashboard-demo").is_file()


# ---------------------------------------------------------------------------
# Top-level: build_snapshot, print_ops_dashboard
# ---------------------------------------------------------------------------

def build_snapshot(workspace_root: Path, reefiki_root: Path) -> dict[str, Any]:
    root, root_warnings = _resolve_allowed_root(workspace_root)
    catalog = _project_catalog(reefiki_root)
    repos, discovery_warnings = discover_git_repositories(root)
    projects = [inspect_workspace_project(repo, reefiki_root, catalog) for repo in repos]
    warnings = [*root_warnings, *discovery_warnings]
    control = _reefiki_control(reefiki_root)
    memory = _memory_dashboard_status(reefiki_root)
    reefiki_log = control.get("latest_log_entries") or []
    if _is_synthetic_demo_workspace(root):
        reefiki_log = []
        control = {
            **control,
            "last_log_heading": None,
            "last_log_iso": None,
            "latest_log_entries": [],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "workspace_root": str(root),
        "reefiki_root": str(reefiki_root),
        "workspace_warnings": warnings,
        "kpi": derive_kpi(projects),
        "current_work": derive_current_work(projects, limit=5),
        "activity_feed": derive_activity_feed(projects, reefiki_log, limit=30),
        "projects": projects,
        "reefiki": control,
        "memory": memory,
        "tour": dashboard_guided_tour_payload(root, reefiki_root, projects),
    }


def print_ops_dashboard(workspace_root: Path, reefiki_root: Path, fmt: str) -> int:
    snapshot = build_snapshot(workspace_root, reefiki_root)
    if fmt == "json":
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))
        return 0
    kpi = snapshot["kpi"]
    print(f"Codex Workspace Ops Board v2: {snapshot['workspace_root']}")
    print(
        f"Projects: total={kpi['total']} clean={kpi['clean']} "
        f"dirty={kpi['dirty']} codex={kpi['codex_branches']} "
        f"connected={kpi['connected']} warnings={kpi['warnings']}"
    )
    for project in snapshot["projects"]:
        dirty = "dirty" if project["dirty"] else "clean"
        mapping = project["reefiki_mapping"]["mapping_status"]
        stack = ",".join(project["detected_stack"])
        last = (project.get("last_activity") or {}).get("iso", "no-activity")
        print(
            f"- {project['name']}: {dirty} branch={project['branch']} stack={stack} "
            f"reefiki={mapping} last={last}"
        )
    return 0
