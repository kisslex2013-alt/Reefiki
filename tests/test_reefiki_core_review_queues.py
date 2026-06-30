from scripts.reefiki_core.review_queues import build_backlink_index, review_queue_scan, review_queue_summary


def write_page(project, relative_path, text):
    path = project / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_review_queue_module_detects_duplicates_and_backlinks(tmp_path):
    project = tmp_path / "reefiki"
    write_page(
        project,
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
## Related

[[llm-wiki-rag-comparison]]
""",
    )
    write_page(
        project,
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

    items = review_queue_scan(project, stale_days=999)
    duplicates = [item for item in items if item["queue_type"] == "duplicate_candidate"]
    assert duplicates
    assert duplicates[0]["related_page_ids"] == ["llm-wiki-rag-comparison"]

    summary = review_queue_summary(items, limit=1)
    assert summary["counts"]["duplicate_candidate"] >= 1

    backlinks = build_backlink_index(project)
    assert backlinks["pages"]["llm-wiki-rag-comparison"]["incoming"] == ["llm-wiki-vs-rag"]
