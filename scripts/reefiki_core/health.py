from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from .doctor import doctor_payload
from .markdown import as_text
from .privacy import inbox_items
from .review_queues import build_backlink_index, review_queue_scan, review_queue_summary
from .wiki_rows import _wiki_rows


def _ratio(part: int | float, total: int | float) -> float:
    return round(float(part) / float(total), 3) if total else 0.0


def _median_int(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def knowledge_health_payload(project: Path) -> dict[str, object]:
    rows = _wiki_rows(project)
    total_pages = len(rows)
    seen_count = len(list((project / "seen").glob("*.md"))) if (project / "seen").exists() else 0
    inbox_count = len(inbox_items(project))
    doctor = doctor_payload(project)
    backlinks = build_backlink_index(project) if total_pages else {"pages": {}, "orphans": [], "broken_links": []}

    use_counts = [int(row.get("use_count") or 0) for row in rows]
    zero_use_pages = sum(1 for count in use_counts if count == 0)
    last_used_days: list[int] = []
    useful_when_word_counts: list[int] = []
    conflict_pages = 0
    today = date.today()
    for row in rows:
        last_used = as_text(row.get("last_used"))
        if last_used:
            try:
                last_used_days.append((today - date.fromisoformat(last_used)).days)
            except ValueError:
                pass
        useful_when = row.get("useful_when") if isinstance(row.get("useful_when"), list) else []
        useful_when_word_counts.append(sum(len(as_text(item).split()) for item in useful_when))
        body = as_text(row.get("body"))
        if re.search(r"^## Conflict(?:ing claims|s)?\b", body, re.MULTILINE):
            conflict_pages += 1

    type_counts = Counter(as_text(row.get("type")) or "unknown" for row in rows)
    outgoing_counts = [len(page["outgoing"]) for page in backlinks["pages"].values()]
    useful_when_20_words = sum(1 for count in useful_when_word_counts if count >= 20)
    orphan_count = len(backlinks["orphans"])
    broken_link_count = len(backlinks["broken_links"])
    distillation_ratio = _ratio(total_pages, total_pages + seen_count)
    zero_use_ratio = _ratio(zero_use_pages, total_pages)
    orphan_ratio = _ratio(orphan_count, total_pages)
    conflict_ratio = _ratio(conflict_pages, total_pages)
    useful_when_quality_ratio = _ratio(useful_when_20_words, total_pages)
    avg_use_count = round(sum(use_counts) / total_pages, 2) if total_pages else 0.0
    avg_outgoing_links = round(sum(outgoing_counts) / total_pages, 2) if total_pages else 0.0

    warnings: list[dict[str, object]] = []
    if doctor["outcome"] == "fail":
        warnings.append({"code": "doctor_failed", "severity": "block", "message": "Integrity doctor has blocking issues."})
    if broken_link_count > 0:
        warnings.append({"code": "broken_links", "severity": "warn", "message": f"{broken_link_count} broken wikilink(s) need repair."})
    if total_pages and zero_use_ratio > 0.3:
        warnings.append({"code": "high_zero_use_ratio", "severity": "warn", "message": f"{zero_use_pages}/{total_pages} page(s) have use_count=0."})
    if total_pages and orphan_ratio > 0.2:
        warnings.append({"code": "high_orphan_ratio", "severity": "warn", "message": f"{orphan_count}/{total_pages} page(s) have no inbound links."})
    if total_pages and conflict_ratio > 0.05:
        warnings.append({"code": "high_conflict_ratio", "severity": "warn", "message": f"{conflict_pages}/{total_pages} page(s) contain conflict markers."})
    if inbox_count > 0:
        warnings.append({"code": "inbox_pending", "severity": "info", "message": f"{inbox_count} inbox item(s) are waiting for process."})

    recommendations: list[str] = []
    warning_codes = {as_text(warning["code"]) for warning in warnings}
    if "doctor_failed" in warning_codes:
        recommendations.append("Run doctor and fix integrity issues before publish or migration.")
    if "broken_links" in warning_codes:
        recommendations.append("Run backlinks or review-queues --type placeholder_link to repair broken links.")
    if "high_zero_use_ratio" in warning_codes or "high_orphan_ratio" in warning_codes:
        recommendations.append("Run review-queues --summary before choosing a focused queue to triage.")
    if "inbox_pending" in warning_codes:
        recommendations.append("Run process on inbox items before relying on health trends.")

    outcome = "fail" if any(w["severity"] == "block" for w in warnings) else "warn" if warnings else "pass"
    return {
        "project": project.name,
        "outcome": outcome,
        "generated_on": today.isoformat(),
        "doctor": doctor,
        "size": {
            "wiki_pages": total_pages,
            "seen_pages": seen_count,
            "inbox_items": inbox_count,
            "distillation_ratio": distillation_ratio,
            "type_counts": dict(sorted(type_counts.items())),
        },
        "usage": {
            "avg_use_count": avg_use_count,
            "zero_use_pages": zero_use_pages,
            "zero_use_ratio": zero_use_ratio,
            "median_last_used_days": _median_int(last_used_days),
            "top_used_pages": [
                {
                    "id": as_text(row.get("id")),
                    "title": as_text(row.get("title")),
                    "use_count": int(row.get("use_count") or 0),
                    "file": as_text(row.get("file")),
                }
                for row in sorted(
                    [row for row in rows if int(row.get("use_count") or 0) > 0],
                    key=lambda item: int(item.get("use_count") or 0),
                    reverse=True,
                )[:10]
            ],
        },
        "quality": {
            "useful_when_20_word_pages": useful_when_20_words,
            "useful_when_20_word_ratio": useful_when_quality_ratio,
            "conflict_pages": conflict_pages,
            "conflict_ratio": conflict_ratio,
        },
        "structure": {
            "orphan_pages": orphan_count,
            "orphan_ratio": orphan_ratio,
            "broken_links": broken_link_count,
            "avg_outgoing_links": avg_outgoing_links,
        },
        "warnings": warnings,
        "recommendations": recommendations,
    }


def print_health(project: Path, fmt: str) -> int:
    payload = knowledge_health_payload(project)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if payload["outcome"] == "fail" else 0
    print(f"Project: {payload['project']}")
    print(f"Outcome: {payload['outcome']}")
    size = payload["size"]
    usage = payload["usage"]
    quality = payload["quality"]
    structure = payload["structure"]
    print(f"Size: wiki={size['wiki_pages']} seen={size['seen_pages']} inbox={size['inbox_items']} distillation={size['distillation_ratio']}")
    print(f"Usage: avg_use_count={usage['avg_use_count']} zero_use={usage['zero_use_pages']} ({usage['zero_use_ratio']}) median_last_used_days={usage['median_last_used_days']}")
    print(f"Quality: useful_when_20_word_ratio={quality['useful_when_20_word_ratio']} conflicts={quality['conflict_pages']}")
    print(f"Structure: orphans={structure['orphan_pages']} ({structure['orphan_ratio']}) broken_links={structure['broken_links']} avg_outgoing={structure['avg_outgoing_links']}")
    if payload["warnings"]:
        print("Warnings:")
        for warning in payload["warnings"]:
            print(f"  {warning['severity']}: {warning['code']} - {warning['message']}")
    if payload["recommendations"]:
        print("Recommendations:")
        for recommendation in payload["recommendations"]:
            print(f"  - {recommendation}")
    return 1 if payload["outcome"] == "fail" else 0


def dashboard_next_action(
    health: dict[str, object],
    review_summary: dict[str, object],
    limit: int,
) -> str:
    warnings = health.get("warnings", [])
    warning_codes = {as_text(warning.get("code")) for warning in warnings if isinstance(warning, dict)}
    if health.get("outcome") == "fail":
        return "run doctor and fix integrity issues"
    if "broken_links" in warning_codes:
        return f"run review-queues --type placeholder_link --limit {max(1, limit)}"
    queues = review_summary.get("queues", [])
    if isinstance(queues, list) and queues:
        first_queue = queues[0]
        if isinstance(first_queue, dict):
            queue_type = as_text(first_queue.get("queue_type"))
            if queue_type:
                return f"run review-queues --type {queue_type} --limit {max(1, limit)}"
    size = health.get("size", {})
    if isinstance(size, dict) and int(size.get("inbox_items", 0)) > 0:
        return "run process on inbox items"
    return "no action"


def dashboard_payload(project: Path, stale_days: int = 90, limit: int = 5) -> dict[str, object]:
    health = knowledge_health_payload(project)
    queue_items = review_queue_scan(project, stale_days=stale_days)
    review_summary = review_queue_summary(queue_items, limit=max(1, limit))
    next_action = dashboard_next_action(health, review_summary, limit=max(1, limit))
    return {
        "project": project.name,
        "generated_on": date.today().isoformat(),
        "outcome": health["outcome"],
        "health": {
            "outcome": health["outcome"],
            "size": health["size"],
            "usage": health["usage"],
            "quality": health["quality"],
            "structure": health["structure"],
            "warnings_count": len(health["warnings"]),
            "warnings": health["warnings"],
            "recommendations": health["recommendations"],
        },
        "review_queues": review_summary,
        "next_action": next_action,
    }


def print_dashboard(project: Path, stale_days: int, limit: int, fmt: str) -> int:
    payload = dashboard_payload(project, stale_days=stale_days, limit=limit)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if payload["outcome"] == "fail" else 0
    health = payload["health"]
    size = health["size"]
    usage = health["usage"]
    structure = health["structure"]
    queues = payload["review_queues"]
    print(f"Dashboard: {payload['project']}")
    print(f"Outcome: {payload['outcome']}")
    print(f"Health: wiki={size['wiki_pages']} inbox={size['inbox_items']} warnings={health['warnings_count']}")
    print(f"Usage: zero_use={usage['zero_use_pages']} ({usage['zero_use_ratio']})")
    print(f"Structure: orphans={structure['orphan_pages']} broken_links={structure['broken_links']}")
    print(f"Review queues: {queues['total']}")
    for queue in queues["queues"]:
        samples = ", ".join(queue["sample_page_ids"])
        suffix = f" sample: {samples}" if samples else ""
        print(f"- {queue['queue_type']}: {queue['count']}{suffix}")
    print(f"Next action: {payload['next_action']}")
    return 1 if payload["outcome"] == "fail" else 0
