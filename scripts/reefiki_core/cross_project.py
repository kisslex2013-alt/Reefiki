from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .markdown import as_text, parse_frontmatter
from .project_paths import list_projects


INDEX_FIELD_RE = re.compile(r"^- ([^:]+):\s*(.*)$")


def _relative_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _query_terms(query: str) -> list[str]:
    return [term.lower() for term in re.findall(r"\w+", query, flags=re.UNICODE)]


def _assert_unique_project_names(projects: list[Path]) -> None:
    seen: dict[str, Path] = {}
    for project in projects:
        key = project.name.lower()
        if key in seen:
            raise SystemExit(f"Duplicate project name for cross-query: {seen[key]} and {project}")
        seen[key] = project


def _selected_projects(root: Path, project_names: list[str] | None) -> list[Path]:
    projects = list_projects(root)
    _assert_unique_project_names(projects)
    if not project_names:
        return projects
    requested: set[str] = set()
    for name in project_names:
        normalized = name.strip().lower()
        if not normalized:
            raise SystemExit("Empty project name in cross-query filter")
        if normalized in requested:
            raise SystemExit(f"Duplicate project filter: {name}")
        requested.add(normalized)
    by_name = {project.name.lower(): project for project in projects}
    missing = sorted(name for name in requested if name not in by_name)
    if missing:
        raise SystemExit(f"Unknown REEFIKI project(s): {', '.join(missing)}")
    return [by_name[name] for name in sorted(requested)]


def _parse_index_entries(project: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    index = project / "wiki" / "index.md"
    if not index.exists():
        return [], [{"project": project.name, "reason": "missing_index", "file": "wiki/index.md"}]
    entries: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in index.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("### "):
            if current:
                entries.append(current)
            current = {"id": line[4:].strip()}
            continue
        if current is None:
            continue
        match = INDEX_FIELD_RE.match(line)
        if match:
            current[match.group(1).strip()] = match.group(2).strip()
    if current:
        entries.append(current)
    if not entries:
        warnings.append({"project": project.name, "reason": "empty_index", "file": "wiki/index.md"})
    return entries, warnings


def _safe_index_page(project: Path, entry: dict[str, str]) -> tuple[Path | None, str | None]:
    raw_file = entry.get("file", "")
    if not raw_file:
        return None, "missing_file"
    if raw_file.startswith("/") or raw_file.startswith("\\"):
        return None, "absolute_file_path"
    page = (project / raw_file).resolve()
    wiki = (project / "wiki").resolve()
    try:
        page.relative_to(wiki)
    except ValueError:
        return None, "outside_project_wiki"
    if page.suffix.lower() != ".md":
        return None, "non_markdown_page"
    if not page.exists():
        return None, "missing_page"
    return page, None


def _score_match(query: str, fields: dict[str, str], body: str) -> tuple[int, list[str], str]:
    terms = _query_terms(query)
    if not terms:
        return 1, ["all"], ""
    weighted_fields = {
        "id": 6,
        "title": 6,
        "type": 3,
        "tags": 5,
        "useful_when": 4,
        "abstract": 4,
        "body": 1,
    }
    values = {**fields, "body": body}
    score = 0
    matched_fields: list[str] = []
    for field, weight in weighted_fields.items():
        value = values.get(field, "").lower()
        if not value:
            continue
        hits = sum(value.count(term) for term in terms)
        if hits:
            score += hits * weight
            matched_fields.append(field)
    snippet = _snippet(body, terms)
    return score, matched_fields, snippet


def _snippet(body: str, terms: list[str]) -> str:
    if not terms:
        return ""
    lowered = body.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return ""
    start = max(0, min(positions) - 80)
    end = min(len(body), min(positions) + 220)
    return " ".join(body[start:end].split())


def _result_from_entry(root: Path, project: Path, entry: dict[str, str], page: Path, query: str) -> dict[str, Any] | None:
    text = page.read_text(encoding="utf-8", errors="replace")
    frontmatter, body = parse_frontmatter(text)
    fields = {
        "id": as_text(frontmatter.get("id")) or entry.get("id", page.stem),
        "title": as_text(frontmatter.get("title")) or entry.get("id", page.stem),
        "type": as_text(frontmatter.get("type")) or entry.get("type", ""),
        "tags": as_text(frontmatter.get("tags")) or entry.get("tags", ""),
        "useful_when": as_text(frontmatter.get("useful_when")) or entry.get("useful_when", ""),
        "abstract": as_text(frontmatter.get("abstract")),
        "sources": as_text(frontmatter.get("sources")),
    }
    score, matched_fields, snippet = _score_match(query, fields, body)
    if score <= 0:
        return None
    wiki_file = page.relative_to(project).as_posix()
    return {
        "project": project.name,
        "project_path": _relative_to_root(root, project),
        "id": fields["id"],
        "title": fields["title"],
        "type": fields["type"],
        "tags": fields["tags"],
        "useful_when": fields["useful_when"],
        "abstract": fields["abstract"],
        "file": wiki_file,
        "score": score,
        "matched_fields": matched_fields,
        "snippet": snippet,
        "provenance": {
            "project": project.name,
            "page": f"{project.name}/{wiki_file}",
            "index": f"{project.name}/wiki/index.md",
            "sources": fields["sources"],
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        },
    }


def _synthesis(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {
            "summary": "No cross-project matches found.",
            "themes": [],
        }
    by_project: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_project.setdefault(as_text(result["project"]), []).append(result)
    project_names = sorted(by_project)
    themes: list[dict[str, Any]] = []
    for project_name in project_names:
        top = by_project[project_name][0]
        themes.append(
            {
                "claim": f"{project_name}: {top['title']}",
                "evidence": [
                    {
                        "project": project_name,
                        "page": top["file"],
                        "id": top["id"],
                    }
                ],
            }
        )
    return {
        "summary": f"Top matches span {len(project_names)} project(s): {', '.join(project_names)}.",
        "themes": themes,
    }


def cross_project_query_payload(
    root: Path,
    query: str,
    limit: int,
    project_names: list[str] | None = None,
) -> dict[str, Any]:
    projects = _selected_projects(root, project_names)
    results: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for project in projects:
        entries, project_warnings = _parse_index_entries(project)
        warnings.extend(project_warnings)
        for entry in entries:
            page, reason = _safe_index_page(project, entry)
            if page is None:
                warnings.append(
                    {
                        "project": project.name,
                        "id": entry.get("id", ""),
                        "file": entry.get("file", ""),
                        "reason": as_text(reason),
                    }
                )
                continue
            result = _result_from_entry(root, project, entry, page, query)
            if result:
                results.append(result)
    results.sort(key=lambda item: (-int(item["score"]), as_text(item["project"]), as_text(item["id"])))
    limited = results[: max(1, limit)]
    return {
        "query": query,
        "read_only": True,
        "searched_projects": [project.name for project in projects],
        "count": len(limited),
        "total_matches": len(results),
        "results": limited,
        "synthesis": _synthesis(limited),
        "warnings": warnings,
    }


def print_cross_project_query(
    root: Path,
    query: str,
    limit: int,
    project_names: list[str] | None,
    fmt: str,
) -> int:
    payload = cross_project_query_payload(root, query, limit, project_names=project_names)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"query: {payload['query']}")
    print(f"read_only: {str(payload['read_only']).lower()}")
    print(f"projects: {', '.join(payload['searched_projects'])}")
    print(f"matches: {payload['count']} of {payload['total_matches']}")
    print(f"synthesis: {payload['synthesis']['summary']}")
    for idx, result in enumerate(payload["results"], 1):
        provenance = result["provenance"]
        print(f"{idx}. [{result['project']}] {result['title']} ({result['file']})")
        print(f"   type: {result['type']} | matched: {', '.join(result['matched_fields'])}")
        if result["abstract"]:
            print(f"   abstract: {result['abstract']}")
        if result["snippet"]:
            print(f"   snippet: {result['snippet']}")
        print(
            "   provenance: "
            f"project={provenance['project']} page={provenance['page']} "
            f"sources={provenance['sources'] or '-'} sha256={provenance['sha256'][:12]}"
        )
    if payload["warnings"]:
        print(f"warnings: {len(payload['warnings'])}")
    return 0
