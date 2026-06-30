from pathlib import Path

from scripts.reefiki_core.index_search import (
    best_chunk_context,
    build_index,
    escape_fts,
    project_local_lookup,
    search,
    search_files_payload,
)


def write_project_page(project: Path, slug: str, body: str) -> None:
    target = project / "wiki" / "synthesis"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{slug}.md").write_text(
        f"""---
id: {slug}
title: "{slug}"
type: synthesis
tags: [test, index]
useful_when:
  - "testing extracted index search helpers"
sources: []
date_added: 2026-06-11
use_count: 0
last_used: null
---
{body}
""",
        encoding="utf-8",
    )


def test_escape_fts_quotes_keyword_tokens() -> None:
    assert escape_fts("python AND NOT") == '"python" OR "AND" OR "NOT"'


def test_build_index_search_and_best_chunk_context(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "wiki").mkdir(parents=True)
    write_project_page(
        project,
        "needle-page",
        """# Overview
General text.

## Retrieval Contract
Needle details live here.
""",
    )

    assert build_index(project) == 1
    rows = search(project, "Needle", 5, chunked=True)

    assert [row["id"] for row in rows] == ["needle-page"]
    assert rows[0]["heading_path"] == "Overview > Retrieval Contract"
    assert rows[0]["snippet"] == "Needle details live here."
    assert best_chunk_context(project, "Needle", "needle-page") == {
        "heading_path": "Overview > Retrieval Contract",
        "snippet": "Needle details live here.",
    }


def test_search_files_payload_keeps_agent_file_list_shape(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "wiki").mkdir(parents=True)
    write_project_page(project, "files-page", "Files payload needle.")
    build_index(project)

    rows = search(project, "needle", 5)
    payload = search_files_payload("needle", rows)

    assert payload["query"] == "needle"
    assert payload["count"] == 1
    assert payload["files"][0]["docid"] == "files-page"
    assert payload["files"][0]["path"] == "wiki/synthesis/files-page.md"


def test_project_local_lookup_keeps_memory_lookup_shape(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "wiki").mkdir(parents=True)
    write_project_page(
        project,
        "lookup-page",
        """# Overview
General text.

## Memory Match
Lookup needle appears here.
""",
    )
    build_index(project)

    hits = project_local_lookup(project, "needle", 5)

    assert hits == [
        {
            "project": "project",
            "id": "lookup-page",
            "title": "lookup-page",
            "type": "synthesis",
            "file": "wiki/synthesis/lookup-page.md",
            "useful_when": "testing extracted index search helpers",
            "matched_heading": "Overview > Memory Match",
            "matched_chunk": "Lookup needle appears here.",
            "score": hits[0]["score"],
        }
    ]
