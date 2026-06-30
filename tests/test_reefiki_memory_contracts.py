import unittest
import ast
import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import pytest

from scripts.reefiki_memory import (
    AccessBoundaryContext,
    MemoryDecisionTrace,
    PolicySafetyLayer,
    ProviderCapability,
    ProviderDescriptor,
    PromotionCandidate,
    RouteDecision,
    build_default_registry,
)

ROOT = Path(__file__).resolve().parents[1]
REEFIKI_PATH = ROOT / "scripts" / "reefiki.py"
SPEC = importlib.util.spec_from_file_location("reefiki", REEFIKI_PATH)
reefiki = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reefiki)

pytestmark = [pytest.mark.memory, pytest.mark.contract, pytest.mark.slow]


class MemoryContractTests(unittest.TestCase):
    def test_production_sqlite_connections_use_shared_helper(self):
        direct_connect_calls: list[int] = []
        for source_path in [
            REEFIKI_PATH,
            ROOT / "scripts" / "reefiki_core" / "index_search.py",
        ]:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            parent_by_node: dict[ast.AST, ast.AST] = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parent_by_node[child] = parent

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (
                    isinstance(func, ast.Attribute)
                    and func.attr == "connect"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "sqlite3"
                ):
                    continue
                current: ast.AST | None = node
                parent_function = ""
                while current is not None:
                    if isinstance(current, ast.FunctionDef):
                        parent_function = current.name
                        break
                    current = parent_by_node.get(current)
                if parent_function != "sqlite_connection":
                    direct_connect_calls.append(node.lineno)

        self.assertEqual([], direct_connect_calls)

    def test_sqlite_connection_sets_busy_timeout_and_commits(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "index.sqlite"
            with reefiki.sqlite_connection(database, row_factory=True) as conn:
                timeout_ms = conn.execute("PRAGMA busy_timeout").fetchone()[0]
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.execute("INSERT INTO items VALUES ('ok')")
                row = conn.execute("SELECT name FROM items").fetchone()

            self.assertEqual(reefiki.SQLITE_BUSY_TIMEOUT_MS, timeout_ms)
            self.assertEqual("ok", row["name"])
            with reefiki.sqlite_connection(database) as conn:
                saved = conn.execute("SELECT name FROM items").fetchone()[0]
            self.assertEqual("ok", saved)

    def test_build_index_uses_project_local_advisory_lock(self):
        index_search_path = ROOT / "scripts" / "reefiki_core" / "index_search.py"
        tree = ast.parse(index_search_path.read_text(encoding="utf-8"))
        build_index = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "build_index"
        )
        lock_calls = [
            node
            for node in ast.walk(build_index)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "index_lock"
        ]

        self.assertEqual(1, len(lock_calls))

    def test_index_lock_serializes_between_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            holder_script = (
                "import importlib.util, pathlib, sys, time\n"
                f"spec=importlib.util.spec_from_file_location('reefiki', {str(REEFIKI_PATH)!r})\n"
                "reefiki=importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(reefiki)\n"
                "project=pathlib.Path(sys.argv[1])\n"
                "with reefiki.index_lock(project):\n"
                "    print('locked', flush=True)\n"
                "    time.sleep(1.0)\n"
            )
            waiter_script = (
                "import importlib.util, pathlib, sys\n"
                f"spec=importlib.util.spec_from_file_location('reefiki', {str(REEFIKI_PATH)!r})\n"
                "reefiki=importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(reefiki)\n"
                "project=pathlib.Path(sys.argv[1])\n"
                "with reefiki.index_lock(project):\n"
                "    print('acquired', flush=True)\n"
            )
            holder = subprocess.Popen(
                [sys.executable, "-c", holder_script, str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual("locked", holder.stdout.readline().strip())
                started = time.monotonic()
                completed = subprocess.run(
                    [sys.executable, "-c", waiter_script, str(project)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                elapsed = time.monotonic() - started
            finally:
                holder.wait(timeout=5)

            self.assertIn("acquired", completed.stdout)
            self.assertGreaterEqual(elapsed, 0.7)
            self.assertTrue((project / ".reefiki" / "index.lock").exists())

    def test_write_unique_text_uses_numbered_path_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "draft.md"
            base.write_text("existing\n", encoding="utf-8")

            created = reefiki.write_unique_text(base, "new\n")

            self.assertEqual(base.with_name("draft-2.md"), created)
            self.assertEqual("existing\n", base.read_text(encoding="utf-8"))
            self.assertEqual("new\n", created.read_text(encoding="utf-8"))

    def test_promotion_drafts_allocate_unique_paths_for_same_content(self):
        content = "We decided to keep atomic promotion draft writes because concurrent agents can collide."
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()

            first = reefiki.write_promotion_draft(project, content, memory_id="memo-1")
            second = reefiki.write_promotion_draft(project, content, memory_id="memo-2")

            self.assertNotEqual(first, second)
            self.assertEqual(first.stem + "-2", second.stem)
            self.assertIn("Memory ID: memo-1", first.read_text(encoding="utf-8"))
            self.assertIn("Memory ID: memo-2", second.read_text(encoding="utf-8"))

    def test_production_subprocess_calls_set_timeout(self):
        tree = ast.parse(REEFIKI_PATH.read_text(encoding="utf-8"))
        missing_timeout: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "run"
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            ):
                if not any(keyword.arg == "timeout" for keyword in node.keywords):
                    missing_timeout.append(node.lineno)

        self.assertEqual([], missing_timeout)

    def test_run_git_uses_replacement_decoding_for_localized_stderr(self):
        captured_kwargs: dict[str, object] = {}
        original_run = reefiki.subprocess.run

        def fake_run(args, **kwargs):
            captured_kwargs.update(kwargs)
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="localized error")

        try:
            reefiki.subprocess.run = fake_run
            reefiki.run_git(self.root if hasattr(self, "root") else ROOT, ["status"])
        finally:
            reefiki.subprocess.run = original_run

        self.assertEqual("replace", captured_kwargs.get("errors"))

    def test_pre_commit_config_runs_secret_scan_hook(self):
        config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

        self.assertIn("id: reefiki-secret-scan", config)
        self.assertIn("python scripts/reefiki.py secret-scan", config)

    def test_memoir_store_env_override_wins(self):
        store = reefiki.memoir_store_path(
            environ={"REEFIKI_MEMOIR_STORE": "D:/stores/custom"},
            platform_name="win32",
            home=Path("C:/Users/Ada"),
        )

        self.assertEqual(Path("D:/stores/custom"), store)

    def test_memoir_store_honors_standard_env_after_specific_override(self):
        store = reefiki.memoir_store_path(
            environ={"MEMOIR_STORE": "D:/stores/standard"},
            platform_name="win32",
            home=Path("C:/Users/Ada"),
        )

        self.assertEqual(Path("D:/stores/standard"), store)

    def test_memoir_store_specific_env_wins_over_standard_env(self):
        store = reefiki.memoir_store_path(
            environ={
                "REEFIKI_MEMOIR_STORE": "D:/stores/specific",
                "MEMOIR_STORE": "D:/stores/standard",
            },
            platform_name="win32",
            home=Path("C:/Users/Ada"),
        )

        self.assertEqual(Path("D:/stores/specific"), store)

    def test_existing_codex_memoir_store_wins_over_platform_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            codex_store = home / ".codex" / "memoir-stores" / "reefiki"
            codex_store.mkdir(parents=True)
            store = reefiki.memoir_store_path(
                environ={"LOCALAPPDATA": str(home / "AppData" / "Local")},
                platform_name="win32",
                home=home,
            )

        self.assertEqual(codex_store, store)

    def test_parse_memoir_json_output_ignores_uvx_resolver_logs(self):
        output = """INFO add_decision: package resolver noise
WARN retrying resolver
{
  "success": true,
  "memories": [
    {
      "path": "context.project.branding",
      "content": "REEFIKI"
    }
  ],
  "count": 1
}
"""

        payload = reefiki._parse_memoir_json_output(output)

        self.assertTrue(payload["success"])
        self.assertEqual(1, payload["count"])
        self.assertEqual("context.project.branding", payload["memories"][0]["path"])

    def test_default_memoir_store_uses_localappdata_on_windows(self):
        store = reefiki.memoir_store_path(
            environ={"LOCALAPPDATA": "C:/Users/Ada/AppData/Local"},
            platform_name="win32",
            home=Path("C:/Users/Ada"),
        )

        self.assertEqual(Path("C:/Users/Ada/AppData/Local/memoir/reefiki"), store)

    def test_default_memoir_store_uses_xdg_data_home_off_windows(self):
        store = reefiki.memoir_store_path(
            environ={"XDG_DATA_HOME": "/home/ada/.local/share"},
            platform_name="linux",
            home=Path("/home/ada"),
        )

        self.assertEqual(Path("/home/ada/.local/share/memoir/reefiki"), store)

    def test_default_registry_declares_three_core_providers(self):
        registry = build_default_registry(Path("projects/reefiki"))

        self.assertEqual(["graphify", "memoir", "reefiki"], sorted(registry.providers))
        self.assertEqual(
            {"read", "search", "promote_source", "health", "provenance"},
            set(registry.providers["memoir"].capabilities),
        )
        self.assertIn(ProviderCapability.WRITE_DRAFT, registry.providers["reefiki"].capabilities)
        self.assertIn(ProviderCapability.RELATED_SUGGESTIONS, registry.providers["graphify"].capabilities)

    def test_reefiki_self_project_uses_repo_root_for_graphify_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            project = repo / "projects" / "reefiki"
            project.mkdir(parents=True)
            (repo / "AGENTS.md").write_text("# REEFIKI", encoding="utf-8")
            (project / "_domain.md").write_text("# Domain\n", encoding="utf-8")
            report = repo / "graphify-out" / "GRAPH_REPORT.md"
            report.parent.mkdir()
            report.write_text("# Graph Report", encoding="utf-8")

            self.assertEqual(repo, reefiki.project_code_path(project))
            self.assertEqual(report, reefiki.graphify_report_path(project))

    def test_route_decision_serializes_stable_shape(self):
        decision = RouteDecision(
            recommended_layer="reefiki",
            reason="durable decision/procedure intent",
            target_project="reefiki",
            secondary_layers=["graphify"],
            risk_flags=["public_snapshot_sensitive"],
        )

        self.assertEqual(
            {
                "input_hash": None,
                "recommended_layer": "reefiki",
                "secondary_layers": ["graphify"],
                "reason": "durable decision/procedure intent",
                "target_project": "reefiki",
                "risk_flags": ["public_snapshot_sensitive"],
                "needs_user_confirmation": False,
            },
            decision.to_dict(),
        )

    def test_memory_decision_trace_binds_route_policy_and_candidates(self):
        boundary = AccessBoundaryContext(
            project="reefiki",
            allowed_scopes=["projects/reefiki/wiki"],
            forbidden_scopes=["projects/metrica", "secrets", "raw"],
            visibility="private",
        )
        candidate = PromotionCandidate(
            content="Use promotion inbox before durable writes.",
            source_layer="memoir",
            target_project="reefiki",
            suggested_action="CREATE",
        )
        trace = MemoryDecisionTrace(
            operation="promote",
            boundary_context=boundary,
            route_decision=RouteDecision(
                recommended_layer="reefiki",
                reason="durable decision/procedure intent",
                target_project="reefiki",
            ),
            promotion_candidates=[candidate],
            safety_outcome="needs_review",
        )

        payload = trace.to_dict()

        self.assertEqual("promote", payload["operation"])
        self.assertEqual("reefiki", payload["boundary_context"]["project"])
        self.assertEqual("reefiki", payload["route_decision"]["recommended_layer"])
        self.assertEqual("CREATE", payload["promotion_candidates"][0]["suggested_action"])
        self.assertEqual("needs_review", payload["safety_outcome"])

    def test_policy_preflight_passes_allowed_private_scope(self):
        boundary = AccessBoundaryContext(
            project="reefiki",
            allowed_scopes=["projects/reefiki/wiki"],
            forbidden_scopes=["projects/metrica", "secrets", "raw"],
            visibility="private",
        )

        checks = PolicySafetyLayer().preflight(
            boundary,
            operation="lookup",
            content="Find the REEFIKI 2 control plane spec.",
            paths=["projects/reefiki/wiki/synthesis/reefiki-2-control-plane-spec.md"],
        )

        self.assertEqual("pass", checks.outcome)
        self.assertEqual([], checks.blocking_reasons)

    def test_policy_preflight_blocks_forbidden_scope(self):
        boundary = AccessBoundaryContext(
            project="reefiki",
            allowed_scopes=["projects/reefiki/wiki"],
            forbidden_scopes=["projects/metrica", "secrets", "raw"],
            visibility="private",
        )

        checks = PolicySafetyLayer().preflight(
            boundary,
            operation="pack",
            content="Build a handoff pack.",
            paths=["projects/metrica/wiki/index.md"],
        )

        self.assertEqual("block", checks.outcome)
        self.assertIn("forbidden_scope:projects/metrica", checks.blocking_reasons)

    def test_policy_preflight_blocks_secret_content_for_public_visibility(self):
        boundary = AccessBoundaryContext(
            project="reefiki",
            allowed_scopes=["projects/reefiki/wiki"],
            forbidden_scopes=["projects/metrica", "secrets", "raw"],
            visibility="public",
        )

        checks = PolicySafetyLayer().preflight(
            boundary,
            operation="export",
            content="TAVILY_" + "API_" + "KEY=tvly-" + "dev-1234567890abcdef",
            paths=["projects/reefiki/wiki/index.md"],
        )

        self.assertEqual("block", checks.outcome)
        self.assertIn("secret_like_content", checks.blocking_reasons)
        self.assertIn("public_visibility_requires_explicit_review", checks.warnings)


class MemoryCliContractTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.project = self.root / "projects" / "reefiki"
        (self.project / "wiki").mkdir(parents=True)
        (self.root / "projects" / "_template").mkdir(parents=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args: str):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = reefiki.main(["--project", str(self.root), *args])
        return code, stdout.getvalue()

    def run_project_cli(self, *args: str):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = reefiki.main(["--project", str(self.project), *args])
        return code, stdout.getvalue()

    def run_repo_cli(self, repo: Path, *args: str):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = reefiki.main(["--project", str(repo), *args])
        return code, stdout.getvalue()

    def init_synthetic_git_repo(self, repo: Path):
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True, text=True)
        (repo / "README.md").write_text("main\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)

    def write_project_scaffold(self):
        (self.project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (self.project / "_domain.md").write_text("domain\n", encoding="utf-8")
        for dirname in ["raw", "inbox", "seen"]:
            (self.project / dirname).mkdir(exist_ok=True)
        (self.project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (self.project / "wiki" / "log.md").write_text("", encoding="utf-8")

    def write_wiki_page(self, slug: str):
        target = self.project / "wiki" / "synthesis"
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{slug}.md").write_text(
            f"""---
id: {slug}
title: {slug}
type: synthesis
tags: [test]
useful_when: testing doctor index health
sources: []
date_added: 2026-06-08
use_count: 0
last_used:
---

# {slug}

Body.
""",
            encoding="utf-8",
        )

    def test_memory_status_json_exposes_default_provider_registry(self):
        code, output = self.run_cli("memory", "status", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(["graphify", "memoir", "reefiki"], sorted(payload["providers"]))
        self.assertIn("write_draft", payload["providers"]["reefiki"]["capabilities"])
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertEqual("missing_report", payload["graphify"]["status"])
        self.assertEqual(0, payload["review_queues"]["total"])
        self.assertEqual(0, payload["promotion_inbox"]["active"])
        self.assertEqual(0, payload["promotion_inbox"]["closed"])

    def test_doctor_json_passes_healthy_project(self):
        self.write_project_scaffold()
        reefiki.build_index(self.project)

        code, output = self.run_project_cli("doctor", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual([], payload["issues"])
        self.assertEqual("ok", payload["index"]["status"])
        self.assertEqual("ok", payload["index"]["integrity_check"])

    def test_doctor_json_fails_corrupt_sqlite_index(self):
        self.write_project_scaffold()
        state = self.project / ".reefiki"
        state.mkdir()
        (state / "index.sqlite").write_text("not sqlite\n", encoding="utf-8")

        code, output = self.run_project_cli("doctor", "--format", "json")

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("fail", payload["outcome"])
        self.assertIn("sqlite_corrupt", [issue["code"] for issue in payload["issues"]])
        self.assertEqual("reefiki", payload["project"])

    def test_doctor_json_reports_missing_required_project_paths(self):
        code, output = self.run_project_cli("doctor", "--format", "json")

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("fail", payload["outcome"])
        self.assertIn("missing_required_path", [issue["code"] for issue in payload["issues"]])

    def test_doctor_json_warns_on_stale_index_page_count(self):
        self.write_project_scaffold()
        reefiki.build_index(self.project)
        self.write_wiki_page("new-page-after-index")

        code, output = self.run_project_cli("doctor", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual("ok", payload["index"]["integrity_check"])
        self.assertIn("index_page_count_mismatch", [warning["code"] for warning in payload["warnings"]])

    def test_health_json_reports_practical_metrics_and_recommendations(self):
        self.write_project_scaffold()
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "used.md").write_text(
            """---
id: used
type: concept
title: "Used"
tags: [health]
useful_when:
  - "checks practical knowledge health usage metrics with enough words to pass the useful when quality threshold"
date_added: 2026-06-01
use_count: 3
last_used: 2026-06-08
---
Links to [[unused]].
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "concepts" / "unused.md").write_text(
            """---
id: unused
type: concept
title: "Unused"
tags: [health]
useful_when:
  - "checks zero use health signal"
date_added: 2026-01-01
use_count: 0
last_used: null
---
No outgoing links.
""",
            encoding="utf-8",
        )
        reefiki.build_index(self.project)

        code, output = self.run_project_cli("health", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("warn", payload["outcome"])
        self.assertEqual("pass", payload["doctor"]["outcome"])
        self.assertEqual(2, payload["size"]["wiki_pages"])
        self.assertEqual(0.5, payload["usage"]["zero_use_ratio"])
        self.assertEqual(1, payload["structure"]["orphan_pages"])
        self.assertEqual(0, payload["structure"]["broken_links"])
        self.assertIn("high_zero_use_ratio", {warning["code"] for warning in payload["warnings"]})
        self.assertTrue(payload["recommendations"])

    def test_health_ignores_gitkeep_inbox_placeholder(self):
        self.write_project_scaffold()
        (self.project / "inbox" / ".gitkeep").write_text("", encoding="utf-8")
        reefiki.build_index(self.project)

        code, output = self.run_project_cli("health", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(0, payload["size"]["inbox_items"])
        self.assertNotIn("inbox_pending", {warning["code"] for warning in payload["warnings"]})

    def test_log_archives_are_not_indexed_as_wiki_pages(self):
        (self.project / "wiki" / "skills").mkdir(parents=True)
        (self.project / "wiki" / "skills" / "runbook.md").write_text(
            """---
id: runbook
type: skill
title: "Runbook"
tags: [test]
useful_when:
  - "testing index"
verified: 2026-05-30
date_added: 2026-05-30
use_count: 0
last_used: null
---

## Шаги

1. Do the thing.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "logs").mkdir()
        (self.project / "wiki" / "logs" / "log-2026-05.md").write_text(
            "## [2026-05-30] meta | archived\n",
            encoding="utf-8",
        )

        count = reefiki.build_index(self.project)

        self.assertEqual(1, count)

    def test_escape_fts_quotes_keyword_tokens(self):
        self.assertEqual('"python" OR "AND" OR "NOT"', reefiki.escape_fts("python AND NOT"))

    def test_search_handles_fts_keywords_as_user_text(self):
        self.write_project_scaffold()
        self.write_wiki_page("python-notes")
        reefiki.build_index(self.project)

        rows = reefiki.search(self.project, "python AND NOT", limit=5)

        self.assertEqual(["python-notes"], [row["id"] for row in rows])

    def test_search_handles_punctuation_only_query(self):
        self.write_project_scaffold()
        self.write_wiki_page("punctuation-notes")
        reefiki.build_index(self.project)

        rows = reefiki.search(self.project, "---", limit=5)

        self.assertEqual([], list(rows))

    def test_index_records_wiki_links_and_search_filters_by_link_graph(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "target.md").write_text(
            """---
id: target
type: concept
title: "Target"
tags: [memory, graph]
useful_when:
  - "filter graph links"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Target page.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "synthesis" / "source.md").write_text(
            """---
id: source
type: synthesis
title: "Source"
tags: [memory]
useful_when:
  - "filter graph links"
sources: [current-session]
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[target]].
""",
            encoding="utf-8",
        )

        reefiki.build_index(self.project)
        rows = reefiki.search(
            self.project,
            "",
            10,
            page_type="synthesis",
            tag="memory",
            link_to="target",
        )

        self.assertEqual(["source"], [row["id"] for row in rows])

    def test_search_handles_punctuation_only_query_without_fts_crash(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "safe-search.md").write_text(
            """---
id: safe-search
type: concept
title: "Safe search"
tags: [memory]
useful_when:
  - "guard punctuation-only search"
date_added: 2026-06-08
use_count: 0
last_used: null
---
Plain body.
""",
            encoding="utf-8",
        )
        reefiki.build_index(self.project)

        rows = reefiki.search(self.project, "!!!!", 10)

        self.assertEqual([], rows)

    def test_search_handles_hyphenated_query_without_fts_syntax_error(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "anti-daily-log.md").write_text(
            """---
id: anti-daily-log
type: concept
title: "Anti daily log"
tags: [memory]
useful_when:
  - "find hyphenated terms"
date_added: 2026-06-08
use_count: 0
last_used: null
---
The anti daily log guardrail avoids noisy memory capture.
""",
            encoding="utf-8",
        )
        reefiki.build_index(self.project)

        rows = reefiki.search(self.project, "anti-daily-log", 10)

        self.assertEqual(["anti-daily-log"], [row["id"] for row in rows])

    def test_search_can_find_orphans_from_generated_link_cache(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "linked.md").write_text(
            """---
id: linked
type: concept
title: "Linked"
tags: [memory]
useful_when:
  - "check orphan filter"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[orphan]].
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "concepts" / "orphan.md").write_text(
            """---
id: orphan
type: concept
title: "Orphan"
tags: [memory]
useful_when:
  - "check orphan filter"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Back reference to [[linked]].
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "concepts" / "lonely.md").write_text(
            """---
id: lonely
type: concept
title: "Lonely"
tags: [memory]
useful_when:
  - "check orphan filter"
date_added: 2026-05-31
use_count: 0
last_used: null
---
No links.
""",
            encoding="utf-8",
        )

        rows = reefiki.search(self.project, "", 10, orphan=True)

        self.assertEqual(["lonely"], [row["id"] for row in rows])

    def test_search_returns_heading_chunk_context_when_enabled(self):
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "chunks.md").write_text(
            """---
id: chunks
type: synthesis
title: "Chunk Search"
tags: [memory]
useful_when:
  - "check chunk search"
sources: [current-session]
date_added: 2026-05-31
use_count: 0
last_used: null
---
# Overview

Intro text.

## Retrieval Contract

Needle phrase appears here.
""",
            encoding="utf-8",
        )

        rows = reefiki.search(self.project, "Needle", 10, chunked=True)

        self.assertEqual(["chunks"], [row["id"] for row in rows])
        self.assertEqual("Overview > Retrieval Contract", rows[0]["heading_path"])
        self.assertIn("Needle phrase", rows[0]["snippet"])

    def test_search_json_default_keeps_full_body_for_compatibility(self):
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "full-json.md").write_text(
            """---
id: full-json
type: synthesis
title: "Full Json Search"
tags: [memory]
useful_when:
  - "check default full json output"
sources: [current-session]
date_added: 2026-06-09
use_count: 0
last_used: null
---
Needle compatibility body.
""",
            encoding="utf-8",
        )
        reefiki.build_index(self.project)

        code, output = self.run_project_cli("search", "Needle", "--format", "json")
        payload = json.loads(output)

        self.assertEqual(0, code)
        self.assertEqual(["full-json"], [row["id"] for row in payload])
        self.assertIn("body", payload[0])
        self.assertIn("Needle compatibility body", payload[0]["body"])

    def test_search_json_compact_output_omits_full_body(self):
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "compact.md").write_text(
            """---
id: compact
type: synthesis
title: "Compact Search"
tags: [memory]
abstract: "Needle compact summary."
useful_when:
  - "check compact search output"
sources: [current-session]
date_added: 2026-06-09
use_count: 0
last_used: null
---
Needle body phrase.

This full body should not be serialized in compact output.
""",
            encoding="utf-8",
        )
        reefiki.build_index(self.project)

        code, output = self.run_project_cli(
            "search",
            "Needle",
            "--format",
            "json",
            "--output",
            "compact",
        )
        payload = json.loads(output)

        self.assertEqual(0, code)
        self.assertEqual(["compact"], [row["id"] for row in payload])
        self.assertNotIn("body", payload[0])
        self.assertEqual("Needle compact summary.", payload[0]["abstract"])
        self.assertEqual("wiki/synthesis/compact.md", payload[0]["file"])

    def test_search_json_files_output_returns_agent_file_list(self):
        (self.project / "wiki" / "decisions").mkdir(parents=True)
        (self.project / "wiki" / "decisions" / "routing-contract.md").write_text(
            """---
id: routing-contract
type: decision
title: "Routing Contract"
tags: [memory]
useful_when:
  - "check files search output"
sources: [current-session]
date_added: 2026-06-09
use_count: 0
last_used: null
---
Needle routing phrase.
""",
            encoding="utf-8",
        )
        reefiki.build_index(self.project)

        code, output = self.run_project_cli(
            "search",
            "Needle",
            "--format",
            "json",
            "--output",
            "files",
        )
        payload = json.loads(output)

        self.assertEqual(0, code)
        self.assertEqual("Needle", payload["query"])
        self.assertEqual(1, payload["count"])
        self.assertEqual("routing-contract", payload["files"][0]["docid"])
        self.assertEqual("wiki/decisions/routing-contract.md", payload["files"][0]["path"])
        self.assertNotIn("body", payload["files"][0])

    def test_search_indexes_abstract_as_l0_summary(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "abstract-page.md").write_text(
            """---
id: abstract-page
type: concept
title: "Abstract Page"
tags: [memory]
abstract: "Needle summary phrase for abstract-first query loading."
useful_when:
  - "check abstract search"
date_added: 2026-06-08
use_count: 0
last_used: null
---
Body intentionally omits the matching phrase.
""",
            encoding="utf-8",
        )
        reefiki.build_index(self.project)

        rows = reefiki.search(self.project, "Needle summary", 10)

        self.assertEqual(["abstract-page"], [row["id"] for row in rows])
        self.assertEqual("Needle summary phrase for abstract-first query loading.", rows[0]["abstract"])

    def test_overview_files_are_not_indexed_as_wiki_pages(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "_overview.md").write_text(
            "# Concepts overview\n\nFolder map only, not a durable wiki page.\n",
            encoding="utf-8",
        )
        (self.project / "wiki" / "concepts" / "real-page.md").write_text(
            """---
id: real-page
type: concept
title: "Real Page"
tags: [memory]
useful_when:
  - "check overview skip"
date_added: 2026-06-08
use_count: 0
last_used: null
---
Real page body.
""",
            encoding="utf-8",
        )

        count = reefiki.build_index(self.project)
        rows = reefiki.search(self.project, "Folder map", 10)

        self.assertEqual(1, count)
        self.assertEqual([], rows)

    def test_review_queues_can_filter_by_queue_type(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check queue filter"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[missing-page]].
""",
            encoding="utf-8",
        )

        items = reefiki.review_queue_scan(self.project, stale_days=999, queue_type="placeholder_link")

        self.assertEqual(["placeholder_link"], sorted({item["queue_type"] for item in items}))
        self.assertEqual(["source"], [item["page_id"] for item in items])

    def test_review_queues_summary_reports_counts_samples_and_actions(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check queue summary"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[missing-page]].
""",
            encoding="utf-8",
        )

        items = reefiki.review_queue_scan(self.project, stale_days=999)
        summary = reefiki.review_queue_summary(items, limit=1)

        self.assertGreaterEqual(summary["total"], 1)
        self.assertEqual(1, summary["counts"]["placeholder_link"])
        self.assertEqual("placeholder_link", summary["queues"][0]["queue_type"])
        self.assertEqual(["source"], summary["queues"][0]["sample_page_ids"])
        self.assertEqual([{"page_id": "source", "count": 1}], summary["queues"][0]["top_page_ids"])
        self.assertIn("resolve missing/moved page", summary["queues"][0]["suggested_action"])

    def test_review_queues_summary_cli_supports_json_and_text(self):
        self.write_project_scaffold()
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check queue summary cli"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[missing-page]].
""",
            encoding="utf-8",
        )

        code, stdout = self.run_project_cli("review-queues", "--summary", "--format", "json", "--limit", "1")
        payload = json.loads(stdout)

        self.assertEqual(0, code)
        self.assertEqual(1, payload["counts"]["placeholder_link"])
        self.assertEqual(["source"], payload["queues"][0]["sample_page_ids"])
        self.assertEqual([{"page_id": "source", "count": 1}], payload["queues"][0]["top_page_ids"])

        code, stdout = self.run_project_cli("review-queues", "--summary", "--limit", "1")

        self.assertEqual(0, code)
        self.assertIn("review queue candidates:", stdout)
        self.assertIn("top pages: source (1)", stdout)
        self.assertIn("Use --type <queue>", stdout)

    def test_review_queues_text_output_respects_limit(self):
        self.write_project_scaffold()
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check detailed queue limit"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[target-a]], [[target-b]], and [[target-c]].
""",
            encoding="utf-8",
        )
        for page_id in ["target-a", "target-b", "target-c"]:
            (self.project / "wiki" / "concepts" / f"{page_id}.md").write_text(
                f"""---
id: {page_id}
type: concept
title: "{page_id}"
tags: [memory]
useful_when:
  - "check detailed queue limit target"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Target page.
""",
                encoding="utf-8",
            )

        code, stdout = self.run_project_cli("review-queues", "--type", "missing_backlink", "--limit", "2")

        self.assertEqual(0, code)
        self.assertEqual(2, stdout.count("missing_backlink:"))
        self.assertIn("missing_backlink: target-a", stdout)
        self.assertIn("missing_backlink: target-b", stdout)
        self.assertNotIn("missing_backlink: target-c", stdout)
        self.assertIn("Showing first 2 of 3 candidate(s). Use --limit to adjust.", stdout)

    def test_review_queues_changed_missing_backlink_gate(self):
        self.write_project_scaffold()
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        source = self.project / "wiki" / "concepts" / "source.md"
        source.write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check changed missing backlink gate"
date_added: 2026-05-31
use_count: 0
last_used: null
---
## Related

[[target]] - useful context.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "concepts" / "target.md").write_text(
            """---
id: target
type: concept
title: "Target"
tags: [memory]
useful_when:
  - "check changed missing backlink gate target"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Target page.
""",
            encoding="utf-8",
        )

        code, stdout = self.run_project_cli(
            "review-queues",
            "--changed-path",
            "wiki/concepts/source.md",
            "--fail-on-changed-missing-backlink",
        )

        self.assertEqual(1, code)
        self.assertIn("changed missing_backlink gate: block", stdout)
        self.assertIn("- target <- source", stdout)

        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "[[target]] - useful context.",
                "[[target]] - useful context, intentionally one-way.",
            ),
            encoding="utf-8",
        )

        code, stdout = self.run_project_cli(
            "review-queues",
            "--changed-path",
            "wiki/concepts/source.md",
            "--fail-on-changed-missing-backlink",
        )

        self.assertEqual(0, code)
        self.assertIn("changed missing_backlink gate: pass", stdout)

    def test_review_queues_new_missing_backlink_gate_ignores_baseline_debt(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.root / "README.md").write_text("main\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        self.write_project_scaffold()
        concepts = self.project / "wiki" / "concepts"
        concepts.mkdir(parents=True)
        source = concepts / "source.md"
        source.write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check backlink regression gate"
date_added: 2026-05-31
use_count: 0
last_used: null
---
## Related

[[target-old]] - old useful context.
""",
            encoding="utf-8",
        )
        (concepts / "target-old.md").write_text(
            """---
id: target-old
type: concept
title: "Target old"
tags: [memory]
useful_when:
  - "check old backlink debt"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Old target page.
""",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "projects"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "baseline wiki debt"], cwd=self.root, check=True, capture_output=True, text=True)

        code, stdout = self.run_project_cli(
            "review-queues",
            "--changed-path",
            "wiki/concepts/source.md",
            "--fail-on-new-missing-backlink",
        )

        self.assertEqual(0, code)
        self.assertIn("new missing_backlink gate: pass", stdout)

        source.write_text(
            source.read_text(encoding="utf-8").replace(
                "[[target-old]] - old useful context.",
                "[[target-old]] - old useful context.\n[[target-new]] - new useful context.",
            ),
            encoding="utf-8",
        )
        (concepts / "target-new.md").write_text(
            """---
id: target-new
type: concept
title: "Target new"
tags: [memory]
useful_when:
  - "check new backlink debt"
date_added: 2026-05-31
use_count: 0
last_used: null
---
New target page.
""",
            encoding="utf-8",
        )

        code, stdout = self.run_project_cli("review-queues", "--fail-on-new-missing-backlink")

        self.assertEqual(1, code)
        self.assertIn("new missing_backlink gate: block", stdout)
        self.assertIn("- target-new <- source", stdout)
        self.assertNotIn("- target-old <- source", stdout)

    def test_review_queues_new_missing_backlink_gate_detects_untracked_new_page(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.root / "README.md").write_text("main\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        self.write_project_scaffold()
        concepts = self.project / "wiki" / "concepts"
        concepts.mkdir(parents=True)
        (concepts / "target.md").write_text(
            """---
id: target
type: concept
title: "Target"
tags: [memory]
useful_when:
  - "check untracked backlink regression"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Existing target page.
""",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "projects"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "baseline target"], cwd=self.root, check=True, capture_output=True, text=True)
        (concepts / "new-source.md").write_text(
            """---
id: new-source
type: concept
title: "New source"
tags: [memory]
useful_when:
  - "check new page backlink regression"
date_added: 2026-05-31
use_count: 0
last_used: null
---
## Related

[[target]] - new useful context.
""",
            encoding="utf-8",
        )

        code, stdout = self.run_project_cli("review-queues", "--fail-on-new-missing-backlink")

        self.assertEqual(1, code)
        self.assertIn("new missing_backlink gate: block", stdout)
        self.assertIn("- target <- new-source", stdout)

    def test_dashboard_json_combines_health_queues_and_next_action(self):
        self.write_project_scaffold()
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check dashboard queue summary"
sources: [test]
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[missing-page]].
""",
            encoding="utf-8",
        )

        code, output = self.run_project_cli("dashboard", "--format", "json", "--limit", "1")
        payload = json.loads(output)

        self.assertEqual(0, code)
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual("warn", payload["outcome"])
        self.assertEqual("warn", payload["health"]["outcome"])
        self.assertEqual(3, payload["health"]["warnings_count"])
        self.assertEqual(2, payload["review_queues"]["total"])
        self.assertEqual(1, payload["review_queues"]["counts"]["placeholder_link"])
        self.assertEqual(1, payload["review_queues"]["counts"]["orphan_review"])
        self.assertEqual(
            "run review-queues --type placeholder_link --limit 1",
            payload["next_action"],
        )

    def test_dashboard_text_is_a_short_operator_view(self):
        self.write_project_scaffold()
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check dashboard text"
sources: [test]
date_added: 2026-05-31
use_count: 0
last_used: null
---
Links to [[missing-page]].
""",
            encoding="utf-8",
        )

        code, output = self.run_project_cli("dashboard", "--limit", "1")

        self.assertEqual(0, code)
        self.assertIn("Dashboard: reefiki", output)
        self.assertIn("Outcome: warn", output)
        self.assertIn("Review queues: 2", output)
        self.assertIn("- placeholder_link: 1", output)
        self.assertIn("- orphan_review: 1", output)
        self.assertIn("Next action: run review-queues --type placeholder_link --limit 1", output)

    def test_memory_reflect_json_assembles_existing_gates_read_only(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        project = repo / "projects" / "reefiki"
        (project / "wiki" / "concepts").mkdir(parents=True)
        (project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (project / "_domain.md").write_text("domain\n", encoding="utf-8")
        for dirname in ["raw", "inbox", "seen"]:
            (project / dirname).mkdir(parents=True, exist_ok=True)
        (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (project / "wiki" / "log.md").write_text("", encoding="utf-8")
        (project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check memory reflection source report"
date_added: 2026-06-09
use_count: 0
last_used: null
---
Links to [[target]].
""",
            encoding="utf-8",
        )
        (project / "wiki" / "concepts" / "target.md").write_text(
            """---
id: target
type: concept
title: "Target"
tags: [memory]
useful_when:
  - "check memory reflection target queue"
date_added: 2026-06-09
use_count: 0
last_used: null
---
Target page.
""",
            encoding="utf-8",
        )
        reefiki.build_index(project)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "seed reefiki"], cwd=repo, check=True, capture_output=True, text=True)
        (project / "wiki" / "concepts" / "source.md").write_text(
            (project / "wiki" / "concepts" / "source.md").read_text(encoding="utf-8") + "\nChanged durable note.\n",
            encoding="utf-8",
        )

        code, output = self.run_repo_cli(
            repo,
            "memory",
            "reflect",
            "--project",
            "reefiki",
            "--since",
            "HEAD",
            "--format",
            "json",
            "--limit",
            "1",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual("HEAD", payload["since"])
        self.assertEqual("review", payload["outcome"])
        self.assertEqual(
            [
                "memory_diff",
                "health",
                "review_queues_summary",
                "memory_status_summary",
                "memory_pack_strict",
                "promotion_inbox",
            ],
            payload["included_sources"],
        )
        self.assertIn("raw", payload["excluded_scopes"])
        self.assertEqual(1, payload["included"]["changed_paths"]["total"])
        self.assertEqual("warn", payload["included"]["health"]["outcome"])
        self.assertEqual(1, payload["included"]["review_queues"]["counts"]["missing_backlink"])
        self.assertIn(payload["included"]["pack_quality"]["strict"]["outcome"], {"pass", "fail"})
        self.assertIn("blocking_reasons", payload["included"]["pack_quality"]["strict"])
        self.assertTrue(payload["candidate_actions"])
        self.assertIn("review-queues --type", payload["candidate_actions"][0]["action"])
        self.assertEqual("largest open review queue", payload["candidate_actions"][0]["reason"])
        self.assertIn("auto-apply wiki changes", {item["action"] for item in payload["blocked_actions"]})
        self.assertFalse((project / "plans").exists())

    def test_memory_reflect_candidate_action_uses_largest_queue(self):
        payload = {
            "project": "reefiki",
            "task": "memory reflection",
            "since": "HEAD",
            "included": {
                "health": {"outcome": "warn"},
                "review_queues": {
                    "queues": [
                        {"queue_type": "orphan_review", "count": 2},
                        {"queue_type": "missing_backlink", "count": 76},
                    ]
                },
                "promotion_inbox": {},
                "pack_quality": {"strict": {"outcome": "pass"}},
                "changed_paths": {"total": 0},
            },
        }

        actions = reefiki.reflection_candidate_actions(payload, limit=5)

        self.assertEqual("run review-queues --type missing_backlink --limit 5", actions[0]["action"])
        self.assertEqual("largest open review queue", actions[0]["reason"])

    def test_memory_reflect_since_date_uses_date_baseline(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        project = repo / "projects" / "reefiki"
        (project / "wiki" / "concepts").mkdir(parents=True)
        (project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (project / "_domain.md").write_text("domain\n", encoding="utf-8")
        for dirname in ["raw", "inbox", "seen"]:
            (project / dirname).mkdir(parents=True, exist_ok=True)
        (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (project / "wiki" / "log.md").write_text("", encoding="utf-8")
        (project / "wiki" / "concepts" / "dated.md").write_text(
            """---
id: dated
type: concept
title: "Dated"
tags: [memory]
useful_when:
  - "check dated reflection baseline"
date_added: 2026-06-09
use_count: 0
last_used: null
---
Initial page.
""",
            encoding="utf-8",
        )
        reefiki.build_index(project)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "commit", "-m", "seed dated"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_AUTHOR_DATE": "2026-06-01T12:00:00", "GIT_COMMITTER_DATE": "2026-06-01T12:00:00"},
        )
        (project / "wiki" / "concepts" / "dated.md").write_text(
            (project / "wiki" / "concepts" / "dated.md").read_text(encoding="utf-8") + "\nChanged after baseline.\n",
            encoding="utf-8",
        )

        code, output = self.run_repo_cli(
            repo,
            "memory",
            "reflect",
            "--project",
            "reefiki",
            "--since",
            "2026-06-01",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("2026-06-01", payload["included"]["changed_paths"]["since_date"])
        self.assertIn("--since-date 2026-06-01", payload["candidate_actions"][-1]["action"])

    def test_memory_reflect_does_not_create_search_index_when_missing(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        project = repo / "projects" / "reefiki"
        (project / "wiki" / "concepts").mkdir(parents=True)
        (project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (project / "_domain.md").write_text("domain\n", encoding="utf-8")
        for dirname in ["raw", "inbox", "seen"]:
            (project / dirname).mkdir(parents=True, exist_ok=True)
        (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (project / "wiki" / "log.md").write_text("", encoding="utf-8")
        (project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check reflection stays read only without index"
date_added: 2026-06-09
use_count: 0
last_used: null
---
No links.
""",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "seed no index"], cwd=repo, check=True, capture_output=True, text=True)

        code, output = self.run_repo_cli(
            repo,
            "memory",
            "reflect",
            "--project",
            "reefiki",
            "--since",
            "HEAD",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("fail", payload["included"]["pack_quality"]["strict"]["outcome"])
        self.assertIn("index:missing", payload["included"]["pack_quality"]["strict"]["blocking_reasons"])
        self.assertFalse((project / ".reefiki").exists())

    def test_memory_reflect_blocks_invalid_since_ref(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        project = repo / "projects" / "reefiki"
        (project / "wiki").mkdir(parents=True)
        (project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (project / "_domain.md").write_text("domain\n", encoding="utf-8")
        for dirname in ["raw", "inbox", "seen"]:
            (project / dirname).mkdir(parents=True, exist_ok=True)
        (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (project / "wiki" / "log.md").write_text("", encoding="utf-8")

        code, output = self.run_repo_cli(
            repo,
            "memory",
            "reflect",
            "--project",
            "reefiki",
            "--since",
            "does-not-exist",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("blocked", payload["outcome"])
        self.assertIn("error", payload["included"]["changed_paths"])

    def test_memory_reflect_blocks_invalid_since_date_without_traceback(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        project = repo / "projects" / "reefiki"
        (project / "wiki").mkdir(parents=True)
        (project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (project / "_domain.md").write_text("domain\n", encoding="utf-8")
        for dirname in ["raw", "inbox", "seen"]:
            (project / dirname).mkdir(parents=True, exist_ok=True)
        (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (project / "wiki" / "log.md").write_text("", encoding="utf-8")

        code, output = self.run_repo_cli(
            repo,
            "memory",
            "reflect",
            "--project",
            "reefiki",
            "--since",
            "2026-99-99",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("blocked", payload["outcome"])
        self.assertIn("99", payload["included"]["changed_paths"]["error"])

    def test_memory_reflect_write_report_only_writes_plans_artifact(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        project = repo / "projects" / "reefiki"
        (project / "wiki" / "concepts").mkdir(parents=True)
        (project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (project / "_domain.md").write_text("domain\n", encoding="utf-8")
        for dirname in ["raw", "inbox", "seen"]:
            (project / dirname).mkdir(parents=True, exist_ok=True)
        (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
        (project / "wiki" / "log.md").write_text("", encoding="utf-8")
        (project / "wiki" / "concepts" / "source.md").write_text(
            """---
id: source
type: concept
title: "Source"
tags: [memory]
useful_when:
  - "check reflection report write"
date_added: 2026-06-09
use_count: 0
last_used: null
---
Links to [[target]].
""",
            encoding="utf-8",
        )
        (project / "wiki" / "concepts" / "target.md").write_text(
            """---
id: target
type: concept
title: "Target"
tags: [memory]
useful_when:
  - "check reflection report target"
date_added: 2026-06-09
use_count: 0
last_used: null
---
Target.
""",
            encoding="utf-8",
        )
        reefiki.build_index(project)
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "seed report"], cwd=repo, check=True, capture_output=True, text=True)

        code, output = self.run_repo_cli(
            repo,
            "memory",
            "reflect",
            "--project",
            "reefiki",
            "--since",
            "HEAD",
            "--write-report",
            "--limit",
            "1",
        )

        self.assertEqual(0, code)
        report = project / output.strip()
        self.assertEqual(project / "plans" / f"reflection-{date.today().isoformat()}.md", report)
        text = report.read_text(encoding="utf-8")
        self.assertIn("# Memory Reflection: reefiki", text)
        self.assertIn("## Included Sources", text)
        self.assertIn("## Candidate Actions", text)
        self.assertEqual([], list((project / "raw").glob("*")))

    def test_memory_golden_reports_lookup_misses_as_eval_signal(self):
        (self.project / "golden-queries.yml").write_text(
            """version: 1
project: reefiki
queries:
  - id: missing-lookup
    kind: lookup
    query: impossible missing thing
    layer: reefiki
    expect_ids: [missing-page]
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "golden",
            "--project",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual(1, payload["failed"])
        self.assertEqual(["missing_ids:missing-page"], payload["cases"][0]["errors"])
        self.assertEqual(
            [
                {
                    "case_id": "missing-lookup",
                    "missing_ids": ["missing-page"],
                    "actual_ids": [],
                    "expected_ids": ["missing-page"],
                    "query": "impossible missing thing",
                }
            ],
            payload["misses"],
        )

    def test_memory_status_json_reports_control_plane_health(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "lonely.md").write_text(
            """---
id: lonely
type: concept
title: "Lonely page"
tags: [memory]
useful_when:
  - "check status queues"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
Body.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli("memory", "status", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertGreaterEqual(payload["review_queues"]["total"], 1)
        self.assertIn("orphan_review", payload["review_queues"]["counts"])
        self.assertEqual(
            "run graphify only when structural navigation is needed",
            payload["graphify"]["next_action"],
        )

    def test_memory_status_summary_reports_next_action_for_open_queues(self):
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "concepts" / "lonely.md").write_text(
            """---
id: lonely
type: concept
title: "Lonely page"
tags: [memory]
useful_when:
  - "check status next action"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
Body.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli("memory", "status", "--summary", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(True, payload["has_open"])
        self.assertEqual("run review-queues --summary for project reefiki", payload["next_action"])

        code, output = self.run_cli("memory", "status", "--summary")

        self.assertEqual(0, code)
        self.assertIn("next: run review-queues --summary for project reefiki", output)

    def test_memory_status_json_reports_promotion_inbox_summary(self):
        draft = reefiki.write_promotion_draft(
            self.project,
            "We decided to expose promotion inbox counts in memory status because operators need queue visibility.",
            memory_id="memo-status",
            confidence=0.8,
        )
        reefiki.reject_promotion_inbox_draft(
            self.project,
            str(draft),
            reason="status summary test",
            yes=True,
        )
        reefiki.prune_closed_promotion_drafts(self.project, yes=True)

        code, output = self.run_cli("memory", "status", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(0, payload["promotion_inbox"]["active"])
        self.assertEqual(1, payload["promotion_inbox"]["closed"])
        self.assertEqual(1, payload["promotion_inbox"]["total"])
        self.assertEqual({"rejected": 1}, payload["promotion_inbox"]["closed_counts"])

    def test_memory_status_fail_on_open_ignores_closed_promotion_drafts(self):
        draft = reefiki.write_promotion_draft(
            self.project,
            "We decided to keep closed promotion drafts out of open status gates.",
            memory_id="memo-status-closed",
            confidence=0.8,
        )
        reefiki.reject_promotion_inbox_draft(
            self.project,
            str(draft),
            reason="closed gate test",
            yes=True,
        )
        reefiki.prune_closed_promotion_drafts(self.project, yes=True)

        code, output = self.run_cli(
            "memory",
            "status",
            "--fail-on-open",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(False, payload["has_open"])
        self.assertEqual(0, payload["promotion_inbox"]["active"])
        self.assertEqual(1, payload["promotion_inbox"]["closed"])

    def test_memory_status_fail_on_open_detects_active_promotion_drafts(self):
        reefiki.write_promotion_draft(
            self.project,
            "We decided to fail status gates when promotion drafts still need review.",
            memory_id="memo-status-active",
            confidence=0.8,
        )

        code, output = self.run_cli(
            "memory",
            "status",
            "--fail-on-open",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual(True, payload["has_open"])
        self.assertEqual(1, payload["promotion_inbox"]["active"])

    def test_memory_status_json_accepts_project_name(self):
        metrica = self.root / "projects" / "metrica"
        (metrica / "wiki").mkdir(parents=True)

        code, output = self.run_cli(
            "memory",
            "status",
            "--project",
            "metrica",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("metrica", payload["project"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertEqual(["projects/metrica"], payload["policy"]["checked_paths"])
        self.assertEqual(0, payload["promotion_inbox"]["total"])

    def test_memory_status_json_accepts_all_projects(self):
        metrica = self.root / "projects" / "metrica"
        hermes = self.root / "projects" / "Hermes"
        (metrica / "wiki").mkdir(parents=True)
        (hermes / "wiki").mkdir(parents=True)

        code, output = self.run_cli(
            "memory",
            "status",
            "--all-projects",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("all", payload["project"])
        project_names = [item["project"] for item in payload["projects"]]
        self.assertEqual(["Hermes", "metrica", "reefiki"], project_names)
        self.assertEqual(3, payload["total"])
        self.assertIn("promotion_inbox", payload["projects"][0])

    def test_memory_status_json_all_projects_can_filter_only_open(self):
        metrica = self.root / "projects" / "metrica"
        hermes = self.root / "projects" / "Hermes"
        (metrica / "wiki" / "concepts").mkdir(parents=True)
        (hermes / "wiki").mkdir(parents=True)
        (metrica / "wiki" / "concepts" / "lonely.md").write_text(
            """---
id: lonely
type: concept
title: "Lonely page"
tags: [memory]
useful_when:
  - "check all projects only-open"
date_added: 2026-05-23
use_count: 0
last_used: null
---
Body.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "status",
            "--all-projects",
            "--only-open",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(["metrica"], [item["project"] for item in payload["projects"]])
        self.assertEqual(1, payload["total"])
        self.assertEqual(True, payload["only_open"])

    def test_memory_status_jsonl_all_projects_only_open_outputs_one_line_per_project(self):
        metrica = self.root / "projects" / "metrica"
        hermes = self.root / "projects" / "Hermes"
        (metrica / "wiki" / "concepts").mkdir(parents=True)
        (hermes / "wiki").mkdir(parents=True)
        (metrica / "wiki" / "concepts" / "lonely.md").write_text(
            """---
id: lonely
type: concept
title: "Lonely page"
tags: [memory]
useful_when:
  - "check jsonl only-open"
date_added: 2026-05-23
use_count: 0
last_used: null
---
Body.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "status",
            "--all-projects",
            "--only-open",
            "--format",
            "jsonl",
        )

        self.assertEqual(0, code)
        lines = [json.loads(line) for line in output.splitlines() if line.strip()]
        self.assertEqual(1, len(lines))
        self.assertEqual("metrica", lines[0]["project"])
        self.assertGreater(lines[0]["review_queues"]["total"], 0)

    def test_memory_status_all_projects_fail_on_open_returns_nonzero(self):
        metrica = self.root / "projects" / "metrica"
        (metrica / "wiki" / "concepts").mkdir(parents=True)
        (metrica / "wiki" / "concepts" / "lonely.md").write_text(
            """---
id: lonely
type: concept
title: "Lonely page"
tags: [memory]
useful_when:
  - "check fail on open"
date_added: 2026-05-23
use_count: 0
last_used: null
---
Body.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "status",
            "--all-projects",
            "--only-open",
            "--fail-on-open",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual(True, payload["has_open"])
        self.assertGreater(payload["totals"]["review_queues"], 0)

    def test_memory_status_all_projects_summary_json_is_compact(self):
        metrica = self.root / "projects" / "metrica"
        (metrica / "wiki" / "concepts").mkdir(parents=True)
        (metrica / "wiki" / "concepts" / "lonely.md").write_text(
            """---
id: lonely
type: concept
title: "Lonely page"
tags: [memory]
useful_when:
  - "check summary"
date_added: 2026-05-23
use_count: 0
last_used: null
---
Body.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "status",
            "--all-projects",
            "--only-open",
            "--summary",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("all", payload["project"])
        self.assertEqual(True, payload["summary"])
        self.assertNotIn("providers", payload["projects"][0])
        self.assertIn("review_queues", payload["projects"][0])

    def test_memory_route_json_uses_route_decision_contract(self):
        code, output = self.run_cli(
            "memory",
            "route",
            "we decided to keep promotion inbox",
            "--project-hint",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["recommended_layer"])
        self.assertEqual(["graphify"], payload["secondary_layers"])
        self.assertEqual(["durable_write_requires_review"], payload["risk_flags"])
        self.assertEqual("reefiki", payload["target_project"])

    def test_memory_route_text_stays_backward_readable(self):
        code, output = self.run_cli(
            "memory",
            "route",
            "where is auth module",
            "--project-hint",
            "reefiki",
        )

        self.assertEqual(0, code)
        self.assertIn("layer: graphify", output)
        self.assertIn("reason: structure/navigation intent", output)
        self.assertIn("project_hint: reefiki", output)

    def test_memory_route_sends_roadmap_governance_to_reefiki(self):
        code, output = self.run_cli(
            "memory",
            "route",
            "continue REEFIKI roadmap development",
            "--project-hint",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["recommended_layer"])
        self.assertEqual(["memoir"], payload["secondary_layers"])
        self.assertEqual("project roadmap/governance intent", payload["reason"])
        self.assertEqual("reefiki", payload["target_project"])

    def test_memory_explain_json_reports_route_policy_and_source_decisions(self):
        code, output = self.run_cli(
            "memory",
            "explain",
            "where is the memory status implementation?",
            "--project",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("where is the memory status implementation?", payload["query"])
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual("graphify", payload["route"]["recommended_layer"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        graphify = next(
            item for item in payload["source_decisions"] if item["layer"] == "graphify"
        )
        self.assertEqual("unavailable", graphify["status"])
        self.assertEqual("missing graphify report", graphify["reason"])
        self.assertIn("graphify", payload["excluded_sources"])

    def test_memory_explain_roadmap_keeps_reefiki_selected(self):
        code, output = self.run_cli(
            "memory",
            "explain",
            "continue REEFIKI roadmap development",
            "--project",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["route"]["recommended_layer"])
        reefiki_source = next(
            item for item in payload["source_decisions"] if item["layer"] == "reefiki"
        )
        memoir_source = next(
            item for item in payload["source_decisions"] if item["layer"] == "memoir"
        )
        self.assertEqual("selected", reefiki_source["status"])
        self.assertEqual("secondary", memoir_source["status"])
        self.assertEqual("run memory lookup --project reefiki --layer reefiki", payload["next_action"])

    def test_memory_explain_text_stays_readable(self):
        code, output = self.run_cli(
            "memory",
            "explain",
            "we decided to keep promotion inbox",
            "--project",
            "reefiki",
        )

        self.assertEqual(0, code)
        self.assertIn("route: reefiki", output)
        self.assertIn("policy: pass", output)
        self.assertIn("sources:", output)

    def test_memory_preflight_json_reports_blocking_reasons(self):
        code, output = self.run_cli(
            "memory",
            "preflight",
            "--project-name",
            "reefiki",
            "--visibility",
            "public",
            "--content",
            "api_" + "key=secret-value",
            "--path",
            "projects/metrica/wiki/index.md",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertIn("forbidden_scope:projects/metrica", payload["blocking_reasons"])
        self.assertIn("secret_like_content", payload["blocking_reasons"])

    def test_secret_scan_cli_blocks_secret_like_file_content(self):
        target = self.root / "notes.md"
        target.write_text("api_" + "key=secret-value\n", encoding="utf-8")

        code, output = self.run_cli(
            "secret-scan",
            "notes.md",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("secret_like_content", payload["reason"])
        self.assertEqual(["notes.md"], payload["blocking_paths"])

    def test_memory_lookup_blocks_forbidden_project_before_provider_reads(self):
        metrica = self.root / "projects" / "metrica"
        (metrica / "wiki").mkdir(parents=True)

        code, output = self.run_cli(
            "memory",
            "lookup",
            "sync",
            "--project",
            "metrica",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["policy"]["outcome"])
        self.assertIn("forbidden_scope:projects/metrica", payload["policy"]["blocking_reasons"])
        self.assertEqual(
            "global memory lookup keeps private project scopes isolated; "
            "use project-local search/query instead: "
            "python scripts/reefiki.py --project projects/metrica search \"<query>\" "
            "--limit 5 --format json",
            payload["next_action"],
        )

    def test_memory_lookup_blocks_forbidden_project_case_insensitively(self):
        metrica = self.root / "projects" / "metrica"
        (metrica / "wiki").mkdir(parents=True)

        code, output = self.run_cli(
            "memory",
            "lookup",
            "sync",
            "--project",
            "Metrica",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["policy"]["outcome"])
        self.assertIn("forbidden_scope:projects/metrica", payload["policy"]["blocking_reasons"])
        self.assertIn("projects/metrica", payload["next_action"])

    def test_memory_lookup_allowed_project_keeps_existing_json_shape(self):
        code, output = self.run_cli(
            "memory",
            "lookup",
            "control plane",
            "--project",
            "reefiki",
            "--layer",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("control plane", payload["query"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertIn("reefiki", payload)

    def test_memory_promote_json_writes_review_draft_with_policy_trace(self):
        code, output = self.run_cli(
            "memory",
            "promote",
            "We decided to keep promotion inbox before durable wiki writes because auto-promotion is risky.",
            "--target-project",
            "reefiki",
            "--memory-id",
            "memo-99",
            "--confidence",
            "0.8",
            "--write-draft",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertEqual("promote", payload["verdict"])
        self.assertEqual("CREATE", payload["promotion_candidate"]["suggested_action"])
        self.assertEqual("needs_verification", payload["promotion_candidate"]["review_state"])
        self.assertEqual("promote", payload["trace"]["operation"])
        self.assertEqual("needs_review", payload["trace"]["safety_outcome"])
        self.assertIn("draft_path", payload)
        self.assertTrue((self.project / payload["draft_path"]).exists())

    def test_memory_promote_blocks_forbidden_target_before_draft_write(self):
        metrica = self.root / "projects" / "metrica"
        (metrica / "wiki").mkdir(parents=True)

        code, output = self.run_cli(
            "memory",
            "promote",
            "We decided to promote this into a forbidden project scope.",
            "--target-project",
            "metrica",
            "--write-draft",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["policy"]["outcome"])
        self.assertIn("forbidden_scope:projects/metrica", payload["policy"]["blocking_reasons"])
        self.assertNotIn("draft_path", payload)

    def test_memory_promotion_inbox_lists_review_drafts(self):
        code, output = self.run_cli(
            "memory",
            "promote",
            "We decided to keep promotion inbox before durable wiki writes because auto-promotion is risky.",
            "--target-project",
            "reefiki",
            "--memory-id",
            "memo-100",
            "--confidence",
            "0.8",
            "--write-draft",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        draft_payload = json.loads(output)

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertEqual(1, payload["total"])
        draft = payload["drafts"][0]
        self.assertEqual(draft_payload["draft_path"], draft["path"])
        self.assertEqual("promote", draft["verdict"])
        self.assertEqual("decision", draft["target_type"])
        self.assertEqual("needs_verification", draft["review_state"])
        self.assertEqual("memo-100", draft["memory_id"])

    def test_memory_promotion_inbox_shows_single_draft(self):
        code, output = self.run_cli(
            "memory",
            "promote",
            "We decided to keep promotion inbox before durable wiki writes because auto-promotion is risky.",
            "--target-project",
            "reefiki",
            "--memory-id",
            "memo-101",
            "--confidence",
            "0.8",
            "--write-draft",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        draft_path = json.loads(output)["draft_path"]

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--show",
            draft_path,
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(draft_path, payload["draft"]["path"])
        self.assertIn("promotion inbox", payload["draft"]["summary"])
        self.assertIn("Review this draft", payload["draft"]["body"])

    def test_memory_promotion_inbox_applies_draft(self):
        code, output = self.run_cli(
            "memory",
            "promote",
            "We decided to keep promotion inbox apply flow explicit because durable writes need review.",
            "--target-project",
            "reefiki",
            "--memory-id",
            "memo-102",
            "--confidence",
            "0.8",
            "--write-draft",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        draft_path = json.loads(output)["draft_path"]

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--apply",
            draft_path,
            "--yes",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("applied", payload["action"])
        self.assertTrue((self.project / payload["page_path"]).exists())
        draft_text = (self.project / draft_path).read_text(encoding="utf-8")
        self.assertIn("Review state: applied", draft_text)

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        self.assertEqual(0, json.loads(output)["total"])

    def test_memory_promotion_inbox_rejects_draft(self):
        code, output = self.run_cli(
            "memory",
            "promote",
            "We decided to keep promotion inbox reject flow explicit because not every draft should become durable.",
            "--target-project",
            "reefiki",
            "--memory-id",
            "memo-103",
            "--confidence",
            "0.8",
            "--write-draft",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        draft_path = json.loads(output)["draft_path"]

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--reject",
            draft_path,
            "--reason",
            "duplicate working note",
            "--yes",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("rejected", payload["action"])
        self.assertEqual(draft_path, payload["draft_path"])
        draft_text = (self.project / draft_path).read_text(encoding="utf-8")
        self.assertIn("Review state: rejected", draft_text)
        self.assertIn("duplicate working note", draft_text)

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        self.assertEqual(0, json.loads(output)["total"])

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--all",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        self.assertEqual(1, json.loads(output)["total"])

    def test_memory_promotion_inbox_prunes_closed_drafts(self):
        code, output = self.run_cli(
            "memory",
            "promote",
            "We decided to prune closed promotion drafts because active review queues should stay clean.",
            "--target-project",
            "reefiki",
            "--memory-id",
            "memo-104",
            "--confidence",
            "0.8",
            "--write-draft",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        draft_path = json.loads(output)["draft_path"]

        code, _ = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--reject",
            draft_path,
            "--reason",
            "test closed queue",
            "--yes",
        )
        self.assertEqual(0, code)

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--prune-closed",
            "--yes",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(1, payload["moved"])
        self.assertFalse((self.project / draft_path).exists())
        archived_path = self.project / payload["drafts"][0]["to"]
        self.assertTrue(archived_path.exists())
        self.assertTrue(str(archived_path.relative_to(self.project)).startswith("plans\\closed") or str(archived_path.relative_to(self.project)).startswith("plans/closed"))

        code, output = self.run_cli(
            "memory",
            "promotion-inbox",
            "--project",
            "reefiki",
            "--all",
            "--format",
            "json",
        )
        self.assertEqual(0, code)
        archived = json.loads(output)
        self.assertEqual(1, archived["total"])
        self.assertEqual(payload["drafts"][0]["to"], archived["drafts"][0]["path"])

    def test_memory_golden_runs_lookup_and_promote_cases(self):
        (self.project / "wiki" / "decisions").mkdir(parents=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "decisions" / "routing-contract.md").write_text(
            """---
id: routing-contract
type: decision
title: "Routing contract"
tags: [memory]
useful_when:
  - "route memory"
date_added: 2026-05-20
use_count: 0
last_used: null
---
Use REEFIKI for durable routing and memory governance.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
            """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [reefiki-2]
useful_when:
  - "build memory pack"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
            encoding="utf-8",
        )
        (self.project / "golden-queries.yml").write_text(
            """version: 1
project: reefiki
queries:
  - id: lookup-routing-contract
    kind: lookup
    query: routing contract
    layer: reefiki
    expect_ids: [routing-contract]
  - id: promote-durable-decision
    kind: promote
    content: We decided to keep promotion inbox before durable wiki writes because auto-promotion is risky.
    expect_verdict: promote
    expect_target_type: decision
  - id: pack-reefiki-2-handoff
    kind: pack
    task: REEFIKI 2 memory pack
    expect_ids: [reefiki-2-control-plane-spec]
    expect_route_layer: reefiki
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "golden",
            "--project",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual(3, payload["total"])
        self.assertEqual(3, payload["passed"])
        self.assertEqual(0, payload["failed"])
        self.assertEqual(
            ["lookup-routing-contract", "promote-durable-decision", "pack-reefiki-2-handoff"],
            [case["id"] for case in payload["cases"]],
        )

    def test_memory_golden_lookup_uses_project_local_search_for_private_project(self):
        metrica = self.root / "projects" / "metrica"
        (metrica / "wiki" / "decisions").mkdir(parents=True)
        (metrica / "wiki" / "decisions" / "sync-contract.md").write_text(
            """---
id: sync-contract
type: decision
title: "Metrica sync contract"
tags: [sync, metrica]
useful_when:
  - "check metrica sync"
date_added: 2026-06-08
use_count: 0
last_used: null
---
Local cache online sync uses an explicit conflict modal.
""",
            encoding="utf-8",
        )
        (metrica / "golden-queries.yml").write_text(
            """version: 1
project: metrica
queries:
  - id: lookup-sync-contract
    kind: lookup
    query: sync conflict modal
    layer: reefiki
    expect_ids: [sync-contract]
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "lookup",
            "--project",
            "metrica",
            "sync conflict modal",
            "--format",
            "json",
        )
        self.assertEqual(1, code)
        blocked = json.loads(output)
        self.assertIn("forbidden_scope:projects/metrica", blocked["policy"]["blocking_reasons"])
        self.assertIn('projects/metrica search "<query>"', blocked["next_action"])

        code, output = self.run_cli(
            "memory",
            "golden",
            "--project",
            "metrica",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("metrica", payload["project"])
        self.assertEqual(1, payload["passed"])
        self.assertEqual(0, payload["failed"])
        self.assertEqual(["sync-contract"], payload["cases"][0]["details"]["actual_ids"])

    def test_worktree_status_recommends_keep_for_main_and_delete_for_merged_task_worktree(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        done = self.root / "done-worktree"
        subprocess.run(["git", "worktree", "add", "-b", "codex/done", str(done), "main"], cwd=repo, check=True, capture_output=True, text=True)

        code, output = self.run_repo_cli(repo, "worktree-status", "--base", "main", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        by_branch = {item["branch"]: item for item in payload["worktrees"]}
        self.assertEqual("keep", by_branch["main"]["recommendation"])
        self.assertEqual("delete", by_branch["codex/done"]["recommendation"])
        self.assertEqual([], by_branch["codex/done"]["dirty_paths"])
        self.assertTrue(by_branch["codex/done"]["ancestor_of_base"])

    def test_worktree_status_reviews_unmerged_and_blocks_dirty_worktrees(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        review = self.root / "review-worktree"
        dirty = self.root / "dirty-worktree"
        subprocess.run(["git", "worktree", "add", "-b", "codex/review", str(review), "main"], cwd=repo, check=True, capture_output=True, text=True)
        (review / "feature.txt").write_text("feature\n", encoding="utf-8")
        subprocess.run(["git", "add", "feature.txt"], cwd=review, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "feature"], cwd=review, check=True, capture_output=True, text=True)
        subprocess.run(["git", "worktree", "add", "-b", "codex/dirty", str(dirty), "main"], cwd=repo, check=True, capture_output=True, text=True)
        (dirty / "dirty.txt").write_text("dirty\n", encoding="utf-8")

        code, output = self.run_repo_cli(repo, "worktree-status", "--base", "main", "--format", "json")

        self.assertEqual(0, code)
        payload = json.loads(output)
        by_branch = {item["branch"]: item for item in payload["worktrees"]}
        self.assertEqual("review", by_branch["codex/review"]["recommendation"])
        self.assertEqual(1, by_branch["codex/review"]["ahead"])
        self.assertEqual(0, by_branch["codex/review"]["behind"])
        self.assertFalse(by_branch["codex/review"]["ancestor_of_base"])
        self.assertEqual("block", by_branch["codex/dirty"]["recommendation"])
        self.assertEqual(["dirty.txt"], by_branch["codex/dirty"]["dirty_paths"])

    def test_worktree_status_treats_dirty_shared_checkout_outside_scope_as_excluded_context(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        hermes_note = repo / "projects" / "Hermes" / "wiki" / "notes.md"
        hermes_note.parent.mkdir(parents=True)
        hermes_note.write_text("parallel agent work\n", encoding="utf-8")

        code, output = self.run_repo_cli(
            repo,
            "worktree-status",
            "--base",
            "main",
            "--scope",
            "projects/reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertTrue(payload["shared_checkout_dirty"])
        self.assertFalse(payload["scope_conflicts"])
        self.assertEqual(["projects/Hermes/wiki/notes.md"], payload["excluded_dirty_paths"])
        self.assertEqual("start_fresh_worktree", payload["recommendation"])
        main = next(item for item in payload["worktrees"] if item["branch"] == "main")
        self.assertEqual(["projects/Hermes/wiki/notes.md"], main["dirty_paths_by_scope"]["projects/Hermes"])
        self.assertEqual("start_fresh_worktree", main["scope_recommendation"])

    def test_worktree_status_blocks_dirty_shared_checkout_inside_scope(self):
        repo = self.root / "repo"
        self.init_synthetic_git_repo(repo)
        reefiki_note = repo / "projects" / "reefiki" / "wiki" / "notes.md"
        reefiki_note.parent.mkdir(parents=True)
        reefiki_note.write_text("target scope work\n", encoding="utf-8")

        code, output = self.run_repo_cli(
            repo,
            "worktree-status",
            "--base",
            "main",
            "--scope",
            "projects/reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertTrue(payload["shared_checkout_dirty"])
        self.assertEqual(["projects/reefiki/wiki/notes.md"], payload["scope_conflicts"])
        self.assertEqual([], payload["excluded_dirty_paths"])
        self.assertEqual("blocked_by_dirty_target_scope", payload["recommendation"])
        main = next(item for item in payload["worktrees"] if item["branch"] == "main")
        self.assertEqual("blocked_by_dirty_target_scope", main["scope_recommendation"])

    def test_memory_diff_reports_worktree_wiki_changes(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.project / "wiki" / "decisions").mkdir(parents=True)
        page = self.project / "wiki" / "decisions" / "routing-contract.md"
        page.write_text(
            """---
id: routing-contract
type: decision
title: "Routing contract"
tags: [memory]
useful_when:
  - "route memory"
date_added: 2026-05-20
use_count: 0
last_used: null
---
Use REEFIKI for durable routing.
""",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        page.write_text(page.read_text(encoding="utf-8") + "\nMemory governance changed.\n", encoding="utf-8")

        code, output = self.run_cli(
            "memory",
            "diff",
            "--project",
            "reefiki",
            "--from",
            "HEAD",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual("HEAD", payload["from"])
        self.assertEqual("WORKTREE", payload["to"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertEqual(1, payload["total"])
        self.assertEqual({"M": 1}, payload["counts"])
        self.assertEqual("wiki/decisions/routing-contract.md", payload["files"][0]["path"])

    def test_memory_diff_since_date_uses_first_matching_commit_parent(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.project / "wiki" / "decisions").mkdir(parents=True)
        page = self.project / "wiki" / "decisions" / "routing-contract.md"
        page.write_text(
            """---
id: routing-contract
type: decision
title: "Routing contract"
tags: [memory]
useful_when:
  - "route memory"
date_added: 2026-05-20
use_count: 0
last_used: null
---
Use REEFIKI for durable routing.
""",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "base"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_DATE": "2026-05-20T10:00:00+00:00",
                "GIT_COMMITTER_DATE": "2026-05-20T10:00:00+00:00",
            },
        )
        page.write_text(page.read_text(encoding="utf-8") + "\nMemory governance changed.\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "update routing"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_DATE": "2026-05-22T10:00:00+00:00",
                "GIT_COMMITTER_DATE": "2026-05-22T10:00:00+00:00",
            },
        )

        code, output = self.run_cli(
            "memory",
            "diff",
            "--project",
            "reefiki",
            "--since-date",
            "2026-05-21",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("2026-05-21", payload["since_date"])
        self.assertEqual("WORKTREE", payload["to"])
        self.assertEqual(1, payload["total"])
        self.assertEqual("wiki/decisions/routing-contract.md", payload["files"][0]["path"])

    def test_guard_staged_allows_only_target_project_wiki_paths(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        page = self.root / "projects" / "metrica" / "wiki" / "skills" / "metrica-skill.md"
        page.parent.mkdir(parents=True)
        page.write_text("skill\n", encoding="utf-8")
        subprocess.run(["git", "add", "projects/metrica/wiki/skills/metrica-skill.md"], cwd=self.root, check=True)

        code, output = self.run_cli(
            "guard-staged",
            "--target-project",
            "metrica",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual(["projects/metrica/wiki/skills/metrica-skill.md"], payload["staged_paths"])
        self.assertEqual([], payload["blocking_paths"])

    def test_guard_staged_blocks_cross_project_and_non_wiki_paths(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        allowed = self.root / "projects" / "metrica" / "wiki" / "skills" / "metrica-skill.md"
        blocked = self.root / "projects" / "reefiki" / "wiki" / "skills" / "reefiki-skill.md"
        non_wiki = self.root / "projects" / "metrica" / "notes.md"
        allowed.parent.mkdir(parents=True)
        blocked.parent.mkdir(parents=True)
        allowed.write_text("allowed\n", encoding="utf-8")
        blocked.write_text("blocked\n", encoding="utf-8")
        non_wiki.write_text("blocked\n", encoding="utf-8")
        subprocess.run(
            [
                "git",
                "add",
                "projects/metrica/wiki/skills/metrica-skill.md",
                "projects/reefiki/wiki/skills/reefiki-skill.md",
                "projects/metrica/notes.md",
            ],
            cwd=self.root,
            check=True,
        )

        code, output = self.run_cli(
            "guard-staged",
            "--target-project",
            "metrica",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual(
            ["projects/metrica/notes.md", "projects/reefiki/wiki/skills/reefiki-skill.md"],
            payload["blocking_paths"],
        )

    def test_guard_staged_allows_target_project_with_spaces(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        page = self.root / "projects" / "Security Guidance" / "wiki" / "skills" / "guard.md"
        page.parent.mkdir(parents=True)
        page.write_text("guard\n", encoding="utf-8")
        subprocess.run(["git", "add", "projects/Security Guidance/wiki/skills/guard.md"], cwd=self.root, check=True)

        code, output = self.run_cli(
            "guard-staged",
            "--target-project",
            "Security Guidance",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual(
            ["projects/Security Guidance/wiki/skills/guard.md"],
            payload["staged_paths"],
        )
        self.assertEqual([], payload["blocking_paths"])

    def test_repo_path_scope_helper_enforces_segment_boundaries(self):
        self.assertTrue(
            reefiki.repo_path_in_scope(
                "projects/Security Guidance/wiki/skills/guard.md",
                "projects/Security Guidance/wiki",
            )
        )
        self.assertTrue(
            reefiki.repo_path_in_scope(
                "projects/metrica/wiki/../wiki/skills/metrica.md",
                "projects/metrica/wiki",
            )
        )
        self.assertFalse(
            reefiki.repo_path_in_scope(
                "projects/metrica/wiki2/skills/metrica.md",
                "projects/metrica/wiki",
            )
        )
        self.assertFalse(
            reefiki.repo_path_in_scope(
                "projects/metrica/wiki",
                "projects/metrica/wiki/skills",
            )
        )

    def test_harvest_commit_uses_isolated_index_and_leaves_other_staged_paths(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        initial = self.root / "README.md"
        initial.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        metrica_page = self.root / "projects" / "metrica" / "wiki" / "skills" / "metrica-harvest.md"
        hermes_page = self.root / "projects" / "Hermes" / "wiki" / "synthesis" / "hermes-draft.md"
        metrica_page.parent.mkdir(parents=True)
        hermes_page.parent.mkdir(parents=True)
        metrica_page.write_text("metrica harvest\n", encoding="utf-8")
        hermes_page.write_text("hermes draft\n", encoding="utf-8")
        subprocess.run(["git", "add", "projects/Hermes/wiki/synthesis/hermes-draft.md"], cwd=self.root, check=True)

        code, output = self.run_cli(
            "harvest-commit",
            "--target-project",
            "metrica",
            "--path",
            "projects/metrica/wiki/skills/metrica-harvest.md",
            "--message",
            "Harvest Metrica isolated",
            "--no-validate",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual(["projects/metrica/wiki/skills/metrica-harvest.md"], payload["committed_paths"])
        self.assertIn("projects/Hermes/wiki/synthesis/hermes-draft.md", payload["preexisting_staged_paths"])
        show = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(["projects/metrica/wiki/skills/metrica-harvest.md"], show.stdout.split())
        cached = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(["projects/Hermes/wiki/synthesis/hermes-draft.md"], cached.stdout.split())
        status = subprocess.run(
            ["git", "status", "--short", "--", "projects/metrica/wiki/skills/metrica-harvest.md"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual("", status.stdout)

    def test_harvest_commit_blocks_paths_outside_target_wiki(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        notes = self.root / "projects" / "metrica" / "notes.md"
        notes.parent.mkdir(parents=True)
        notes.write_text("not wiki\n", encoding="utf-8")

        code, output = self.run_cli(
            "harvest-commit",
            "--target-project",
            "metrica",
            "--path",
            "projects/metrica/notes.md",
            "--message",
            "Bad harvest",
            "--no-validate",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("path_outside_target_wiki", payload["reason"])
        self.assertEqual(["projects/metrica/notes.md"], payload["blocking_paths"])

    def test_harvest_commit_allows_target_project_with_spaces(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        initial = self.root / "README.md"
        initial.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        page = self.root / "projects" / "Security Guidance" / "wiki" / "skills" / "rename-proof.md"
        page.parent.mkdir(parents=True)
        page.write_text(
            "---\n"
            "id: rename-proof\n"
            "type: skill\n"
            "title: Rename proof\n"
            "tags: [security-guidance]\n"
            "useful_when:\n"
            "  - proving harvest handles project names with spaces\n"
            "---\n",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "harvest-commit",
            "--target-project",
            "Security Guidance",
            "--path",
            "projects/Security Guidance/wiki/skills/rename-proof.md",
            "--message",
            "Harvest spaced project",
            "--no-validate",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual(
            ["projects/Security Guidance/wiki/skills/rename-proof.md"],
            payload["committed_paths"],
        )

    def test_harvest_commit_blocks_secret_like_content(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        page = self.root / "projects" / "reefiki" / "wiki" / "synthesis" / "secret.md"
        page.parent.mkdir(parents=True)
        page.write_text("api_" + "key=secret-value\n", encoding="utf-8")

        code, output = self.run_cli(
            "harvest-commit",
            "--target-project",
            "reefiki",
            "--path",
            "projects/reefiki/wiki/synthesis/secret.md",
            "--message",
            "Harvest secret",
            "--no-validate",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("secret_like_content", payload["reason"])
        self.assertEqual(["projects/reefiki/wiki/synthesis/secret.md"], payload["blocking_paths"])

    def test_publish_task_dry_run_classifies_private_only_branch_and_cleanup(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("Hermes\nmetrica\nreefiki\nSuno\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", "-b", "codex/hermes-harvest"], cwd=self.root, check=True, capture_output=True, text=True)
        page = self.root / "projects" / "Hermes" / "wiki" / "synthesis" / "harvest.md"
        page.parent.mkdir(parents=True)
        page.write_text("private\n", encoding="utf-8")
        subprocess.run(["git", "add", "projects/Hermes/wiki/synthesis/harvest.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "harvest"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--private-remote",
            "origin",
            "--public-remote",
            "public",
            "--cleanup",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual("private-only", payload["diff_class"])
        self.assertEqual(["projects/Hermes/wiki/synthesis/harvest.md"], payload["changed_paths"])
        self.assertIn("push_task_branch", payload["actions"])
        self.assertIn("push_private_main", payload["actions"])
        self.assertNotIn("push_public_snapshot", payload["actions"])
        self.assertIn("cleanup_task_worktree", payload["post_merge_actions"])

    def test_publish_task_dry_run_classifies_mixed_branch_for_public_snapshot(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("Hermes\nmetrica\nreefiki\nSuno\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", "-b", "codex/mixed"], cwd=self.root, check=True, capture_output=True, text=True)
        readme.write_text("base\npublic\n", encoding="utf-8")
        page = self.root / "projects" / "Hermes" / "wiki" / "synthesis" / "harvest.md"
        page.parent.mkdir(parents=True)
        page.write_text("private\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "projects/Hermes/wiki/synthesis/harvest.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "mixed"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--private-remote",
            "origin",
            "--public-remote",
            "public",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("mixed", payload["diff_class"])
        self.assertIn("push_public_snapshot", payload["actions"])
        self.assertEqual(["projects/Hermes"], payload["public_snapshot_exclusions"])

    def test_publish_task_dry_run_blocks_dirty_worktree(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        readme.write_text("dirty\n", encoding="utf-8")

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("dirty_worktree", payload["reason"])
        self.assertEqual(["README.md"], payload["dirty_paths"])

    def test_publish_task_blocks_missing_private_project_inventory(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", "-b", "codex/public-change"], cwd=self.root, check=True, capture_output=True, text=True)
        readme.write_text("base\npublic\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "public"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("private_project_inventory_missing", payload["reason"])

    def test_publish_task_blocks_empty_private_project_inventory(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("# intentionally empty\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("private_project_inventory_empty", payload["reason"])

    def test_publish_task_blocks_incomplete_private_project_inventory(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("Hermes\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("private_project_inventory_incomplete", payload["reason"])
        self.assertEqual(["reefiki"], payload["missing_private_projects"])

    def test_publish_task_blocks_secret_like_changed_content(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("reefiki\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", "-b", "codex/secret"], cwd=self.root, check=True, capture_output=True, text=True)
        readme.write_text("api_" + "key=secret-value\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "secret"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("secret_like_content", payload["reason"])
        self.assertEqual(["README.md"], payload["blocking_paths"])

    def test_publish_task_blocks_secret_like_public_snapshot_content_on_resume(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        public_remote = self.root.parent / "public.git"
        subprocess.run(["git", "init", "--bare", str(public_remote)], check=True, capture_output=True, text=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("reefiki\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("api_" + "key=secret-value\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--public-remote",
            str(public_remote),
            "--public-snapshot",
            "--apply",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("secret_like_content", payload["reason"])
        self.assertEqual(["README.md"], payload["blocking_paths"])
        public_main = subprocess.run(
            ["git", "show-ref", "--verify", "refs/heads/main"],
            cwd=public_remote,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, public_main.returncode)

    def test_publish_task_dry_run_blocks_secret_like_public_snapshot_content(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        public_remote = self.root.parent / "public.git"
        subprocess.run(["git", "init", "--bare", str(public_remote)], check=True, capture_output=True, text=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("reefiki\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("api_" + "key=secret-value\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--public-remote",
            str(public_remote),
            "--public-snapshot",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("secret_like_content", payload["reason"])
        self.assertEqual(["README.md"], payload["blocking_paths"])
        public_main = subprocess.run(
            ["git", "show-ref", "--verify", "refs/heads/main"],
            cwd=public_remote,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, public_main.returncode)

    def test_publish_task_can_resume_public_snapshot_after_private_push(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        config = self.root / "scripts" / "public-snapshot.private-projects.txt"
        config.parent.mkdir(parents=True)
        config.write_text("Hermes\nmetrica\nreefiki\nSuno\n", encoding="utf-8")
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "publish-task",
            "--base",
            "main",
            "--public-snapshot",
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("empty", payload["diff_class"])
        self.assertEqual(["push_public_snapshot"], payload["actions"])
        self.assertTrue(payload["public_snapshot_requested"])

    def test_cleanup_worktree_dry_run_blocks_unmerged_branch(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        side = self.root.parent / "side-worktree"
        subprocess.run(["git", "worktree", "add", "-b", "codex/side", str(side), "main"], cwd=self.root, check=True, capture_output=True, text=True)
        try:
            side_readme = side / "README.md"
            side_readme.write_text("base\nside\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=side, check=True)
            subprocess.run(["git", "commit", "-m", "side"], cwd=side, check=True, capture_output=True, text=True)

            code, output = self.run_cli(
                "cleanup-worktree",
                "--worktree",
                str(side),
                "--base",
                "main",
                "--dry-run",
                "--format",
                "json",
            )

            self.assertEqual(1, code)
            payload = json.loads(output)
            self.assertEqual("block", payload["outcome"])
            self.assertEqual("unmerged_worktree_head", payload["reason"])
            self.assertTrue(side.exists())
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(side)], cwd=self.root, check=False, capture_output=True, text=True)

    def test_cleanup_worktree_semantic_superseded_requires_real_evidence(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        side = self.root.parent / "side-worktree"
        subprocess.run(["git", "worktree", "add", "-b", "codex/side", str(side), "main"], cwd=self.root, check=True, capture_output=True, text=True)
        try:
            (side / "README.md").write_text("base\nside\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=side, check=True)
            subprocess.run(["git", "commit", "-m", "side"], cwd=side, check=True, capture_output=True, text=True)

            code, output = self.run_cli(
                "cleanup-worktree",
                "--worktree",
                str(side),
                "--base",
                "main",
                "--semantic-superseded",
                "too short",
                "--dry-run",
                "--format",
                "json",
            )

            self.assertEqual(1, code)
            payload = json.loads(output)
            self.assertEqual("block", payload["outcome"])
            self.assertEqual("semantic_evidence_too_short", payload["reason"])
            self.assertTrue(side.exists())
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(side)], cwd=self.root, check=False, capture_output=True, text=True)

    def test_cleanup_worktree_semantic_superseded_removes_unmerged_branch_with_explicit_evidence(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        side = self.root.parent / "side-worktree"
        subprocess.run(["git", "worktree", "add", "-b", "codex/side", str(side), "main"], cwd=self.root, check=True, capture_output=True, text=True)
        (side / "README.md").write_text("base\nside\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=side, check=True)
        subprocess.run(["git", "commit", "-m", "side"], cwd=side, check=True, capture_output=True, text=True)
        evidence = "superseded by commit abc123 after manual semantic diff review"

        code, output = self.run_cli(
            "cleanup-worktree",
            "--worktree",
            str(side),
            "--base",
            "main",
            "--semantic-superseded",
            evidence,
            "--dry-run",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertEqual(evidence, payload["semantic_superseded"])
        self.assertIn("semantic_superseded_cleanup", payload["actions"])
        self.assertTrue(side.exists())

        code, output = self.run_cli(
            "cleanup-worktree",
            "--worktree",
            str(side),
            "--base",
            "main",
            "--semantic-superseded",
            evidence,
            "--apply",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertTrue(payload["removed"])
        self.assertFalse(side.exists())
        branch = subprocess.run(["git", "branch", "--list", "codex/side"], cwd=self.root, check=True, capture_output=True, text=True)
        self.assertEqual("", branch.stdout.strip())

    def test_cleanup_worktree_deletes_branch_merged_to_base_even_when_launcher_checkout_is_behind(self):
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        old_main = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()
        readme.write_text("base\nnew main\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "new main"], cwd=self.root, check=True, capture_output=True, text=True)
        side = self.root.parent / "side-worktree"
        subprocess.run(["git", "worktree", "add", "-b", "codex/side", str(side), "main"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", "--detach", old_main], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "cleanup-worktree",
            "--worktree",
            str(side),
            "--base",
            "main",
            "--apply",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertTrue(payload["removed"])
        self.assertFalse(side.exists())
        branch = subprocess.run(["git", "branch", "--list", "codex/side"], cwd=self.root, check=True, capture_output=True, text=True)
        self.assertEqual("", branch.stdout.strip())

    def test_tool_trigger_recommends_understand_anything_only_for_visual_graph_need(self):
        code, output = self.run_cli(
            "tool-trigger",
            "Understand-Anything",
            "--signal",
            "need visual onboarding graph for a large unknown codebase",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("Understand-Anything", payload["tool"])
        self.assertEqual("sandbox-recommended", payload["outcome"])
        self.assertIn("isolated sandbox", payload["next_action"])
        self.assertIn("do_not_install_globally", payload["guards"])
        self.assertIn("no_auto_update_hooks", payload["guards"])

    def test_tool_trigger_keeps_understand_anything_in_watch_without_trigger(self):
        code, output = self.run_cli(
            "tool-trigger",
            "Understand-Anything",
            "--signal",
            "normal REEFIKI query and harvest workflow",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("watch", payload["outcome"])
        self.assertEqual("keep documented as candidate; do not run sandbox smoke yet", payload["next_action"])

    def test_tool_trigger_keeps_ecc_reference_only(self):
        code, output = self.run_cli(
            "tool-trigger",
            "ECC",
            "--signal",
            "need readiness gates and external tool security checklist",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("ECC", payload["tool"])
        self.assertEqual("reference-only", payload["outcome"])
        self.assertIn("borrow_patterns_only", payload["guards"])
        self.assertIn("readiness snapshots", payload["next_action"])

    def test_memory_pack_builds_policy_checked_handoff_bundle(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "skills").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
            """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [reefiki-2]
useful_when:
  - "build memory pack"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "skills" / "global-memory-orchestration-cli.md").write_text(
            """---
id: global-memory-orchestration-cli
type: skill
title: "Global memory orchestration CLI"
tags: [memory]
useful_when:
  - "build memory pack"
date_added: 2026-05-20
use_count: 0
last_used: null
---
Use memory status, lookup, golden, diff and pack.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "log.md").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "memory",
            "pack",
            "REEFIKI 2 memory pack",
            "--project",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("reefiki", payload["project"])
        self.assertEqual("REEFIKI 2 memory pack", payload["task"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertEqual("pass", payload["safety_outcome"])
        self.assertIn("task_route", payload)
        self.assertIn("assembly_trace", payload)
        self.assertEqual("pack", payload["task_route"]["operation"])
        self.assertEqual("reefiki", payload["assembly_trace"]["pack_scope"]["target_project"])
        self.assertEqual(["reefiki"], payload["assembly_trace"]["pack_scope"]["source_layers"])
        self.assertEqual("reefiki", payload["route_trace"]["route_decision"]["recommended_layer"])
        self.assertEqual(
            payload["task_route"]["route_decision"],
            payload["route_trace"]["route_decision"],
        )
        self.assertIn("projects/metrica", payload["exclusions"])
        self.assertGreaterEqual(len(payload["contents"]), 1)
        self.assertEqual("reefiki-2-control-plane-spec", payload["contents"][0]["id"])
        self.assertIn("global-memory-orchestration-cli", [item["id"] for item in payload["contents"]])
        self.assertIn("why_included", payload["contents"][0])
        self.assertEqual("critical REEFIKI 2 handoff context", payload["contents"][0]["why_included"])
        self.assertIn("diff", payload)
        self.assertIn("golden", payload)
        self.assertEqual("pass", payload["quality"]["outcome"])
        self.assertEqual([], payload["quality"]["missing_required_ids"])
        self.assertIn("reefiki-2-control-plane-spec", payload["quality"]["required_ids"])
        self.assertIn("global-memory-orchestration-cli", payload["quality"]["required_ids"])
        self.assertLessEqual(
            payload["quality"]["type_counts"]["synthesis"],
            payload["quality"]["max_items_by_type"]["synthesis"],
        )
        self.assertLessEqual(
            payload["quality"]["type_counts"]["skill"],
            payload["quality"]["max_items_by_type"]["skill"],
        )
        self.assertEqual([], payload["quality"]["violations"])
        orphan_queue = next(
            item for item in payload["open_queues"] if item["queue_type"] == "orphan_review"
        )
        self.assertGreaterEqual(orphan_queue["count"], 1)
        self.assertIn("items", orphan_queue)
        orphan_page_ids = [item["page_id"] for item in orphan_queue["items"]]
        self.assertIn("reefiki-2-control-plane-spec", orphan_page_ids)
        self.assertTrue(all("suggested_action" in item for item in orphan_queue["items"]))

    def test_memory_pack_markdown_includes_handoff_sections(self):
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
            """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [reefiki-2]
useful_when:
  - "build memory pack"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli("memory", "pack", "REEFIKI 2 memory pack", "--project", "reefiki")

        self.assertEqual(0, code)
        self.assertIn("# Memory Pack: REEFIKI 2 memory pack", output)
        self.assertIn("## Contents", output)
        self.assertIn("## Quality", output)
        self.assertIn("- outcome: pass", output)
        self.assertIn("- missing_required_ids: none", output)
        self.assertIn("## Golden", output)
        self.assertIn("## Diff", output)
        self.assertIn("## Open Queues", output)
        self.assertIn("orphan_review", output)
        self.assertIn("action:", output)
        self.assertIn("## Exclusions", output)

    def test_memory_pack_accepts_hyphenated_task_text(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "skills").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
            """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [reefiki-2]
useful_when:
  - "anti daily log guardrail"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "skills" / "global-memory-orchestration-cli.md").write_text(
            """---
id: global-memory-orchestration-cli
type: skill
title: "Global memory orchestration CLI"
tags: [memory]
useful_when:
  - "anti daily log guardrail"
date_added: 2026-05-20
use_count: 0
last_used: null
---
Use memory status, lookup, golden, diff and pack.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "log.md").write_text("", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "memory",
            "pack",
            "anti-daily-log guardrail",
            "--project",
            "reefiki",
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("anti-daily-log guardrail", payload["task"])
        self.assertEqual("pass", payload["policy"]["outcome"])
        self.assertGreaterEqual(len(payload["contents"]), 1)

    def test_memory_pack_strict_reports_lookup_storage_error_without_traceback(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "skills").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
            """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [reefiki-2]
useful_when:
  - "build memory pack"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "skills" / "global-memory-orchestration-cli.md").write_text(
            """---
id: global-memory-orchestration-cli
type: skill
title: "Global memory orchestration CLI"
tags: [memory]
useful_when:
  - "build memory pack"
date_added: 2026-05-20
use_count: 0
last_used: null
---
Use memory status, lookup, golden, diff and pack.
""",
            encoding="utf-8",
        )
        (self.project / "golden-queries.yml").write_text(
            """version: 1
project: reefiki
queries: []
""",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)
        original_lookup = reefiki.global_lookup
        original_golden = reefiki.run_golden_queries

        def failing_lookup(*_args, **_kwargs):
            raise sqlite3.OperationalError("unable to open database file")

        reefiki.global_lookup = failing_lookup
        reefiki.run_golden_queries = failing_lookup
        try:
            code, output = self.run_cli(
                "memory",
                "pack",
                "REEFIKI 2 memory pack",
                "--project",
                "reefiki",
                "--strict",
                "--format",
                "json",
            )
        finally:
            reefiki.global_lookup = original_lookup
            reefiki.run_golden_queries = original_golden

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("unable to open database file", payload["lookup_error"])
        self.assertEqual({"error": "unable to open database file"}, payload["golden"])
        self.assertEqual("fail", payload["strict"]["outcome"])
        self.assertIn("lookup:error", payload["strict"]["blocking_reasons"])
        self.assertIn("golden:error", payload["strict"]["blocking_reasons"])
        self.assertIn("reefiki-2-control-plane-spec", [item["id"] for item in payload["contents"]])

    def test_memory_pack_strict_fails_when_required_ids_do_not_fit_limit(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "skills").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
            """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [reefiki-2]
useful_when:
  - "build memory pack"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
            encoding="utf-8",
        )
        (self.project / "wiki" / "skills" / "global-memory-orchestration-cli.md").write_text(
            """---
id: global-memory-orchestration-cli
type: skill
title: "Global memory orchestration CLI"
tags: [memory]
useful_when:
  - "build memory pack"
date_added: 2026-05-20
use_count: 0
last_used: null
---
Use memory status, lookup, golden, diff and pack.
""",
            encoding="utf-8",
        )
        (self.project / "golden-queries.yml").write_text(
            """version: 1
project: reefiki
queries: []
""",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.root, check=True, capture_output=True, text=True)

        code, output = self.run_cli(
            "memory",
            "pack",
            "REEFIKI 2 memory pack",
            "--project",
            "reefiki",
            "--limit",
            "1",
            "--strict",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("fail", payload["strict"]["outcome"])
        self.assertIn("quality:missing_required_ids", payload["strict"]["blocking_reasons"])

    def test_memory_pack_strict_fails_on_missing_golden_or_diff_error(self):
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
            """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [reefiki-2]
useful_when:
  - "build memory pack"
sources: [current-session]
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
            encoding="utf-8",
        )

        code, output = self.run_cli(
            "memory",
            "pack",
            "REEFIKI 2 memory pack",
            "--project",
            "reefiki",
            "--strict",
            "--format",
            "json",
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("fail", payload["strict"]["outcome"])
        self.assertIn("golden:error", payload["strict"]["blocking_reasons"])
        self.assertIn("diff:error", payload["strict"]["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
