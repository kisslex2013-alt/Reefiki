from __future__ import annotations

from pathlib import Path

from .markdown import as_text, parse_frontmatter
from .project_paths import iter_pages, relative


def _wiki_rows(project: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for page in iter_pages(project):
        text = page.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        rows.append(
            {
                "id": as_text(fm.get("id")) or page.stem,
                "type": as_text(fm.get("type")) or page.parent.name.rstrip("s"),
                "title": as_text(fm.get("title")) or page.stem,
                "tags": fm.get("tags") if isinstance(fm.get("tags"), list) else [],
                "useful_when": fm.get("useful_when") if isinstance(fm.get("useful_when"), list) else [],
                "sources": fm.get("sources") if isinstance(fm.get("sources"), list) else [],
                "date_added": as_text(fm.get("date_added")),
                "use_count": int(fm.get("use_count") or 0),
                "last_used": as_text(fm.get("last_used")) or None,
                "verified": as_text(fm.get("verified")) or None,
                "file": relative(project, page),
                "body": body.strip(),
            }
        )
    return rows
