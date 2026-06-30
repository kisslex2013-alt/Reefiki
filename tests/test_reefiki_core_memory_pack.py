from pathlib import Path

from scripts.reefiki_core.memory_pack import memory_pack, memory_pack_strict_result


def test_memory_pack_strict_result_collects_blocking_reasons() -> None:
    result = {
        "safety_outcome": "pass",
        "lookup_error": "unable to open database file",
        "quality": {
            "outcome": "warn",
            "violations": ["missing_required_ids"],
        },
        "golden": {
            "failed": 1,
        },
        "diff": {
            "error": "bad ref",
        },
    }

    assert memory_pack_strict_result(result) == {
        "outcome": "fail",
        "blocking_reasons": [
            "lookup:error",
            "quality:missing_required_ids",
            "golden:failed",
            "diff:error",
        ],
    }


def test_memory_pack_uses_injected_lookup_and_golden(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    (project / "wiki" / "synthesis").mkdir(parents=True)
    (project / "wiki" / "synthesis" / "reefiki-2-control-plane-spec.md").write_text(
        """---
id: reefiki-2-control-plane-spec
type: synthesis
title: "REEFIKI 2 control plane"
tags: [memory]
useful_when:
  - "build memory pack"
date_added: 2026-05-20
use_count: 0
last_used: null
---
REEFIKI 2 uses policy, lookup, golden queries and memory diff.
""",
        encoding="utf-8",
    )
    calls = []

    def fake_lookup(root, **kwargs):
        calls.append((root, kwargs))
        return {
            "reefiki": [
                {
                    "id": "matched-page",
                    "type": "skill",
                    "title": "Matched Page",
                    "file": "wiki/skills/matched-page.md",
                    "score": 0.5,
                }
            ]
        }

    def fake_golden(root, project_name):
        return {"path": "golden-queries.yml", "total": 1, "passed": 1, "failed": 0}

    result = memory_pack(
        tmp_path,
        "reefiki",
        "memory pack",
        global_lookup_fn=fake_lookup,
        run_golden_queries_fn=fake_golden,
        limit=8,
    )

    assert calls == [
        (
            tmp_path,
            {
                "query": "memory pack",
                "project": "reefiki",
                "include_memoir": False,
                "include_reefiki": True,
                "include_graph": False,
                "limit": 8,
            },
        )
    ]
    assert result["golden"] == {
        "path": "golden-queries.yml",
        "total": 1,
        "passed": 1,
        "failed": 0,
    }
    assert "reefiki-2-control-plane-spec" in [item["id"] for item in result["contents"]]


def test_memory_pack_uses_dogfood_profile_and_excludes_unrelated_open_design_hit(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    (project / "wiki" / "registries").mkdir(parents=True)
    (project / "wiki" / "synthesis").mkdir(parents=True)
    (project / "wiki" / "decisions").mkdir(parents=True)
    (tmp_path / "docs" / "skill-products").mkdir(parents=True)
    (tmp_path / "docs" / "ODYSSEUS_DOGFOOD.md").write_text(
        "# Odysseus Dogfood Plan\n\nOdysseus is an external dogfood workspace for REEFIKI.\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "skill-products" / "AGENT_READINESS_SPEC.md").write_text(
        "# Agent Readiness\n\nExternal repo onboarding and readiness checks.\n",
        encoding="utf-8",
    )
    pages = {
        "registries/external-tool-watchlist.md": (
            "external-tool-watchlist",
            "synthesis",
            "External tool watchlist",
            "Odysseus is tracked as a dogfood candidate, not a runtime dependency.",
        ),
        "synthesis/june-2026-roadmap-batch-recovery.md": (
            "june-2026-roadmap-batch-recovery",
            "synthesis",
            "Roadmap batch recovery",
            "Agent Readiness is a read-only external repo advisor.",
        ),
        "decisions/read-only-cross-project-query-boundary.md": (
            "read-only-cross-project-query-boundary",
            "decision",
            "Cross-project query boundary",
            "Cross-project query is read-only and keeps provenance.",
        ),
    }
    index_entries = []
    for rel_path, (page_id, page_type, title, body) in pages.items():
        page = project / "wiki" / rel_path
        page.write_text(
            f"""---
id: {page_id}
type: {page_type}
title: "{title}"
tags: [dogfood, external, roadmap]
useful_when:
  - "building an external dogfood pack"
date_added: 2026-06-12
use_count: 0
last_used: null
---
{body}
""",
            encoding="utf-8",
        )
        index_entries.append(
            f"""### {page_id}
- type: {page_type}
- tags: [dogfood, external, roadmap]
- useful_when: ["building an external dogfood pack"]
- file: wiki/{rel_path}
- date_added: 2026-06-12
- use_count: 0
"""
        )
    (project / "wiki" / "index.md").write_text(
        "# Index\n\n" + "\n".join(index_entries),
        encoding="utf-8",
    )

    def fake_lookup(root, **kwargs):
        return {
            "reefiki": [
                {
                    "id": "metrica-open-design-static-proof",
                    "type": "synthesis",
                    "title": "Metrica open-design static proof",
                    "file": "wiki/synthesis/metrica-open-design-static-proof.md",
                    "score": -3.0,
                },
                {
                    "id": "external-tool-watchlist",
                    "type": "synthesis",
                    "title": "External tool watchlist",
                    "file": "wiki/registries/external-tool-watchlist.md",
                    "score": 4.0,
                },
            ]
        }

    result = memory_pack(
        tmp_path,
        "reefiki",
        "Odysseus dogfood external repo onboarding",
        global_lookup_fn=fake_lookup,
        run_golden_queries_fn=lambda *_args: {"total": 0, "passed": 0, "failed": 0, "path": "golden-queries.yml"},
        limit=8,
        include_golden=False,
    )

    ids = [item["id"] for item in result["contents"]]
    assert ids[:5] == [
        "odysseus-dogfood-brief",
        "external-tool-watchlist",
        "june-2026-roadmap-batch-recovery",
        "agent-readiness-spec",
        "read-only-cross-project-query-boundary",
    ]
    assert "metrica-open-design-static-proof" not in ids
    assert result["task_route"]["route_decision"]["recommended_layer"] == "reefiki"
    assert result["quality"]["required_ids"] == ids[:5]
