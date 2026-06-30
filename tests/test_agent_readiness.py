import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REEFIKI = ROOT / "scripts" / "reefiki.py"


class AgentReadinessTests(unittest.TestCase):
    def run_cli(self, *args: str) -> tuple[int, str, str]:
        completed = subprocess.run(
            [sys.executable, str(REEFIKI), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return completed.returncode, completed.stdout, completed.stderr

    def git(self, repo: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)

    def init_git(self, repo: Path) -> None:
        self.git(repo, "init", "-b", "main")

    def snapshot_paths(self, root: Path) -> set[str]:
        return {path.relative_to(root).as_posix() for path in root.rglob("*")}

    def payload_for(self, repo: Path) -> dict:
        code, stdout, stderr = self.run_cli("agent-readiness", "--repo", str(repo), "--format", "json")
        self.assertEqual(0, code, stderr)
        return json.loads(stdout)

    def test_agent_readiness_json_works_on_non_git_frontend_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "app"
            (repo / "src" / "app").mkdir(parents=True)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            before = self.snapshot_paths(repo)

            payload = self.payload_for(repo)

            self.assertEqual("agent-readiness.v1", payload["schema_version"])
            self.assertFalse(payload["repo"]["is_git"])
            self.assertIn("frontend", payload["summary"]["repo_types"])
            self.assertIn("skill.browser-runtime-smoke-gate", [item["id"] for item in payload["recommendations"]["skills"]])
            for block_items in payload["recommendations"].values():
                for item in block_items:
                    for key in ["reason", "evidence", "severity", "confidence", "review_state"]:
                        self.assertIn(key, item)
            self.assertEqual(before, self.snapshot_paths(repo))

    def test_agent_readiness_detects_dirty_git_and_missing_agent_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            self.init_git(repo)
            (repo / "notes.md").write_text("dirty\n", encoding="utf-8")
            before_status = subprocess.run(
                ["git", "status", "--short"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

            payload = self.payload_for(repo)
            after_status = subprocess.run(
                ["git", "status", "--short"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

            self.assertEqual(before_status, after_status)
            self.assertEqual("P0", payload["summary"]["risk_level"])
            risk_ids = [risk["id"] for risk in payload["risks"]]
            self.assertIn("dirty_worktree", risk_ids)
            self.assertIn("missing_agent_contract", risk_ids)
            self.assertNotIn("staged_paths_present", risk_ids)
            self.assertIn("skill.safe-task-worktree-bootstrap", [item["id"] for item in payload["recommendations"]["skills"]])
            self.assertIn("rule.add-agent-contract", [item["id"] for item in payload["recommendations"]["rules"]])

    def test_agent_readiness_detects_public_remote_security_and_secret_paths_without_reading_them(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            self.init_git(repo)
            self.git(repo, "remote", "add", "public", "https://example.invalid/public.git")
            (repo / "AGENTS.md").write_text("rules\n", encoding="utf-8")
            (repo / "auth").mkdir()
            (repo / "auth" / "login.py").write_text("print('safe')\n", encoding="utf-8")
            (repo / ".env").write_text("PLACEHOLDER=do-not-read\n", encoding="utf-8")

            code, stdout, stderr = self.run_cli("agent-readiness", "--repo", str(repo), "--format", "json")
            payload = json.loads(stdout)

            self.assertEqual(0, code, stderr)
            self.assertNotIn("do-not-read", stdout)
            self.assertIn("public_remote_present", [risk["id"] for risk in payload["risks"]])
            self.assertIn("security_sensitive_surface", [risk["id"] for risk in payload["risks"]])
            self.assertIn("skill.staged-scope-and-publish-guard", [item["id"] for item in payload["recommendations"]["skills"]])
            self.assertIn("hook.secret-scan", [item["id"] for item in payload["recommendations"]["hooks"]])
            secret_signal = next(item for item in payload["signals"] if item["id"] == "secret_like_paths_skipped")
            self.assertEqual(1, secret_signal["value"])
            self.assertEqual([".env"], secret_signal["evidence"])

    def test_agent_readiness_does_not_skip_source_files_with_secret_words(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "src" / "stages").mkdir(parents=True)
            (repo / "src" / "stages" / "token_count.rs").write_text("fn count() {}\n", encoding="utf-8")
            (repo / "token").write_text("PLACEHOLDER=do-not-read\n", encoding="utf-8")

            payload = self.payload_for(repo)

            self.assertIn("rust", payload["summary"]["repo_types"])
            secret_signal = next(item for item in payload["signals"] if item["id"] == "secret_like_paths_skipped")
            self.assertEqual(["token"], secret_signal["evidence"])

    def test_agent_readiness_detects_staged_paths_separately_from_unstaged_dirty(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            self.init_git(repo)
            (repo / "AGENTS.md").write_text("rules\n", encoding="utf-8")
            self.git(repo, "add", "AGENTS.md")

            payload = self.payload_for(repo)

            self.assertIn("staged_paths_present", [risk["id"] for risk in payload["risks"]])

    def test_agent_readiness_does_not_treat_package_manifest_as_test_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("rules\n", encoding="utf-8")
            (repo / "package.json").write_text("{}", encoding="utf-8")

            payload = self.payload_for(repo)

            self.assertIn("missing_test_gate", [risk["id"] for risk in payload["risks"]])
            test_signal = next(item for item in payload["signals"] if item["id"] == "test_markers")
            self.assertEqual([], test_signal["value"])

    def test_agent_readiness_detects_test_config_as_completion_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("rules\n", encoding="utf-8")
            (repo / "package.json").write_text("{}", encoding="utf-8")
            (repo / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")

            payload = self.payload_for(repo)

            self.assertNotIn("missing_test_gate", [risk["id"] for risk in payload["risks"]])
            test_signal = next(item for item in payload["signals"] if item["id"] == "test_markers")
            self.assertEqual(["vitest.config.ts"], test_signal["value"])

    def test_agent_readiness_detects_nested_tests_as_completion_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("rules\n", encoding="utf-8")
            (repo / "crates" / "app" / "tests").mkdir(parents=True)
            (repo / "crates" / "app" / "Cargo.toml").write_text("[package]\nname='app'\n", encoding="utf-8")
            (repo / "crates" / "app" / "tests" / "integration.rs").write_text("#[test]\nfn works() {}\n", encoding="utf-8")

            payload = self.payload_for(repo)

            self.assertNotIn("missing_test_gate", [risk["id"] for risk in payload["risks"]])
            test_signal = next(item for item in payload["signals"] if item["id"] == "test_markers")
            self.assertEqual(["crates/app/tests/integration.rs"], test_signal["value"])

    def test_agent_readiness_fixture_matrix_covers_repo_shapes_and_recommendations(self):
        scenarios = [
            ("python", {"pyproject.toml": ""}, "repo_types", "python"),
            ("rust", {"Cargo.toml": ""}, "repo_types", "rust"),
            ("go", {"go.mod": ""}, "repo_types", "go"),
            ("monorepo", {"pnpm-workspace.yaml": "", "packages/app/package.json": "{}"}, "repo_types", "monorepo"),
            ("deploy", {"Dockerfile": ""}, "skills", "skill.release-readiness-gates"),
            ("migration", {"migrations/001.sql": "select 1;"}, "skills", "skill.legacy-migration-audit"),
            ("frontend", {"package.json": "{}", "src/app/page.tsx": ""}, "skills", "skill.browser-runtime-smoke-gate"),
            ("agent-adapters", {"AGENTS.md": "rules\n"}, "adapters", "adapter.cursor"),
            ("codex-hooks", {".codex/hooks.json": "{}"}, "hooks", "hook.review-existing-hooks"),
            ("reefiki-bridge", {"projects/demo/wiki/index.md": "# Index\n"}, "skills", "skill.reefiki-experience-monitor"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, files, block, expected in scenarios:
                with self.subTest(name=name):
                    repo = root / name
                    repo.mkdir()
                    for rel, text in files.items():
                        path = repo / rel
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(text, encoding="utf-8")

                    payload = self.payload_for(repo)

                    if block == "repo_types":
                        self.assertIn(expected, payload["summary"]["repo_types"])
                    else:
                        ids = [item["id"] for item in payload["recommendations"][block]]
                        self.assertIn(expected, ids)

    def test_agent_readiness_marks_low_confidence_agent_surface_drift_as_review_needed(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("canonical rules\n", encoding="utf-8")
            (repo / "CLAUDE.md").write_text("claude rules\n", encoding="utf-8")
            (repo / ".cursorrules").write_text("cursor rules\n", encoding="utf-8")

            payload = self.payload_for(repo)
            rule = next(item for item in payload["recommendations"]["rules"] if item["id"] == "rule.consolidate-agent-contracts")

            self.assertEqual("low", rule["confidence"])
            self.assertEqual("review_needed", rule["review_state"])

    def test_agent_readiness_reports_monorepo_package_scopes(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n  - 'packages/*'\n", encoding="utf-8")
            (repo / "apps" / "web" / "src" / "app").mkdir(parents=True)
            (repo / "apps" / "web" / "package.json").write_text("{}", encoding="utf-8")
            (repo / "packages" / "worker").mkdir(parents=True)
            (repo / "packages" / "worker" / "pyproject.toml").write_text("[project]\nname='worker'\n", encoding="utf-8")
            before = self.snapshot_paths(repo)

            payload = self.payload_for(repo)

            self.assertEqual(before, self.snapshot_paths(repo))
            self.assertEqual(2, payload["summary"]["package_count"])
            package_signal = next(item for item in payload["signals"] if item["id"] == "package_scopes")
            scopes = {item["path"]: item for item in package_signal["value"]}
            self.assertIn("apps/web", scopes)
            self.assertIn("packages/worker", scopes)
            self.assertIn("frontend", scopes["apps/web"]["repo_types"])
            self.assertIn("python", scopes["packages/worker"]["repo_types"])
            self.assertIn("monorepo_package_scope_ambiguity", [risk["id"] for risk in payload["risks"]])
            frontend_skill = next(item for item in payload["recommendations"]["skills"] if item["id"] == "skill.browser-runtime-smoke-gate")
            self.assertIn("package:apps/web", frontend_skill["evidence"])
            self.assertIn("rule.scope-agent-work-by-package", [item["id"] for item in payload["recommendations"]["rules"]])
            self.assertIn("adapter.scoped-monorepo-adapters", [item["id"] for item in payload["recommendations"]["adapters"]])

    def test_agent_readiness_ignores_docs_only_package_scope_dirs(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "packages" / "archive").mkdir(parents=True)
            (repo / "packages" / "archive" / "README.md").write_text("# archive\n", encoding="utf-8")
            (repo / "packages" / "examples").mkdir(parents=True)
            (repo / "packages" / "examples" / "README.md").write_text("# examples\n", encoding="utf-8")

            payload = self.payload_for(repo)

            self.assertEqual(0, payload["summary"]["package_count"])
            self.assertNotIn("monorepo_package_scope_ambiguity", [risk["id"] for risk in payload["risks"]])

    def test_agent_readiness_ignores_generated_vercel_output_package_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            (repo / "vercel.json").write_text("{}", encoding="utf-8")
            generated = repo / ".vercel" / "output" / "functions" / "api" / "demo.func"
            generated.mkdir(parents=True)
            (generated / "package.json").write_text("{}", encoding="utf-8")
            (generated / ".env.local").write_text("PLACEHOLDER=do-not-read\n", encoding="utf-8")

            payload = self.payload_for(repo)

            self.assertEqual(0, payload["summary"]["package_count"])
            package_signal = next(item for item in payload["signals"] if item["id"] == "package_scopes")
            self.assertEqual([], package_signal["value"])
            skipped_dirs = next(item for item in payload["signals"] if item["id"] == "skipped_dirs")
            self.assertIn(".vercel", skipped_dirs["value"])

    def test_agent_readiness_does_not_follow_symlinked_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / "outside"
            outside.mkdir()
            (outside / "package.json").write_text("{}", encoding="utf-8")
            (outside / "src" / "app").mkdir(parents=True)
            repo = Path(temp) / "repo"
            repo.mkdir()
            link = repo / "linked-outside"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink creation is not available: {exc}")

            payload = self.payload_for(repo)

            self.assertNotIn("frontend", payload["summary"]["repo_types"])
            skipped_dirs = next(item for item in payload["signals"] if item["id"] == "skipped_dirs")
            self.assertIn("linked-outside", skipped_dirs["value"])

    def test_skills_recommend_alias_and_write_report_do_not_write_inside_target_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            reefiki_root = Path(temp) / "reefiki"
            (reefiki_root / "projects").mkdir(parents=True)
            repo = Path(temp) / "target"
            repo.mkdir()

            code, stdout, stderr = self.run_cli(
                "--project",
                str(reefiki_root),
                "skills",
                "recommend",
                "--repo",
                str(repo),
                "--format",
                "json",
                "--write-report",
            )
            payload = json.loads(stdout)
            report_path = Path(payload["report_path"])

            self.assertEqual(0, code, stderr)
            self.assertTrue(report_path.exists())
            self.assertEqual((reefiki_root / "reports").resolve(), report_path.parent.resolve())
            self.assertFalse((repo / "reports").exists())
            self.assertIn("# Agent Readiness Report", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
