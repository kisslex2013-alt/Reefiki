from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from .index_search import build_index, search, search_existing
from .link_confidence import link_confidence_payload
from .markdown import as_text
from .memory_golden import load_golden_queries
from .project_paths import find_project
from .review_queues import review_queue_scan, review_queue_summary


VISIBILITY_STATUSES = ("answerable", "weak", "missing")
CONTRIBUTOR_QUEUE_TYPES = {
    "duplicate_candidate",
    "needs_verification",
    "placeholder_link",
    "stale_review",
}


def _text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [text for item in value if (text := as_text(item))]
    return []


def _normalize_case(raw: dict[str, object], fallback_id: str) -> dict[str, object]:
    query = as_text(raw.get("query"))
    if not query:
        raise SystemExit(f"Visibility audit query is missing text: {fallback_id}")
    expected_ids = _text_list(raw.get("expected_ids") or raw.get("expect_ids"))
    return {
        "id": as_text(raw.get("id")) or fallback_id,
        "query": query,
        "expected_ids": expected_ids,
    }


def load_visibility_queries_file(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise SystemExit(f"Missing visibility query file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_queries = data.get("queries") if isinstance(data, dict) else data
    if not isinstance(raw_queries, list):
        raise SystemExit("Visibility query file must contain a JSON list or a queries list.")
    cases: list[dict[str, object]] = []
    for index, raw in enumerate(raw_queries, 1):
        if not isinstance(raw, dict):
            raise SystemExit(f"Visibility query #{index} must be an object.")
        cases.append(_normalize_case(raw, f"query-{index}"))
    return cases


def load_visibility_queries_from_golden(project: Path, path: Path | None = None) -> list[dict[str, object]]:
    config = load_golden_queries(path or project / "golden-queries.yml")
    cases: list[dict[str, object]] = []
    for index, raw in enumerate(config.get("queries", []), 1):
        if not isinstance(raw, dict) or as_text(raw.get("kind")) != "lookup":
            continue
        cases.append(_normalize_case(raw, f"golden-{index}"))
    if not cases:
        raise SystemExit("No lookup queries found for visibility audit.")
    return cases


def inline_visibility_query(query: str, expected_ids: list[str] | None = None) -> list[dict[str, object]]:
    return [
        {
            "id": "inline-query",
            "query": query,
            "expected_ids": expected_ids or [],
        }
    ]


def _search_rows(project: Path, query: str, limit: int, allow_rebuild_index: bool) -> list[Any]:
    if allow_rebuild_index:
        return list(search(project, query, limit))
    database = project / ".reefiki" / "index.sqlite"
    if not database.exists():
        raise SystemExit(
            "Missing wiki search index. Run `reefiki index` or omit --no-rebuild-index."
        )
    return list(search_existing(project, database, query, limit))


def _row_payload(row: Any) -> dict[str, object]:
    score = row["score"] if "score" in row.keys() else 0.0
    return {
        "id": as_text(row["id"]),
        "title": as_text(row["title"]),
        "type": as_text(row["type"]),
        "file": as_text(row["file"]),
        "score": float(score or 0.0),
    }


def _review_items_by_page(review_items: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in review_items:
        grouped.setdefault(as_text(item.get("page_id")), []).append(item)
    return grouped


def _contributors_for_retrieved(
    retrieved_ids: list[str],
    review_by_page: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    contributors: list[dict[str, object]] = []
    for page_id in retrieved_ids:
        for item in review_by_page.get(page_id, []):
            queue_type = as_text(item.get("queue_type"))
            if queue_type not in CONTRIBUTOR_QUEUE_TYPES:
                continue
            contributors.append(
                {
                    "page_id": page_id,
                    "queue_type": queue_type,
                    "reason": as_text(item.get("reason")),
                    "suggested_action": as_text(item.get("suggested_action")),
                }
            )
    return contributors


def _suggested_improvements(
    status: str,
    missing_expected_ids: list[str],
    contributors: list[dict[str, object]],
    expected_ids: list[str],
) -> list[str]:
    suggestions: list[str] = []
    if not expected_ids:
        suggestions.append("Add expected_ids to make visibility measurable for this query.")
    if status == "missing":
        suggestions.append("Add or link a durable wiki page that answers this query.")
    if missing_expected_ids:
        suggestions.append(
            "Improve title/tags/useful_when/body links for expected page ids: "
            + ", ".join(missing_expected_ids)
        )
    for item in contributors[:3]:
        action = as_text(item.get("suggested_action"))
        if action and action not in suggestions:
            suggestions.append(action)
    return suggestions


def _audit_query(
    project: Path,
    case: dict[str, object],
    limit: int,
    allow_rebuild_index: bool,
    review_by_page: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    expected_ids = _text_list(case.get("expected_ids"))
    rows = _search_rows(project, as_text(case.get("query")), max(1, limit), allow_rebuild_index)
    retrieved = [_row_payload(row) for row in rows]
    retrieved_ids = [as_text(item.get("id")) for item in retrieved]
    found_expected_ids = [page_id for page_id in expected_ids if page_id in retrieved_ids]
    missing_expected_ids = [page_id for page_id in expected_ids if page_id not in retrieved_ids]
    reasons: list[str] = []

    if not retrieved_ids:
        status = "missing"
        reasons.append("no_retrieved_pages")
    elif not expected_ids:
        status = "weak"
        reasons.append("no_expected_ids")
    elif missing_expected_ids:
        status = "weak"
        reasons.append("missing_expected_ids:" + ",".join(missing_expected_ids))
    else:
        status = "answerable"

    contributors = _contributors_for_retrieved(retrieved_ids, review_by_page)
    coverage = None if not expected_ids else len(found_expected_ids) / len(expected_ids)
    return {
        "id": as_text(case.get("id")),
        "query": as_text(case.get("query")),
        "expected_ids": expected_ids,
        "status": status,
        "reasons": reasons,
        "retrieved": retrieved,
        "citation_coverage": {
            "expected_ids": expected_ids,
            "found_expected_ids": found_expected_ids,
            "missing_expected_ids": missing_expected_ids,
            "coverage": coverage,
        },
        "stale_noisy_contributors": contributors,
        "suggested_improvements": _suggested_improvements(
            status,
            missing_expected_ids,
            contributors,
            expected_ids,
        ),
    }


def visibility_audit_payload(
    root: Path,
    project_name: str,
    query_cases: list[dict[str, object]],
    query_source: str,
    limit: int = 5,
    stale_days: int = 90,
    allow_rebuild_index: bool = False,
) -> dict[str, object]:
    project = find_project(root, project_name)
    if allow_rebuild_index:
        build_index(project)
    review_items = review_queue_scan(project, stale_days=stale_days)
    review_by_page = _review_items_by_page(review_items)
    queries = [
        _audit_query(project, case, limit, allow_rebuild_index, review_by_page)
        for case in query_cases
    ]
    counts: Counter[str] = Counter(as_text(item.get("status")) for item in queries)
    summary = {status: counts[status] for status in VISIBILITY_STATUSES}
    summary["total"] = len(queries)
    groups = {
        status: [item for item in queries if item.get("status") == status]
        for status in VISIBILITY_STATUSES
    }
    link_payload = link_confidence_payload(project, stale_days=stale_days, limit=limit)
    return {
        "schema_version": 1,
        "project": project.name,
        "generated_on": date.today().isoformat(),
        "read_only": not allow_rebuild_index,
        "wiki_read_only": True,
        "query_source": query_source,
        "inputs": {
            "limit": max(1, limit),
            "stale_days": stale_days,
            "allow_rebuild_index": allow_rebuild_index,
            "contributor_queue_types": sorted(CONTRIBUTOR_QUEUE_TYPES),
        },
        "summary": summary,
        "groups": groups,
        "queries": queries,
        "signals": {
            "review_queue_counts": review_queue_summary(review_items, limit=limit)["counts"],
            "link_confidence_class_counts": link_payload["class_counts"],
            "link_confidence_needed": link_payload["confidence_tagging"]["needed"],
        },
    }


def _print_visibility_audit_text(payload: dict[str, object]) -> None:
    summary = payload["summary"]
    print(f"visibility audit: {payload['project']}")
    print(
        "summary: "
        f"answerable {summary['answerable']}, "
        f"weak {summary['weak']}, "
        f"missing {summary['missing']}, "
        f"total {summary['total']}"
    )
    for query in payload["queries"]:
        print(f"- {query['status']}: {query['id']}")
        print(f"  query: {query['query']}")
        retrieved = ", ".join(item["id"] for item in query["retrieved"]) or "none"
        print(f"  retrieved: {retrieved}")
        if query["reasons"]:
            print(f"  reasons: {', '.join(query['reasons'])}")
        suggestions = query.get("suggested_improvements") or []
        if suggestions:
            print(f"  next: {suggestions[0]}")


def _resolve_query_cases(
    project: Path,
    from_golden: bool,
    query: str | None,
    queries_file: str | None,
    expected_ids: list[str],
) -> tuple[str, list[dict[str, object]]]:
    selected = sum(bool(item) for item in [from_golden, query, queries_file])
    if selected > 1:
        raise SystemExit("Choose only one query source: --from-golden, --query or --queries-file.")
    if query:
        return "inline", inline_visibility_query(query, expected_ids)
    if queries_file:
        return "queries-file", load_visibility_queries_file(Path(queries_file))
    return "golden", load_visibility_queries_from_golden(project)


def print_visibility_audit(
    root: Path,
    project_name: str,
    from_golden: bool,
    query: str | None,
    queries_file: str | None,
    expected_ids: list[str],
    limit: int,
    stale_days: int,
    allow_rebuild_index: bool,
    fmt: str,
) -> int:
    project = find_project(root, project_name)
    query_source, query_cases = _resolve_query_cases(
        project,
        from_golden,
        query,
        queries_file,
        expected_ids,
    )
    payload = visibility_audit_payload(
        root,
        project_name,
        query_cases,
        query_source=query_source,
        limit=limit,
        stale_days=stale_days,
        allow_rebuild_index=allow_rebuild_index,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    _print_visibility_audit_text(payload)
    return 0
