import tempfile
import unittest
from pathlib import Path

from scripts.reefiki_core.promotion import (
    apply_promotion_draft,
    promotion_dry_run,
    promotion_inbox_summary,
    write_promotion_draft,
)


class PromotionCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name) / "project"
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "decisions").mkdir(parents=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "log.md").write_text("", encoding="utf-8")
        (self.project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_promotion_dry_run_suggests_decision_for_decision_like_content(self) -> None:
        result = promotion_dry_run(
            self.project,
            "We decided to keep promotion drafts before durable writes because automatic promotion is risky.",
        )

        self.assertEqual("promote", result["verdict"])
        self.assertEqual("decision", result["suggested_target_type"])
        self.assertEqual("needs_verification", result["review_state"])

    def test_apply_promotion_draft_creates_page_and_updates_summary(self) -> None:
        draft = write_promotion_draft(
            self.project,
            "We decided to keep promotion drafts before durable writes because automatic promotion is risky.",
        )

        page = apply_promotion_draft(self.project, str(draft), yes=True)
        summary = promotion_inbox_summary(self.project)

        self.assertTrue(page.exists())
        self.assertEqual(1, summary["active"])
        self.assertIn("promotion draft applied", (self.project / "wiki" / "log.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
