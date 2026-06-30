from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REEFIKI_PATH = ROOT / "scripts" / "reefiki.py"

import importlib.util


SPEC = importlib.util.spec_from_file_location("reefiki", REEFIKI_PATH)
reefiki = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reefiki)

pytestmark = [pytest.mark.agent_flow, pytest.mark.integration, pytest.mark.contract]


class AgentFlowE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, project: Path, *args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = reefiki.main(["--project", str(project), *args])
        return code, stdout.getvalue()

    def init_git_repo(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)

    def write_project_fixture(self, project: Path) -> None:
        (project / "wiki" / "concepts").mkdir(parents=True)
        for dirname in ["raw", "inbox", "seen"]:
            (project / dirname).mkdir(parents=True, exist_ok=True)
        (project / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (project / "_domain.md").write_text("agent flow fixture\n", encoding="utf-8")
        (project / "wiki" / "log.md").write_text("", encoding="utf-8")
        (project / "wiki" / "index.md").write_text(
            """# Index

Last updated: 2026-06-11
Total pages: 1

## Sources
## Entities
## Concepts

### agent-flow-fixture
- type: concept
- tags: [agent-flow]
- useful_when: ["checking fixture flow status output"]
- file: wiki/concepts/agent-flow-fixture.md
- date_added: 2026-06-11
- use_count: 0

## Synthesis
## Decisions
## Skills
""",
            encoding="utf-8",
        )
        (project / "wiki" / "concepts" / "agent-flow-fixture.md").write_text(
            """---
id: agent-flow-fixture
title: Agent Flow Fixture
type: concept
tags: [agent-flow]
useful_when:
  - "checking fixture flow status output"
date_added: 2026-06-11
use_count: 0
last_used:
---

# Agent Flow Fixture
""",
            encoding="utf-8",
        )

    def test_save_then_status_flow_uses_fixture_project_only(self) -> None:
        project = self.root / "projects" / "reefiki"
        self.write_project_fixture(project)

        code, output = self.run_cli(project, "save", "https://example.com/agent-flow?b=2&a=1")

        self.assertEqual(0, code)
        self.assertIn("Saved: inbox/example-com-agent-flow.md", output)
        self.assertEqual(
            "https://example.com/agent-flow?b=2&a=1\n",
            (project / "inbox" / "example-com-agent-flow.md").read_text(encoding="utf-8"),
        )
        self.assertIn("/save | https://example.com/agent-flow?b=2&a=1", (project / "wiki" / "log.md").read_text(encoding="utf-8"))
        self.assertEqual([], list((project / "raw").glob("*")))

        code, output = self.run_cli(project, "status")

        self.assertEqual(0, code)
        self.assertIn("Project: reefiki", output)
        self.assertIn("Inbox: 1 (example-com-agent-flow.md)", output)
        self.assertIn("Wiki: concept=1", output)

    def test_guard_staged_blocks_non_target_paths_before_harvest_commit(self) -> None:
        repo = self.root / "repo"
        self.init_git_repo(repo)
        allowed = repo / "projects" / "reefiki" / "wiki" / "skills" / "agent-flow.md"
        blocked = repo / "README.md"
        allowed.parent.mkdir(parents=True)
        allowed.write_text("agent flow\n", encoding="utf-8")
        blocked.write_text("public change\n", encoding="utf-8")
        subprocess.run(["git", "add", "projects/reefiki/wiki/skills/agent-flow.md", "README.md"], cwd=repo, check=True)

        code, output = self.run_cli(repo, "guard-staged", "--target-project", "reefiki", "--format", "json")

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual(["README.md"], payload["blocking_paths"])
        self.assertIn("projects/reefiki/wiki/skills/agent-flow.md", payload["staged_paths"])

    def test_publish_preflight_blocks_dirty_fixture_repo_without_mutating(self) -> None:
        repo = self.root / "repo"
        self.init_git_repo(repo)
        (repo / "scripts").mkdir()
        (repo / "projects" / "reefiki").mkdir(parents=True)
        (repo / "scripts" / "public-snapshot.private-projects.txt").write_text("reefiki\n", encoding="utf-8")
        (repo / "README.md").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md", "scripts/public-snapshot.private-projects.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True, text=True)
        (repo / "README.md").write_text("dirty\n", encoding="utf-8")

        code, output = self.run_cli(repo, "publish-task", "--base", "main", "--dry-run", "--cleanup", "--format", "json")

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual("dirty_worktree", payload["reason"])
        self.assertEqual(["README.md"], payload["dirty_paths"])

    def test_onboarding_fixture_flow_writes_demo_project_and_status_works(self) -> None:
        fixture_root = self.root / "onboarding"

        code, output = self.run_cli(
            ROOT,
            "onboarding",
            "--fixture-root",
            str(fixture_root),
            "--format",
            "json",
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("fixture", payload["mode"])
        project = fixture_root / "projects" / "reefiki-onboarding-demo"
        self.assertTrue((project / "raw" / "onboarding-source.md").exists())
        self.assertTrue((project / "wiki" / "concepts" / "onboarding-first-source.md").exists())
        self.assertTrue((project / "wiki" / "synthesis" / "onboarding-session-summary.md").exists())
        self.assertFalse((project / "inbox" / "onboarding-source.md").exists())

        code, output = self.run_cli(project, "status")

        self.assertEqual(0, code)
        self.assertIn("Project: reefiki-onboarding-demo", output)
        self.assertIn("Inbox: 0", output)
        self.assertIn("Wiki: concept=1, synthesis=1", output)

    def test_adapter_call_exposes_query_status_and_gated_save(self) -> None:
        project = self.root / "projects" / "reefiki"
        self.write_project_fixture(project)

        code, output = self.run_cli(project, "adapter-call", "reefiki_status", "--project", "reefiki")

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual("pass", payload["outcome"])
        self.assertTrue(payload["read_only"])
        self.assertIn("Project: reefiki", payload["status_text"])

        code, output = self.run_cli(
            project,
            "adapter-call",
            "reefiki_query",
            "--project",
            "reefiki",
            "--payload",
            '{"query":"agent flow","limit":2}',
        )

        self.assertEqual(0, code)
        payload = json.loads(output)
        self.assertEqual(1, payload["count"])
        self.assertEqual("agent-flow-fixture", payload["results"][0]["id"])

        code, output = self.run_cli(
            project,
            "adapter-call",
            "reefiki_save",
            "--project",
            "reefiki",
            "--payload",
            '{"source":"https://example.com/adapter"}',
        )

        self.assertEqual(1, code)
        payload = json.loads(output)
        self.assertEqual("block", payload["outcome"])
        self.assertEqual([], list((project / "inbox").glob("*.md")))

    def test_agent_command_contracts_cover_required_conformance_surfaces(self) -> None:
        command_dir = ROOT / "projects" / "_template" / ".claude" / "commands"
        expectations = {
            "save.md": ["python scripts/reefiki.py --project projects/<name> privacy", "dedup", "wiki/log.md", "inbox/"],
            "process.md": ["privacy", "raw/<source-id>.md", "seen/<source-slug>.md", "wiki/index.md"],
            "query.md": ["search", "--format json", "provenance", "use_count", "last_used"],
            "harvest.md": ["bounded harvest", "wiki-write", "harvest-commit"],
            "status.md": ["python scripts/reefiki.py --project projects/<name> status", "inbox/", "Health"],
        }
        for filename, required_fragments in expectations.items():
            text = (command_dir / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                for fragment in required_fragments:
                    self.assertIn(fragment, text)


if __name__ == "__main__":
    unittest.main()
