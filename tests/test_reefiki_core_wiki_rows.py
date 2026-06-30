from scripts.reefiki_core.wiki_rows import _wiki_rows


def test_wiki_rows_normalizes_frontmatter_and_body(tmp_path) -> None:
    project = tmp_path / "project"
    page = project / "wiki" / "concepts" / "runbook.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        """---
id: runbook
type: concept
title: "Runbook"
tags: [ops]
useful_when:
  - "checking wiki row normalization"
sources:
  - "https://example.com"
date_added: 2026-06-11
use_count: 2
last_used: 2026-06-11
verified: 2026-06-11
---

Body text.
""",
        encoding="utf-8",
    )

    rows = _wiki_rows(project)

    assert rows == [
        {
            "id": "runbook",
            "type": "concept",
            "title": "Runbook",
            "tags": ["ops"],
            "useful_when": ["checking wiki row normalization"],
            "sources": ["https://example.com"],
            "date_added": "2026-06-11",
            "use_count": 2,
            "last_used": "2026-06-11",
            "verified": "2026-06-11",
            "file": "wiki/concepts/runbook.md",
            "body": "Body text.",
        }
    ]


def test_wiki_rows_falls_back_to_file_and_parent_names(tmp_path) -> None:
    project = tmp_path / "project"
    page = project / "wiki" / "skills" / "fallback.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\nuse_count: 0\n---\nBody.\n", encoding="utf-8")

    rows = _wiki_rows(project)

    assert rows[0]["id"] == "fallback"
    assert rows[0]["type"] == "skill"
    assert rows[0]["title"] == "fallback"
    assert rows[0]["tags"] == []
    assert rows[0]["useful_when"] == []
    assert rows[0]["sources"] == []
    assert rows[0]["last_used"] is None
