import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REEFIKI_PATH = ROOT / "scripts" / "reefiki.py"
SPEC = importlib.util.spec_from_file_location("reefiki", REEFIKI_PATH)
reefiki = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reefiki)


class DedupCheckTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.project = self.root / "project"
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "inbox").mkdir()
        (self.project / "seen").mkdir()
        (self.project / "wiki" / "log.md").write_text("", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def run_dedup(self, source: str):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = reefiki.dedup_check(self.project, source)
        return code, stdout.getvalue()

    def run_save(self, source: str):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = reefiki.save_source(self.project, source)
        return code, stdout.getvalue()

    def write_project_file(self, relative_path: str, text: str) -> Path:
        path = self.project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_url_duplicate_is_found_in_wiki_inbox_and_seen(self):
        url = "https://example.com/source"
        self.write_project_file("wiki/concepts/source.md", f"---\nsources:\n  - {url}\n---\n")
        self.write_project_file("inbox/source.md", url)
        self.write_project_file("seen/source.md", f"rejected source: {url}")

        code, output = self.run_dedup(url)

        self.assertEqual(code, 1)
        self.assertIn("url:wiki/concepts/source.md", output)
        self.assertIn("url:inbox/source.md", output)
        self.assertIn("url:seen/source.md", output)

    def test_url_duplicate_uses_canonical_form(self):
        self.write_project_file(
            "wiki/concepts/source.md",
            "source: http://www.example.com/path/?b=2&a=1\n",
        )

        code, output = self.run_dedup("https://example.com/path?a=1&b=2")

        self.assertEqual(code, 1)
        self.assertIn("url:wiki/concepts/source.md", output)

    def test_file_duplicate_is_found_by_sha256_across_project_text_files(self):
        source = self.project / "incoming.md"
        source.write_text("same durable content\n", encoding="utf-8")
        self.write_project_file("wiki/concepts/existing.md", "same durable content\n")
        self.write_project_file("inbox/other-name.md", "same durable content\n")
        self.write_project_file("seen/rejected.md", "same durable content\n")

        code, output = self.run_dedup(str(source))

        self.assertEqual(code, 1)
        self.assertIn("sha256:wiki/concepts/existing.md", output)
        self.assertIn("sha256:inbox/other-name.md", output)
        self.assertIn("sha256:seen/rejected.md", output)

    def test_file_duplicate_is_found_by_inbox_name(self):
        source = self.project / "captured.md"
        source.write_text("new content\n", encoding="utf-8")
        self.write_project_file("inbox/captured.md", "different content\n")

        code, output = self.run_dedup(str(source))

        self.assertEqual(code, 1)
        self.assertIn("name:inbox/captured.md", output)

    def test_file_dedup_refuses_source_outside_project(self):
        source = self.root / "outside.md"
        source.write_text("external content\n", encoding="utf-8")

        code, output = self.run_dedup(str(source))

        self.assertEqual(code, 2)
        self.assertIn("Refused: path-outside-project", output)

    def test_save_file_refuses_source_outside_project(self):
        source = self.root / "outside.md"
        source.write_text("external content\n", encoding="utf-8")

        code, output = self.run_save(str(source))

        self.assertEqual(code, 2)
        self.assertIn("Refused: path-outside-project", output)
        self.assertFalse((self.project / "inbox" / "outside.md").exists())

    def test_new_url_returns_zero(self):
        code, output = self.run_dedup("https://example.com/new")

        self.assertEqual(code, 0)
        self.assertIn("No duplicates found.", output)

    def test_missing_file_returns_two(self):
        code, output = self.run_dedup("missing.md")

        self.assertEqual(code, 2)
        self.assertIn("Source file not found:", output)

    def test_classify_path_refuses_outside_project_path(self):
        source = self.root / "outside.md"
        source.write_text("external content\n", encoding="utf-8")

        ok, reason = reefiki.classify_path(str(source), self.project)

        self.assertFalse(ok)
        self.assertEqual("path-outside-project", reason)

    def test_plan_check_refuses_outside_project_path(self):
        external_plan = self.root / "external-plan.md"
        body = "# External\n"
        checksum = reefiki.hashlib.sha256(body.encode("utf-8")).hexdigest()
        external_plan.write_text(
            body + f"\n<!-- reefiki-plan-sha256:{checksum} -->\n",
            encoding="utf-8",
        )
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            code = reefiki.plan_check(self.project, str(external_plan))

        self.assertEqual(2, code)
        self.assertIn("Refused: path-outside-project", stdout.getvalue())

    def test_save_url_writes_inbox_and_log_after_dedup(self):
        code, output = self.run_save("https://example.com/path?a=1")

        self.assertEqual(code, 0)
        self.assertIn("Saved: inbox/example-com-path.md", output)
        self.assertEqual(
            "https://example.com/path?a=1\n",
            (self.project / "inbox" / "example-com-path.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "/save | https://example.com/path?a=1",
            (self.project / "wiki" / "log.md").read_text(encoding="utf-8"),
        )

    def test_save_url_refuses_canonical_duplicate_before_writing(self):
        self.write_project_file("wiki/concepts/source.md", "http://www.example.com/path/?b=2&a=1\n")

        code, output = self.run_save("https://example.com/path?a=1&b=2")

        self.assertEqual(code, 1)
        self.assertIn("Duplicate candidate(s):", output)
        self.assertFalse((self.project / "inbox" / "example-com-path.md").exists())


if __name__ == "__main__":
    unittest.main()
