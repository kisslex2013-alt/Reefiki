from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .markdown import as_text


BLOCKING_OUTCOMES = {"block", "fail", "failed", "error"}
REVIEW_OUTCOMES = {"review", "warn", "warning"}


def _normalized_outcome(value: object, default: str = "info") -> str:
    outcome = as_text(value).lower()
    if outcome in BLOCKING_OUTCOMES:
        return "block"
    if outcome in REVIEW_OUTCOMES:
        return "review"
    if outcome == "pass":
        return "pass"
    return default


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _source_label(source: str | None, index: int) -> str:
    return as_text(source) or f"input:{index}"


def _pointer(source: str, key: str) -> str:
    return f"{source}#/{key}"


def _row(
    *,
    source: str,
    tool: str,
    check_id: str,
    title: str,
    outcome: str,
    summary: str,
    evidence_key: str,
    facts: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "tool": tool,
        "check_id": check_id,
        "title": title,
        "outcome": outcome,
        "summary": summary,
        "evidence_pointer": _pointer(source, evidence_key),
        "facts": facts or {},
    }


def _path_count_summary(label: str, paths: list[Any]) -> str:
    count = len(paths)
    return f"{count} {label}" if count != 1 else f"1 {label[:-1]}"


def _guard_rows(payload: dict[str, Any], source: str) -> list[dict[str, object]]:
    staged_paths = _as_list(payload.get("staged_paths"))
    blocking_paths = _as_list(payload.get("blocking_paths"))
    violations = [_as_dict(item) for item in _as_list(payload.get("violations"))]
    raw_violations = [item for item in violations if as_text(item.get("reason")).startswith("raw_")]
    log_violations = [item for item in violations if as_text(item.get("reason")) == "log_not_append_only"]
    scope_violations = [item for item in violations if as_text(item.get("reason")) == "outside_mode_scope"]
    outcome = _normalized_outcome(payload.get("outcome"))
    return [
        _row(
            source=source,
            tool="guard-staged",
            check_id="guard.target_project",
            title="target project and mode",
            outcome=outcome,
            summary=(
                f"target_project={as_text(payload.get('target_project')) or 'unknown'} "
                f"mode={as_text(payload.get('mode')) or 'unknown'}"
            ),
            evidence_key="target_project",
            facts={
                "target_project": payload.get("target_project"),
                "mode": payload.get("mode"),
                "allowed_prefix": payload.get("allowed_prefix"),
            },
        ),
        _row(
            source=source,
            tool="guard-staged",
            check_id="guard.scope",
            title="staged path scope",
            outcome=outcome,
            summary=(
                f"{_path_count_summary('staged paths', staged_paths)} checked for "
                f"{as_text(payload.get('allowed_prefix')) or as_text(payload.get('target_project'))}"
            ),
            evidence_key="staged_paths",
            facts={
                "target_project": payload.get("target_project"),
                "mode": payload.get("mode"),
                "blocking_paths": blocking_paths,
            },
        ),
        _row(
            source=source,
            tool="guard-staged",
            check_id="guard.raw",
            title="raw immutability guard",
            outcome="block" if raw_violations else "pass",
            summary="raw path modification blocked" if raw_violations else "no forbidden raw path change",
            evidence_key="violations",
            facts={"violations": raw_violations},
        ),
        _row(
            source=source,
            tool="guard-staged",
            check_id="guard.log",
            title="append-only log guard",
            outcome="block" if log_violations else "pass",
            summary="wiki log edit is not append-only" if log_violations else "wiki log append-only check passed or not applicable",
            evidence_key="violations",
            facts={"violations": log_violations},
        ),
        _row(
            source=source,
            tool="guard-staged",
            check_id="guard.mode",
            title="operation mode guard",
            outcome="block" if scope_violations else "pass",
            summary="paths outside operation mode scope" if scope_violations else "paths fit operation mode scope",
            evidence_key="violations",
            facts={"violations": scope_violations},
        ),
    ]


def _publish_rows(payload: dict[str, Any], source: str) -> list[dict[str, object]]:
    changed_paths = _as_list(payload.get("changed_paths"))
    blocking_paths = _as_list(payload.get("blocking_paths"))
    checked_paths = _as_list(payload.get("checked_paths"))
    actions = _as_list(payload.get("actions"))
    public_exclusions = _as_list(payload.get("public_snapshot_exclusions"))
    outcome = _normalized_outcome(payload.get("outcome"))
    reason = as_text(payload.get("reason"))
    base_is_ancestor = payload.get("base_is_ancestor")
    secret_outcome = "block" if blocking_paths and checked_paths else "pass"
    if reason and "secret" in reason:
        secret_outcome = "block"
    return [
        _row(
            source=source,
            tool="publish-task",
            check_id="publish.diff",
            title="changed path classification",
            outcome=outcome,
            summary=f"diff_class={as_text(payload.get('diff_class')) or 'unknown'} over {_path_count_summary('changed paths', changed_paths)}",
            evidence_key="changed_paths",
            facts={
                "diff_class": payload.get("diff_class"),
                "changed_paths": changed_paths,
                "reason": payload.get("reason"),
            },
        ),
        _row(
            source=source,
            tool="publish-task",
            check_id="publish.public_snapshot",
            title="public snapshot intent",
            outcome="pass" if outcome != "block" else "block",
            summary=f"intent={as_text(payload.get('public_snapshot_intent')) or 'none'} actions={', '.join(map(str, actions)) or 'none'}",
            evidence_key="public_snapshot_intent",
            facts={
                "actions": actions,
                "public_snapshot_requested": payload.get("public_snapshot_requested"),
                "snapshot_origin": payload.get("snapshot_origin"),
            },
        ),
        _row(
            source=source,
            tool="publish-task",
            check_id="publish.private_exclusions",
            title="private project exclusions",
            outcome="pass" if outcome != "block" else "block",
            summary=f"{_path_count_summary('private exclusions', public_exclusions)} applied to public snapshot",
            evidence_key="public_snapshot_exclusions",
            facts={
                "private_projects": _as_list(payload.get("private_projects")),
                "public_snapshot_exclusions": public_exclusions,
            },
        ),
        _row(
            source=source,
            tool="publish-task",
            check_id="publish.secret_scan",
            title="secret scan evidence",
            outcome=secret_outcome,
            summary=(
                f"{_path_count_summary('checked paths', checked_paths)} checked; "
                f"{_path_count_summary('blocking paths', blocking_paths)} blocked"
            ),
            evidence_key="blocking_paths" if blocking_paths else "checked_paths",
            facts={
                "checked_paths": checked_paths,
                "blocking_paths": blocking_paths,
                "reason": payload.get("reason") if secret_outcome == "block" else None,
            },
        ),
        _row(
            source=source,
            tool="publish-task",
            check_id="publish.base_reachability",
            title="base reachability",
            outcome="pass" if base_is_ancestor is True else "block" if base_is_ancestor is False else "review",
            summary=f"base={as_text(payload.get('base')) or 'unknown'} base_is_ancestor={base_is_ancestor}",
            evidence_key="base_is_ancestor",
            facts={"base": payload.get("base"), "head": payload.get("head")},
        ),
    ]


def _cleanup_rows(payload: dict[str, Any], source: str) -> list[dict[str, object]]:
    dirty_paths = _as_list(payload.get("dirty_paths"))
    actions = _as_list(payload.get("actions"))
    outcome = _normalized_outcome(payload.get("outcome"))
    reachable = payload.get("head_reachable_from_base")
    branch_delete_allowed = payload.get("branch_delete_allowed")
    return [
        _row(
            source=source,
            tool="cleanup-worktree",
            check_id="cleanup.worktree",
            title="cleanup target state",
            outcome=outcome,
            summary=f"worktree={as_text(payload.get('worktree')) or 'unknown'} branch={as_text(payload.get('branch')) or 'unknown'}",
            evidence_key="worktree",
            facts={"reason": payload.get("reason"), "dirty_paths": dirty_paths},
        ),
        _row(
            source=source,
            tool="cleanup-worktree",
            check_id="cleanup.reachability",
            title="cleanup reachability",
            outcome="pass" if reachable is True else "block" if reachable is False else "review",
            summary=f"head_reachable_from_base={reachable}",
            evidence_key="head_reachable_from_base",
            facts={"base": payload.get("base"), "head": payload.get("head")},
        ),
        _row(
            source=source,
            tool="cleanup-worktree",
            check_id="cleanup.dirty",
            title="cleanup dirty paths",
            outcome="block" if dirty_paths else "pass",
            summary=f"{_path_count_summary('dirty paths', dirty_paths)} in cleanup target",
            evidence_key="dirty_paths",
            facts={"dirty_paths": dirty_paths},
        ),
        _row(
            source=source,
            tool="cleanup-worktree",
            check_id="cleanup.branch_delete",
            title="task branch cleanup",
            outcome="pass" if branch_delete_allowed or outcome == "pass" else outcome,
            summary=f"branch_delete_allowed={branch_delete_allowed} actions={', '.join(map(str, actions)) or 'none'}",
            evidence_key="branch_delete_allowed",
            facts={"actions": actions, "semantic_superseded": payload.get("semantic_superseded")},
        ),
    ]


def _secret_scan_rows(payload: dict[str, Any], source: str) -> list[dict[str, object]]:
    checked_paths = _as_list(payload.get("checked_paths"))
    blocking_paths = _as_list(payload.get("blocking_paths"))
    outcome = _normalized_outcome(payload.get("outcome"))
    return [
        _row(
            source=source,
            tool="secret-scan",
            check_id="secret.scan",
            title="secret scan",
            outcome=outcome,
            summary=(
                f"{_path_count_summary('checked paths', checked_paths)} checked; "
                f"{_path_count_summary('blocking paths', blocking_paths)} blocked"
            ),
            evidence_key="blocking_paths" if blocking_paths else "checked_paths",
            facts={
                "operation": payload.get("operation"),
                "reason": payload.get("reason"),
                "checked_paths": checked_paths,
                "blocking_paths": blocking_paths,
            },
        )
    ]


def _worktree_status_rows(payload: dict[str, Any], source: str) -> list[dict[str, object]]:
    scope_conflicts = _as_list(payload.get("scope_conflicts"))
    excluded_dirty_paths = _as_list(payload.get("excluded_dirty_paths"))
    recommendation = as_text(payload.get("recommendation"))
    outcome = "block" if recommendation.startswith("blocked") or scope_conflicts else "review" if recommendation not in {"keep", "delete"} else "pass"
    return [
        _row(
            source=source,
            tool="worktree-status",
            check_id="worktree.scope",
            title="worktree scope status",
            outcome=outcome,
            summary=f"recommendation={recommendation or 'unknown'} scope_conflicts={len(scope_conflicts)} excluded_dirty={len(excluded_dirty_paths)}",
            evidence_key="recommendation",
            facts={
                "scope_conflicts": scope_conflicts,
                "excluded_dirty_paths": excluded_dirty_paths,
                "shared_checkout_dirty": payload.get("shared_checkout_dirty"),
                "shared_checkout_behind": payload.get("shared_checkout_behind"),
            },
        )
    ]


def _infer_tool(payload: dict[str, Any]) -> str:
    if "target_project" in payload and "staged_paths" in payload:
        return "guard-staged"
    if "diff_class" in payload or "public_snapshot_intent" in payload:
        return "publish-task"
    if "worktree" in payload and ("head_reachable_from_base" in payload or "branch_delete_allowed" in payload):
        return "cleanup-worktree"
    if payload.get("operation") == "secret-scan":
        return "secret-scan"
    if "worktrees" in payload and "shared_checkout" in payload:
        return "worktree-status"
    return "unknown"


def _rows_for_payload(payload: dict[str, Any], source: str) -> list[dict[str, object]]:
    tool = _infer_tool(payload)
    if tool == "guard-staged":
        return _guard_rows(payload, source)
    if tool == "publish-task":
        return _publish_rows(payload, source)
    if tool == "cleanup-worktree":
        return _cleanup_rows(payload, source)
    if tool == "secret-scan":
        return _secret_scan_rows(payload, source)
    if tool == "worktree-status":
        return _worktree_status_rows(payload, source)
    return [
        _row(
            source=source,
            tool="unknown",
            check_id="unknown.payload",
            title="unknown payload",
            outcome="review",
            summary="input payload shape is not recognized",
            evidence_key="",
        )
    ]


def policy_evidence_matrix(inputs: list[tuple[dict[str, Any], str | None]]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for index, (payload, source_name) in enumerate(inputs, start=1):
        source = _source_label(source_name, index)
        tool = _infer_tool(payload)
        sources.append(
            {
                "source": source,
                "tool": tool,
                "outcome": _normalized_outcome(payload.get("outcome")),
                "reason": payload.get("reason"),
            }
        )
        rows.extend(_rows_for_payload(payload, source))

    row_outcomes = [as_text(row.get("outcome")) for row in rows]
    outcome = "block" if "block" in row_outcomes else "review" if "review" in row_outcomes else "pass"
    return {
        "schema_version": 1,
        "outcome": outcome,
        "explanatory_only": True,
        "decision_authority": "source gates only; this matrix cannot approve, bypass or override a guard",
        "sources": sources,
        "rows": rows,
    }


def load_policy_evidence_inputs(paths: list[str]) -> list[tuple[dict[str, Any], str]]:
    inputs: list[tuple[dict[str, Any], str]] = []
    for path_text in paths:
        path = Path(path_text)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"policy-evidence input must be a JSON object: {path}")
        inputs.append((payload, path.as_posix()))
    return inputs


def print_policy_evidence(paths: list[str], fmt: str) -> int:
    if not paths:
        raise SystemExit("policy-evidence requires at least one --input JSON file.")
    payload = policy_evidence_matrix(load_policy_evidence_inputs(paths))
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"outcome: {payload['outcome']}")
        print("decision_authority: source gates only; explanatory matrix cannot bypass guards")
        for row in payload["rows"]:
            print(f"- {row['outcome']} {row['tool']}:{row['check_id']} {row['summary']} ({row['evidence_pointer']})")
    return 0 if payload["outcome"] != "block" else 1
