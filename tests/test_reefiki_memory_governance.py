import importlib.util
import tempfile
import unittest
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REEFIKI_PATH = ROOT / "scripts" / "reefiki.py"
SPEC = importlib.util.spec_from_file_location("reefiki", REEFIKI_PATH)
reefiki = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reefiki)

pytestmark = [pytest.mark.memory, pytest.mark.governance, pytest.mark.contract]


class MemoryGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.project = self.root / "project"
        (self.project / "wiki" / "concepts").mkdir(parents=True)
        (self.project / "wiki" / "decisions").mkdir(parents=True)
        (self.project / "wiki" / "synthesis").mkdir(parents=True)
        (self.project / "wiki" / "log.md").write_text("", encoding="utf-8")
        (self.project / "wiki" / "index.md").write_text(
            "# Index — test\n\nLast updated: 2026-05-14\nTotal pages: 0\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n\n## Decisions\n\n## Skills\n",
            encoding="utf-8",
        )
        self.repo_root = self.root
        (self.repo_root / "projects").mkdir(exist_ok=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_page(self, relative_path: str, text: str) -> Path:
        path = self.project / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_promotion_dry_run_prefers_memoir_only_for_short_rule(self):
        result = reefiki.promotion_dry_run(
            self.project,
            "This project prefers pytest.",
            memory_id="m-1",
            confidence=0.7,
        )
        self.assertEqual("memoir-only", result["verdict"])
        self.assertEqual([], result["duplicate_candidate_refs"])

    def test_promotion_dry_run_suggests_promotion_for_decision_like_text(self):
        result = reefiki.promotion_dry_run(
            self.project,
            "We decided to keep memoir for short working memory and REEFIKI for durable knowledge because that avoids duplication.",
            memory_id="m-2",
            confidence=0.8,
        )
        self.assertEqual("promote", result["verdict"])
        self.assertEqual("decision", result["suggested_target_type"])
        self.assertEqual("needs_verification", result["review_state"])

    def test_review_queue_scan_finds_orphan_duplicate_and_needs_verification(self):
        self.write_page(
            "wiki/concepts/a.md",
            """---
id: a
type: concept
title: "Shared title"
tags: [one]
useful_when:
  - "x"
date_added: 2026-01-01
use_count: 0
last_used: null
---
Body only.
""",
        )
        self.write_page(
            "wiki/synthesis/b.md",
            """---
id: b
type: synthesis
title: "Shared title"
tags: [two]
useful_when:
  - "y"
date_added: 2026-01-01
use_count: 0
last_used: null
---
Body only.
""",
        )
        items = reefiki.review_queue_scan(self.project, stale_days=30)
        queue_types = {(item["page_id"], item["queue_type"]) for item in items}
        self.assertIn(("a", "orphan_review"), queue_types)
        self.assertIn(("b", "needs_verification"), queue_types)
        self.assertIn(("a", "duplicate_candidate"), queue_types)
        self.assertIn(("b", "duplicate_candidate"), queue_types)
        self.assertIn(("a", "stale_review"), queue_types)

    def test_review_queue_scan_does_not_flag_source_and_concept_as_duplicates_only_by_shared_source(self):
        self.write_page(
            "wiki/sources/s1.md",
            """---
id: s1
type: source
title: "Original source"
tags: [src]
useful_when:
  - "read source"
sources:
  - raw/source.txt
date_added: 2026-01-01
use_count: 0
last_used: null
---
Body.
""",
        )
        self.write_page(
            "wiki/concepts/c1.md",
            """---
id: c1
type: concept
title: "Derived concept"
tags: [concept]
useful_when:
  - "reuse idea"
sources:
  - raw/source.txt
date_added: 2026-01-01
use_count: 0
last_used: null
---
Body.
""",
        )
        items = reefiki.review_queue_scan(self.project, stale_days=30)
        dups = [item for item in items if item["queue_type"] == "duplicate_candidate"]
        self.assertEqual([], [item for item in dups if item["page_id"] in {"s1", "c1"}])

    def test_review_queue_scan_ignores_shared_current_session_as_duplicate_signal(self):
        self.write_page(
            "wiki/concepts/promotion-gate.md",
            """---
id: promotion-gate
type: concept
title: "Promotion gate"
tags: [governance]
useful_when:
  - "route memory"
sources: [current-session-2026-05-14]
date_added: 2026-05-14
use_count: 0
last_used: null
---
Body.
""",
        )
        self.write_page(
            "wiki/decisions/routing-contract.md",
            """---
id: routing-contract
type: decision
title: "Routing contract"
tags: [governance]
useful_when:
  - "choose memory layer"
sources: [current-session-2026-05-14]
date_added: 2026-05-14
use_count: 0
last_used: null
---
## Контекст

## Варианты

## Решение
""",
        )
        items = reefiki.review_queue_scan(self.project, stale_days=30)
        dups = [item for item in items if item["queue_type"] == "duplicate_candidate"]
        self.assertEqual([], [item for item in dups if item["page_id"] in {"promotion-gate", "routing-contract"}])

    def test_review_queue_scan_requires_similar_titles_for_shared_source_duplicates(self):
        self.write_page(
            "wiki/concepts/llm-wiki-vs-rag.md",
            """---
id: llm-wiki-vs-rag
type: concept
title: "LLM Wiki vs RAG"
tags: [wiki]
useful_when:
  - "compare memory patterns"
sources: [raw/karpathy-wiki-overview.txt]
date_added: 2026-05-14
use_count: 0
last_used: null
---
Body.
""",
        )
        self.write_page(
            "wiki/synthesis/karpathy-who-is.md",
            """---
id: karpathy-who-is
type: synthesis
title: "Karpathy: who is"
tags: [people]
useful_when:
  - "identify the author"
sources: [raw/karpathy-wiki-overview.txt]
date_added: 2026-05-14
use_count: 0
last_used: null
---
Body.
""",
        )
        self.write_page(
            "wiki/synthesis/llm-wiki-rag-comparison.md",
            """---
id: llm-wiki-rag-comparison
type: synthesis
title: "LLM Wiki and RAG comparison"
tags: [wiki]
useful_when:
  - "compare memory patterns"
sources: [raw/karpathy-wiki-overview.txt]
date_added: 2026-05-14
use_count: 0
last_used: null
---
Body.
""",
        )
        items = reefiki.review_queue_scan(self.project, stale_days=30)
        dups = [item for item in items if item["queue_type"] == "duplicate_candidate"]
        by_page = {item["page_id"]: item for item in dups}
        self.assertNotIn("karpathy-who-is", by_page)
        self.assertEqual(["llm-wiki-rag-comparison"], by_page["llm-wiki-vs-rag"]["related_page_ids"])

    def test_review_queue_scan_ignores_broad_governance_overlap_from_shared_source(self):
        self.write_page(
            "wiki/decisions/skill-adoption-governance.md",
            """---
id: skill-adoption-governance
type: decision
title: "Skill adoption governance"
tags: [skills, governance]
useful_when:
  - "decide how to adopt external skills"
sources: [raw/external-skills-audit.md]
date_added: 2026-05-30
use_count: 0
last_used: null
---
## Контекст

## Варианты

## Решение
""",
        )
        self.write_page(
            "wiki/concepts/external-skill-governance.md",
            """---
id: external-skill-governance
type: concept
title: "External skill governance"
tags: [skills, governance]
useful_when:
  - "review an external skill candidate"
sources: [raw/external-skills-audit.md]
date_added: 2026-05-30
use_count: 0
last_used: null
---
Body.
""",
        )

        items = reefiki.review_queue_scan(self.project, stale_days=30)
        dups = [item for item in items if item["queue_type"] == "duplicate_candidate"]

        self.assertEqual([], [item for item in dups if item["page_id"] in {"skill-adoption-governance", "external-skill-governance"}])

    def test_review_queue_scan_flags_missing_related_reference_as_conflict(self):
        self.write_page(
            "wiki/concepts/c.md",
            """---
id: c
type: concept
title: "Reference page"
tags: [three]
useful_when:
  - "z"
date_added: 2026-05-01
use_count: 0
last_used: null
---
## Related
[[missing-page]] — broken relation
""",
        )
        items = reefiki.review_queue_scan(self.project, stale_days=30)
        matches = [item for item in items if item["page_id"] == "c" and item["queue_type"] == "conflict_review"]
        self.assertEqual(1, len(matches))
        self.assertEqual(["missing-page"], matches[0]["related_page_ids"])

    def test_review_queue_scan_flags_explicit_conflicting_claim_marker(self):
        self.write_page(
            "wiki/decisions/current-routing.md",
            """---
id: current-routing
type: decision
title: "Current routing"
tags: [routing]
useful_when:
  - "choose the active route"
sources: [raw/routing.md]
date_added: 2026-05-30
use_count: 0
last_used: null
---
## Контекст

## Варианты

## Решение

Use route A.

## Conflicting claims

[[old-routing]] says route B was active.
""",
        )
        self.write_page(
            "wiki/decisions/old-routing.md",
            """---
id: old-routing
type: decision
title: "Old routing"
tags: [routing]
useful_when:
  - "understand old route"
sources: [raw/old-routing.md]
date_added: 2026-05-01
use_count: 0
last_used: null
---
## Контекст

## Варианты

## Решение

Use route B.
""",
        )

        items = reefiki.review_queue_scan(self.project, stale_days=90)
        matches = [
            item
            for item in items
            if item["page_id"] == "current-routing" and item["queue_type"] == "conflict_review"
        ]

        self.assertEqual(1, len(matches))
        self.assertEqual(["old-routing"], matches[0]["related_page_ids"])
        self.assertEqual("explicit conflicting-claims marker", matches[0]["reason"])

    def test_review_queue_scan_ignores_wikilinks_outside_related_section(self):
        self.write_page(
            "wiki/synthesis/e.md",
            """---
id: e
type: synthesis
title: "Prose example"
tags: [five]
useful_when:
  - "example"
sources:
  - raw/example.md
date_added: 2026-05-01
use_count: 0
last_used: null
---
In prose we may mention [[wikilinks]] as a concept example.
""",
        )
        items = reefiki.review_queue_scan(self.project, stale_days=30)
        matches = [item for item in items if item["page_id"] == "e" and item["queue_type"] == "conflict_review"]
        self.assertEqual([], matches)

    def test_review_queue_scan_reports_link_health_queues(self):
        self.write_page(
            "wiki/concepts/a.md",
            """---
id: a
type: concept
title: "A"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Mentions [[b]] and [[missing-page]].
""",
        )
        self.write_page(
            "wiki/concepts/b.md",
            """---
id: b
type: concept
title: "B"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Does not link back.
""",
        )
        self.write_page(
            "wiki/concepts/c.md",
            """---
id: c
type: concept
title: "C"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Standalone.
""",
        )

        items = reefiki.review_queue_scan(self.project, stale_days=90)
        queues = {(item["page_id"], item["queue_type"], tuple(item["related_page_ids"])) for item in items}

        self.assertIn(("a", "placeholder_link", ("missing-page",)), queues)
        self.assertIn(("b", "missing_backlink", ("a",)), queues)
        self.assertIn(("c", "orphan_review", ()), queues)

    def test_review_queues_respects_intentional_one_way_inbound_links(self):
        self.write_page(
            "wiki/concepts/a.md",
            """---
id: a
type: concept
title: "A"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Links to [[b]].
""",
        )
        self.write_page(
            "wiki/concepts/b.md",
            """---
id: b
type: concept
title: "B"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
This page intentionally does not link back.

## Intentional one-way inbound links

- `a`
""",
        )

        items = reefiki.review_queue_scan(self.project, stale_days=90)
        queues = {(item["page_id"], item["queue_type"], tuple(item["related_page_ids"])) for item in items}

        self.assertNotIn(("b", "missing_backlink", ("a",)), queues)

    def test_review_queues_respects_intentional_one_way_outbound_links(self):
        self.write_page(
            "wiki/concepts/a.md",
            """---
id: a
type: concept
title: "A"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
## Related

[[b]] — useful context, but intentionally one-way.

## Intentional one-way outbound links

- `c`
""",
        )
        self.write_page(
            "wiki/concepts/b.md",
            """---
id: b
type: concept
title: "B"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Does not link back.
""",
        )
        self.write_page(
            "wiki/concepts/c.md",
            """---
id: c
type: concept
title: "C"
tags: [one]
useful_when:
  - "link health"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Does not link back.
""",
        )

        items = reefiki.review_queue_scan(self.project, stale_days=90)
        queues = {(item["page_id"], item["queue_type"], tuple(item["related_page_ids"])) for item in items}

        self.assertNotIn(("b", "missing_backlink", ("a",)), queues)
        self.assertNotIn(("c", "missing_backlink", ("a",)), queues)

    def test_write_review_queue_report_creates_markdown_artifact(self):
        self.write_page(
            "wiki/concepts/d.md",
            """---
id: d
type: concept
title: "Lonely page"
tags: [four]
useful_when:
  - "w"
date_added: 2026-01-01
use_count: 0
last_used: null
---
Body only.
""",
        )
        report = reefiki.write_review_queue_report(self.project, stale_days=30)
        text = report.read_text(encoding="utf-8")
        self.assertTrue(report.exists())
        self.assertIn("# Review Queue Report", text)
        self.assertIn("## orphan_review", text)
        self.assertIn("`d`", text)

    def test_build_backlink_index_reports_links_orphans_and_broken_targets(self):
        self.write_page(
            "wiki/concepts/a.md",
            """---
id: a
type: concept
title: "A"
tags: [one]
useful_when:
  - "link index"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Links to [[b]] and [[missing-page]].
""",
        )
        self.write_page(
            "wiki/concepts/b.md",
            """---
id: b
type: concept
title: "B"
tags: [one]
useful_when:
  - "link index"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Linked page.
""",
        )
        self.write_page(
            "wiki/concepts/c.md",
            """---
id: c
type: concept
title: "C"
tags: [one]
useful_when:
  - "link index"
date_added: 2026-05-01
use_count: 0
last_used: null
---
Standalone.
""",
        )

        payload = reefiki.build_backlink_index(self.project)

        self.assertEqual(["b", "missing-page"], payload["pages"]["a"]["outgoing"])
        self.assertEqual(["a"], payload["pages"]["b"]["incoming"])
        self.assertEqual(["a", "c"], payload["orphans"])
        self.assertEqual(
            [{"source_id": "a", "target_id": "missing-page", "file": "wiki/concepts/a.md", "line": 1}],
            payload["broken_links"],
        )

    def test_write_promotion_draft_creates_markdown_artifact(self):
        draft = reefiki.write_promotion_draft(
            self.project,
            "We decided to keep memoir for short working memory and REEFIKI for durable knowledge because that avoids duplication.",
            memory_id="memo-42",
            confidence=0.8,
        )
        text = draft.read_text(encoding="utf-8")
        self.assertTrue(draft.exists())
        self.assertIn("# Promotion Draft", text)
        self.assertIn("Verdict: promote", text)
        self.assertIn("Suggested target type: decision", text)
        self.assertIn("Memory ID: memo-42", text)

    def test_apply_promotion_draft_creates_decision_page_and_updates_log(self):
        draft = reefiki.write_promotion_draft(
            self.project,
            "We decided to keep memoir for short working memory and REEFIKI for durable knowledge because that avoids duplication.",
            memory_id="memo-77",
            confidence=0.8,
        )
        page = reefiki.apply_promotion_draft(self.project, str(draft), yes=True)
        text = page.read_text(encoding="utf-8")
        self.assertTrue(page.exists())
        self.assertIn("type: decision", text)
        self.assertIn("## Контекст", text)
        log_text = (self.project / "wiki" / "log.md").read_text(encoding="utf-8")
        self.assertIn("promotion draft applied", log_text)

    def test_memory_route_prefers_graphify_for_structure_queries(self):
        result = reefiki.memory_route("where is the auth module and what files is it connected to?")
        self.assertEqual("graphify", result["layer"])

    def test_memory_route_prefers_reefiki_for_durable_decision_queries(self):
        result = reefiki.memory_route("we decided to keep one routing contract for memory governance")
        self.assertEqual("reefiki", result["layer"])

    def test_find_project_works_from_repo_root(self):
        target = self.repo_root / "projects" / "reefiki"
        target.mkdir(parents=True, exist_ok=True)
        found = reefiki.find_project(self.repo_root, "reefiki")
        self.assertEqual(target.resolve(), found.resolve())

    def test_global_lookup_returns_reefiki_hits(self):
        target = self.repo_root / "projects" / "reefiki"
        (target / "wiki" / "concepts").mkdir(parents=True)
        (target / "wiki" / "log.md").write_text("", encoding="utf-8")
        (target / "wiki" / "index.md").write_text(
            "# Index — test\n\nLast updated: 2026-05-14\nTotal pages: 0\n\n## Sources\n\n## Entities\n\n## Concepts\n\n## Synthesis\n\n## Decisions\n\n## Skills\n",
            encoding="utf-8",
        )
        (target / "wiki" / "concepts" / "routing.md").write_text(
            """---
id: routing
type: concept
title: "Routing contract"
tags: [memory]
useful_when:
  - "route memory"
date_added: 2026-05-14
use_count: 0
last_used: null
---
Use REEFIKI for durable routing and memory governance.
""",
            encoding="utf-8",
        )
        result = reefiki.global_lookup(
            self.repo_root,
            query="routing contract",
            project="reefiki",
            include_memoir=False,
            include_reefiki=True,
            include_graph=False,
            limit=5,
        )
        self.assertEqual("reefiki", result["reefiki"][0]["project"])
        self.assertEqual("routing", result["reefiki"][0]["id"])


if __name__ == "__main__":
    unittest.main()
