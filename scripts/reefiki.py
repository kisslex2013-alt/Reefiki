#!/usr/bin/env python3
"""
Small local tools for REEFIKI projects.

Markdown stays the source of truth. The SQLite database under .reefiki/ is a
rebuildable search/cache layer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit(
        "REEFIKI requires Python 3.11 or newer. "
        f"Running: {sys.version.split()[0]}"
    )

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from reefiki_agent_readiness import print_agent_readiness
from reefiki_core.adapters import ADAPTER_TOOLS, print_adapter_call
from reefiki_core.adapter_smoke import print_adapter_smoke
from reefiki_core.code_context import graphify_report_path, project_code_path
from reefiki_core.cleanup_worktree import cleanup_worktree_payload, print_cleanup_worktree
from reefiki_core.connect_check import print_connect_check
from reefiki_core.confidence_pass import print_confidence_pass
from reefiki_core.cross_project import print_cross_project_query
from reefiki_core.duplicates import _normalize_text
from reefiki_core.file_utils import (
    numbered_path,
    slugify,
    write_new_bytes,
    write_new_text,
    write_unique_text,
)
from reefiki_core.git_utils import require_git_success, run_git
from reefiki_core.guard_staged import guard_staged_payload, print_guard_staged
from reefiki_core.guided_tour import print_guided_tour
from reefiki_core.harvest_commit import harvest_commit_payload, print_harvest_commit
from reefiki_core.health import (
    dashboard_next_action,
    dashboard_payload,
    knowledge_health_payload,
    print_dashboard,
    print_health,
)
from reefiki_core.doctor import doctor_payload, print_doctor
from reefiki_core.index_search import (
    build_index,
    escape_fts,
    print_search,
    project_local_lookup,
    search,
)
from reefiki_core.init_workspace import PROJECT_PROFILES, print_init_workspace
from reefiki_core.link_confidence import print_link_confidence
from reefiki_core.markdown_import import IMPORT_SOURCE_KINDS, print_markdown_import
from reefiki_core.markdown import (
    as_text,
    parse_frontmatter,
)
from reefiki_core.capture_evidence import print_capture_evidence
from reefiki_core.notify import print_notify
from reefiki_core.policy_evidence import print_policy_evidence
from reefiki_core.memory_golden import (
    load_golden_queries,
    print_memory_golden_result,
    run_golden_queries as run_golden_queries_payload,
)
from reefiki_core.memory_cli import (
    print_memory_golden as print_memory_golden_core,
    print_memory_pack as print_memory_pack_core,
    print_memory_reflect as print_memory_reflect_core,
    read_only_pack_quality as read_only_pack_quality_core,
)
from reefiki_core.memory_diff import memory_diff, print_memory_diff, resolve_since_date_ref
from reefiki_core.memory_explain import memory_explain, print_memory_explain
from reefiki_core.memory_lookup import global_lookup, print_global_lookup, run_memoir
from reefiki_core.memory_pack import (
    memory_pack as memory_pack_payload,
    memory_pack_strict_result,
    print_memory_pack_result,
)
from reefiki_core.memory_route import memory_route, print_memory_route
from reefiki_core.memory_reflect import (
    memory_reflect as memory_reflect_payload,
    print_memory_reflect_result,
    read_only_pack_quality as memory_reflect_read_only_pack_quality,
    reflection_candidate_actions,
    reflection_report_markdown,
    write_memory_reflection_report,
)
from reefiki_core.memory_preflight import memory_preflight, print_memory_preflight
from reefiki_core.memory_status import (
    compact_status_result,
    memory_status,
    memory_status_all_projects,
    memory_status_has_open,
    memory_status_next_action,
    print_memory_status,
)
from reefiki_core.memoir_io import (
    _memoir_base_command,
    _parse_memoir_json_output,
    memoir_store_path,
    run_memoir as run_memoir_with_timeout,
)
from reefiki_core.plans import plan_check, plan_create, timeline
from reefiki_core.ops_dashboard import (
    DEFAULT_WORKSPACE_ROOT,
    print_ops_dashboard,
    print_ops_dashboard_demo,
    serve_ops_dashboard,
)
from reefiki_core.orchestration_check import print_orchestration_check
from reefiki_core.onboarding import (
    DEFAULT_ONBOARDING_PROJECT,
    DEFAULT_ONBOARDING_QUESTION,
    DEFAULT_ONBOARDING_SESSION_NOTE,
    DEFAULT_ONBOARDING_SOURCE,
    SUPPORTED_ONBOARDING_LANGUAGES,
    print_onboarding_wizard,
)
from reefiki_core.project_paths import (
    db_path,
    find_project,
    iter_pages,
    list_projects,
    project_root,
    relative,
    repo_root,
)
from reefiki_core.process_utils import SUBPROCESS_TIMEOUT_SECONDS, git_repo_root
from reefiki_core.project_commands import (
    ProjectCommandDeps,
    dispatch_project_command as dispatch_project_command_core,
)
from reefiki_core.privacy import (
    canonical_url,
    classify_path,
    dedup_check,
    privacy_scan,
)
from reefiki_core.promotion import (
    apply_promotion_draft,
    apply_promotion_inbox_draft,
    print_global_promote,
    parse_promotion_draft,
    print_memory_promotion_inbox,
    print_promotion_dry_run,
    promotion_dry_run,
    promotion_inbox,
    promotion_inbox_summary,
    prune_closed_promotion_drafts,
    reject_promotion_inbox_draft,
    update_promotion_draft_review_state,
    write_promotion_draft,
)
from reefiki_core.publish_task import publish_task_payload, print_publish_task
from reefiki_core.repo_paths import (
    repo_path_in_scope,
    resolve_contained_path,
)
from reefiki_core.retrieval_benchmark import print_retrieval_benchmark
from reefiki_core.retrieval_preflight import print_retrieval_preflight
from reefiki_core.review_queues import (
    build_backlink_index,
    print_backlink_index,
    print_review_queues,
    review_queue_scan,
    review_queue_summary,
    write_review_queue_report,
)
from reefiki_core.save import append_save_log, save_source
from reefiki_core.secret_scan import print_secret_scan
from reefiki_core.storage import (
    SQLITE_BUSY_TIMEOUT_MS,
    index_lock,
    sqlite_connection,
)
from reefiki_core.obligations_extract import print_obligations_extract
from reefiki_core.status import status
from reefiki_core.test_observability import print_test_observability
from reefiki_core.tool_trigger import print_tool_trigger, tool_trigger_payload
from reefiki_core.verify_intent import print_verify_intent
from reefiki_core.visibility_audit import print_visibility_audit
from reefiki_core.wiki_rows import _wiki_rows
from reefiki_core.wiki_write import print_wiki_write
from reefiki_core.worktree_status import (
    git_ahead_behind,
    parse_git_worktree_porcelain,
    print_worktree_status,
    worktree_status_payload,
    worktree_status_recommendation,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


CONCEPT_TYPES = {"concept", "decision", "skill", "synthesis", "source_note"}


def run_golden_queries(root: Path, project_name: str, path: Path | None = None) -> dict[str, object]:
    return run_golden_queries_payload(
        root,
        project_name,
        project_local_lookup_fn=project_local_lookup,
        global_lookup_fn=global_lookup,
        promotion_dry_run_fn=promotion_dry_run,
        memory_pack_fn=memory_pack,
        path=path,
    )


def memory_pack(
    root: Path,
    project_name: str,
    task: str,
    limit: int = 8,
    include_golden: bool = True,
) -> dict[str, object]:
    return memory_pack_payload(
        root,
        project_name,
        task,
        global_lookup_fn=global_lookup,
        run_golden_queries_fn=run_golden_queries,
        limit=limit,
        include_golden=include_golden,
    )


def print_memory_golden(root: Path, project_name: str, path: str | None, fmt: str) -> int:
    return print_memory_golden_core(
        root,
        project_name,
        path,
        fmt,
        run_golden_queries_fn=run_golden_queries,
    )


def print_memory_pack(root: Path, project_name: str, task: str, limit: int, strict: bool, fmt: str) -> int:
    return print_memory_pack_core(
        root,
        project_name,
        task,
        limit,
        strict,
        fmt,
        memory_pack_fn=memory_pack,
    )


def read_only_pack_quality(root: Path, project: Path, task: str, limit: int) -> dict[str, object]:
    return read_only_pack_quality_core(root, project, task, limit, memory_pack_fn=memory_pack)


def memory_reflect(
    root: Path,
    project_name: str,
    since: str,
    task: str,
    limit: int = 5,
) -> dict[str, object]:
    return memory_reflect_payload(root, project_name, since=since, task=task, limit=limit, pack_fn=memory_pack)


def print_memory_reflect(
    root: Path,
    project_name: str,
    since: str,
    task: str,
    limit: int,
    write_report: bool,
    fmt: str,
) -> int:
    return print_memory_reflect_core(
        root,
        project_name,
        since,
        task,
        limit,
        write_report,
        fmt,
        memory_reflect_fn=memory_reflect,
    )


PROJECT_COMMANDS = {
    "index",
    "search",
    "privacy",
    "dedup",
    "save",
    "status",
    "doctor",
    "health",
    "dashboard",
    "plan",
    "timeline",
    "review-queues",
    "backlinks",
    "promote-dry-run",
}


def dispatch_project_command(args: argparse.Namespace, project: Path) -> int:
    return dispatch_project_command_core(
        args,
        project,
        ProjectCommandDeps(
            build_index=build_index,
            relative=relative,
            db_path=db_path,
            print_search=print_search,
            privacy_scan=privacy_scan,
            dedup_check=dedup_check,
            save_source=save_source,
            status=status,
            print_doctor=print_doctor,
            print_health=print_health,
            print_dashboard=print_dashboard,
            plan_create=plan_create,
            plan_check=plan_check,
            timeline=timeline,
            write_review_queue_report=write_review_queue_report,
            print_review_queues=print_review_queues,
            print_backlink_index=print_backlink_index,
            apply_promotion_draft=apply_promotion_draft,
            write_promotion_draft=write_promotion_draft,
            print_promotion_dry_run=print_promotion_dry_run,
        ),
    )


def resolve_repo_relative_optional_path(repo: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else repo / path


def repo_root_or_resolved_path(path: Path) -> Path:
    try:
        return repo_root(path)
    except SystemExit:
        return path.resolve()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description="REEFIKI local tools")
    parser.add_argument("--project", dest="root_path", default=".", help="project root with wiki/")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("index")
    search_parser = sub.add_parser("search")
    search_parser.add_argument("query", nargs="?", default="")
    search_parser.add_argument("--limit", type=int, default=7)
    search_parser.add_argument("--format", choices=["text", "json"], default="text")
    search_parser.add_argument("--output", choices=["full", "compact", "files"], default="full")
    search_parser.add_argument("--type", dest="page_type")
    search_parser.add_argument("--tag")
    search_parser.add_argument("--link-to")
    search_parser.add_argument("--linked-by")
    search_parser.add_argument("--orphan", action="store_true")
    search_parser.add_argument("--chunks", action="store_true")
    sub.add_parser("privacy")
    dedup_parser = sub.add_parser("dedup")
    dedup_parser.add_argument("source")
    save_parser = sub.add_parser("save")
    save_parser.add_argument("source")
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--format", choices=["text", "json"], default="text")
    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--format", choices=["text", "json"], default="text")
    health_parser = sub.add_parser("health")
    health_parser.add_argument("--format", choices=["text", "json"], default="text")
    dashboard_parser = sub.add_parser("dashboard")
    dashboard_parser.add_argument("--stale-days", type=int, default=90)
    dashboard_parser.add_argument("--limit", type=int, default=5)
    dashboard_parser.add_argument("--format", choices=["text", "json"], default="text")
    agent_readiness_parser = sub.add_parser("agent-readiness")
    agent_readiness_parser.add_argument("--repo", required=True)
    agent_readiness_parser.add_argument("--format", choices=["text", "json"], default="text")
    agent_readiness_parser.add_argument("--write-report", action="store_true")
    ops_dashboard_parser = sub.add_parser(
        "ops-dashboard",
        description="Read-only workspace snapshot, synthetic demo fixture, or localhost board.",
    )
    ops_dashboard_parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT))
    ops_dashboard_parser.add_argument("--format", choices=["text", "json"], default="text")
    ops_dashboard_sub = ops_dashboard_parser.add_subparsers(dest="ops_dashboard_cmd")
    ops_dashboard_demo_parser = ops_dashboard_sub.add_parser("demo")
    ops_dashboard_demo_parser.add_argument("--fixture-root", required=True)
    ops_dashboard_demo_parser.add_argument("--format", choices=["text", "json"], default="text")
    ops_dashboard_serve_parser = ops_dashboard_sub.add_parser("serve")
    ops_dashboard_serve_parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT))
    ops_dashboard_serve_parser.add_argument("--port", type=int, default=7310)
    ops_dashboard_serve_parser.add_argument(
        "--ui",
        choices=["current", "next"],
        default="current",
        help="Static dashboard bundle to serve. Default keeps the existing UI.",
    )
    ops_dashboard_serve_parser.add_argument(
        "--allow-log-path",
        action="append",
        default=[],
        help="Explicit extra live-log allowlist entry. Format: [name=]path",
    )
    onboarding_parser = sub.add_parser("onboarding")
    onboarding_parser.add_argument("--project-name", default=DEFAULT_ONBOARDING_PROJECT)
    onboarding_parser.add_argument("--source", default=DEFAULT_ONBOARDING_SOURCE)
    onboarding_parser.add_argument("--question", default=DEFAULT_ONBOARDING_QUESTION)
    onboarding_parser.add_argument("--session-note", default=DEFAULT_ONBOARDING_SESSION_NOTE)
    onboarding_parser.add_argument("--fixture-root")
    onboarding_parser.add_argument("--lang", choices=SUPPORTED_ONBOARDING_LANGUAGES)
    onboarding_interactive = onboarding_parser.add_mutually_exclusive_group()
    onboarding_interactive.add_argument("--interactive", action="store_true")
    onboarding_interactive.add_argument("--no-interactive", action="store_true")
    onboarding_parser.add_argument("--show-commands", action="store_true")
    onboarding_parser.add_argument("--plain", action="store_true")
    onboarding_parser.add_argument("--yes", action="store_true")
    onboarding_parser.add_argument("--format", choices=["text", "json"], default="text")
    init_parser = sub.add_parser("init")
    init_parser.add_argument("--workspace", required=True)
    init_parser.add_argument("--project-name", required=True)
    init_parser.add_argument("--title")
    init_parser.add_argument("--profile", choices=PROJECT_PROFILES, default="product")
    init_parser.add_argument("--code-project")
    init_parser.add_argument("--apply-bridge", action="store_true")
    init_parser.add_argument("--format", choices=["text", "json"], default="text")
    import_parser = sub.add_parser("import")
    import_parser.add_argument("source")
    import_parser.add_argument("--from", dest="source_kind", choices=IMPORT_SOURCE_KINDS, default="markdown")
    import_parser.add_argument("--dry-run", action="store_true")
    import_parser.add_argument("--max-files", type=int, default=100)
    import_parser.add_argument("--format", choices=["text", "json"], default="text")
    tour_parser = sub.add_parser("tour")
    tour_parser.add_argument("--fixture-root")
    tour_parser.add_argument("--workspace-root")
    tour_parser.add_argument("--connect-path")
    tour_parser.add_argument("--format", choices=["text", "json"], default="text")
    adapter_parser = sub.add_parser("adapter-call")
    adapter_parser.add_argument("tool", choices=sorted(ADAPTER_TOOLS))
    adapter_parser.add_argument("--project", dest="adapter_project", default="reefiki")
    adapter_parser.add_argument("--payload", default="{}")
    adapter_parser.add_argument("--allow-write", action="store_true")
    adapter_smoke_parser = sub.add_parser("adapter-smoke")
    adapter_smoke_parser.add_argument("--project-name", default="reefiki")
    adapter_smoke_parser.add_argument("--query", default="memory control plane")
    adapter_smoke_parser.add_argument("--limit", type=int, default=5)
    adapter_smoke_parser.add_argument("--format", choices=["text", "json"], default="text")
    cross_query_parser = sub.add_parser("cross-query")
    cross_query_parser.add_argument("query", nargs="?", default="")
    cross_query_parser.add_argument("--limit", type=int, default=7)
    cross_query_parser.add_argument("--project-name", action="append", default=[])
    cross_query_parser.add_argument("--format", choices=["text", "json"], default="text")
    connect_check_parser = sub.add_parser("connect-check")
    connect_check_parser.add_argument("path")
    connect_check_parser.add_argument("--format", choices=["text", "json"], default="text")
    skills_parser = sub.add_parser("skills")
    skills_sub = skills_parser.add_subparsers(dest="skills_cmd", required=True)
    skills_recommend_parser = skills_sub.add_parser("recommend")
    skills_recommend_parser.add_argument("--repo", required=True)
    skills_recommend_parser.add_argument("--format", choices=["text", "json"], default="text")
    skills_recommend_parser.add_argument("--write-report", action="store_true")
    plan_parser = sub.add_parser("plan")
    plan_sub = plan_parser.add_subparsers(dest="plan_cmd", required=True)
    plan_create_parser = plan_sub.add_parser("create")
    plan_create_parser.add_argument("title")
    plan_check_parser = plan_sub.add_parser("check")
    plan_check_parser.add_argument("path")
    timeline_parser = sub.add_parser("timeline")
    timeline_parser.add_argument("--limit", type=int, default=10)
    timeline_parser.add_argument("--format", choices=["text", "json"], default="text")
    secret_scan_parser = sub.add_parser("secret-scan")
    secret_scan_parser.add_argument("paths", nargs="*")
    secret_scan_parser.add_argument("--all", action="store_true", dest="scan_all")
    secret_scan_parser.add_argument("--format", choices=["text", "json"], default="text")
    guard_parser = sub.add_parser("guard-staged")
    guard_parser.add_argument("--target-project", required=True)
    guard_parser.add_argument("--mode", choices=["harvest", "process", "docs", "code", "code/docs"], default="harvest")
    guard_parser.add_argument("--format", choices=["text", "json"], default="text")
    harvest_commit_parser = sub.add_parser("harvest-commit")
    harvest_commit_parser.add_argument("--target-project", required=True)
    harvest_commit_parser.add_argument("--path", action="append", default=[])
    harvest_commit_parser.add_argument("--message", required=True)
    harvest_commit_parser.add_argument("--no-validate", action="store_true")
    harvest_commit_parser.add_argument("--lock-timeout", type=float, default=30.0)
    harvest_commit_parser.add_argument("--format", choices=["text", "json"], default="text")
    wiki_write_parser = sub.add_parser("wiki-write")
    wiki_write_parser.add_argument("--code-project", default=".")
    wiki_write_parser.add_argument("--target-project")
    wiki_write_parser.add_argument("--path", required=True)
    wiki_write_parser.add_argument("--content-file", required=True)
    wiki_write_parser.add_argument("--message", required=True)
    wiki_write_parser.add_argument("--no-validate", action="store_true")
    wiki_write_parser.add_argument("--baseline-ref", default="HEAD")
    wiki_write_parser.add_argument("--stale-days", type=int, default=90)
    wiki_write_parser.add_argument("--lock-timeout", type=float, default=30.0)
    wiki_write_parser.add_argument("--direct-repo", action="store_true")
    wiki_write_parser.add_argument("--format", choices=["text", "json"], default="text")
    publish_task_parser = sub.add_parser("publish-task")
    publish_task_parser.add_argument("--base", default="origin/main")
    publish_task_parser.add_argument("--private-remote", default="origin")
    publish_task_parser.add_argument("--public-remote", default="public")
    publish_task_parser.add_argument("--dry-run", action="store_true")
    publish_task_parser.add_argument("--apply", action="store_true")
    publish_task_parser.add_argument("--cleanup", action="store_true")
    publish_task_parser.add_argument("--public-snapshot", action="store_true")
    publish_task_parser.add_argument("--format", choices=["text", "json"], default="text")
    cleanup_worktree_parser = sub.add_parser("cleanup-worktree")
    cleanup_worktree_parser.add_argument("--worktree", required=True)
    cleanup_worktree_parser.add_argument("--base", default="origin/main")
    cleanup_worktree_parser.add_argument("--dry-run", action="store_true")
    cleanup_worktree_parser.add_argument("--apply", action="store_true")
    cleanup_worktree_parser.add_argument("--semantic-superseded")
    cleanup_worktree_parser.add_argument("--format", choices=["text", "json"], default="text")
    worktree_status_parser = sub.add_parser("worktree-status")
    worktree_status_parser.add_argument("--base", default="origin/main")
    worktree_status_parser.add_argument("--scope", action="append", default=[])
    worktree_status_parser.add_argument("--ledger")
    worktree_status_parser.add_argument("--max-lease-days", type=int, default=14)
    worktree_status_parser.add_argument("--format", choices=["text", "json"], default="text")
    orchestration_check_parser = sub.add_parser("orchestration-check")
    orchestration_check_parser.add_argument("--base", default="origin/main")
    orchestration_check_parser.add_argument("--scope", action="append", default=[])
    orchestration_check_parser.add_argument("--ledger")
    orchestration_check_parser.add_argument("--max-lease-days", type=int, default=14)
    orchestration_check_parser.add_argument("--remote", default="origin")
    orchestration_check_parser.add_argument("--include-global-config", action="store_true")
    orchestration_check_parser.add_argument("--format", choices=["text", "json"], default="text")
    confidence_pass_parser = sub.add_parser("confidence-pass")
    confidence_pass_parser.add_argument("--project-name", default="reefiki")
    confidence_pass_parser.add_argument("--base", default="origin/main")
    confidence_pass_parser.add_argument("--include-pytest", action="store_true")
    confidence_pass_parser.add_argument("--pytest-arg", action="append", default=[])
    confidence_pass_parser.add_argument("--format", choices=["text", "json"], default="text")
    retrieval_preflight_parser = sub.add_parser("retrieval-preflight")
    retrieval_preflight_parser.add_argument("candidate", choices=["qmd"])
    retrieval_preflight_parser.add_argument("--project-name", default="reefiki")
    retrieval_preflight_parser.add_argument("--observed-misses", type=int, default=0)
    retrieval_preflight_parser.add_argument("--allow-runtime-eval", action="store_true")
    retrieval_preflight_parser.add_argument("--format", choices=["text", "json"], default="text")
    retrieval_benchmark_parser = sub.add_parser("retrieval-benchmark")
    retrieval_benchmark_parser.add_argument("candidate", choices=["qmd"])
    retrieval_benchmark_parser.add_argument("--project-name", default="reefiki")
    retrieval_benchmark_parser.add_argument("--limit", type=int, default=5)
    retrieval_benchmark_parser.add_argument("--qmd-results")
    retrieval_benchmark_parser.add_argument("--write-report", action="store_true")
    retrieval_benchmark_parser.add_argument("--cleanup-generated", action="store_true")
    retrieval_benchmark_parser.add_argument("--format", choices=["text", "json"], default="text")
    tool_trigger_parser = sub.add_parser("tool-trigger")
    tool_trigger_parser.add_argument("tool")
    tool_trigger_parser.add_argument("--signal", default="")
    tool_trigger_parser.add_argument("--format", choices=["text", "json"], default="text")
    test_observability_parser = sub.add_parser("test-observability")
    test_observability_parser.add_argument("--format", choices=["text", "json"], default="text")
    review_parser = sub.add_parser("review-queues")
    review_parser.add_argument("--stale-days", type=int, default=90)
    review_parser.add_argument("--format", choices=["text", "json"], default="text")
    review_parser.add_argument("--write-report", action="store_true")
    review_parser.add_argument("--type", dest="queue_type")
    review_parser.add_argument("--summary", action="store_true")
    review_parser.add_argument("--limit", type=int, default=5)
    review_parser.add_argument("--changed-path", action="append", default=[])
    review_parser.add_argument("--fail-on-changed-missing-backlink", action="store_true")
    review_parser.add_argument("--fail-on-new-missing-backlink", action="store_true")
    review_parser.add_argument("--baseline-ref", default="HEAD")
    backlink_parser = sub.add_parser("backlinks")
    backlink_parser.add_argument("--format", choices=["text", "json"], default="text")
    backlink_parser.add_argument("--write", action="store_true")
    link_confidence_parser = sub.add_parser("link-confidence")
    link_confidence_parser.add_argument("--project-name", default="reefiki")
    link_confidence_parser.add_argument("--stale-days", type=int, default=90)
    link_confidence_parser.add_argument("--limit", type=int, default=5)
    link_confidence_parser.add_argument("--ambiguity-threshold", type=int, default=3)
    link_confidence_parser.add_argument("--format", choices=["text", "json"], default="text")
    link_confidence_parser.add_argument("--write-report", action="store_true")
    visibility_audit_parser = sub.add_parser("visibility-audit")
    visibility_source = visibility_audit_parser.add_mutually_exclusive_group()
    visibility_source.add_argument("--from-golden", action="store_true")
    visibility_source.add_argument("--query")
    visibility_source.add_argument("--queries-file")
    visibility_audit_parser.add_argument("--project-name", default="reefiki")
    visibility_audit_parser.add_argument("--expect-id", action="append", default=[])
    visibility_audit_parser.add_argument("--limit", type=int, default=5)
    visibility_audit_parser.add_argument("--stale-days", type=int, default=90)
    visibility_audit_parser.add_argument("--rebuild-index", action="store_true")
    visibility_audit_parser.add_argument("--format", choices=["text", "json"], default="text")
    verify_intent_parser = sub.add_parser("verify-intent")
    verify_intent_brief = verify_intent_parser.add_mutually_exclusive_group(required=True)
    verify_intent_brief.add_argument("--brief")
    verify_intent_brief.add_argument("--brief-file")
    verify_intent_parser.add_argument("--report", default="")
    verify_intent_parser.add_argument("--report-file")
    verify_intent_parser.add_argument("--artifact", action="append", default=[])
    verify_intent_parser.add_argument("--changed-path", action="append", default=[])
    verify_intent_parser.add_argument("--expect-term", action="append", default=[])
    verify_intent_parser.add_argument("--expect-path", action="append", default=[])
    verify_intent_parser.add_argument("--allowed-path", action="append", default=[])
    verify_intent_parser.add_argument("--fail-on", choices=["block", "warn"], default="block")
    verify_intent_parser.add_argument("--format", choices=["text", "json"], default="text")
    obligations_parser = sub.add_parser("obligations-extract")
    obligations_parser.add_argument("--source", action="append", default=[])
    obligations_parser.add_argument("--text", default="")
    obligations_parser.add_argument("--owner-hint", default="")
    obligations_parser.add_argument("--source-hint", default="")
    obligations_parser.add_argument("--write-report", action="store_true")
    obligations_parser.add_argument("--report-path")
    obligations_parser.add_argument("--format", choices=["text", "json"], default="text")
    capture_evidence_parser = sub.add_parser("capture-evidence")
    capture_evidence_parser.add_argument("--kind", choices=["browser", "command", "diff", "manual"], required=True)
    capture_evidence_parser.add_argument("--claim", required=True)
    capture_evidence_parser.add_argument("--evidence", default="")
    capture_evidence_parser.add_argument("--task-id", default="")
    capture_evidence_parser.add_argument("--source-artifact", default="")
    capture_evidence_parser.add_argument("--url", default="")
    capture_evidence_parser.add_argument("--selector", default="")
    capture_evidence_parser.add_argument("--viewport", default="")
    capture_evidence_parser.add_argument("--screenshot-path", default="")
    capture_evidence_parser.add_argument("--command-summary", default="")
    capture_evidence_parser.add_argument("--diff-summary", default="")
    capture_evidence_parser.add_argument("--related-path", action="append", default=[])
    capture_evidence_parser.add_argument("--captured-at", default="")
    capture_evidence_parser.add_argument("--write-draft", action="store_true")
    capture_evidence_parser.add_argument("--draft-path")
    capture_evidence_parser.add_argument("--format", choices=["text", "json"], default="text")
    notify_parser = sub.add_parser("notify")
    notify_parser.add_argument("--event", choices=["review_ready", "review-ready", "blocked", "failed"], required=True)
    notify_parser.add_argument("--source-artifact", required=True)
    notify_parser.add_argument("--reason", required=True)
    notify_parser.add_argument("--next-action", required=True)
    notify_parser.add_argument("--evidence-pointer", required=True)
    notify_parser.add_argument("--task-id", default="")
    notify_parser.add_argument("--previous-fingerprint", action="append", default=[])
    notify_parser.add_argument("--adapter-config", default="")
    notify_parser.add_argument("--format", choices=["text", "json"], default="text")
    policy_evidence_parser = sub.add_parser("policy-evidence")
    policy_evidence_parser.add_argument("--input", action="append", required=True, default=[])
    policy_evidence_parser.add_argument("--format", choices=["text", "json"], default="text")
    promote_parser = sub.add_parser("promote-dry-run")
    promote_parser.add_argument("content")
    promote_parser.add_argument("--memory-id")
    promote_parser.add_argument("--confidence", type=float, default=0.6)
    promote_parser.add_argument("--format", choices=["text", "json"], default="text")
    promote_parser.add_argument("--write-draft", action="store_true")
    promote_parser.add_argument("--apply-draft")
    promote_parser.add_argument("--yes", action="store_true")
    memory_parser = sub.add_parser("memory")
    memory_sub = memory_parser.add_subparsers(dest="memory_cmd", required=True)
    memory_status_parser = memory_sub.add_parser("status")
    memory_status_parser.add_argument("--project", default="reefiki")
    memory_status_parser.add_argument("--all-projects", action="store_true")
    memory_status_parser.add_argument("--only-open", action="store_true")
    memory_status_parser.add_argument("--summary", action="store_true")
    memory_status_parser.add_argument("--fail-on-open", action="store_true")
    memory_status_parser.add_argument("--format", choices=["text", "json", "jsonl"], default="text")
    memory_preflight_parser = memory_sub.add_parser("preflight")
    memory_preflight_parser.add_argument("--project-name", default="reefiki")
    memory_preflight_parser.add_argument(
        "--visibility",
        choices=["private", "project", "public"],
        default="private",
    )
    memory_preflight_parser.add_argument("--operation", default="lookup")
    memory_preflight_parser.add_argument("--content", default="")
    memory_preflight_parser.add_argument("--path", action="append", default=[])
    memory_preflight_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_route_parser = memory_sub.add_parser("route")
    memory_route_parser.add_argument("content")
    memory_route_parser.add_argument("--project-hint")
    memory_route_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_explain_parser = memory_sub.add_parser("explain")
    memory_explain_parser.add_argument("query")
    memory_explain_parser.add_argument("--project", default="reefiki")
    memory_explain_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_lookup_parser = memory_sub.add_parser("lookup")
    memory_lookup_parser.add_argument("query")
    memory_lookup_parser.add_argument("--project")
    memory_lookup_parser.add_argument("--limit", type=int, default=5)
    memory_lookup_parser.add_argument(
        "--layer",
        choices=["all", "memoir", "reefiki", "graphify"],
        default="all",
    )
    memory_lookup_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_golden_parser = memory_sub.add_parser("golden")
    memory_golden_parser.add_argument("--project", dest="golden_project", default="reefiki")
    memory_golden_parser.add_argument("--path")
    memory_golden_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_diff_parser = memory_sub.add_parser("diff")
    memory_diff_parser.add_argument("--project", dest="diff_project", default="reefiki")
    memory_diff_source = memory_diff_parser.add_mutually_exclusive_group(required=True)
    memory_diff_source.add_argument("--from", dest="from_ref")
    memory_diff_source.add_argument("--since-date", dest="since_date")
    memory_diff_parser.add_argument("--to", dest="to_ref")
    memory_diff_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_pack_parser = memory_sub.add_parser("pack")
    memory_pack_parser.add_argument("task")
    memory_pack_parser.add_argument("--project", dest="pack_project", default="reefiki")
    memory_pack_parser.add_argument("--limit", type=int, default=8)
    memory_pack_parser.add_argument("--strict", action="store_true")
    memory_pack_parser.add_argument("--format", choices=["md", "json"], default="md")
    memory_reflect_parser = memory_sub.add_parser("reflect")
    memory_reflect_parser.add_argument("--project", dest="reflect_project", default="reefiki")
    memory_reflect_parser.add_argument("--since", required=True)
    memory_reflect_parser.add_argument("--task", default="memory reflection")
    memory_reflect_parser.add_argument("--limit", type=int, default=5)
    memory_reflect_parser.add_argument("--write-report", action="store_true")
    memory_reflect_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_promote_parser = memory_sub.add_parser("promote")
    memory_promote_parser.add_argument("content")
    memory_promote_parser.add_argument("--target-project", default="reefiki")
    memory_promote_parser.add_argument("--memory-id")
    memory_promote_parser.add_argument("--confidence", type=float, default=0.6)
    memory_promote_parser.add_argument("--write-draft", action="store_true")
    memory_promote_parser.add_argument("--format", choices=["text", "json"], default="text")
    memory_promotion_inbox_parser = memory_sub.add_parser("promotion-inbox")
    memory_promotion_inbox_parser.add_argument("--project", default="reefiki")
    memory_promotion_inbox_parser.add_argument("--show")
    inbox_action = memory_promotion_inbox_parser.add_mutually_exclusive_group()
    inbox_action.add_argument("--apply")
    inbox_action.add_argument("--reject")
    memory_promotion_inbox_parser.add_argument("--reason")
    memory_promotion_inbox_parser.add_argument("--yes", action="store_true")
    memory_promotion_inbox_parser.add_argument("--all", action="store_true")
    memory_promotion_inbox_parser.add_argument("--prune-closed", action="store_true")
    memory_promotion_inbox_parser.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args(argv)
    if args.cmd == "agent-readiness":
        report_root = repo_root(Path(args.root_path)) if args.write_report else None
        return print_agent_readiness(args.repo, args.format, args.write_report, report_root)
    if args.cmd == "skills" and args.skills_cmd == "recommend":
        report_root = repo_root(Path(args.root_path)) if args.write_report else None
        return print_agent_readiness(args.repo, args.format, args.write_report, report_root)
    if args.cmd == "ops-dashboard":
        workspace_root = Path(args.workspace_root)
        if args.ops_dashboard_cmd == "demo":
            return print_ops_dashboard_demo(args.fixture_root, args.format)
        root = repo_root_or_resolved_path(Path(args.root_path))
        if args.ops_dashboard_cmd == "serve":
            return serve_ops_dashboard(
                workspace_root,
                root,
                args.port,
                allow_log_paths=args.allow_log_path,
                ui=args.ui,
            )
        return print_ops_dashboard(workspace_root, root, args.format)
    if args.cmd == "onboarding":
        return print_onboarding_wizard(
            repo_root_or_resolved_path(Path(args.root_path)),
            args.project_name,
            args.source,
            args.question,
            args.session_note,
            args.fixture_root,
            args.format,
            args.lang,
            (
                True
                if args.interactive
                else False
                if args.no_interactive
                else None
            ),
            args.show_commands,
            args.plain,
            args.yes,
        )
    if args.cmd == "init":
        return print_init_workspace(
            args.workspace,
            args.project_name,
            args.title,
            args.profile,
            args.code_project,
            args.apply_bridge,
            args.format,
        )
    if args.cmd == "import":
        return print_markdown_import(
            project_root(Path(args.root_path)),
            args.source,
            args.source_kind,
            args.dry_run,
            args.max_files,
            args.format,
        )
    if args.cmd == "adapter-call":
        return print_adapter_call(
            repo_root(Path(args.root_path)),
            args.tool,
            args.adapter_project,
            args.payload,
            args.allow_write,
        )
    if args.cmd == "tour":
        return print_guided_tour(
            repo_root_or_resolved_path(Path(args.root_path)),
            args.format,
            fixture_root=args.fixture_root,
            workspace_root=args.workspace_root,
            connect_path=args.connect_path,
        )
    if args.cmd == "adapter-smoke":
        return print_adapter_smoke(
            repo_root(Path(args.root_path)),
            args.project_name,
            args.query,
            args.limit,
            args.format,
        )
    if args.cmd == "cross-query":
        return print_cross_project_query(
            repo_root(Path(args.root_path)),
            args.query,
            args.limit,
            args.project_name,
            args.format,
        )
    if args.cmd == "connect-check":
        return print_connect_check(args.path, args.format)
    if args.cmd == "worktree-status":
        repo = git_repo_root(Path(args.root_path))
        ledger_path = resolve_repo_relative_optional_path(repo, args.ledger)
        return print_worktree_status(
            repo,
            args.base,
            args.format,
            scopes=args.scope,
            ledger_path=ledger_path,
            max_lease_days=args.max_lease_days,
        )
    if args.cmd == "orchestration-check":
        repo = git_repo_root(Path(args.root_path))
        ledger_path = resolve_repo_relative_optional_path(repo, args.ledger)
        return print_orchestration_check(
            repo,
            args.base,
            ledger_path,
            args.scope,
            args.max_lease_days,
            args.remote,
            args.include_global_config,
            args.format,
        )
    if args.cmd == "confidence-pass":
        repo = git_repo_root(Path(args.root_path))
        return print_confidence_pass(
            repo,
            project_name=args.project_name,
            base=args.base,
            include_pytest=args.include_pytest,
            pytest_args=args.pytest_arg,
            fmt=args.format,
            memory_golden_fn=run_golden_queries,
        )
    if args.cmd == "retrieval-preflight":
        return print_retrieval_preflight(
            repo_root(Path(args.root_path)),
            args.project_name,
            args.candidate,
            args.observed_misses,
            args.allow_runtime_eval,
            args.format,
        )
    if args.cmd == "retrieval-benchmark":
        root = repo_root(Path(args.root_path))
        qmd_results_path = None
        if args.qmd_results:
            qmd_results_path, reason = resolve_contained_path(root, args.qmd_results)
            if qmd_results_path is None:
                raise SystemExit(f"Invalid qmd results path: {reason}")
        return print_retrieval_benchmark(
            root,
            args.project_name,
            args.candidate,
            args.limit,
            qmd_results_path,
            args.write_report,
            args.cleanup_generated,
            args.format,
        )
    if args.cmd == "link-confidence":
        return print_link_confidence(
            repo_root(Path(args.root_path)),
            args.project_name,
            args.stale_days,
            args.limit,
            args.ambiguity_threshold,
            args.format,
            args.write_report,
        )
    if args.cmd == "visibility-audit":
        return print_visibility_audit(
            repo_root(Path(args.root_path)),
            args.project_name,
            args.from_golden,
            args.query,
            args.queries_file,
            args.expect_id,
            args.limit,
            args.stale_days,
            args.rebuild_index,
            args.format,
        )
    if args.cmd == "verify-intent":
        return print_verify_intent(
            args.brief,
            args.brief_file,
            args.report,
            args.report_file,
            args.artifact,
            args.changed_path,
            args.expect_term,
            args.expect_path,
            args.allowed_path,
            args.fail_on,
            args.format,
        )
    if args.cmd == "obligations-extract":
        return print_obligations_extract(
            repo_root(Path(args.root_path)),
            args.source,
            args.text,
            args.owner_hint,
            args.source_hint,
            args.write_report,
            args.report_path,
            args.format,
        )
    if args.cmd == "capture-evidence":
        return print_capture_evidence(
            repo_root_or_resolved_path(Path(args.root_path)),
            args.kind,
            args.claim,
            args.evidence,
            args.task_id,
            args.source_artifact,
            args.url,
            args.selector,
            args.viewport,
            args.screenshot_path,
            args.command_summary,
            args.diff_summary,
            args.related_path,
            args.captured_at,
            args.write_draft,
            args.draft_path,
            args.format,
        )
    if args.cmd == "notify":
        return print_notify(
            args.event,
            args.source_artifact,
            args.reason,
            args.next_action,
            args.evidence_pointer,
            args.task_id,
            args.previous_fingerprint,
            args.adapter_config,
            args.format,
        )
    if args.cmd == "policy-evidence":
        return print_policy_evidence(args.input, args.format)
    if args.cmd == "test-observability":
        return print_test_observability(repo_root(Path(args.root_path)), args.format)

    if args.cmd in PROJECT_COMMANDS:
        return dispatch_project_command(args, project_root(Path(args.root_path)))

    repo = repo_root(Path(args.root_path))
    if args.cmd == "secret-scan":
        return print_secret_scan(repo, args.paths, args.format, scan_all=args.scan_all)
    if args.cmd == "guard-staged":
        return print_guard_staged(repo, args.target_project, args.format, args.mode)
    if args.cmd == "harvest-commit":
        return print_harvest_commit(
            repo,
            args.target_project,
            args.path,
            args.message,
            validate=not args.no_validate,
            fmt=args.format,
            lock_timeout_seconds=args.lock_timeout,
        )
    if args.cmd == "wiki-write":
        return print_wiki_write(
            repo_root_or_resolved_path(Path(args.root_path)),
            Path(args.code_project),
            args.target_project,
            args.path,
            args.content_file,
            args.message,
            validate=not args.no_validate,
            baseline_ref=args.baseline_ref,
            stale_days=args.stale_days,
            lock_timeout_seconds=args.lock_timeout,
            direct_repo=args.direct_repo,
            fmt=args.format,
        )
    if args.cmd == "publish-task":
        dry_run = args.dry_run or not args.apply
        return print_publish_task(
            repo,
            args.base,
            args.private_remote,
            args.public_remote,
            dry_run=dry_run,
            cleanup=args.cleanup,
            public_snapshot=args.public_snapshot,
            fmt=args.format,
        )
    if args.cmd == "cleanup-worktree":
        dry_run = args.dry_run or not args.apply
        return print_cleanup_worktree(
            repo,
            args.worktree,
            args.base,
            dry_run,
            args.format,
            args.semantic_superseded,
        )
    if args.cmd == "tool-trigger":
        return print_tool_trigger(args.tool, args.signal, args.format)
    if args.cmd == "memory":
        if args.memory_cmd == "status":
            return print_memory_status(
                repo,
                args.project,
                args.all_projects,
                args.only_open,
                args.summary,
                args.fail_on_open,
                args.format,
            )
        if args.memory_cmd == "preflight":
            return print_memory_preflight(
                project=args.project_name,
                visibility=args.visibility,
                operation=args.operation,
                content=args.content,
                paths=args.path,
                fmt=args.format,
            )
        if args.memory_cmd == "route":
            return print_memory_route(args.content, args.project_hint, args.format)
        if args.memory_cmd == "explain":
            return print_memory_explain(
                repo,
                query=args.query,
                project_name=args.project,
                fmt=args.format,
            )
        if args.memory_cmd == "lookup":
            layer = args.layer
            return print_global_lookup(
                repo,
                query=args.query,
                project=args.project,
                include_memoir=layer in {"all", "memoir"},
                include_reefiki=layer in {"all", "reefiki"},
                include_graph=layer in {"all", "graphify"},
                limit=args.limit,
                fmt=args.format,
            )
        if args.memory_cmd == "golden":
            return print_memory_golden(
                repo,
                project_name=args.golden_project,
                path=args.path,
                fmt=args.format,
            )
        if args.memory_cmd == "diff":
            return print_memory_diff(
                repo,
                project_name=args.diff_project,
                from_ref=args.from_ref or "HEAD",
                to_ref=args.to_ref,
                since_date=args.since_date,
                fmt=args.format,
            )
        if args.memory_cmd == "pack":
            return print_memory_pack(
                repo,
                project_name=args.pack_project,
                task=args.task,
                limit=args.limit,
                strict=args.strict,
                fmt=args.format,
            )
        if args.memory_cmd == "reflect":
            return print_memory_reflect(
                repo,
                project_name=args.reflect_project,
                since=args.since,
                task=args.task,
                limit=args.limit,
                write_report=args.write_report,
                fmt=args.format,
            )
        if args.memory_cmd == "promote":
            return print_global_promote(
                repo,
                content=args.content,
                target_project=args.target_project,
                memory_id=args.memory_id,
                confidence=args.confidence,
                write_draft=args.write_draft,
                fmt=args.format,
            )
        if args.memory_cmd == "promotion-inbox":
            return print_memory_promotion_inbox(
                repo,
                project_name=args.project,
                show=args.show,
                apply=args.apply,
                reject=args.reject,
                reason=args.reason,
                yes=args.yes,
                include_all=args.all,
                prune_closed=args.prune_closed,
                fmt=args.format,
            )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
