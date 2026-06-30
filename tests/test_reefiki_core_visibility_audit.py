import json
from pathlib import Path

import pytest

from scripts import reefiki
from scripts.reefiki_core.index_search import build_index
from scripts.reefiki_core.visibility_audit import (
    load_visibility_queries_file,
    visibility_audit_payload,
)


def write_page(project: Path, relative_path: str, page_id: str, body: str) -> None:
    path = project / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {page_id}
type: concept
title: "{page_id}"
tags: [visibility]
useful_when:
  - "testing visibility audit"
sources: [current-test]
date_added: 2020-01-01
use_count: 0
last_used: null
---
{body}
""",
        encoding="utf-8",
    )


def write_fixture_project(root: Path) -> Path:
    project = root / "projects" / "reefiki"
    write_page(
        project,
        "wiki/concepts/alpha-guide.md",
        "alpha-guide",
        "Alpha durable retrieval answer with citation-ready guidance.",
    )
    write_page(
        project,
        "wiki/concepts/beta-guide.md",
        "beta-guide",
        "Beta page exists for an unrelated operator workflow.",
    )
    return project


def test_visibility_audit_payload_groups_answerable_weak_and_missing_cases(tmp_path: Path) -> None:
    write_fixture_project(tmp_path)
    cases = [
        {
            "id": "answerable-alpha",
            "query": "alpha durable retrieval answer",
            "expected_ids": ["alpha-guide"],
        },
        {
            "id": "weak-beta",
            "query": "alpha durable retrieval answer",
            "expected_ids": ["beta-guide"],
        },
        {
            "id": "missing-gamma",
            "query": "zzzznotfoundunique",
            "expected_ids": ["gamma-guide"],
        },
    ]

    payload = visibility_audit_payload(
        tmp_path,
        "reefiki",
        cases,
        query_source="fixture",
        limit=3,
        stale_days=1,
        allow_rebuild_index=True,
    )

    assert payload["read_only"] is False
    assert payload["wiki_read_only"] is True
    assert payload["summary"] == {"answerable": 1, "weak": 1, "missing": 1, "total": 3}
    assert [item["id"] for item in payload["groups"]["answerable"]] == ["answerable-alpha"]
    assert [item["id"] for item in payload["groups"]["weak"]] == ["weak-beta"]
    assert [item["id"] for item in payload["groups"]["missing"]] == ["missing-gamma"]

    answerable = payload["queries"][0]
    assert answerable["status"] == "answerable"
    assert answerable["citation_coverage"]["coverage"] == 1.0
    assert answerable["retrieved"][0]["id"] == "alpha-guide"
    assert answerable["stale_noisy_contributors"][0]["page_id"] == "alpha-guide"
    assert answerable["stale_noisy_contributors"][0]["queue_type"] == "stale_review"

    weak = payload["queries"][1]
    assert weak["status"] == "weak"
    assert "missing_expected_ids:beta-guide" in weak["reasons"]
    assert weak["citation_coverage"]["missing_expected_ids"] == ["beta-guide"]

    missing = payload["queries"][2]
    assert missing["status"] == "missing"
    assert "no_retrieved_pages" in missing["reasons"]
    assert missing["suggested_improvements"]


def test_inline_query_without_expected_ids_is_weak_and_exit_zero(tmp_path: Path, capsys) -> None:
    write_fixture_project(tmp_path)

    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "visibility-audit",
            "--project-name",
            "reefiki",
            "--query",
            "alpha durable retrieval answer",
            "--rebuild-index",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["summary"] == {"answerable": 0, "weak": 1, "missing": 0, "total": 1}
    assert payload["queries"][0]["status"] == "weak"
    assert "no_expected_ids" in payload["queries"][0]["reasons"]


def test_cli_requires_explicit_rebuild_when_index_is_missing(tmp_path: Path) -> None:
    write_fixture_project(tmp_path)

    with pytest.raises(SystemExit, match="Missing wiki search index"):
        reefiki.main(
            [
                "--project",
                str(tmp_path),
                "visibility-audit",
                "--project-name",
                "reefiki",
                "--query",
                "alpha durable retrieval answer",
                "--format",
                "json",
            ]
        )


def test_from_golden_text_output_groups_known_query(tmp_path: Path, capsys) -> None:
    project = write_fixture_project(tmp_path)
    (project / "golden-queries.yml").write_text(
        """
version: 1
project: reefiki
queries:
  - id: lookup-alpha
    kind: lookup
    query: alpha durable retrieval answer
    layer: reefiki
    expect_ids: [alpha-guide]
""".lstrip(),
        encoding="utf-8",
    )

    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "visibility-audit",
            "--project-name",
            "reefiki",
            "--from-golden",
            "--rebuild-index",
            "--format",
            "text",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "summary: answerable 1, weak 0, missing 0, total 1" in output
    assert "- answerable: lookup-alpha" in output


def test_rebuild_index_refreshes_existing_search_cache(tmp_path: Path, capsys) -> None:
    project = tmp_path / "projects" / "reefiki"
    write_page(
        project,
        "wiki/concepts/old-guide.md",
        "old-guide",
        "Old page indexed before the alpha guide exists.",
    )
    build_index(project)
    write_page(
        project,
        "wiki/concepts/alpha-guide.md",
        "alpha-guide",
        "Alpha durable retrieval answer with citation-ready guidance.",
    )

    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "visibility-audit",
            "--project-name",
            "reefiki",
            "--query",
            "alpha durable retrieval answer",
            "--expect-id",
            "alpha-guide",
            "--rebuild-index",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["summary"] == {"answerable": 1, "weak": 0, "missing": 0, "total": 1}
    assert payload["queries"][0]["citation_coverage"]["coverage"] == 1.0


def test_load_visibility_queries_file_accepts_expected_ids(tmp_path: Path) -> None:
    queries_file = tmp_path / "cases.json"
    queries_file.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "id": "routing",
                        "query": "routing promotion contract",
                        "expected_ids": ["routing-contract"],
                    },
                    {
                        "id": "legacy-key",
                        "query": "memory control plane",
                        "expect_ids": ["global-memory-orchestration-cli"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_visibility_queries_file(queries_file) == [
        {
            "id": "routing",
            "query": "routing promotion contract",
            "expected_ids": ["routing-contract"],
        },
        {
            "id": "legacy-key",
            "query": "memory control plane",
            "expected_ids": ["global-memory-orchestration-cli"],
        },
    ]
