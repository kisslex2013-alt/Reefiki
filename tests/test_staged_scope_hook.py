from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "scripts" / "staged_scope_hook.py"


class StagedScopeHookTests(unittest.TestCase):
    def init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)

    def run_hook(self, root: Path, command: str) -> tuple[int, dict]:
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "functions.exec_command",
            "tool_input": {"cmd": command},
        }
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            cwd=root,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        return proc.returncode, data

    def test_blocks_broad_git_add(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)

            for command in ["git add -A", "git add .", "git add ..", "git add -- .", "git add ./", "git add ../"]:
                with self.subTest(command=command):
                    code, data = self.run_hook(root, command)

                    self.assertEqual(2, code)
                    self.assertEqual("block", data["decision"])
                    self.assertIn("broad staging", data["reason"])

    def test_allows_single_project_wiki_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)
            page = root / "projects" / "reefiki" / "wiki" / "skills" / "guard.md"
            page.parent.mkdir(parents=True)
            page.write_text("guard\n", encoding="utf-8")
            subprocess.run(["git", "add", "projects/reefiki/wiki/skills/guard.md"], cwd=root, check=True)

            code, data = self.run_hook(root, "git commit -m test")

            self.assertEqual(0, code)
            self.assertNotEqual("block", data.get("decision"))
            self.assertIn("guard passed", data["hookSpecificOutput"]["additionalContext"])

    def test_blocks_mixed_project_wiki_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)
            allowed = root / "projects" / "reefiki" / "wiki" / "skills" / "guard.md"
            other = root / "projects" / "metrica" / "wiki" / "skills" / "guard.md"
            allowed.parent.mkdir(parents=True)
            other.parent.mkdir(parents=True)
            allowed.write_text("guard\n", encoding="utf-8")
            other.write_text("guard\n", encoding="utf-8")
            subprocess.run(
                [
                    "git",
                    "add",
                    "projects/reefiki/wiki/skills/guard.md",
                    "projects/metrica/wiki/skills/guard.md",
                ],
                cwd=root,
                check=True,
            )

            code, data = self.run_hook(root, "git commit -m test")

            self.assertEqual(2, code)
            self.assertEqual("block", data["decision"])
            self.assertIn("projects/metrica/wiki/skills/guard.md", data["reason"])

    def test_blocks_wiki_commit_mixed_with_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)
            page = root / "projects" / "reefiki" / "wiki" / "skills" / "guard.md"
            script = root / "scripts" / "tool.py"
            page.parent.mkdir(parents=True)
            script.parent.mkdir(parents=True)
            page.write_text("guard\n", encoding="utf-8")
            script.write_text("print('tool')\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", "projects/reefiki/wiki/skills/guard.md", "scripts/tool.py"],
                cwd=root,
                check=True,
            )

            code, data = self.run_hook(root, "git commit -m test")

            self.assertEqual(2, code)
            self.assertEqual("block", data["decision"])
            self.assertIn("scripts/tool.py", data["reason"])

    def test_blocks_manual_git_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.init_repo(root)

            code, data = self.run_hook(root, "git push origin main")

            self.assertEqual(2, code)
            self.assertEqual("block", data["decision"])
            self.assertIn("publish-task", data["reason"])


if __name__ == "__main__":
    unittest.main()
