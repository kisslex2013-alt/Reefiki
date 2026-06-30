"""Ops Dashboard v2 — local read-only workspace overview.

Public API (re-exported for backwards compatibility with v1 imports):
    DEFAULT_WORKSPACE_ROOT
    SCHEMA_VERSION
    MAX_METADATA_FILES, MAX_METADATA_DEPTH
    FORBIDDEN_DIR_NAMES
    build_snapshot(workspace_root, reefiki_root) -> dict
    print_ops_dashboard(workspace_root, reefiki_root, fmt) -> int
    serve_ops_dashboard(workspace_root, reefiki_root, port, allow_log_paths=None, ui="current") -> int
"""

from .snapshot import (
    DEFAULT_WORKSPACE_ROOT,
    FORBIDDEN_DIR_NAMES,
    MAX_METADATA_DEPTH,
    MAX_METADATA_FILES,
    SCHEMA_VERSION,
    build_snapshot,
    detect_stack,
    discover_git_repositories,
    match_reefiki_mapping,
    print_ops_dashboard,
    scan_project_metadata,
    _parse_roadmap_md as parse_roadmap_md,
    _parse_tasks_md as parse_tasks_md,
)
from .server import DEFAULT_PORT, build_ops_dashboard_server, serve_ops_dashboard
from .demo import create_ops_dashboard_demo, print_ops_dashboard_demo
from .logs import (
    DEFAULT_LOG_STALE_SECONDS,
    RuntimeLogBuffer,
    build_log_sources,
    logs_health_payload,
    logs_tail_payload,
    redact_log_line,
)

ops_dashboard_snapshot = build_snapshot

__all__ = [
    "DEFAULT_PORT",
    "DEFAULT_LOG_STALE_SECONDS",
    "DEFAULT_WORKSPACE_ROOT",
    "FORBIDDEN_DIR_NAMES",
    "MAX_METADATA_DEPTH",
    "MAX_METADATA_FILES",
    "SCHEMA_VERSION",
    "RuntimeLogBuffer",
    "build_ops_dashboard_server",
    "build_log_sources",
    "build_snapshot",
    "create_ops_dashboard_demo",
    "detect_stack",
    "discover_git_repositories",
    "logs_health_payload",
    "logs_tail_payload",
    "match_reefiki_mapping",
    "ops_dashboard_snapshot",
    "parse_roadmap_md",
    "parse_tasks_md",
    "print_ops_dashboard",
    "print_ops_dashboard_demo",
    "redact_log_line",
    "scan_project_metadata",
    "serve_ops_dashboard",
]
