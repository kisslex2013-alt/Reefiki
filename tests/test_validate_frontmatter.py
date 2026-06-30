import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_frontmatter.py"
SPEC = importlib.util.spec_from_file_location("validate_frontmatter", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


class FrontmatterValidatorTests(unittest.TestCase):
    def test_json_output_reports_rule_codes_and_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "project" / "wiki" / "concepts" / "broken.md"
            path.parent.mkdir(parents=True)
            path.write_text("No frontmatter\n", encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = validator.main(["--format", "json", str(path)])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, code)
        self.assertEqual("fail", payload["outcome"])
        self.assertEqual("frontmatter.missing", payload["errors"][0]["code"])
        self.assertTrue(payload["errors"][0]["path"].endswith("broken.md"))

    def test_json_output_reports_location_expected_and_actual(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "project" / "wiki" / "concepts" / "bad-type.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                """---
id: bad-type
type: weird
title: "Bad Type"
tags: [memory]
useful_when:
  - "check diagnostics"
date_added: 2026-05-31
use_count: 0
last_used: null
---
Body.
""",
                encoding="utf-8",
            )

            report = validator.validate_file_report(path)

        item = next(error for error in report if error["code"] == "frontmatter.unknown_type")
        self.assertEqual(3, item["line"])
        self.assertEqual(1, item["column"])
        self.assertEqual("weird", item["actual"])
        self.assertIn("concept", item["expected"])

    def test_id_must_match_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "project" / "wiki" / "concepts" / "actual-file.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                """---
id: different-id
type: concept
title: "Bad ID"
tags: [memory]
useful_when:
  - "check id filename mismatch"
date_added: 2026-06-08
use_count: 0
last_used: null
---
Body.
""",
                encoding="utf-8",
            )

            report = validator.validate_file_report(path)

        item = next(error for error in report if error["code"] == "frontmatter.id_filename_mismatch")
        self.assertEqual("actual-file", item["expected"])
        self.assertEqual("different-id", item["actual"])

    def test_schema_version_is_checked_from_project_domain(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            (project / "wiki" / "concepts").mkdir(parents=True)
            (project / "_domain.md").write_text(
                """---
schema_version: "0.9"
---

# Domain
""",
                encoding="utf-8",
            )
            page = project / "wiki" / "concepts" / "valid-page.md"
            page.write_text(
                """---
id: valid-page
type: concept
title: "Valid Page"
tags: [memory]
useful_when:
  - "check schema version"
date_added: 2026-06-08
use_count: 0
last_used: null
---
Body.
""",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = validator.main(["--format", "json", str(page)])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(1, code)
        self.assertEqual("fail", payload["outcome"])
        item = next(error for error in payload["errors"] if error["code"] == "schema_version.unsupported")
        self.assertEqual("1.0", item["expected"])
        self.assertEqual("0.9", item["actual"])

    def test_overview_file_is_skipped_without_frontmatter(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wiki" / "concepts" / "_overview.md"
            path.parent.mkdir(parents=True)
            path.write_text("# Concepts overview\n", encoding="utf-8")

            errors = validator.validate_file(path)

        self.assertEqual([], errors)

    def test_log_archive_file_is_skipped_without_frontmatter_and_index_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            wiki = Path(temp) / "project" / "wiki"
            logs = wiki / "logs"
            logs.mkdir(parents=True)
            archive = logs / "log-2026-04.md"
            archive.write_text("# Log archive\n\nAppend-only archive.\n", encoding="utf-8")
            index = wiki / "index.md"
            index.write_text(
                """# Index

Total pages: 0

## Sources
## Entities
## Concepts
## Synthesis
## Decisions
## Skills
""",
                encoding="utf-8",
            )

            file_report = validator.validate_file_report(archive)
            index_report = validator.validate_index_report(index)

        self.assertFalse([item for item in file_report if item["code"] == "frontmatter.missing"])
        self.assertFalse([item for item in index_report if item["code"].startswith("index.files_")])


if __name__ == "__main__":
    unittest.main()
