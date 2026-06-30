from scripts.reefiki_core.markdown import (
    as_text,
    extract_heading_chunks,
    extract_wiki_links,
    parse_frontmatter,
    split_inline_list,
)


def test_parse_frontmatter_keeps_existing_scalar_and_list_contract() -> None:
    text = """---
id: sample-page
title: "Sample Page"
tags: [alpha, "beta, gamma"]
use_count: 3
last_used: null
useful_when:
  - "checking list parsing"
---
# Body
"""

    frontmatter, body = parse_frontmatter(text)

    assert frontmatter == {
        "id": "sample-page",
        "title": "Sample Page",
        "tags": ["alpha", "beta, gamma"],
        "use_count": 3,
        "last_used": None,
        "useful_when": ["checking list parsing"],
    }
    assert body == "\n# Body\n"


def test_parse_frontmatter_returns_text_when_missing_or_unclosed() -> None:
    assert parse_frontmatter("plain text") == ({}, "plain text")
    assert parse_frontmatter("---\nid: broken\nplain") == ({}, "---\nid: broken\nplain")


def test_split_inline_list_respects_quoted_commas() -> None:
    assert split_inline_list("alpha, 'beta, gamma', delta") == ["alpha", " 'beta, gamma'", " delta"]


def test_as_text_matches_existing_search_index_contract() -> None:
    assert as_text(["alpha", "beta"]) == "alpha beta"
    assert as_text(None) == ""
    assert as_text(7) == "7"


def test_extract_wiki_links_slugifies_targets_and_reports_lines() -> None:
    body = "Intro [[First Page|label]]\nNo link\nSee [[Second Page#Section]] and [[ ]]"

    assert extract_wiki_links(body) == [
        {"target_id": "first-page", "kind": "wikilink", "line": 1},
        {"target_id": "second-page", "kind": "wikilink", "line": 3},
        {"target_id": "plan", "kind": "wikilink", "line": 3},
    ]


def test_extract_heading_chunks_preserves_heading_path_and_start_line() -> None:
    body = """Lead text
# Overview
Intro
## Retrieval Contract
Details
# Next
Tail
"""

    assert extract_heading_chunks(body) == [
        {"heading_path": "Page", "content": "Lead text", "start_line": 1},
        {"heading_path": "Overview", "content": "Intro", "start_line": 3},
        {"heading_path": "Overview > Retrieval Contract", "content": "Details", "start_line": 5},
        {"heading_path": "Next", "content": "Tail", "start_line": 7},
    ]
