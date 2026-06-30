from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .code_context import graphify_report_path
from .graphify_adapter import graphify_lookup
from .index_search import project_local_lookup
from .memoir_io import memoir_store_path, run_memoir as run_memoir_with_timeout
from .memory_preflight import memory_global_strict_preflight
from .process_utils import SUBPROCESS_TIMEOUT_SECONDS
from .project_paths import find_project, list_projects


GLOBAL_MEMOIR_STORE = memoir_store_path()
MEMOIR_LOOKUP_TIMEOUT_SECONDS = int(
    os.environ.get("REEFIKI_MEMOIR_LOOKUP_TIMEOUT", str(min(SUBPROCESS_TIMEOUT_SECONDS, 15)))
)
PRIVATE_GLOBAL_LOOKUP_PROJECTS = {"metrica", "hermes"}


def run_memoir(store: Path, args: list[str]) -> dict[str, object]:
    return run_memoir_with_timeout(store, args, timeout_seconds=MEMOIR_LOOKUP_TIMEOUT_SECONDS)


def _provider_error(provider: str, exc: BaseException) -> dict[str, object]:
    return {
        "provider": provider,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def _project_key(project: str) -> str:
    return project.strip().casefold()


def _blocked_lookup_next_action(project: str, policy: dict[str, object], limit: int) -> str | None:
    project_key = _project_key(project)
    blocking_reasons = set(policy.get("blocking_reasons", []))
    if "secret_like_content" in blocking_reasons:
        return None
    if f"forbidden_scope:projects/{project_key}" not in blocking_reasons:
        return None
    return (
        "global memory lookup keeps private project scopes isolated; "
        "use project-local search/query instead: "
        f"python scripts/reefiki.py --project projects/{project_key} search \"<query>\" "
        f"--limit {limit} --format json"
    )


def _global_lookup_projects(root: Path, project: str | None) -> list[Path]:
    if project:
        return [find_project(root, project)]
    return [
        project_path
        for project_path in list_projects(root)
        if _project_key(project_path.name) not in PRIVATE_GLOBAL_LOOKUP_PROJECTS
    ]


def global_lookup(
    root: Path,
    query: str,
    project: str | None,
    include_memoir: bool,
    include_reefiki: bool,
    include_graph: bool,
    limit: int,
) -> dict[str, object]:
    target_project = project or "reefiki"
    policy = memory_global_strict_preflight(
        project=target_project,
        visibility="private",
        operation="lookup",
        content=query,
        paths=[f"projects/{target_project}"] if project else [],
    )
    result: dict[str, object] = {
        "query": query,
        "policy": policy,
        "memoir": None,
        "reefiki": [],
        "graphify": [],
    }
    if policy["outcome"] == "block":
        next_action = _blocked_lookup_next_action(target_project, policy, limit)
        if next_action:
            result["next_action"] = next_action
        return result

    target_projects = _global_lookup_projects(root, project)

    if include_memoir:
        try:
            result["memoir"] = run_memoir(
                GLOBAL_MEMOIR_STORE,
                ["recall", query, "--limit", str(limit), "--threshold", "0.35"],
            )
        except (SystemExit, subprocess.TimeoutExpired) as exc:
            result["memoir"] = _provider_error("memoir", exc)

    if include_reefiki:
        reefiki_hits: list[dict[str, object]] = []
        per_project_limit = max(1, limit)
        for project_path in target_projects:
            reefiki_hits.extend(project_local_lookup(project_path, query, per_project_limit))
        reefiki_hits.sort(key=lambda item: item["score"])
        result["reefiki"] = reefiki_hits[:limit]

    if include_graph:
        graph_hits: list[dict[str, object]] = []
        query_lower = query.lower()
        for project_path in target_projects:
            graph_matches = graphify_lookup(project_path, query, limit)
            if graph_matches:
                graph_hits.extend(graph_matches)
                continue
            report = graphify_report_path(project_path)
            if not report:
                continue
            lines = report.read_text(encoding="utf-8", errors="replace").splitlines()
            matches: list[dict[str, object]] = []
            for idx, line in enumerate(lines, 1):
                if query_lower in line.lower():
                    matches.append(
                        {
                            "project": project_path.name,
                            "report": str(report),
                            "line": idx,
                            "text": line.strip(),
                        }
                    )
                    if len(matches) >= limit:
                        break
            graph_hits.extend(matches)
        result["graphify"] = graph_hits[:limit]
    return result


def print_global_lookup(
    root: Path,
    query: str,
    project: str | None,
    include_memoir: bool,
    include_reefiki: bool,
    include_graph: bool,
    limit: int,
    fmt: str,
) -> int:
    result = global_lookup(
        root,
        query=query,
        project=project,
        include_memoir=include_memoir,
        include_reefiki=include_reefiki,
        include_graph=include_graph,
        limit=limit,
    )
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("policy", {}).get("outcome") == "block" else 0
    if result.get("policy", {}).get("outcome") == "block":
        print(f"query: {result['query']}")
        print("policy: block")
        print(f"blocking_reasons: {', '.join(result['policy']['blocking_reasons'])}")
        if result.get("next_action"):
            print(f"next_action: {result['next_action']}")
        return 1
    print(f"query: {result['query']}")
    memoir_block = result.get("memoir")
    if memoir_block:
        if isinstance(memoir_block, dict) and memoir_block.get("error"):
            print(f"memoir: error: {memoir_block['error']}")
        else:
            memories = memoir_block.get("memories", []) if isinstance(memoir_block, dict) else []
            print(f"memoir: {len(memories)} hit(s)")
            for item in memories[:limit]:
                print(f"  - {item.get('path')}: {item.get('content')}")
    reefiki_block = result.get("reefiki", [])
    print(f"reefiki: {len(reefiki_block)} hit(s)")
    for item in reefiki_block:
        print(f"  - [{item['project']}] {item['title']} ({item['file']})")
    graph_block = result.get("graphify", [])
    print(f"graphify: {len(graph_block)} hit(s)")
    for item in graph_block:
        if "report" in item:
            print(f"  - [{item['project']}] {item['text']} ({item['report']}:{item['line']})")
        else:
            location = item.get("source_file") or item.get("graph")
            if item.get("source_location"):
                location = f"{location}:{item['source_location']}"
            print(f"  - [{item['project']}] {item['text']} ({location})")
    return 0
