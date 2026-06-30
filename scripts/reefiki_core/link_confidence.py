from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from .markdown import as_text, extract_wiki_links
from .project_paths import find_project
from .review_queues import build_backlink_index, review_queue_scan, review_queue_summary
from .wiki_rows import _wiki_rows


LINK_CLASSES = ["extracted-looking", "inferred-looking", "ambiguous-looking"]
CONFIDENCE_MARKERS = ["EXTRACTED", "INFERRED", "AMBIGUOUS"]
MARKER_CLASSES = {
    "EXTRACTED": "extracted-looking",
    "INFERRED": "inferred-looking",
    "AMBIGUOUS": "ambiguous-looking",
}


def _heading_by_line(body: str) -> dict[int, str]:
    heading = "Page"
    headings: dict[int, str] = {}
    for lineno, line in enumerate(body.splitlines(), 1):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            heading = match.group(1).strip()
        headings[lineno] = heading
    return headings


def _has_relation_note(line: str) -> bool:
    marker = line.find("]]")
    if marker < 0:
        return False
    after = line[marker + 2 :].strip()
    if not after.startswith(("-", ":", "—", "–")):
        return False
    return bool(after.lstrip("-:—– ").strip())


def _related_confidence_marker(section: str, line: str) -> str | None:
    if section.lower() != "related":
        return None
    match = re.search(r"\]\]\s+\[(EXTRACTED|INFERRED|AMBIGUOUS)\](?=\s|$)", line, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).upper()


def _missing_backlink_pairs(review_items: list[dict[str, object]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for item in review_items:
        if item.get("queue_type") != "missing_backlink":
            continue
        target_id = as_text(item.get("page_id"))
        for source_id in item.get("related_page_ids") or []:
            pairs.add((as_text(source_id), target_id))
    return pairs


def _broken_pairs(backlinks: dict[str, object]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for item in backlinks.get("broken_links") or []:
        if isinstance(item, dict):
            pairs.add((as_text(item.get("source_id")), as_text(item.get("target_id"))))
    return pairs


def _classify_link(
    source_id: str,
    target_id: str,
    section: str,
    line: str,
    confidence_marker: str | None,
    broken_pairs: set[tuple[str, str]],
    missing_pairs: set[tuple[str, str]],
) -> tuple[str, str]:
    pair = (source_id, target_id)
    if pair in broken_pairs:
        return "ambiguous-looking", "broken_target"
    if confidence_marker:
        return MARKER_CLASSES[confidence_marker], f"explicit_marker_{confidence_marker.lower()}"
    if pair in missing_pairs:
        return "ambiguous-looking", "missing_backlink"
    if section.lower() == "related" and _has_relation_note(line):
        return "extracted-looking", "related_edge_with_note"
    return "inferred-looking", "implicit_or_unexplained_edge"


def _confidence_tagging_decision(ambiguous_count: int, ambiguity_threshold: int) -> dict[str, object]:
    threshold = max(1, ambiguity_threshold)
    if ambiguous_count >= threshold:
        return {
            "needed": True,
            "reason": f"Repeated ambiguous wikilinks found: {ambiguous_count} >= threshold {threshold}.",
            "smallest_next_slice": (
                "Add an optional confidence marker only for `## Related` edge lines in `_schema.md`, "
                "then triage the top ambiguous links before any auto-rewrite."
            ),
        }
    if ambiguous_count:
        return {
            "needed": False,
            "reason": f"Only {ambiguous_count} ambiguous wikilink(s), below threshold {threshold}.",
            "smallest_next_slice": "Triage current placeholder/missing_backlink queue before changing schema.",
        }
    return {
        "needed": False,
        "reason": "No ambiguous wikilinks found in the current report.",
        "smallest_next_slice": "No schema slice needed; keep current Related prose and review-queue gates.",
    }


def link_confidence_payload(
    project: Path,
    stale_days: int = 90,
    limit: int = 5,
    ambiguity_threshold: int = 3,
) -> dict[str, object]:
    rows = _wiki_rows(project)
    backlinks = build_backlink_index(project)
    review_items = review_queue_scan(project, stale_days=stale_days)
    review_summary = review_queue_summary(review_items, limit=limit)
    broken_pairs = _broken_pairs(backlinks)
    missing_pairs = _missing_backlink_pairs(review_items)

    samples: dict[str, list[dict[str, object]]] = {name: [] for name in LINK_CLASSES}
    counts: Counter[str] = Counter()
    explicit_marker_counts: Counter[str] = Counter()
    total_links = 0
    sample_limit = max(1, limit)

    for row in rows:
        source_id = as_text(row.get("id"))
        file = as_text(row.get("file"))
        body = as_text(row.get("body"))
        lines = body.splitlines()
        headings = _heading_by_line(body)
        for link in extract_wiki_links(body):
            target_id = as_text(link.get("target_id"))
            line_no = int(link.get("line") or 0)
            line = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
            section = headings.get(line_no, "Page")
            confidence_marker = _related_confidence_marker(section, line)
            if confidence_marker:
                explicit_marker_counts[confidence_marker] += 1
            link_class, reason = _classify_link(
                source_id,
                target_id,
                section,
                line,
                confidence_marker,
                broken_pairs,
                missing_pairs,
            )
            total_links += 1
            counts[link_class] += 1
            if len(samples[link_class]) < sample_limit:
                samples[link_class].append(
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "file": file,
                        "line": line_no,
                        "section": section,
                        "reason": reason,
                        "confidence_marker": confidence_marker,
                    }
                )

    class_counts = {name: counts[name] for name in LINK_CLASSES}
    return {
        "schema_version": 1,
        "project": project.name,
        "generated_on": date.today().isoformat(),
        "read_only": True,
        "inputs": {
            "review_queues": True,
            "backlinks": True,
            "wikilinks": True,
            "stale_days": stale_days,
            "ambiguity_threshold": max(1, ambiguity_threshold),
        },
        "totals": {
            "pages": len(rows),
            "wikilinks": total_links,
            "review_queue_items": len(review_items),
            "broken_links": len(backlinks.get("broken_links") or []),
            "orphans": len(backlinks.get("orphans") or []),
        },
        "class_counts": class_counts,
        "explicit_marker_counts": {name: explicit_marker_counts[name] for name in CONFIDENCE_MARKERS},
        "classes": samples,
        "review_queue_counts": review_summary["counts"],
        "confidence_tagging": _confidence_tagging_decision(
            class_counts["ambiguous-looking"],
            ambiguity_threshold,
        ),
    }


def write_link_confidence_report(root: Path, payload: dict[str, object]) -> Path:
    report_dir = root / "docs" / "link-confidence"
    report_dir.mkdir(parents=True, exist_ok=True)
    project_name = as_text(payload.get("project"))
    generated_on = as_text(payload.get("generated_on")) or date.today().isoformat()
    path = report_dir / f"link-confidence-{project_name}-{generated_on}.md"
    confidence = payload["confidence_tagging"]
    lines = [
        "# Link Confidence Report",
        "",
        f"Date: {generated_on}",
        f"Project: {project_name}",
        f"Read-only: {str(payload.get('read_only') is True).lower()}",
        f"Confidence tagging needed: {'yes' if confidence['needed'] else 'no'}",
        f"Reason: {confidence['reason']}",
        "",
        "## Totals",
        "",
    ]
    for key, value in payload["totals"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Classes", ""])
    for class_name, count in payload["class_counts"].items():
        lines.append(f"### {class_name}")
        lines.append("")
        lines.append(f"Count: {count}")
        for item in payload["classes"][class_name]:
            marker = f" [{item['confidence_marker']}]" if item.get("confidence_marker") else ""
            lines.append(
                f"- `{item['source_id']}` -> `{item['target_id']}`{marker} "
                f"({item['file']}:{item['line']}, {item['reason']})"
            )
        lines.append("")
    lines.extend(["## Explicit Markers", ""])
    for marker, count in payload.get("explicit_marker_counts", {}).items():
        lines.append(f"- {marker}: {count}")
    lines.extend(
        [
            "",
            "## Review Queue Counts",
            "",
        ]
    )
    for queue_type, count in payload["review_queue_counts"].items():
        lines.append(f"- {queue_type}: {count}")
    lines.extend(
        [
            "",
            "## Smallest Next Slice",
            "",
            as_text(confidence["smallest_next_slice"]),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def print_link_confidence(
    root: Path,
    project_name: str,
    stale_days: int,
    limit: int,
    ambiguity_threshold: int,
    fmt: str,
    write_report: bool,
) -> int:
    project = find_project(root, project_name)
    payload = link_confidence_payload(
        project,
        stale_days=stale_days,
        limit=limit,
        ambiguity_threshold=ambiguity_threshold,
    )
    if write_report:
        payload["report_path"] = write_link_confidence_report(root, payload).relative_to(root).as_posix()
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"project: {payload['project']}")
    print(f"read_only: {str(payload['read_only']).lower()}")
    print(f"wikilinks: {payload['totals']['wikilinks']}")
    for class_name, count in payload["class_counts"].items():
        print(f"{class_name}: {count}")
    confidence = payload["confidence_tagging"]
    print(f"confidence_tagging_needed: {'yes' if confidence['needed'] else 'no'}")
    print(f"reason: {confidence['reason']}")
    print(f"smallest_next_slice: {confidence['smallest_next_slice']}")
    if write_report:
        print(f"report: {payload['report_path']}")
    return 0
