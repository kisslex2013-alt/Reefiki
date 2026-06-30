from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

try:
    from reefiki_memory import build_default_registry
except ModuleNotFoundError:  # pragma: no cover - package import fallback for tests
    from scripts.reefiki_memory import build_default_registry

from .graphify_adapter import graphify_artifact_status
from .markdown import as_text
from .memory_preflight import memory_preflight
from .project_paths import find_project, list_projects
from .promotion import promotion_inbox_summary
from .review_queues import review_queue_scan


def memory_status(root: Path, project_name: str = "reefiki") -> dict[str, object]:
    project = find_project(root, project_name) if (root / "projects").exists() else root
    registry = build_default_registry(project)
    result = registry.to_dict()
    result["project"] = project.name
    result["policy"] = memory_preflight(
        project=project.name,
        visibility="public",
        operation="status",
        content="",
        paths=[f"projects/{project.name}"],
    )
    result["graphify"] = graphify_artifact_status(project)
    try:
        queue_items = review_queue_scan(project)
        counts = Counter(as_text(item.get("queue_type")) for item in queue_items)
        result["review_queues"] = {
            "total": len(queue_items),
            "counts": dict(sorted(counts.items())),
        }
    except Exception as exc:  # pragma: no cover - defensive status reporting
        result["review_queues"] = {"error": str(exc)}
    try:
        result["promotion_inbox"] = promotion_inbox_summary(project)
    except Exception as exc:  # pragma: no cover - defensive status reporting
        result["promotion_inbox"] = {"error": str(exc)}
    result["next_action"] = memory_status_next_action(result)
    return result


def memory_status_all_projects(root: Path, only_open: bool = False) -> dict[str, object]:
    projects = [
        memory_status(root, project.name)
        for project in list_projects(root)
    ]
    if only_open:
        projects = [
            item for item in projects
            if int(item.get("review_queues", {}).get("total", 0)) > 0
            or int(item.get("promotion_inbox", {}).get("active", 0)) > 0
        ]
    totals = {
        "review_queues": sum(
            int(item.get("review_queues", {}).get("total", 0))
            for item in projects
            if isinstance(item.get("review_queues"), dict)
        ),
        "promotion_active": sum(
            int(item.get("promotion_inbox", {}).get("active", 0))
            for item in projects
            if isinstance(item.get("promotion_inbox"), dict)
        ),
        "promotion_closed": sum(
            int(item.get("promotion_inbox", {}).get("closed", 0))
            for item in projects
            if isinstance(item.get("promotion_inbox"), dict)
        ),
    }
    return {
        "project": "all",
        "only_open": only_open,
        "total": len(projects),
        "totals": totals,
        "projects": projects,
    }


def memory_status_has_open(result: dict[str, object]) -> bool:
    if result.get("project") == "all":
        projects = result.get("projects", [])
        if isinstance(projects, list) and any(
            memory_status_has_open(item)
            for item in projects
            if isinstance(item, dict)
        ):
            return True
        totals = result.get("totals", {})
        if not isinstance(totals, dict):
            return False
        return int(totals.get("review_queues", 0)) > 0 or int(totals.get("promotion_active", 0)) > 0
    queues = result.get("review_queues", {})
    promotion = result.get("promotion_inbox", {})
    if isinstance(queues, dict) and queues.get("error"):
        return True
    if isinstance(promotion, dict) and promotion.get("error"):
        return True
    queue_total = int(queues.get("total", 0)) if isinstance(queues, dict) else 0
    promotion_active = int(promotion.get("active", 0)) if isinstance(promotion, dict) else 0
    return queue_total > 0 or promotion_active > 0


def memory_status_next_action(result: dict[str, object]) -> str | None:
    if result.get("project") == "all":
        totals = result.get("totals", {})
        if isinstance(totals, dict) and int(totals.get("review_queues", 0)) > 0:
            return "run memory status --all-projects --only-open --summary"
        if isinstance(totals, dict) and int(totals.get("promotion_active", 0)) > 0:
            return "run memory status --all-projects --only-open --summary"
        return None
    project = as_text(result.get("project")) or "reefiki"
    queues = result.get("review_queues", {})
    promotion = result.get("promotion_inbox", {})
    if isinstance(queues, dict) and queues.get("error"):
        return "fix review queue scan error before using status gate"
    if isinstance(queues, dict) and int(queues.get("total", 0)) > 0:
        return f"run review-queues --summary for project {project}"
    if isinstance(promotion, dict) and promotion.get("error"):
        return "fix promotion inbox scan error before using status gate"
    if isinstance(promotion, dict) and int(promotion.get("active", 0)) > 0:
        return f"run memory promotion-inbox --project {project}"
    return None


def compact_status_item(item: dict[str, object]) -> dict[str, object]:
    queues = item.get("review_queues", {}) if isinstance(item.get("review_queues"), dict) else {}
    promotion = item.get("promotion_inbox", {}) if isinstance(item.get("promotion_inbox"), dict) else {}
    graphify = item.get("graphify", {}) if isinstance(item.get("graphify"), dict) else {}
    policy = item.get("policy", {}) if isinstance(item.get("policy"), dict) else {}
    return {
        "project": item.get("project"),
        "policy": policy.get("outcome"),
        "graphify": graphify.get("status"),
        "review_queues": queues,
        "promotion_inbox": promotion,
        "has_open": memory_status_has_open(item),
        "next_action": item.get("next_action"),
    }


def compact_status_result(result: dict[str, object]) -> dict[str, object]:
    if result.get("project") == "all":
        return {
            "project": "all",
            "summary": True,
            "only_open": result.get("only_open", False),
            "total": result.get("total", 0),
            "totals": result.get("totals", {}),
            "has_open": memory_status_has_open(result),
            "next_action": memory_status_next_action(result),
            "projects": [
                compact_status_item(item)
                for item in result.get("projects", [])
                if isinstance(item, dict)
            ],
        }
    compact = compact_status_item(result)
    compact["summary"] = True
    return compact


def print_memory_status(
    root: Path,
    project_name: str,
    all_projects: bool,
    only_open: bool,
    summary: bool,
    fail_on_open: bool,
    fmt: str,
) -> int:
    result = memory_status_all_projects(root, only_open=only_open) if all_projects else memory_status(root, project_name=project_name)
    result["has_open"] = memory_status_has_open(result)
    output_result = compact_status_result(result) if summary else result
    if isinstance(output_result, dict):
        output_result["has_open"] = result["has_open"]
    if fmt == "jsonl":
        items = output_result.get("projects", []) if all_projects else [output_result]
        for item in items:
            print(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        return 1 if fail_on_open and result["has_open"] else 0
    if fmt == "json":
        print(json.dumps(output_result, ensure_ascii=False, indent=2))
        return 1 if fail_on_open and result["has_open"] else 0
    if summary:
        if all_projects:
            print(f"projects: {output_result['total']}")
            print(f"open: {'yes' if result['has_open'] else 'no'}")
            totals = output_result.get("totals", {})
            if isinstance(totals, dict):
                print(f"review_queues: {totals.get('review_queues', '-')}")
                print(f"promotion_inbox: active={totals.get('promotion_active', '-')} closed={totals.get('promotion_closed', '-')}")
            if output_result.get("next_action"):
                print(f"next: {output_result['next_action']}")
            for item in output_result.get("projects", []):
                if isinstance(item, dict):
                    queues = item.get("review_queues", {}) if isinstance(item.get("review_queues"), dict) else {}
                    promotion = item.get("promotion_inbox", {}) if isinstance(item.get("promotion_inbox"), dict) else {}
                    print(
                        f"  - {item.get('project')}: "
                        f"review_queues={queues.get('total', '-')} "
                        f"promotion_active={promotion.get('active', '-')} "
                        f"promotion_closed={promotion.get('closed', '-')}"
                    )
        else:
            print(f"project: {output_result.get('project')}")
            print(f"open: {'yes' if result['has_open'] else 'no'}")
            print(f"graphify: {output_result.get('graphify')}")
            queues = output_result.get("review_queues", {}) if isinstance(output_result.get("review_queues"), dict) else {}
            promotion = output_result.get("promotion_inbox", {}) if isinstance(output_result.get("promotion_inbox"), dict) else {}
            print(f"review_queues: {queues.get('total', '-')}")
            print(f"promotion_inbox: active={promotion.get('active', '-')} closed={promotion.get('closed', '-')}")
            if output_result.get("next_action"):
                print(f"next: {output_result['next_action']}")
        return 1 if fail_on_open and result["has_open"] else 0
    if all_projects:
        print(f"projects: {result['total']}")
        totals = result.get("totals", {})
        if isinstance(totals, dict):
            print(f"review_queues: {totals.get('review_queues', '-')}")
            print(f"promotion_inbox: active={totals.get('promotion_active', '-')} closed={totals.get('promotion_closed', '-')}")
        for item in result.get("projects", []):
            if not isinstance(item, dict):
                continue
            queues = item.get("review_queues", {}) if isinstance(item.get("review_queues"), dict) else {}
            promotion = item.get("promotion_inbox", {}) if isinstance(item.get("promotion_inbox"), dict) else {}
            print(
                f"  - {item.get('project')}: "
                f"review_queues={queues.get('total', '-')} "
                f"promotion_active={promotion.get('active', '-')} "
                f"promotion_closed={promotion.get('closed', '-')}"
            )
        return 1 if fail_on_open and result["has_open"] else 0
    providers = result.get("providers", {})
    print(f"providers: {len(providers)}")
    if isinstance(providers, dict):
        for provider_id, provider in providers.items():
            capabilities = ", ".join(provider.get("capabilities", []))
            print(f"  - {provider_id}: {provider.get('kind')} [{capabilities}]")
    graphify = result.get("graphify", {})
    if isinstance(graphify, dict):
        print(f"graphify: {graphify.get('status')}")
    queues = result.get("review_queues", {})
    if isinstance(queues, dict):
        print(f"review_queues: {queues.get('total', '-')}")
    promotion = result.get("promotion_inbox", {})
    if isinstance(promotion, dict):
        print(f"promotion_inbox: active={promotion.get('active', '-')} closed={promotion.get('closed', '-')}")
    return 1 if fail_on_open and result["has_open"] else 0
