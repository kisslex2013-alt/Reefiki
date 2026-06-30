from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from .markdown import as_text, parse_frontmatter
from .privacy import inbox_items
from .project_paths import iter_pages


def status_payload(project: Path) -> dict[str, object]:
    inbox = [path.name for path in inbox_items(project)]
    seen = list((project / "seen").glob("*.md"))
    expired = 0
    active = 0
    today = date.today().isoformat()
    for path in seen:
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^quarantine_until:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
        if match and match.group(1) <= today:
            expired += 1
        else:
            active += 1
    counts: Counter[str] = Counter()
    stale = 0
    for page in iter_pages(project):
        fm, _ = parse_frontmatter(page.read_text(encoding="utf-8"))
        counts[as_text(fm.get("type")) or "unknown"] += 1
        date_added = as_text(fm.get("date_added"))
        if int(fm.get("use_count") or 0) == 0 and date_added:
            try:
                age = (date.today() - date.fromisoformat(date_added)).days
                if age > 60:
                    stale += 1
            except ValueError:
                pass
    log = (project / "wiki" / "log.md").read_text(encoding="utf-8", errors="replace")
    last_lint = "never"
    lint_matches = re.findall(r"^## \[(\d{4}-\d{2}-\d{2})\] /lint", log, re.MULTILINE)
    if lint_matches:
        last_lint = lint_matches[-1]
    return {
        "project": project.name,
        "inbox": {"count": len(inbox), "items": inbox[:5]},
        "seen": {"count": len(seen), "expired": expired, "active": active},
        "wiki": {"counts": {key: counts[key] for key in sorted(counts)}, "stale": stale},
        "last_lint": last_lint,
    }


def _print_status_text(payload: dict[str, object]) -> None:
    inbox = payload["inbox"]
    seen = payload["seen"]
    wiki = payload["wiki"]
    assert isinstance(inbox, dict)
    assert isinstance(seen, dict)
    assert isinstance(wiki, dict)
    items = inbox.get("items") or []
    counts = wiki.get("counts") or {}
    assert isinstance(items, list)
    assert isinstance(counts, dict)
    print(f"Project: {payload['project']}")
    print(f"Inbox: {inbox['count']}" + (f" ({', '.join(items)})" if items else ""))
    print(f"Seen: {seen['count']} ({seen['expired']} expired, {seen['active']} active)")
    print(
        "Wiki: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        + f" | stale={wiki['stale']}"
    )
    print(f"Last lint: {payload['last_lint']}")


def status(project: Path, fmt: str = "text") -> int:
    payload = status_payload(project)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_status_text(payload)
    return 0
