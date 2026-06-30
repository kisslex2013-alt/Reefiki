from pathlib import Path

from scripts.reefiki_core.adapters import adapter_call_payload


def write_fixture_project(root: Path) -> Path:
    project = root / "projects" / "reefiki"
    (project / "wiki" / "concepts").mkdir(parents=True)
    for dirname in ["inbox", "raw", "seen"]:
        (project / dirname).mkdir(parents=True, exist_ok=True)
    (project / "wiki" / "log.md").write_text("", encoding="utf-8")
    (project / "_domain.md").write_text("adapter fixture\n", encoding="utf-8")
    (project / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (project / "wiki" / "concepts" / "adapter-contract.md").write_text(
        """---
id: adapter-contract
type: concept
title: "Adapter Contract"
tags: [adapter]
useful_when:
  - "checking adapter query results"
date_added: 2026-06-12
use_count: 0
last_used: null
---

# Adapter Contract

The adapter exposes query, save and status over a local JSON call surface.
""",
        encoding="utf-8",
    )
    (project / "wiki" / "index.md").write_text(
        """# Index

Last updated: 2026-06-12
Total pages: 1

## Sources
## Entities
## Concepts

### adapter-contract
- type: concept
- tags: [adapter]
- useful_when: ["checking adapter query results"]
- file: wiki/concepts/adapter-contract.md
- date_added: 2026-06-12
- use_count: 0

## Synthesis
## Decisions
## Skills
""",
        encoding="utf-8",
    )
    return project


def test_adapter_status_is_read_only(tmp_path: Path) -> None:
    write_fixture_project(tmp_path)

    payload = adapter_call_payload(tmp_path, "reefiki_status", "reefiki", {})

    assert payload["outcome"] == "pass"
    assert payload["read_only"] is True
    assert "Project: reefiki" in payload["status_text"]


def test_adapter_query_returns_compact_results(tmp_path: Path) -> None:
    write_fixture_project(tmp_path)

    payload = adapter_call_payload(
        tmp_path,
        "reefiki_query",
        "reefiki",
        {"query": "adapter", "limit": 3},
    )

    assert payload["outcome"] == "pass"
    assert payload["read_only"] is True
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "adapter-contract"


def test_adapter_save_blocks_without_explicit_write(tmp_path: Path) -> None:
    project = write_fixture_project(tmp_path)

    payload = adapter_call_payload(
        tmp_path,
        "reefiki_save",
        "reefiki",
        {"source": "https://example.com/adapter"},
    )

    assert payload["outcome"] == "block"
    assert payload["blocking_reasons"] == ["write_requires_allow_write"]
    assert list((project / "inbox").glob("*.md")) == []


def test_adapter_save_delegates_to_save_source_when_allowed(tmp_path: Path) -> None:
    project = write_fixture_project(tmp_path)

    payload = adapter_call_payload(
        tmp_path,
        "reefiki_save",
        "reefiki",
        {"source": "https://example.com/adapter"},
        allow_write=True,
    )

    assert payload["outcome"] == "pass"
    assert payload["read_only"] is False
    assert "Saved: inbox/example-com-adapter.md" in payload["save_text"]
    assert (project / "inbox" / "example-com-adapter.md").read_text(encoding="utf-8") == "https://example.com/adapter\n"
