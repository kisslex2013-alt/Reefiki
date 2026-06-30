from pathlib import Path

import pytest

from scripts.reefiki_core.memory_golden import (
    load_golden_queries,
    print_memory_golden_result,
    run_golden_queries,
)


def test_load_golden_queries_parses_supported_case_fields(tmp_path: Path) -> None:
    golden = tmp_path / "golden-queries.yml"
    golden.write_text(
        """
# comments are ignored
version: 1
queries:
  - id: lookup-routing
    kind: lookup
    layer: reefiki
    limit: 5
    query: routing contract
    expect_ids: [reefiki-routing-and-promotion-contract, "global-memory-orchestration-cli"]
  - id: promote-decision
    kind: promote
    content: We decided to keep explicit promotion review.
    expect_verdict: promote
    expect_target_type: decision
  - id: memoir-only
    kind: promote
    expect_target_type: null
""".lstrip(),
        encoding="utf-8",
    )

    payload = load_golden_queries(golden)

    assert payload["version"] == 1
    assert payload["queries"] == [
        {
            "id": "lookup-routing",
            "kind": "lookup",
            "layer": "reefiki",
            "limit": 5,
            "query": "routing contract",
            "expect_ids": [
                "reefiki-routing-and-promotion-contract",
                "global-memory-orchestration-cli",
            ],
        },
        {
            "id": "promote-decision",
            "kind": "promote",
            "content": "We decided to keep explicit promotion review.",
            "expect_verdict": "promote",
            "expect_target_type": "decision",
        },
        {
            "id": "memoir-only",
            "kind": "promote",
            "expect_target_type": None,
        },
    ]


def test_load_golden_queries_blocks_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yml"

    with pytest.raises(SystemExit, match="Missing golden query file"):
        load_golden_queries(missing)


def test_print_memory_golden_result_reports_failures(capsys: pytest.CaptureFixture[str]) -> None:
    result = {
        "project": "reefiki",
        "passed": 1,
        "total": 2,
        "failed": 1,
        "cases": [
            {"status": "pass", "id": "known"},
            {"status": "fail", "id": "missing"},
        ],
    }

    assert print_memory_golden_result(result, "text") == 1
    assert capsys.readouterr().out == (
        "project: reefiki\n"
        "golden: 1/2 passed\n"
        "  - pass: known\n"
        "  - fail: missing\n"
    )


def test_run_golden_queries_uses_injected_helpers(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    golden = project / "golden-queries.yml"
    golden.write_text(
        """
version: 1
project: reefiki
queries:
  - id: lookup-routing
    kind: lookup
    layer: all
    query: routing contract
    expect_ids: [routing-contract]
  - id: promote-decision
    kind: promote
    content: Keep promotion review.
    expect_verdict: promote
    expect_target_type: decision
  - id: pack-handoff
    kind: pack
    task: REEFIKI 2 memory pack
    expect_ids: [reefiki-2-control-plane-spec]
    expect_route_layer: reefiki
""".lstrip(),
        encoding="utf-8",
    )
    lookup_calls = []
    promote_calls = []
    pack_calls = []

    def fake_project_local_lookup(_project: Path, _query: str, limit: int = 5) -> list[dict[str, object]]:
        raise AssertionError("lookup layer should use global helper for non-reefiki layer")

    def fake_global_lookup(root: Path, **kwargs: object) -> dict[str, object]:
        lookup_calls.append((root, kwargs))
        return {
            "reefiki": [
                {"id": "routing-contract"},
            ]
        }

    def fake_promotion_dry_run(project_path: Path, content: str, confidence: float = 0.8) -> dict[str, object]:
        promote_calls.append((project_path, content, confidence))
        return {"verdict": "promote", "suggested_target_type": "decision"}

    def fake_memory_pack(root: Path, project_name: str, task: str, limit: int = 8, include_golden: bool = True) -> dict[str, object]:
        pack_calls.append((root, project_name, task, limit, include_golden))
        return {
            "contents": [{"id": "reefiki-2-control-plane-spec"}],
            "task_route": {"route_decision": {"recommended_layer": "reefiki"}},
            "assembly_trace": {"pack_scope": {"source_layers": ["reefiki"]}},
        }

    payload = run_golden_queries(
        tmp_path,
        "reefiki",
        project_local_lookup_fn=fake_project_local_lookup,
        global_lookup_fn=fake_global_lookup,
        promotion_dry_run_fn=fake_promotion_dry_run,
        memory_pack_fn=fake_memory_pack,
    )

    assert payload["passed"] == 3
    assert lookup_calls == [
        (
            tmp_path,
                {
                    "query": "routing contract",
                    "project": "reefiki",
                    "include_memoir": True,
                    "include_reefiki": True,
                    "include_graph": True,
                    "limit": 5,
                },
        )
    ]
    assert promote_calls == [(project, "Keep promotion review.", 0.8)]
    assert pack_calls == [(tmp_path, "reefiki", "REEFIKI 2 memory pack", 8, False)]


def test_run_golden_queries_validates_graphify_lookup_hits(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    (project / "golden-queries.yml").write_text(
        """
version: 1
project: reefiki
queries:
  - id: lookup-graph-node
    kind: lookup
    layer: graphify
    query: memory lookup graph
    expect_ids: [scripts_reefiki_core_memory_lookup_py]
""".lstrip(),
        encoding="utf-8",
    )

    def fake_project_local_lookup(_project: Path, _query: str, limit: int = 5) -> list[dict[str, object]]:
        raise AssertionError("graphify layer should use global helper")

    def fake_global_lookup(root: Path, **kwargs: object) -> dict[str, object]:
        return {
            "graphify": [
                {"node_id": "scripts_reefiki_core_memory_lookup_py"},
            ],
            "reefiki": [],
        }

    payload = run_golden_queries(
        tmp_path,
        "reefiki",
        project_local_lookup_fn=fake_project_local_lookup,
        global_lookup_fn=fake_global_lookup,
        promotion_dry_run_fn=lambda *_args, **_kwargs: {},
        memory_pack_fn=lambda *_args, **_kwargs: {},
    )

    assert payload["passed"] == 1
    assert payload["cases"][0]["details"]["actual_ids"] == ["scripts_reefiki_core_memory_lookup_py"]
