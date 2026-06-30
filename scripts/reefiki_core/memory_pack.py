from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from .markdown import as_text
from .memory_diff import memory_diff
from .memory_preflight import memory_preflight
from .memory_route import _is_external_dogfood_intent, memory_route
from .project_paths import find_project
from .review_queues import review_queue_scan
from .wiki_rows import _wiki_rows


def memory_pack(
    root: Path,
    project_name: str,
    task: str,
    global_lookup_fn: Callable[..., dict[str, object]],
    run_golden_queries_fn: Callable[..., dict[str, object]],
    limit: int = 8,
    include_golden: bool = True,
) -> dict[str, object]:
    project = find_project(root, project_name)
    policy = memory_preflight(
        project=project.name,
        visibility="private",
        operation="pack",
        content=task,
        paths=[f"projects/{project.name}/wiki"],
    )
    route = memory_route(task, project_hint=project.name)
    task_route = {
        key: value for key, value in route.items() if key not in {"layer", "project_hint"}
    }
    assembly_trace = {
        "pack_scope": {
            "target_project": project.name,
            "source_layers": ["reefiki"],
            "include_golden": include_golden,
            "include_diff": True,
            "include_open_queues": True,
            "excluded_scopes": ["projects/metrica", "projects/hermes", "secrets", "raw"],
        }
    }
    result: dict[str, object] = {
        "pack_id": hashlib.sha256(f"{project.name}:{task}".encode("utf-8")).hexdigest()[:16],
        "task": task,
        "project": project.name,
        "policy": policy,
        "task_route": {
            "operation": "pack",
            "route_decision": task_route,
        },
        "assembly_trace": assembly_trace,
        "route_trace": {
            "operation": "pack",
            "route_decision": task_route,
        },
        "contents": [],
        "quality": None,
        "golden": None,
        "diff": None,
        "open_queues": [],
        "exclusions": assembly_trace["pack_scope"]["excluded_scopes"],
        "safety_outcome": "block" if policy["outcome"] == "block" else "pass",
        "lookup_error": None,
    }
    if policy["outcome"] == "block":
        return result

    try:
        lookup = global_lookup_fn(
            root,
            query=task,
            project=project.name,
            include_memoir=False,
            include_reefiki=True,
            include_graph=False,
            limit=limit,
        )
    except sqlite3.OperationalError as exc:
        result["lookup_error"] = str(exc)
        lookup = {"reefiki": []}
    dogfood_intent = _is_external_dogfood_intent(task.strip().lower())
    if dogfood_intent:
        critical_order = [
            "odysseus-dogfood-brief",
            "external-tool-watchlist",
            "june-2026-roadmap-batch-recovery",
            "agent-readiness-spec",
            "read-only-cross-project-query-boundary",
        ]
    else:
        critical_order = [
            "reefiki-2-control-plane-spec",
            "reefiki-2-external-agent-research-synthesis",
            "reefiki-2-control-plane-research-comparison",
            "reefiki-routing-and-promotion-contract",
            "global-memory-orchestration-cli",
        ]
    critical_ids = set(critical_order)
    critical_rank = {item_id: index for index, item_id in enumerate(critical_order)}
    max_items_by_type = {
        "synthesis": 5,
        "decision": 3,
        "skill": 2,
        "concept": 2,
        "source": 2,
        "entity": 2,
    }
    contents_by_id: dict[str, dict[str, object]] = {}
    docs_by_id = _dogfood_docs(root) if dogfood_intent else {}
    for item_id, item in docs_by_id.items():
        contents_by_id[item_id] = item
    for item in lookup.get("reefiki", []):
        if not isinstance(item, dict):
            continue
        item_id = as_text(item.get("id"))
        if dogfood_intent and item_id not in critical_ids and not _dogfood_lookup_item_relevant(item):
            continue
        contents_by_id[item_id] = {
            "id": item_id,
            "type": item.get("type"),
            "title": item.get("title"),
            "path": item.get("file"),
            "layer": "reefiki",
            "why_included": _critical_reason(dogfood_intent) if item_id in critical_ids else "matched task lookup",
            "score": item.get("score"),
        }
    existing_ids = set(contents_by_id)
    wiki_rows = _wiki_rows(project)
    available_ids = {as_text(row.get("id")) for row in wiki_rows}
    required_ids = [item_id for item_id in critical_order if item_id in available_ids or item_id in docs_by_id]
    for row in wiki_rows:
        row_id = as_text(row.get("id"))
        if row_id not in critical_ids or row_id in existing_ids:
            continue
        contents_by_id[row_id] = {
            "id": row_id,
            "type": row.get("type"),
            "title": row.get("title"),
            "path": row.get("file"),
            "layer": "reefiki",
            "why_included": _critical_reason(dogfood_intent),
            "score": None,
        }
    contents = list(contents_by_id.values())
    contents.sort(
        key=lambda item: (
            0 if item["id"] in critical_ids else 1,
            critical_rank.get(as_text(item["id"]), 999),
            as_text(item.get("type")),
            as_text(item.get("id")),
        )
    )
    packed_contents: list[dict[str, object]] = []
    type_counts: Counter[str] = Counter()
    for item in contents:
        item_type = as_text(item.get("type")) or "unknown"
        if item["id"] not in critical_ids and type_counts[item_type] >= max_items_by_type.get(item_type, 2):
            continue
        packed_contents.append(item)
        type_counts[item_type] += 1
        if len(packed_contents) >= limit:
            break
    result["contents"] = packed_contents
    packed_ids = {as_text(item.get("id")) for item in packed_contents}
    missing_required_ids = [item_id for item_id in required_ids if item_id not in packed_ids]
    violations: list[str] = []
    if missing_required_ids:
        violations.append("missing_required_ids")
    for item_type, count in sorted(type_counts.items()):
        max_count = max_items_by_type.get(item_type, 2)
        if count > max_count:
            violations.append(f"max_items_by_type:{item_type}")
    result["quality"] = {
        "outcome": "pass" if not violations else "warn",
        "required_ids": required_ids,
        "missing_required_ids": missing_required_ids,
        "max_items_by_type": max_items_by_type,
        "type_counts": dict(sorted(type_counts.items())),
        "violations": violations,
    }
    if include_golden:
        try:
            result["golden"] = {
                key: value
                for key, value in run_golden_queries_fn(root, project.name).items()
                if key in {"total", "passed", "failed", "path"}
            }
        except (SystemExit, sqlite3.OperationalError) as exc:
            result["golden"] = {"error": str(exc)}
    try:
        diff = memory_diff(root, project.name, from_ref="HEAD")
        result["diff"] = {key: diff[key] for key in ["from", "to", "counts", "total", "files"]}
    except SystemExit as exc:
        result["diff"] = {"error": str(exc)}
    try:
        queue_items = review_queue_scan(project)
        grouped_queues: dict[str, list[dict[str, object]]] = {}
        for item in queue_items:
            grouped_queues.setdefault(as_text(item.get("queue_type")), []).append(item)
        result["open_queues"] = [
            {
                "queue_type": queue_type,
                "count": len(items),
                "items": [
                    {
                        "page_id": item.get("page_id"),
                        "reason": item.get("reason"),
                        "related_page_ids": item.get("related_page_ids", []),
                        "suggested_action": item.get("suggested_action"),
                    }
                    for item in items[:3]
                ],
            }
            for queue_type, items in sorted(grouped_queues.items())
        ]
    except Exception as exc:  # pragma: no cover - defensive reporting for handoff output
        result["open_queues"] = [{"error": str(exc)}]
    return result


def _critical_reason(dogfood_intent: bool) -> str:
    if dogfood_intent:
        return "external dogfood/onboarding context"
    return "critical REEFIKI 2 handoff context"


def _dogfood_docs(root: Path) -> dict[str, dict[str, object]]:
    candidates = [
        (
            "odysseus-dogfood-brief",
            root / "docs" / "ODYSSEUS_DOGFOOD.md",
            "Odysseus dogfood brief",
        ),
        (
            "agent-readiness-spec",
            root / "docs" / "skill-products" / "AGENT_READINESS_SPEC.md",
            "Agent Readiness spec",
        ),
    ]
    docs: dict[str, dict[str, object]] = {}
    for item_id, path, title in candidates:
        if not path.exists():
            continue
        docs[item_id] = {
            "id": item_id,
            "type": "docs",
            "title": title,
            "path": path.relative_to(root).as_posix(),
            "layer": "reefiki",
            "why_included": "external dogfood/onboarding context",
            "score": None,
        }
    return docs


def _dogfood_lookup_item_relevant(item: dict[str, object]) -> bool:
    score = item.get("score")
    if isinstance(score, int | float) and score > 0:
        return True
    text = " ".join(
        as_text(item.get(key))
        for key in ["id", "type", "title", "path", "tags", "useful_when"]
    ).lower()
    return any(
        token in text
        for token in [
            "odysseus",
            "dogfood",
            "onboarding",
            "roadmap",
            "trigger",
            "agent-readiness",
            "agent readiness",
            "readiness",
            "external",
            "cross-project",
            "governance",
            "watchlist",
        ]
    )


def memory_pack_strict_result(result: dict[str, object]) -> dict[str, object]:
    blocking_reasons: list[str] = []
    if result.get("safety_outcome") == "block":
        blocking_reasons.append("policy:block")
    if result.get("lookup_error"):
        blocking_reasons.append("lookup:error")
    quality = result.get("quality")
    if isinstance(quality, dict) and quality.get("outcome") != "pass":
        violations = quality.get("violations") or ["warn"]
        blocking_reasons.extend(f"quality:{violation}" for violation in violations)
    golden = result.get("golden")
    if isinstance(golden, dict):
        if golden.get("error"):
            blocking_reasons.append("golden:error")
        if int(golden.get("failed") or 0) > 0:
            blocking_reasons.append("golden:failed")
    diff = result.get("diff")
    if isinstance(diff, dict) and diff.get("error"):
        blocking_reasons.append("diff:error")
    return {
        "outcome": "fail" if blocking_reasons else "pass",
        "blocking_reasons": blocking_reasons,
    }


def print_memory_pack_result(result: dict[str, object], strict: bool, fmt: str) -> int:
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"# Memory Pack: {result['task']}")
        print("")
        print(f"- project: {result['project']}")
        print(f"- safety: {result['safety_outcome']}")
        print(f"- items: {len(result['contents'])}")
        print(f"- strict: {result['strict']['outcome']}")
        if result["strict"]["blocking_reasons"]:
            print(f"- strict_reasons: {', '.join(result['strict']['blocking_reasons'])}")
        if result.get("lookup_error"):
            print(f"- lookup_error: {result['lookup_error']}")
        print("")
        print("## Contents")
        for item in result["contents"]:
            print(f"- {item['id']} ({item['path']}) - {item['why_included']}")
        print("")
        print("## Quality")
        quality = result.get("quality")
        if isinstance(quality, dict):
            print(f"- outcome: {quality.get('outcome', '-')}")
            missing = quality.get("missing_required_ids") or []
            if missing:
                print(f"- missing_required_ids: {', '.join(str(item) for item in missing)}")
            else:
                print("- missing_required_ids: none")
            violations = quality.get("violations") or []
            if violations:
                print(f"- violations: {', '.join(str(item) for item in violations)}")
            else:
                print("- violations: none")
        else:
            print("- outcome: unknown")
        print("")
        print("## Golden")
        golden = result.get("golden")
        if isinstance(golden, dict):
            print(f"- passed: {golden.get('passed', '-')}/{golden.get('total', '-')}")
            if golden.get("failed"):
                print(f"- failed: {golden.get('failed')}")
            if golden.get("error"):
                print(f"- error: {golden.get('error')}")
        print("")
        print("## Diff")
        diff = result.get("diff")
        if isinstance(diff, dict):
            print(f"- total: {diff.get('total', '-')}")
            print(f"- from: {diff.get('from', '-')}")
            print(f"- to: {diff.get('to', '-')}")
        print("")
        print("## Open Queues")
        queues = result.get("open_queues", [])
        if queues:
            for queue in queues:
                if isinstance(queue, dict):
                    label = queue.get("queue_type") or "error"
                    count = queue.get("count") or queue.get("error")
                    print(f"- {label}: {count}")
                    for item in queue.get("items", [])[:3] if isinstance(queue.get("items"), list) else []:
                        if not isinstance(item, dict):
                            continue
                        print(f"  - {item.get('page_id')}: {item.get('reason')}")
                        print(f"    action: {item.get('suggested_action')}")
        else:
            print("- none")
        print("")
        print("## Exclusions")
        for exclusion in result["exclusions"]:
            print(f"- {exclusion}")
    if result.get("safety_outcome") == "block":
        return 1
    if strict and result["strict"]["outcome"] == "fail":
        return 1
    return 0
