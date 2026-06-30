from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .project_paths import iter_pages, relative
from .storage import sqlite_connection


def doctor_payload(project: Path) -> dict[str, object]:
    required_paths = [
        ("AGENTS.md", "file"),
        ("_domain.md", "file"),
        ("raw", "dir"),
        ("inbox", "dir"),
        ("seen", "dir"),
        ("wiki/index.md", "file"),
        ("wiki/log.md", "file"),
    ]
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for rel_path, kind in required_paths:
        path = project / rel_path
        exists = path.is_dir() if kind == "dir" else path.is_file()
        if not exists:
            issues.append(
                {
                    "code": "missing_required_path",
                    "path": rel_path,
                    "message": f"Missing required {kind}: {rel_path}",
                }
            )

    wiki_pages = iter_pages(project) if (project / "wiki").exists() else []
    database = project / ".reefiki" / "index.sqlite"
    index: dict[str, object] = {
        "path": relative(project, database) if database.exists() else ".reefiki/index.sqlite",
        "status": "missing",
        "integrity_check": None,
        "page_count": None,
        "wiki_page_count": len(wiki_pages),
    }
    if database.exists():
        try:
            with sqlite_connection(database, row_factory=True) as conn:
                integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
                integrity_result = str(integrity_row[0]) if integrity_row else "missing_result"
                index["integrity_check"] = integrity_result
                if integrity_result != "ok":
                    index["status"] = "failed_integrity_check"
                    issues.append(
                        {
                            "code": "sqlite_integrity_check_failed",
                            "path": relative(project, database),
                            "message": integrity_result,
                        }
                    )
                row = conn.execute("SELECT COUNT(*) AS page_count FROM pages").fetchone()
                index["page_count"] = int(row["page_count"])
                if index["status"] == "missing":
                    index["status"] = "ok"
            if index["page_count"] != len(wiki_pages):
                warnings.append(
                    {
                        "code": "index_page_count_mismatch",
                        "path": relative(project, database),
                        "message": f"Index has {index['page_count']} page(s), wiki has {len(wiki_pages)}.",
                    }
                )
        except sqlite3.DatabaseError as exc:
            index["status"] = "corrupt"
            issues.append(
                {
                    "code": "sqlite_corrupt",
                    "path": relative(project, database),
                    "message": str(exc),
                }
            )
    else:
        warnings.append(
            {
                "code": "index_missing",
                "path": ".reefiki/index.sqlite",
                "message": "SQLite index is missing; run index to rebuild it.",
            }
        )
    return {
        "project": project.name,
        "outcome": "fail" if issues else "pass",
        "issues": issues,
        "warnings": warnings,
        "index": index,
    }


def print_doctor(project: Path, fmt: str) -> int:
    payload = doctor_payload(project)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Project: {payload['project']}")
        print(f"Outcome: {payload['outcome']}")
        index = payload["index"]
        print(
            f"Index: {index['status']} ({index['page_count']} indexed / {index['wiki_page_count']} wiki pages)"
        )
        if payload["issues"]:
            print("Issues:")
            for issue in payload["issues"]:
                print(f"- {issue['code']}: {issue['path']} - {issue['message']}")
        if payload["warnings"]:
            print("Warnings:")
            for warning in payload["warnings"]:
                print(f"- {warning['code']}: {warning['path']} - {warning['message']}")
    return 1 if payload["outcome"] == "fail" else 0
