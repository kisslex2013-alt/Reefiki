from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path

from .file_utils import write_unique_text
from .health import knowledge_health_payload
from .markdown import as_text
from .memory_diff import memory_diff
from .memory_pack import memory_pack_strict_result
from .memory_preflight import memory_preflight
from .memory_status import compact_status_result, memory_status
from .project_paths import find_project
from .promotion import promotion_inbox_summary
from .review_queues import review_queue_scan, review_queue_summary


def reflection_candidate_actions(payload: dict[str, object], limit: int) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    included = payload.get("included", {})
    if not isinstance(included, dict):
        return actions
    health = included.get("health", {})
    queues = included.get("review_queues", {})
    promotion = included.get("promotion_inbox", {})
    pack_quality = included.get("pack_quality", {})
    changed_paths = included.get("changed_paths", {})
    if isinstance(health, dict) and health.get("outcome") == "fail":
        actions.append(
            {
                "action": "run doctor and fix integrity issues",
                "reason": "health gate failed",
                "risk": "low",
            }
        )
    if isinstance(queues, dict):
        queue_list = queues.get("queues", [])
        if isinstance(queue_list, list) and queue_list:
            counted_queues = [queue for queue in queue_list if isinstance(queue, dict)]
            top_queue = max(counted_queues, key=lambda queue: int(queue.get("count", 0) or 0), default=None)
            if top_queue:
                queue_type = as_text(top_queue.get("queue_type"))
                if queue_type:
                    actions.append(
                        {
                            "action": f"run review-queues --type {queue_type} --limit {max(1, limit)}",
                            "reason": "largest open review queue",
                            "risk": "low",
                        }
                    )
    if isinstance(promotion, dict) and int(promotion.get("active", 0) or 0) > 0:
        actions.append(
            {
                "action": f"run memory promotion-inbox --project {payload.get('project')}",
                "reason": "promotion drafts are waiting for review",
                "risk": "low",
            }
        )
    if isinstance(pack_quality, dict):
        strict = pack_quality.get("strict", {})
        if isinstance(strict, dict) and strict.get("outcome") == "fail":
            actions.append(
                {
                    "action": f"run memory pack \"{payload.get('task')}\" --project {payload.get('project')} --strict",
                    "reason": "context pack strict gate failed",
                    "risk": "low",
                }
            )
    if isinstance(changed_paths, dict) and int(changed_paths.get("total", 0) or 0) > 0:
        baseline_arg = (
            f"--since-date {payload.get('since')}"
            if changed_paths.get("since_date")
            else f"--from {payload.get('since')}"
        )
        actions.append(
            {
                "action": f"review memory diff --project {payload.get('project')} {baseline_arg}",
                "reason": "durable wiki paths changed since the reflection baseline",
                "risk": "low",
            }
        )
    if isinstance(changed_paths, dict) and changed_paths.get("error"):
        actions.append(
            {
                "action": f"fix memory reflect --since baseline {payload.get('since')}",
                "reason": "diff baseline could not be resolved",
                "risk": "low",
            }
        )
    if not actions:
        actions.append(
            {
                "action": "no action",
                "reason": "no open reflection signals",
                "risk": "none",
            }
        )
    return actions


def reflection_report_markdown(payload: dict[str, object]) -> str:
    included = payload.get("included", {}) if isinstance(payload.get("included"), dict) else {}
    changed_paths = included.get("changed_paths", {}) if isinstance(included.get("changed_paths"), dict) else {}
    health = included.get("health", {}) if isinstance(included.get("health"), dict) else {}
    queues = included.get("review_queues", {}) if isinstance(included.get("review_queues"), dict) else {}
    promotion = included.get("promotion_inbox", {}) if isinstance(included.get("promotion_inbox"), dict) else {}
    pack_quality = included.get("pack_quality", {}) if isinstance(included.get("pack_quality"), dict) else {}
    pack_strict = pack_quality.get("strict", {}) if isinstance(pack_quality.get("strict"), dict) else {}
    lines = [
        f"# Memory Reflection: {payload.get('project')}",
        "",
        f"Generated: {payload.get('generated_on')}",
        f"Since: {payload.get('since')}",
        f"Outcome: {payload.get('outcome')}",
        "",
        "## Included Sources",
    ]
    for source in payload.get("included_sources", []):
        lines.append(f"- {source}")
    lines.extend(
        [
            "",
            "## Summary",
            f"- changed_paths: {changed_paths.get('total', 0)}",
            f"- health: {health.get('outcome', '-')}",
            f"- review_queues: {queues.get('total', 0)}",
            f"- promotion_active: {promotion.get('active', 0)}",
            f"- pack_strict: {pack_strict.get('outcome', '-')}",
            "",
            "## Candidate Actions",
        ]
    )
    for item in payload.get("candidate_actions", []):
        if isinstance(item, dict):
            lines.append(f"- {item.get('action')} ({item.get('reason')}; risk: {item.get('risk')})")
    lines.extend(["", "## Blocked Actions"])
    for item in payload.get("blocked_actions", []):
        if isinstance(item, dict):
            lines.append(f"- {item.get('action')} - {item.get('reason')}")
    lines.extend(["", "## Excluded Scopes"])
    for scope in payload.get("excluded_scopes", []):
        lines.append(f"- {scope}")
    lines.extend(["", "## JSON Payload", "", "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines).rstrip() + "\n"


def write_memory_reflection_report(project: Path, payload: dict[str, object]) -> Path:
    plans = project / "plans"
    path = plans / f"reflection-{date.today().isoformat()}.md"
    return write_unique_text(path, reflection_report_markdown(payload))


def read_only_pack_quality(
    root: Path,
    project: Path,
    task: str,
    limit: int,
    pack_fn: Callable[..., dict[str, object]],
) -> dict[str, object]:
    index_path = project / ".reefiki" / "index.sqlite"
    if not index_path.exists():
        return {
            "quality": None,
            "golden": None,
            "strict": {
                "outcome": "fail",
                "blocking_reasons": ["index:missing"],
            },
            "open_queues": [],
            "error": "search index missing; run project index before strict pack reflection",
        }
    pack = pack_fn(root, project.name, task, limit=max(limit, 8))
    pack["strict"] = memory_pack_strict_result(pack)
    return {
        "quality": pack.get("quality"),
        "golden": pack.get("golden"),
        "strict": pack.get("strict"),
        "open_queues": pack.get("open_queues", []),
    }


def memory_reflect(
    root: Path,
    project_name: str,
    since: str,
    task: str,
    pack_fn: Callable[..., dict[str, object]],
    limit: int = 5,
) -> dict[str, object]:
    project = find_project(root, project_name)
    limit = max(1, limit)
    policy = memory_preflight(
        project=project.name,
        visibility="private",
        operation="reflect",
        content=task,
        paths=[f"projects/{project.name}/wiki", f"projects/{project.name}/plans"],
    )
    included_sources = [
        "memory_diff",
        "health",
        "review_queues_summary",
        "memory_status_summary",
        "memory_pack_strict",
        "promotion_inbox",
    ]
    excluded_scopes = [
        "wiki writes",
        "raw",
        "seen",
        "_user",
        "config",
        "git state",
        "external services",
        "background jobs",
    ]
    diff_error = False
    try:
        diff_kwargs = (
            {"from_ref": "HEAD", "since_date": since}
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", since.strip())
            else {"from_ref": since}
        )
        changed_paths = {
            key: value
            for key, value in memory_diff(root, project.name, **diff_kwargs).items()
            if key in {"from", "to", "since_date", "counts", "total", "files"}
        }
    except (SystemExit, ValueError) as exc:
        diff_error = True
        changed_paths = {"from": since, "to": "WORKTREE", "error": str(exc), "total": 0, "files": []}
    health = knowledge_health_payload(project)
    review_summary = review_queue_summary(review_queue_scan(project), limit=limit)
    status_summary = compact_status_result(memory_status(root, project.name))
    pack_quality = read_only_pack_quality(root, project, task, limit=limit, pack_fn=pack_fn)
    promotion = promotion_inbox_summary(project)
    payload: dict[str, object] = {
        "project": project.name,
        "since": since,
        "task": task,
        "generated_on": date.today().isoformat(),
        "outcome": "blocked" if policy.get("outcome") == "block" or diff_error else "review",
        "policy": policy,
        "included_sources": included_sources,
        "excluded_scopes": excluded_scopes,
        "included": {
            "changed_paths": changed_paths,
            "health": {
                "outcome": health.get("outcome"),
                "warnings": health.get("warnings", []),
                "recommendations": health.get("recommendations", []),
                "size": health.get("size", {}),
                "structure": health.get("structure", {}),
            },
            "review_queues": review_summary,
            "memory_status": status_summary,
            "pack_quality": pack_quality,
            "promotion_inbox": promotion,
        },
        "candidate_actions": [],
        "blocked_actions": [
            {
                "action": "auto-apply wiki changes",
                "reason": "reflection is report-only",
            },
            {
                "action": "write raw session capture",
                "reason": "raw is immutable and reflection must not capture transcripts",
            },
            {
                "action": "start daemon or cron",
                "reason": "first implementation is explicit CLI only",
            },
            {
                "action": "stage, commit, push, delete, or rewrite files",
                "reason": "reflection is a review artifact, not an apply path",
            },
        ],
    }
    payload["candidate_actions"] = reflection_candidate_actions(payload, limit=limit)
    return payload


def print_memory_reflect_result(payload: dict[str, object], fmt: str) -> int:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"# Memory Reflection: {payload['project']}")
        print(f"- since: {payload['since']}")
        print(f"- outcome: {payload['outcome']}")
        print("")
        print("## Candidate Actions")
        for item in payload.get("candidate_actions", []):
            if isinstance(item, dict):
                print(f"- {item.get('action')} ({item.get('reason')}; risk: {item.get('risk')})")
        print("")
        print("## Blocked Actions")
        for item in payload.get("blocked_actions", []):
            if isinstance(item, dict):
                print(f"- {item.get('action')} - {item.get('reason')}")
    return 1 if payload.get("outcome") == "blocked" else 0
