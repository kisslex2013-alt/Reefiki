import json
import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from reefiki_core.ops_dashboard import (
    DEFAULT_LOG_STALE_SECONDS,
    RuntimeLogBuffer,
    build_ops_dashboard_server,
    build_log_sources,
    create_ops_dashboard_demo,
    detect_stack,
    discover_git_repositories,
    logs_health_payload,
    logs_tail_payload,
    match_reefiki_mapping,
    ops_dashboard_snapshot,
    parse_roadmap_md,
    parse_tasks_md,
    redact_log_line,
    scan_project_metadata,
)

pytestmark = [pytest.mark.dashboard, pytest.mark.integration]


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def init_git(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-b", "main")


def write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_reefiki_root(root: Path) -> Path:
    write(root / "ROADMAP.md", "#### Phase 0j - audit-driven stabilization ⚡ АКТИВНА\n\nCurrent stage text.\n")
    write(
        root / "TASKS.md",
        """# TASKS

## Sprint 20 - Product readiness

- [x] **T-108** Done task
  - 2026-06-11 closeout: completed.
- [~] **T-111** Split package
  - 2026-06-11 progress: moved helpers.
- [ ] **T-116** Add local REEFIKI Ops Dashboard
""",
    )
    for project_name in ["reefiki", "Demo"]:
        project = root / "projects" / project_name
        write(project / "AGENTS.md", "rules\n")
        write(project / "_domain.md", "domain\n")
        (project / "raw").mkdir(parents=True, exist_ok=True)
        (project / "inbox").mkdir(parents=True, exist_ok=True)
        (project / "seen").mkdir(parents=True, exist_ok=True)
        write(project / "wiki" / "index.md", "# Index\n")
        write(
            project / "wiki" / "log.md",
            """# Log

## [2026-06-11] meta | sample

- sample log line
""",
        )
    return root


def non_git_file_snapshot(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or "/.git/" in rel:
            continue
        snapshot[rel] = path.read_bytes()
    return snapshot


def test_workspace_discovery_finds_one_level_git_repos_only(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = workspace / "app"
    nested = workspace / "plain" / "nested"
    init_git(repo)
    init_git(nested)
    (workspace / "plain").mkdir(exist_ok=True)

    repos, warnings = discover_git_repositories(workspace)

    assert warnings == []
    assert [path.name for path in repos] == ["app"]


def test_safe_metadata_scan_skips_secret_paths_and_forbidden_dirs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_git(repo)
    write(repo / ".env.local", "SHOULD_NOT_BE_READ=1\n")
    write(repo / "node_modules" / "leftpad" / "package.json", "{}")
    write(repo / "raw" / "source.md", "raw should be skipped")
    write(repo / "_wiki" / "AGENTS.md", "linked wiki should be skipped")
    write(repo / "package.json", "{}")
    write(repo / "AGENTS.md", "rules")
    write(repo / "tests" / "test_app.py", "def test_ok(): pass")

    metadata = scan_project_metadata(repo)
    files = set(metadata["files"])

    assert ".env.local" not in files
    assert "node_modules/leftpad/package.json" not in files
    assert "raw/source.md" not in files
    assert "_wiki/AGENTS.md" not in files
    assert "package.json" in files
    assert "tests/test_app.py" in files
    assert metadata["skipped_secret_paths"] == [".env.local"]
    assert "node_modules" in metadata["skipped_dirs"]
    assert "raw" in metadata["skipped_dirs"]
    assert "_wiki" in metadata["skipped_dirs"]


def test_stack_detection_handles_docs_only_without_app_manifest() -> None:
    stack = detect_stack({"README.md", "docs/one.md", "notes/two.md"}, {"docs", "notes"})

    assert stack == ["docs-only"]


def test_tasks_parser_detects_sprint_task_states_and_progress() -> None:
    payload = parse_tasks_md(
        """## Sprint 20 - Product readiness

- [x] **T-108** Done
  - 2026-06-11 closeout: complete.
- [~] **T-111** Active
  - 2026-06-11 progress: moved helpers.
- [ ] **T-116** Todo
"""
    )

    assert payload["current_sprint"] == "Sprint 20 - Product readiness"
    assert payload["task_counts"] == {"done": 1, "todo": 1, "active": 1}
    assert payload["active_tasks"][0]["id"] == "T-111"
    assert payload["next_tasks"][0]["id"] == "T-116"
    assert payload["t111_package_split_status"]["progress"] == ["2026-06-11 progress: moved helpers."]


def test_roadmap_parser_returns_compact_active_phase_summary() -> None:
    payload = parse_roadmap_md(
        """# Roadmap

#### Phase 0j - audit-driven stabilization ⚡ АКТИВНА

Current stage.

More detail.
"""
    )

    assert payload["current_phase"] == "Phase 0j - audit-driven stabilization ⚡ АКТИВНА"
    assert "Current stage" in payload["current_stage_summary"]


def test_reefiki_mapping_exact_missing_and_ambiguous() -> None:
    catalog = {
        "by_exact": {"Demo": Path("projects/Demo"), "Other": Path("projects/Other")},
        "by_lower": {"demo": [Path("projects/Demo")], "other": [Path("projects/Other")]},
    }

    assert match_reefiki_mapping("Demo", {}, catalog)["mapping_status"] == "connected"
    assert match_reefiki_mapping("Missing", {}, catalog)["mapping_status"] == "missing"
    ambiguous = match_reefiki_mapping("Demo", {"project_name": "Other"}, catalog)
    assert ambiguous["mapping_status"] == "ambiguous"


def test_snapshot_shape_contains_required_top_level_and_project_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = workspace / "Demo"
    init_git(repo)
    write(repo / "AGENTS.md", "rules")
    write(repo / "pyproject.toml", "[project]\nname='demo'\n")
    write(repo / ".reefiki", "project_name: Demo\n")
    reefiki = make_reefiki_root(tmp_path / "reefiki")

    payload = ops_dashboard_snapshot(workspace, reefiki)

    assert set(payload) == {
        "schema_version",
        "generated_at",
        "workspace_root",
        "reefiki_root",
        "workspace_warnings",
        "kpi",
        "current_work",
        "activity_feed",
        "projects",
        "reefiki",
        "memory",
        "tour",
    }
    assert payload["schema_version"] == "ops-dashboard.v2"
    assert payload["kpi"]["total"] == 1
    assert payload["memory"]["outcome"] == "pass"
    assert payload["memory"]["payload"]["providers"]["reefiki"]["status"] == "available"
    assert payload["memory"]["payload"]["dashboard_limits"]["memory_golden"] == "skipped"
    assert payload["tour"]["schema_version"] == "reefiki.guided-tour.v1"
    assert payload["tour"]["read_only"] is True
    assert [step["id"] for step in payload["tour"]["steps"]] == [
        "onboarding",
        "fixture",
        "status",
        "dashboard",
        "connect",
    ]
    project = payload["projects"][0]
    for key in [
        "name",
        "path",
        "is_git_repo",
        "branch",
        "head",
        "last_activity",
        "dirty",
        "dirty_paths_count",
        "ahead",
        "behind",
        "worktree_count",
        "remotes",
        "detected_stack",
        "gates",
        "detected_files",
        "readiness",
        "reefiki_mapping",
        "reefiki_status",
        "latest_log_entries",
        "warnings",
    ]:
        assert key in project
    assert project["reefiki_mapping"]["mapping_status"] == "connected"


def test_redact_log_line_masks_secret_like_values() -> None:
    token_key = "to" + "ken"
    secret_key = "sec" + "ret"
    bearer_label = "Bear" + "er"
    line, changed = redact_log_line(
        f"12:00:00 ERROR {token_key}=abc123 {bearer_label} qwerty987654321 {secret_key}=demo"
    )

    assert changed is True
    assert "[REDACTED]" in line
    assert "abc123" not in line
    assert "qwerty987654321" not in line


def test_logs_health_and_tail_support_explicit_and_stale_sources(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reefiki = make_reefiki_root(tmp_path / "reefiki")
    runtime = RuntimeLogBuffer()
    live_log = tmp_path / "live.log"
    stale_log = tmp_path / "stale.log"
    token_key = "to" + "ken"
    write(
        live_log,
        f"12:00:00 INFO ready\n12:00:01 ERROR {token_key}=abc123\n",
    )
    write(stale_log, "12:00:00 INFO old line\n")
    old_mtime = int(stale_log.stat().st_mtime) - (DEFAULT_LOG_STALE_SECONDS + 30)
    os.utime(stale_log, (old_mtime, old_mtime))

    sources, default_source = build_log_sources(
        workspace,
        reefiki,
        runtime,
        allow_log_paths=[f"agent={live_log}", f"stale={stale_log}", f"missing={tmp_path / 'missing.log'}"],
    )

    assert default_source == "agent"

    health = logs_health_payload(sources, default_source)
    by_id = {source["id"]: source for source in health["sources"]}

    assert by_id["agent"]["state"] == "live"
    assert by_id["stale"]["state"] == "stale"
    assert by_id["missing"]["state"] == "unavailable"

    payload = logs_tail_payload(sources, "agent", limit=10)

    assert payload["ok"] is True
    assert payload["state"] == "live"
    assert payload["entries"][-1]["redacted"] is True
    assert "[REDACTED]" in payload["entries"][-1]["raw"]


def test_log_sources_dedupe_duplicate_file_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reefiki = make_reefiki_root(tmp_path / "reefiki")
    runtime = RuntimeLogBuffer()
    reefiki_log = reefiki / "projects" / "reefiki" / "wiki" / "log.md"

    sources, default_source = build_log_sources(
        workspace,
        reefiki,
        runtime,
        allow_log_paths=[f"reefiki-wiki={reefiki_log}"],
    )

    paths = [
        str(source["path"])
        for source in sources.values()
        if source.get("path")
    ]
    assert paths.count(str(reefiki_log.resolve(strict=False))) == 1
    assert default_source == "reefiki-main-log"


def test_server_smoke_returns_html_and_json(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = workspace / "Demo"
    init_git(repo)
    write(repo / "AGENTS.md", "rules")
    reefiki = make_reefiki_root(tmp_path / "reefiki")
    live_log = tmp_path / "agent.log"
    write(live_log, "12:00:00 INFO hello\n")
    server = build_ops_dashboard_server(
        workspace,
        reefiki,
        port=0,
        allow_log_paths=[f"agent={live_log}"],
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        html_body = urllib.request.urlopen(f"http://{host}:{port}/", timeout=5).read().decode("utf-8")
        json_body = urllib.request.urlopen(f"http://{host}:{port}/api/snapshot", timeout=5).read().decode("utf-8")
        logs_health_body = urllib.request.urlopen(f"http://{host}:{port}/api/logs/health", timeout=5).read().decode("utf-8")
        logs_tail_body = urllib.request.urlopen(
            f"http://{host}:{port}/api/logs/tail?source=agent",
            timeout=5,
        ).read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "REEFIKI Ops Dashboard v2" in html_body
    assert "REEFIKI Ops Dashboard" in html_body
    static_dir = ROOT / "scripts" / "reefiki_core" / "ops_dashboard" / "static"
    app_body = (static_dir / "app.js").read_text(encoding="utf-8")
    theme_body = (static_dir / "theme.css").read_text(encoding="utf-8")
    i18n_body = (static_dir / "i18n.json").read_text(encoding="utf-8")

    assert 'id="current-work"' in html_body
    assert 'id="first-run"' in html_body
    assert 'id="first-run-dismiss"' in html_body
    assert 'data-i18n-aria-label="pin-column-title"' in html_body
    assert 'data-i18n="col-num"' in html_body
    assert 'data-field="pin"' in html_body
    assert 'data-field="index"' in html_body
    assert 'data-field="mapping-cell"' in html_body
    assert 'class="table-badge"' in html_body
    assert 'class="branch-chip"' in html_body
    assert 'class="kpi-strip"' in html_body
    assert html_body.index('id="first-run"') < html_body.index('id="kpi"') < html_body.index('class="card current-lane"')
    assert html_body.index('class="card current-lane"') < html_body.index('id="projects"')
    assert 'id="reefiki-control"' in html_body
    assert 'class="board__left"' in html_body
    assert 'class="board__right"' in html_body
    assert 'class="board__right-bottom"' not in html_body
    assert html_body.index('id="projects"') < html_body.index('id="inspector"') < html_body.index('id="reefiki-control"')
    assert html_body.index('id="reefiki-control"') < html_body.index('class="card rail-card"')
    assert 'id="lang"' in html_body
    assert 'id="theme"' in html_body
    assert 'id="logs-source"' in html_body
    assert 'id="live-logs"' in html_body
    assert 'data-i18n-aria-label="close-inspector"' in html_body
    assert "reefiki.opsDashboard.language" in app_body
    assert "reefiki.opsDashboard.theme" in app_body
    assert "reefiki.opsDashboard.firstRun.dismissed" in app_body
    assert "renderFirstRunTour" in app_body
    assert "tour-step--current" in theme_body
    assert "tour.status.current" in i18n_body
    assert "reefiki.opsDashboard.pinnedProjects" in app_body
    assert "processI18nNodes" in app_body
    assert "projectReadinessText" in app_body
    assert "projectActionText" in app_body
    assert "togglePinnedProject" in app_body
    assert "composeCurrentWork" in app_body
    assert "connectCommand" in app_body
    assert "renderConnect" in app_body
    assert "scrollConnectIntoView" in app_body
    assert "mapping-action" in app_body
    assert "timelineEvents" in app_body
    assert "logPinnedToBottom" in app_body
    assert "logForceStickToBottom" in app_body
    assert "isLogsNearBottom" in app_body
    assert "previousScrollTop" in app_body
    assert "enhanceSelects" in app_body
    assert "syncCustomSelect" in app_body
    assert "select-ui__option" in app_body
    assert "summary.attention-projects" in app_body
    assert "summary.current-work-mixed-title" in i18n_body
    assert "pin-column-title" in i18n_body
    assert "tab.connect" in i18n_body
    assert "connect.copy" in i18n_body
    assert "logs-status-title.stale" in i18n_body
    assert "action.inspect-dirty" in i18n_body
    assert "els.logsStatus" in app_body and ".title" in app_body
    assert '"/api/logs/health"' in app_body
    assert "/api/logs/tail?" in app_body
    assert "els.lastRefresh.title" in app_body
    assert 'class="activity-list"' in html_body
    assert "grid-template-columns: repeat(8, minmax(92px, 1fr));" in theme_body
    assert "grid-template-columns: repeat(4, minmax(120px, 1fr));" in theme_body
    assert "overflow-x: hidden;" in theme_body
    assert "grid-template-rows: auto minmax(0, 1fr);" in theme_body
    assert "#activity-panel:not([hidden])" in theme_body
    assert "grid-template-columns: 66px minmax(0, 1fr);" in theme_body
    assert "grid-template-columns: max-content max-content minmax(0, 1fr);" in theme_body
    assert "@keyframes panel-enter" in theme_body
    assert "@keyframes item-enter" in theme_body
    assert "@keyframes select-menu-enter" in theme_body
    assert "animation: item-enter" in theme_body
    assert ".select-ui__list" in theme_body
    assert ".native-select-hidden" in theme_body
    assert "prefers-reduced-motion" in theme_body
    assert ".pin-button.is-pinned" in theme_body
    assert ".connect-handoff" in theme_body
    assert "position: sticky;" in theme_body
    assert "[hidden] { display: none !important; }" in theme_body
    assert ".table-badge.tone-warn" in theme_body
    assert "align-content: start;" in theme_body
    assert ".activity-item__body" in theme_body
    assert "overflow-wrap: anywhere;" in theme_body
    assert ".inspector.is-empty" in theme_body
    assert ".badge.tone-unknown" in theme_body
    assert "work-card__action" in html_body
    assert "work-card__meta" not in html_body
    assert 'data-field="recent-log"' not in html_body
    assert 'class="inspector__body"' in html_body
    assert "Русский" in html_body
    assert "Онлайн" in i18n_body
    assert "Интервал" in i18n_body
    assert "Логи" in i18n_body
    assert "устарел" in i18n_body
    assert "Раб. деревья" in i18n_body
    assert "Последний лог" in i18n_body
    assert "Риски" in i18n_body
    assert "сейчас" in i18n_body
    assert "First run" in i18n_body
    assert "Первый запуск" in i18n_body
    assert "Светлая" in i18n_body
    assert json.loads(json_body)["kpi"]["total"] == 1
    assert json.loads(logs_health_body)["default_source_id"] == "agent"
    assert json.loads(logs_tail_body)["source"]["id"] == "agent"


def test_server_default_ui_remains_current_dashboard(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reefiki = make_reefiki_root(tmp_path / "reefiki")
    server = build_ops_dashboard_server(workspace, reefiki, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        html_body = urllib.request.urlopen(f"http://{host}:{port}/", timeout=5).read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "REEFIKI Ops Dashboard v2" in html_body
    assert 'data-ui="ops-board-next"' not in html_body


def test_server_next_ui_serves_static_next_bundle(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reefiki = make_reefiki_root(tmp_path / "reefiki")
    server = build_ops_dashboard_server(workspace, reefiki, port=0, ui="next")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        html_body = urllib.request.urlopen(f"http://{host}:{port}/", timeout=5).read().decode("utf-8")
        js_body = urllib.request.urlopen(f"http://{host}:{port}/static/app.js", timeout=5).read().decode("utf-8")
        css_body = urllib.request.urlopen(f"http://{host}:{port}/static/theme.css", timeout=5).read().decode("utf-8")
        i18n_body = urllib.request.urlopen(f"http://{host}:{port}/static/i18n.json", timeout=5).read().decode("utf-8")
        snapshot_body = urllib.request.urlopen(f"http://{host}:{port}/api/snapshot", timeout=5).read().decode("utf-8")
        logs_health_body = urllib.request.urlopen(f"http://{host}:{port}/api/logs/health", timeout=5).read().decode("utf-8")
        logs_tail_body = urllib.request.urlopen(
            f"http://{host}:{port}/api/logs/tail?source=dashboard-runtime",
            timeout=5,
        ).read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "REEFIKI Workspace Ops Board Next" in html_body
    assert 'data-ui="ops-board-next"' in html_body
    assert 'id="command-center"' in html_body
    assert 'id="projects-search"' in html_body
    assert 'id="projects-views"' in html_body
    assert 'id="projects-filters"' in html_body
    assert 'id="worktrees-search"' in html_body
    assert 'id="worktrees-views"' in html_body
    assert 'id="worktrees-filters"' in html_body
    assert 'id="publish-summary"' in html_body
    assert 'id="logs-search"' in html_body
    assert 'id="logs-views"' in html_body
    assert 'id="logs-filters"' in html_body
    assert 'class="action-help"' in html_body
    assert 'aria-live="polite"' in html_body
    assert "SECTION_IDS" in js_body
    assert "SECTION_HOTKEYS" in js_body
    assert "renderCommandCenter" in js_body
    assert "renderProjectFilters" in js_body
    assert "renderWorktreeFilters" in js_body
    assert "renderPublishSummary" in js_body
    assert "filteredLogEntries" in js_body
    assert "logLevelBucket" in js_body
    assert "textMatches" in js_body
    assert "renderViewControls" in js_body
    assert "saveCurrentView" in js_body
    assert "reefiki.opsBoardNext.savedViews" in js_body
    assert "handleGlobalKeydown" in js_body
    assert "focusSectionSearch" in js_body
    assert "focusFirstRailAction" in js_body
    assert "projectIssues" in js_body
    assert "warningNode" in js_body
    assert "commandHelp" in js_body
    assert "attachWarningAccordion" in js_body
    assert "expandedWarningKey" in js_body
    assert "sectionRollups" in js_body
    assert "activateSection(section);\n      setRail(defaultRail(section));" not in js_body
    assert ".workspace-layout" in css_body
    assert "height: 100dvh;" in css_body
    assert "overflow: hidden;" in css_body
    assert "grid-template-columns: 206px minmax(0, 1fr) 320px;" in css_body
    assert ".query-strip" in css_body
    assert ".search-field" in css_body
    assert ".view-strip" in css_body
    assert ".view-button" in css_body
    assert "input:focus-visible" in css_body
    assert ".rail-action[data-copy-state=\"copied\"]" in css_body
    assert "@keyframes rail-content-enter" in css_body
    assert 'aria-busy="false"' in html_body
    assert ".card-warning-accordion" in css_body
    assert ".warning-toggle" in css_body
    assert ".card-warning-panel" in css_body
    assert ".card-warning-panel.is-closing" in css_body
    assert ".skeleton-card" in css_body
    assert "@keyframes skeleton-shimmer" in css_body
    assert ".warning-explainer" in css_body
    assert ".action-help::after" in css_body
    assert ".command-center" in css_body
    assert ".filter-strip" in css_body
    assert ".nav-item strong" in css_body
    assert "Пульт рабочего пространства" in i18n_body
    i18n_payload = json.loads(i18n_body)
    assert i18n_payload["en"]["nav.overview"] == "Overview"
    assert i18n_payload["ru"]["nav.overview"] == "Обзор"
    assert i18n_payload["ru"]["nav.projects"] == "Проекты"
    assert i18n_payload["ru"]["nav.memory"] == "Память"
    assert i18n_payload["ru"]["nav.worktrees"] == "Раб. деревья"
    assert i18n_payload["ru"]["nav.publish"] == "Публикация"
    assert i18n_payload["ru"]["nav.review"] == "Проверка"
    assert i18n_payload["ru"]["nav.sprint"] == "Спринт"
    assert i18n_payload["ru"]["nav.logs"] == "Логи"
    assert i18n_payload["ru"]["overview.nextSafeAction"] == "Следующее безопасное действие"
    assert i18n_payload["ru"]["projects.search"] == "Поиск проектов"
    assert i18n_payload["ru"]["worktrees.search"] == "Поиск worktrees"
    assert i18n_payload["ru"]["logs.search"] == "Поиск логов"
    assert i18n_payload["ru"]["warning.agents.title"] == "Нет AGENTS.md"
    assert i18n_payload["ru"]["warningAccordion.show"] == "Разобрать предупреждения ({count})"
    assert i18n_payload["ru"]["memory.note"].startswith("Read-only memory status")
    assert i18n_payload["ru"]["memory.graphArtifact"] == "Graph artifact"
    assert i18n_payload["ru"]["memory.snapshotMissingTitle"] == "Memory status отсутствует в snapshot"
    assert i18n_payload["ru"]["memory.topologyTitle"] == "Схема memory control flow"
    assert i18n_payload["ru"]["review.reason"] == "Причина"
    assert i18n_payload["ru"]["action.reviewQueues"] == "Review queues"
    assert i18n_payload["ru"]["commandHelp.connect"].startswith("Копирует handoff")
    assert i18n_payload["ru"]["views.saveCurrent"] == "Сохранить вид"
    assert i18n_payload["en"]["views.projectsTasks"] == "Task branches"
    assert i18n_payload["ru"]["filter.attention"] == "требуют внимания"
    assert i18n_payload["ru"]["filter.warn"] == "warn"
    assert i18n_payload["ru"]["publish.signalSecretScan"] == "Secret scan"
    assert "@keyframes section-enter" in css_body
    assert "@keyframes rail-refresh" in css_body
    assert "@keyframes copy-confirm" in css_body
    assert "prefers-reduced-motion" in css_body
    assert "restartAnimation" in js_body
    assert "is-appearing" in js_body
    assert "is-updating" in js_body
    assert json.loads(snapshot_body)["schema_version"] == "ops-dashboard.v2"
    assert json.loads(logs_health_body)["ok"] is True
    assert json.loads(logs_tail_body)["ok"] is True


def test_server_rejects_unknown_ui(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reefiki = make_reefiki_root(tmp_path / "reefiki")

    with pytest.raises(SystemExit, match="unsupported ops-dashboard ui"):
        build_ops_dashboard_server(workspace, reefiki, port=0, ui="unknown")


def test_static_next_assets_are_self_contained_and_selector_aligned() -> None:
    static_dir = ROOT / "scripts" / "reefiki_core" / "ops_dashboard" / "static_next"
    html_body = (static_dir / "index.html").read_text(encoding="utf-8")
    app_body = (static_dir / "app.js").read_text(encoding="utf-8")
    theme_body = (static_dir / "theme.css").read_text(encoding="utf-8")
    i18n_body = (static_dir / "i18n.json").read_text(encoding="utf-8")

    for body in [html_body, app_body, theme_body, i18n_body]:
        assert "http://" not in body
        assert "https://" not in body
        assert "React" not in body
        assert "vite" not in body.lower()
        assert "pnpm" not in body.lower()

    assert not (static_dir / "package.json").exists()
    assert not (static_dir / "package-lock.json").exists()
    assert not (static_dir / "vite.config.ts").exists()

    for section in ["overview", "projects", "memory", "worktrees", "publish", "review", "sprint", "logs"]:
        assert f'data-section="{section}"' in html_body
        assert f'id="section-{section}"' in html_body
    for node_id in [
        "verdict-card",
        "lang",
        "theme",
        "interval",
        "gate-continue",
        "gate-publish",
        "gate-cleanup",
        "kpi-grid",
        "command-center",
        "projects-search",
        "projects-views",
        "projects-table",
        "projects-filters",
        "memory-notice",
        "memory-panels",
        "memory-topology",
        "memory-insights",
        "worktrees-search",
        "worktrees-views",
        "worktrees-table",
        "worktrees-filters",
        "publish-summary",
        "publish-classification",
        "publish-gates",
        "review-hygiene",
        "review-list",
        "sprint-burndown",
        "active-tasks",
        "log-view",
        "logs-search",
        "logs-views",
        "logs-filters",
        "right-rail",
        "tpl-action",
    ]:
        assert f'id="{node_id}"' in html_body
        assert f'"{node_id}"' in app_body
    assert 'makeSelectable(els["verdict-card"]' in app_body
    assert 'safetyGateRail("publish")' in app_body
    assert "function verdictRail()" in app_body
    assert "function safetyGateRail(kind)" in app_body
    assert "function renderPublishClassification()" in app_body
    assert "function renderReviewHygiene()" in app_body
    assert "function renderSprintBurndown()" in app_body
    assert "function logEntryNode(entry, index)" in app_body
    assert "worktreeIsTaskSignal" in app_body
    assert "commandHelp.worktreeList" in i18n_body
    assert "publish.matrixPublicPrivate" in i18n_body
    assert "review.noisyPagesUnavailable" in i18n_body
    assert "logs.evidenceRaw" in i18n_body
    assert "ui.interval30" in i18n_body
    assert "ui.interval2m" in i18n_body
    assert 'class="mode-button"' in html_body
    assert "segmented-control" not in html_body
    assert "segment-button" not in html_body
    assert ".verdict-card:hover" in theme_body
    assert ".safety-gate:focus-visible" in theme_body
    assert ".signal-grid" in theme_body
    assert ".sprint-burn-bar" in theme_body
    assert ".log-evidence-panel" in theme_body
    assert "not available in current snapshot" in i18n_body
    assert "workspace-layout" in theme_body
    i18n_payload = json.loads(i18n_body)
    assert i18n_payload["en"]["nav.overview"] == "Overview"
    assert i18n_payload["ru"]["nav.overview"] == "Обзор"
    assert i18n_payload["ru"]["nav.projects"] == "Проекты"
    assert i18n_payload["ru"]["nav.memory"] == "Память"
    assert i18n_payload["ru"]["nav.worktrees"] == "Раб. деревья"
    assert i18n_payload["ru"]["nav.publish"] == "Публикация"
    assert i18n_payload["ru"]["nav.review"] == "Проверка"
    assert i18n_payload["ru"]["nav.sprint"] == "Спринт"
    assert i18n_payload["ru"]["nav.logs"] == "Логи"
    assert i18n_payload["en"]["overview.nextSafeAction"] == "Next safe action"
    assert i18n_payload["ru"]["overview.nextSafeAction"] == "Следующее безопасное действие"
    assert i18n_payload["en"]["projects.searchPlaceholder"] == "name, branch, stack, path"
    assert i18n_payload["ru"]["projects.searchPlaceholder"] == "имя, ветка, стек, путь"
    assert i18n_payload["ru"]["worktrees.searchPlaceholder"] == "ветка, путь, рекомендация"
    assert i18n_payload["ru"]["logs.searchPlaceholder"] == "level, команда, сообщение"
    assert i18n_payload["en"]["warningAccordion.show"] == "Explain warnings ({count})"
    assert i18n_payload["ru"]["warningAccordion.hide"] == "Свернуть предупреждения ({count})"
    assert i18n_payload["en"]["warning.dirty.title"] == "Dirty worktree"
    assert i18n_payload["ru"]["warning.dirty.title"] == "Dirty worktree"
    assert i18n_payload["en"]["warning.mappingMissing.title"] == "REEFIKI mapping missing"
    assert i18n_payload["ru"]["warning.mappingMissing.title"] == "Нет REEFIKI mapping"
    assert i18n_payload["en"]["commandHelp.status"].startswith("Copies a git status")
    assert i18n_payload["ru"]["commandHelp.status"].startswith("Копирует git status")
    assert i18n_payload["en"]["views.saveCurrent"] == "Save current"
    assert i18n_payload["ru"]["views.projectsAttention"] == "Требуют внимания"
    assert i18n_payload["ru"]["views.logsDashboard"] == "Dashboard trail"
    assert i18n_payload["ru"]["empty.projectsFiltered"] == "Нет проектов под текущий поиск или фильтр."
    assert i18n_payload["ru"]["empty.logsFiltered"] == "Нет log lines под текущий поиск или фильтр."
    assert i18n_payload["ru"]["filter.attention"] == "требуют внимания"
    assert i18n_payload["en"]["filter.error"] == "error"
    assert i18n_payload["en"]["ui.interval30"] == "30 seconds"
    assert i18n_payload["ru"]["ui.interval2m"] == "2 минуты"
    assert i18n_payload["ru"]["publish.signalSecretScan"] == "Secret scan"
    assert "@keyframes section-enter" in theme_body
    assert "@keyframes item-enter" in theme_body
    assert "@keyframes rail-refresh" in theme_body
    assert "@keyframes rail-content-enter" in theme_body
    assert "@keyframes log-line-enter" in theme_body
    assert "@keyframes copy-confirm" in theme_body
    assert "prefers-reduced-motion" in theme_body
    assert "animation-delay: calc(var(--i, 0)" in theme_body
    rail_refresh_block = theme_body.split("@keyframes rail-refresh", 1)[1].split("@keyframes rail-content-enter", 1)[0]
    assert "transform:" not in rail_refresh_block
    assert "opacity:" not in rail_refresh_block
    assert ".query-strip" in theme_body
    assert ".search-field" in theme_body
    assert '"Aptos", "Segoe UI Variable"' in theme_body
    assert "--muted: #bbc7d8;" in theme_body
    assert "--muted: #334155;" in theme_body
    assert ".app-shell" in theme_body and "height: 100dvh;" in theme_body
    assert "grid-template-columns: 206px minmax(0, 1fr) 320px;" in theme_body
    assert "grid-template-columns: 190px minmax(0, 1fr) 292px;" in theme_body
    assert ".left-nav" in theme_body and "overflow-y: auto;" in theme_body
    assert ".nav-item span:not(.nav-icon)" in theme_body
    assert ".main-stage" in theme_body and "scrollbar-gutter: stable;" in theme_body
    assert ".rail-fields" in theme_body and "flex: 1 1 auto;" in theme_body
    assert ".safety-strip" in theme_body and "min-height: 27px;" in theme_body
    assert ".safety-status" in theme_body and "margin-left: auto;" in theme_body
    assert ".skeleton-line" in theme_body
    assert "@keyframes skeleton-shimmer" in theme_body
    assert ".status-pill.is-skeleton" in theme_body
    assert ".rail-action.skeleton-card" in theme_body
    assert ".dot.is-skeleton" in theme_body
    assert ".gate-icon.is-skeleton" in theme_body
    assert ".mode-button" in theme_body
    assert ".mode-button svg" in theme_body
    assert ".segmented-control" not in theme_body
    assert ".segment-button" not in theme_body
    assert ".card-warning-accordion" in theme_body
    assert ".memory-notice" in theme_body
    assert ".memory-flow" in theme_body
    assert ".memory-flow-node" in theme_body
    assert ".memory-insights" in theme_body
    assert ".memory-insight" in theme_body
    assert ".warning-toggle" in theme_body and 'content: "+"' in theme_body
    assert ".card-warning-panel" in theme_body
    assert "@keyframes warning-panel-enter" in theme_body
    assert "@keyframes warning-panel-exit" in theme_body
    assert ".rail-warnings" not in theme_body
    assert "rail-warnings" not in html_body
    assert ".warning-explainer" in theme_body and ".warning-head" in theme_body
    assert ".rail-actions" in theme_body and "max-height: 34%;" in theme_body
    assert ".action-help::after" in theme_body and "content: attr(data-tooltip);" in theme_body
    assert ".workspace-layout" in theme_body and "overflow: hidden;" in theme_body
    assert ".view-strip" in theme_body
    assert ".view-chip" in theme_body
    assert 'input[type="search"]' in theme_body
    assert ".command-center" in theme_body
    assert ".filter-strip" in theme_body
    assert ".filter-button" in theme_body
    assert ".nav-item strong" in theme_body
    assert "restartAnimation(activePanel" in app_body
    assert 'rail.setAttribute("aria-busy", "true")' in app_body
    assert 'rail.setAttribute("aria-busy", "false")' in app_body
    assert 'restartAnimation(rail, "is-updating")' in app_body
    assert "renderLoadingState" in app_body
    assert "renderTopSkeleton" in app_body
    assert "skeletonList" in app_body
    assert "renderRailSkeleton" in app_body
    assert "state.railPayload" in app_body
    assert 'rail.dataset.loading = "true"' in app_body
    assert 'els["verdict-card"].dataset.loading = "true"' in app_body
    assert 'gate.dataset.loading = "true"' in app_body
    assert "state.snapshotLoading" in app_body
    assert "reviewQueueCard" in app_body
    assert "reviewHealthCard" in app_body
    assert "reviewHealthActions" in app_body
    assert "projectIssues(project)" in app_body
    assert "warningNode(issue)" in app_body
    assert "snapshotIssue(warning)" in app_body
    assert "commandHelp(action)" in app_body
    assert "attachWarningAccordion(node, project" in app_body
    assert "state.expandedWarningKey" in app_body
    attach_block = app_body.split("function attachWarningAccordion", 1)[1].split(
        "function warningAccordionKey", 1
    )[0]
    assert "renderOverview()" not in attach_block
    assert "toggleWarningAccordion(key, issues, button, panel)" in attach_block
    assert "function closeOpenWarningAccordions" in app_body
    assert "function setWarningToggle" in app_body
    assert "function closeWarningPanel" in app_body
    assert "WARNING_PANEL_CLOSE_MS" in app_body
    assert "function memoryPayload" in app_body
    assert "function memorySnapshotState" in app_body
    assert "function renderMemoryNotice" in app_body
    assert "function memoryFallbackCards" in app_body
    assert "function renderMemoryTopology" in app_body
    assert "function renderMemoryInsights" in app_body
    assert "function memoryProviderMeta" in app_body
    assert "function memoryOverallTone" in app_body
    assert "memory.snapshotMissingTitle" in app_body
    assert "payload.warnings" not in app_body
    assert "renderCommandCenter" in app_body
    assert "renderProjectFilters" in app_body
    assert "filteredProjects" in app_body
    assert "projectSearchText" in app_body
    assert "renderWorktreeFilters" in app_body
    assert "filteredWorktreeProjects" in app_body
    assert "worktreeSearchText" in app_body
    assert "renderPublishSummary" in app_body
    assert "sectionRollups" in app_body
    assert "setNavRollup" in app_body
    assert "renderLogFilters" in app_body
    assert "filteredLogEntries" in app_body
    assert "logSearchText" in app_body
    assert "function formatLogTimestamp" in app_body
    assert 'els["generated-at"].textContent = snapshot().generated_at ? formatLogTimestamp(snapshot().generated_at)' in app_body
    assert "${match[4]}:${match[5]} | ${match[3]}-${match[2]}-${match[1]}" in app_body
    assert 'level.className = "log-level-badge"' in app_body
    assert "level.dataset.level = logLevelBucket(entry)" in app_body
    assert 'return "debug"' in app_body
    assert "renderViewControls" in app_body
    assert "applyView" in app_body
    assert "saveCurrentView" in app_body
    assert "localStorage.setItem(STORAGE.savedViews" in app_body
    assert "bindModeButton" in app_body
    assert "nextIntervalValue" in app_body
    assert "iconSvg" in app_body
    assert "bindSegmentedControl" not in app_body
    assert "setSegmentedValue" not in app_body
    assert "SECTION_HOTKEYS" in app_body
    assert "handleGlobalKeydown" in app_body
    assert "clearCurrentSearch" in app_body
    assert "focusFirstRailAction" in app_body
    assert "node.dataset.copyState = \"copied\"" in app_body
    assert "aria-label" in app_body
    assert 'aria-live="polite"' in html_body
    assert 'id="right-rail" aria-live="polite" aria-busy="false"' in html_body
    assert 'data-field="help"' in html_body
    assert "input:focus-visible" in theme_body
    assert ".nav-item:focus-visible" in theme_body
    assert ".ops-table tbody tr:focus-visible" in theme_body
    assert ".rail-action[data-copy-state=\"failed\"]" in theme_body
    assert "grid-template-columns: 132px 56px minmax(0, 1fr);" in theme_body
    assert "align-items: start;" in theme_body
    assert ".log-line span:first-child" in theme_body and "white-space: nowrap;" in theme_body
    assert ".log-level-badge" in theme_body
    assert '.log-level-badge[data-level="warn"]' in theme_body
    assert '.log-level-badge[data-level="error"]' in theme_body
    assert '.log-level-badge[data-level="debug"]' in theme_body


def test_ops_dashboard_demo_fixture_creates_safe_workspace(tmp_path: Path) -> None:
    reefiki = make_reefiki_root(tmp_path / "reefiki")
    payload = create_ops_dashboard_demo(tmp_path / "dashboard-demo")

    assert payload["mode"] == "fixture"
    assert payload["workspace_root"] == str(tmp_path / "dashboard-demo")
    assert payload["serve_command"].endswith("--workspace-root " + str(tmp_path / "dashboard-demo") + " --port 7310")
    assert {
        "DemoApp/AGENTS.md",
        "DemoApp/README.md",
        "DemoApp/.reefiki",
        "AgentTask/AGENTS.md",
        "AgentTask/README.md",
        "AgentTask/notes/first-run.md",
        ".reefiki-dashboard-demo",
    }.issubset(set(payload["artifacts"]))

    repos, warnings = discover_git_repositories(tmp_path / "dashboard-demo")
    assert warnings == []
    assert [repo.name for repo in repos] == ["AgentTask", "DemoApp"]

    snapshot = ops_dashboard_snapshot(tmp_path / "dashboard-demo", reefiki)
    assert snapshot["kpi"]["total"] == 2
    assert snapshot["kpi"]["codex_branches"] == 1
    assert snapshot["kpi"]["dirty"] == 1
    assert any(project["name"] == "AgentTask" for project in snapshot["current_work"])
    assert all(project["latest_log_entries"] == [] for project in snapshot["projects"])
    assert all(event["project"] != "reefiki" for event in snapshot["activity_feed"])
    assert snapshot["reefiki"]["latest_log_entries"] == []


def test_snapshot_does_not_mutate_target_repo_fixture(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    repo = workspace / "Demo"
    init_git(repo)
    write(repo / "AGENTS.md", "rules")
    write(repo / ".reefiki", "project_name: Demo\n")
    write(repo / "notes.md", "unchanged\n")
    reefiki = make_reefiki_root(tmp_path / "reefiki")
    before = non_git_file_snapshot(repo)

    ops_dashboard_snapshot(workspace, reefiki)

    assert non_git_file_snapshot(repo) == before


def test_server_rejects_non_localhost_bind(tmp_path: Path) -> None:
    from reefiki_core.ops_dashboard import build_ops_dashboard_server

    with pytest.raises(SystemExit, match="localhost"):
        build_ops_dashboard_server(tmp_path, tmp_path, port=0, host="0.0.0.0")
