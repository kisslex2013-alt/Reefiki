from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from .file_utils import slugify, write_new_text
from .project_paths import relative
from .repo_paths import resolve_contained_path


def plan_create(project: Path, title: str) -> int:
    plans = project / "plans"
    plans.mkdir(exist_ok=True)
    slug = slugify(title)
    path = plans / f"{slug}.md"
    if path.exists():
        raise SystemExit(f"Plan already exists: {relative(project, path)}")
    body = f"""# {title}

Created: {date.today().isoformat()}
Status: active

## Goal

## Non-goals

## Current State

## Steps

- [ ]

## Decisions

## Evidence

## Recovery Notes

Read this file, `wiki/log.md`, and changed files before resuming.
"""
    checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
    try:
        path = write_new_text(path, body + f"\n<!-- reefiki-plan-sha256:{checksum} -->\n")
    except FileExistsError:
        raise SystemExit(f"Plan already exists: {relative(project, path)}") from None
    print(relative(project, path))
    return 0


def plan_check(project: Path, path_arg: str) -> int:
    path, reason = resolve_contained_path(project, path_arg)
    if path is None:
        print(f"Refused: {reason}")
        return 2
    text = path.read_text(encoding="utf-8")
    match = re.search(r"\n<!-- reefiki-plan-sha256:([a-f0-9]{64}) -->\s*$", text)
    if not match:
        print(f"{relative(project, path)}: no checksum")
        return 1
    body = text[: match.start()]
    actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if actual != match.group(1):
        print(f"{relative(project, path)}: checksum mismatch")
        return 1
    print(f"{relative(project, path)}: checksum OK")
    return 0


def timeline_entries(project: Path) -> list[dict[str, str]]:
    lines = (project / "wiki" / "log.md").read_text(encoding="utf-8", errors="replace").splitlines()
    entries: list[dict[str, str]] = []
    current: list[str] = []

    def append_current() -> None:
        if not current:
            return
        heading = current[0]
        match = re.match(r"^## \[(?P<date>\d{4}-\d{2}-\d{2})\]\s*(?P<title>.*)$", heading)
        body = "\n".join(current[1:]).strip()
        entries.append(
            {
                "date": match.group("date") if match else "",
                "title": match.group("title").strip() if match else heading.removeprefix("## ").strip(),
                "heading": heading,
                "body": body,
                "text": "\n".join(current).rstrip(),
            }
        )

    for line in lines:
        if line.startswith("## ["):
            append_current()
            current = [line]
        elif current:
            current.append(line)
    append_current()
    return entries


def timeline_payload(project: Path, limit: int) -> dict[str, object]:
    entries = timeline_entries(project)
    selected = entries[-limit:] if limit else entries
    return {
        "project": project.name,
        "limit": limit,
        "total": len(entries),
        "returned": len(selected),
        "entries": selected,
    }


def timeline(project: Path, limit: int, fmt: str = "text") -> int:
    payload = timeline_payload(project, limit)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for entry in payload["entries"]:
        assert isinstance(entry, dict)
        print(str(entry["text"]).rstrip())
        print()
    return 0
