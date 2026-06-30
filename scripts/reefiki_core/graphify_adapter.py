from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .code_context import graphify_graph_path, graphify_report_path, project_code_path
from .markdown import as_text
from .process_utils import SUBPROCESS_TIMEOUT_SECONDS


TOKEN_RE = re.compile(r"[a-z0-9]+")


def _load_graph(graph_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(graph_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid graphify graph JSON: {graph_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid graphify graph JSON: {graph_path}: root must be an object")
    return payload


def _git_output(code_path: Path, args: list[str]) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=code_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def graphify_artifact_status(project: Path) -> dict[str, object]:
    report = graphify_report_path(project)
    graph_path = graphify_graph_path(project)
    if report is None and graph_path is None:
        return {
            "status": "missing_report",
            "report_path": None,
            "graph_path": None,
            "next_action": "run graphify only when structural navigation is needed",
        }
    if graph_path is None:
        return {
            "status": "report_only",
            "report_path": str(report) if report else None,
            "graph_path": None,
            "next_action": "run graphify update only when structural navigation is needed",
        }

    payload = _load_graph(graph_path)
    built_at_commit = as_text(payload.get("built_at_commit")) or None
    code_path = project_code_path(project)
    current_head = _git_output(code_path, ["rev-parse", "HEAD"]) if code_path else None
    changed_files_since_build: int | None = None
    status = "available"
    next_action = None
    if built_at_commit and current_head and built_at_commit != current_head:
        diff_output = _git_output(code_path, ["diff", "--name-only", f"{built_at_commit}..HEAD"]) if code_path else None
        if diff_output is not None:
            changed_files_since_build = len([line for line in diff_output.splitlines() if line.strip()])
        status = "stale_report"
        next_action = "run graphify update only when structural navigation is needed"

    return {
        "status": status,
        "report_path": str(report) if report else None,
        "graph_path": str(graph_path),
        "built_at_commit": built_at_commit,
        "current_head": current_head,
        "changed_files_since_build": changed_files_since_build,
        "next_action": next_action,
    }


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _node_id(node: dict[str, object]) -> str:
    return as_text(node.get("id")) or as_text(node.get("node_id"))


def _node_text(node: dict[str, object]) -> str:
    return " ".join(
        [
            _node_id(node),
            as_text(node.get("label")),
            as_text(node.get("source_file")),
            as_text(node.get("source_location")),
        ]
    ).lower()


def _score_node(node: dict[str, object], query: str) -> int:
    haystack = _node_text(node)
    query_norm = " ".join(_tokens(query))
    score = 0
    if query_norm and query_norm in " ".join(_tokens(haystack)):
        score += 5
    for token in set(_tokens(query)):
        if token in haystack:
            score += 1
    return score


def _neighbor_items(
    node_id: str,
    nodes_by_id: dict[str, dict[str, object]],
    links: list[dict[str, object]],
    limit: int = 5,
) -> list[dict[str, object]]:
    neighbors: list[dict[str, object]] = []
    for link in links:
        source = as_text(link.get("source"))
        target = as_text(link.get("target"))
        if source == node_id:
            other_id = target
            direction = "out"
        elif target == node_id:
            other_id = source
            direction = "in"
        else:
            continue
        other = nodes_by_id.get(other_id, {})
        neighbors.append(
            {
                "node_id": other_id,
                "label": as_text(other.get("label")) or other_id,
                "source_file": as_text(other.get("source_file")),
                "source_location": as_text(other.get("source_location")),
                "relation": as_text(link.get("relation")),
                "direction": direction,
                "confidence": as_text(link.get("confidence")),
            }
        )
        if len(neighbors) >= limit:
            break
    return neighbors


def graphify_lookup(project: Path, query: str, limit: int) -> list[dict[str, object]]:
    graph_path = graphify_graph_path(project)
    if not graph_path:
        return []
    payload = _load_graph(graph_path)
    nodes = [node for node in payload.get("nodes", []) if isinstance(node, dict)]
    links = [link for link in payload.get("links", []) if isinstance(link, dict)]
    nodes_by_id = {_node_id(node): node for node in nodes if _node_id(node)}
    freshness = graphify_artifact_status(project)
    scored = [
        (score, node)
        for node in nodes
        if (score := _score_node(node, query)) > 0
    ]
    scored.sort(key=lambda item: (-item[0], as_text(item[1].get("source_file")), as_text(item[1].get("label"))))

    hits: list[dict[str, object]] = []
    for score, node in scored[:limit]:
        node_id = _node_id(node)
        label = as_text(node.get("label")) or node_id
        source_file = as_text(node.get("source_file"))
        source_location = as_text(node.get("source_location"))
        hits.append(
            {
                "project": project.name,
                "id": node_id,
                "node_id": node_id,
                "label": label,
                "source_file": source_file,
                "source_location": source_location,
                "score": score,
                "text": f"{label} ({source_file}:{source_location})",
                "graph": str(graph_path),
                "freshness": freshness,
                "neighbors": _neighbor_items(node_id, nodes_by_id, links),
            }
        )
    return hits
