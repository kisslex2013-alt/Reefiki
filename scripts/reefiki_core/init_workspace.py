from __future__ import annotations

import json
import os
import subprocess
from datetime import date
from pathlib import Path

from .connect_check import connect_check_payload
from .index_search import build_index
from .repo_paths import normalize_target_project_name


INIT_SCHEMA_VERSION = "reefiki.init.v1"
PROJECT_PROFILES = ("product", "agent_surface", "knowledge_domain", "reefiki_core")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
FORBIDDEN_PROJECT_NAME_CHARS = set('<>:"|?*')


def _display_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _init_project_name_problem(project_name: str) -> str | None:
    if any(ord(char) < 32 or ord(char) == 127 for char in project_name):
        return "project name contains control characters"
    if any(char in FORBIDDEN_PROJECT_NAME_CHARS for char in project_name):
        return "project name contains characters that are unsafe in folder names"
    if project_name.endswith("."):
        return "project name must not end with a dot"
    if project_name.upper() in WINDOWS_RESERVED_NAMES:
        return "project name is reserved on Windows"
    return None


def _write_text(path: Path, content: str, created: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    created.append(path)


def _overview(title: str) -> str:
    return f"# {title}\n\nStarter overview for this section.\n"


def _project_files(project: Path, project_name: str, title: str, profile: str) -> dict[Path, str]:
    today = date.today().isoformat()
    return {
        project / "AGENTS.md": (
            f"# {title}\n\n"
            "Use the project-level REEFIKI rules from this workspace. Keep raw sources immutable, "
            "append to `wiki/log.md`, and store durable knowledge in typed wiki pages.\n"
        ),
        project / "_domain.md": (
            "---\n"
            'schema_version: "1.0"\n'
            "---\n\n"
            "# Domain\n\n"
            f"- project_name: {project_name}\n"
            f"- profile: {profile}\n"
            f"- title: {title}\n\n"
            "This project was created by `reefiki init` as a safe first-run workspace.\n"
        ),
        project / ".gitignore": (
            "# REEFIKI local search/cache state\n"
            ".reefiki/\n"
        ),
        project / "inbox" / ".gitkeep": "",
        project / "raw" / ".gitkeep": "",
        project / "seen" / ".gitkeep": "",
        project / "wiki" / "concepts" / "_overview.md": _overview("Concepts"),
        project / "wiki" / "decisions" / "_overview.md": _overview("Decisions"),
        project / "wiki" / "entities" / "_overview.md": _overview("Entities"),
        project / "wiki" / "skills" / "_overview.md": _overview("Skills"),
        project / "wiki" / "sources" / "_overview.md": _overview("Sources"),
        project / "wiki" / "synthesis" / "_overview.md": _overview("Synthesis"),
        project / "wiki" / "concepts" / "first-run-memory.md": (
            "---\n"
            "id: first-run-memory\n"
            "type: concept\n"
            'title: "First-run memory workspace"\n'
            "tags: [first-run, onboarding]\n"
            "useful_when:\n"
            '  - "checking that reefiki init created a usable local memory project"\n'
            f"date_added: {today}\n"
            "use_count: 0\n"
            "last_used: null\n"
            "---\n\n"
            "# First-run memory workspace\n\n"
            "`reefiki init` creates a local markdown wiki project that can be checked with doctor, "
            "searched locally, and connected to a code project later.\n"
        ),
        project / "wiki" / "index.md": (
            "# Index\n\n"
            f"Last updated: {today}\n"
            "Total pages: 1\n\n"
            "## Sources\n"
            "## Entities\n"
            "## Concepts\n\n"
            "### first-run-memory\n"
            "- type: concept\n"
            "- tags: [first-run, onboarding]\n"
            '- useful_when: ["checking that reefiki init created a usable local memory project"]\n'
            "- file: wiki/concepts/first-run-memory.md\n"
            f"- date_added: {today}\n"
            "- use_count: 0\n\n"
            "## Synthesis\n"
            "## Decisions\n"
            "## Skills\n"
        ),
        project / "wiki" / "log.md": (
            "# Log\n\n"
            f"- {today}: init | created first-run project `{project_name}` with profile `{profile}`.\n"
        ),
    }


def _relative_created(root: Path, paths: list[Path]) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in paths)


def _preflight_bridge(code_project: Path) -> tuple[bool, str | None]:
    if not code_project.exists():
        return False, "code_project_missing"
    if not code_project.is_dir():
        return False, "code_project_not_directory"
    if (code_project / "_wiki").exists() or (code_project / "_wiki").is_symlink():
        return False, "bridge_path_exists"
    if (code_project / ".reefiki").exists():
        return False, "marker_path_exists"
    return True, None


def _remove_created_bridge(link: Path) -> None:
    if not (link.exists() or link.is_symlink()):
        return
    if link.is_symlink() or link.is_file():
        link.unlink()
        return
    os.rmdir(link)


def _create_directory_bridge(link: Path, target: Path) -> tuple[bool, str | None]:
    try:
        link.symlink_to(target, target_is_directory=True)
        return True, None
    except OSError as exc:
        symlink_error = str(exc)
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return True, None
        detail = completed.stderr.strip() or completed.stdout.strip() or symlink_error
        return False, detail
    return False, symlink_error


def _append_gitignore(code_project: Path, created: list[Path]) -> tuple[str | None, bool]:
    gitignore = code_project / ".gitignore"
    previous = gitignore.read_text(encoding="utf-8", errors="replace") if gitignore.exists() else None
    lines = previous.splitlines() if previous is not None else []
    changed = False
    for entry in ["_wiki/", ".reefiki"]:
        if entry not in [line.strip() for line in lines]:
            lines.append(entry)
            changed = True
    if changed:
        gitignore.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
        if previous is None:
            created.append(gitignore)
    return previous, changed


def _restore_gitignore(code_project: Path, previous: str | None) -> None:
    gitignore = code_project / ".gitignore"
    if previous is None:
        try:
            gitignore.unlink()
        except FileNotFoundError:
            pass
    else:
        gitignore.write_text(previous, encoding="utf-8")


def _apply_bridge(workspace: Path, project_name: str, code_project: Path) -> dict[str, object]:
    bridge_created: list[Path] = []
    link = code_project / "_wiki"
    marker = code_project / ".reefiki"
    target = workspace / "projects" / project_name
    previous_gitignore: str | None = None
    gitignore_touched = False
    try:
        ok, detail = _create_directory_bridge(link, target)
        if not ok:
            return {
                "requested": True,
                "outcome": "warn",
                "reason": "bridge_unsupported",
                "detail": detail,
                "code_project": _display_path(code_project),
                "created_paths": [],
                "connect_check": None,
            }
        bridge_created.append(link)
        marker.write_text(
            "# REEFIKI connection marker\n"
            f"REEFIKI_path: {workspace.resolve()}\n"
            f"project_name: {project_name}\n"
            "wiki_junction: _wiki\n",
            encoding="utf-8",
            newline="\n",
        )
        bridge_created.append(marker)
        previous_gitignore, gitignore_touched = _append_gitignore(code_project, bridge_created)
        connect_check = connect_check_payload(code_project)
        return {
            "requested": True,
            "outcome": "pass" if connect_check["status"] == "pass" else "warn",
            "reason": None if connect_check["status"] == "pass" else "connect_check_not_pass",
            "code_project": _display_path(code_project),
            "created_paths": _relative_created(code_project, bridge_created),
            "connect_check": connect_check,
        }
    except Exception as exc:
        for path in reversed(bridge_created):
            if path == link:
                _remove_created_bridge(link)
            else:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        if gitignore_touched:
            _restore_gitignore(code_project, previous_gitignore)
        return {
            "requested": True,
            "outcome": "warn",
            "reason": "bridge_apply_failed",
            "detail": str(exc),
            "code_project": _display_path(code_project),
            "created_paths": [],
            "connect_check": None,
        }


def init_workspace_payload(
    workspace: Path,
    project_name: str,
    title: str | None,
    profile: str,
    *,
    code_project: Path | None = None,
    apply_bridge: bool = False,
) -> dict[str, object]:
    try:
        normalized_project = normalize_target_project_name(project_name)
    except SystemExit as exc:
        return {
            "schema_version": INIT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "invalid_project_name",
            "detail": str(exc),
            "workspace": _display_path(workspace),
            "project": {"name": project_name, "profile": profile, "path": None},
            "created_paths": [],
            "bridge": {"requested": apply_bridge, "outcome": "not_requested"},
            "next_actions": ["Use a project name without path separators or '..'."],
        }
    name_problem = _init_project_name_problem(normalized_project)
    if name_problem:
        return {
            "schema_version": INIT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "invalid_project_name",
            "detail": name_problem,
            "workspace": _display_path(workspace),
            "project": {"name": project_name, "profile": profile, "path": None},
            "created_paths": [],
            "bridge": {"requested": apply_bridge, "outcome": "not_requested"},
            "next_actions": ["Use a portable folder name such as first-run, my-app or product-notes."],
        }
    if profile not in PROJECT_PROFILES:
        return {
            "schema_version": INIT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "invalid_profile",
            "workspace": _display_path(workspace),
            "project": {"name": normalized_project, "profile": profile, "path": None},
            "created_paths": [],
            "bridge": {"requested": apply_bridge, "outcome": "not_requested"},
            "next_actions": [f"Use one of: {', '.join(PROJECT_PROFILES)}."],
        }
    workspace = workspace.expanduser().resolve()
    project = workspace / "projects" / normalized_project
    project_title = title or normalized_project.replace("-", " ").replace("_", " ").title()
    if workspace.exists() and not workspace.is_dir():
        return {
            "schema_version": INIT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "workspace_not_directory",
            "workspace": _display_path(workspace),
            "project": {"name": normalized_project, "profile": profile, "path": _display_path(project)},
            "created_paths": [],
            "bridge": {"requested": apply_bridge, "outcome": "not_requested"},
            "next_actions": ["Choose a workspace directory path."],
        }
    if project.exists():
        return {
            "schema_version": INIT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "project_exists",
            "workspace": _display_path(workspace),
            "project": {"name": normalized_project, "profile": profile, "path": _display_path(project)},
            "created_paths": [],
            "bridge": {"requested": apply_bridge, "outcome": "not_requested"},
            "next_actions": ["Choose a different --project-name or workspace."],
        }
    if workspace.exists() and any(workspace.iterdir()):
        return {
            "schema_version": INIT_SCHEMA_VERSION,
            "outcome": "block",
            "reason": "workspace_exists",
            "workspace": _display_path(workspace),
            "project": {"name": normalized_project, "profile": profile, "path": _display_path(project)},
            "created_paths": [],
            "bridge": {"requested": apply_bridge, "outcome": "not_requested"},
            "next_actions": ["Choose an empty workspace path; reefiki init v1 does not merge into existing workspaces."],
        }
    resolved_code_project = code_project.expanduser().resolve() if code_project else None
    if apply_bridge:
        if resolved_code_project is None:
            return {
                "schema_version": INIT_SCHEMA_VERSION,
                "outcome": "block",
                "reason": "code_project_required",
                "workspace": _display_path(workspace),
                "project": {"name": normalized_project, "profile": profile, "path": _display_path(project)},
                "created_paths": [],
                "bridge": {"requested": True, "outcome": "block", "reason": "code_project_required"},
                "next_actions": ["Pass --code-project <path> together with --apply-bridge."],
            }
        ok, reason = _preflight_bridge(resolved_code_project)
        if not ok:
            return {
                "schema_version": INIT_SCHEMA_VERSION,
                "outcome": "block",
                "reason": reason,
                "workspace": _display_path(workspace),
                "project": {"name": normalized_project, "profile": profile, "path": _display_path(project)},
                "created_paths": [],
                "bridge": {
                    "requested": True,
                    "outcome": "block",
                    "reason": reason,
                    "code_project": _display_path(resolved_code_project),
                },
                "next_actions": ["Fix the code project bridge path and rerun init."],
            }
    created: list[Path] = []
    workspace.mkdir(parents=True, exist_ok=True)
    for path, content in _project_files(project, normalized_project, project_title, profile).items():
        _write_text(path, content, created)
    build_index(project)
    created.append(project / ".reefiki" / "index.sqlite")
    bridge = (
        _apply_bridge(workspace, normalized_project, resolved_code_project)
        if apply_bridge and resolved_code_project is not None
        else {
            "requested": bool(code_project),
            "outcome": "not_applied" if code_project else "not_requested",
            "reason": "apply_bridge_required" if code_project and not apply_bridge else None,
            "code_project": _display_path(resolved_code_project) if resolved_code_project else None,
            "created_paths": [],
            "connect_check": None,
        }
    )
    outcome = "pass" if bridge["outcome"] in {"pass", "not_requested", "not_applied"} else "warn"
    next_actions = [
        f"Run `reefiki --project {project} doctor --format json`.",
        f"Run `reefiki --project {project} status`.",
    ]
    if bridge["outcome"] == "not_applied" and resolved_code_project is not None:
        next_actions.append("Rerun with --apply-bridge to create .reefiki and _wiki in the code project.")
    elif bridge["outcome"] == "warn":
        next_actions.append("Review bridge status before relying on project-local _wiki access.")
    else:
        next_actions.append("Run `reefiki onboarding` or connect a real code project when ready.")
    return {
        "schema_version": INIT_SCHEMA_VERSION,
        "outcome": outcome,
        "reason": None if outcome == "pass" else bridge.get("reason"),
        "workspace": _display_path(workspace),
        "project": {
            "name": normalized_project,
            "title": project_title,
            "profile": profile,
            "path": _display_path(project),
        },
        "created_paths": _relative_created(workspace, created),
        "bridge": bridge,
        "next_actions": next_actions,
    }


def print_init_workspace(
    workspace: str,
    project_name: str,
    title: str | None,
    profile: str,
    code_project: str | None,
    apply_bridge: bool,
    fmt: str,
) -> int:
    payload = init_workspace_payload(
        Path(workspace),
        project_name,
        title,
        profile,
        code_project=Path(code_project) if code_project else None,
        apply_bridge=apply_bridge,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"init: {payload['outcome']}")
        if payload.get("reason"):
            print(f"- reason: {payload['reason']}")
        print(f"- workspace: {payload['workspace']}")
        project = payload["project"]
        print(f"- project: {project['name']} ({project.get('profile')})")
        if project.get("path"):
            print(f"- path: {project['path']}")
        bridge = payload["bridge"]
        print(f"- bridge: {bridge.get('outcome')}")
        for action in payload["next_actions"]:
            print(f"- next: {action}")
    return 1 if payload["outcome"] == "block" else 0
