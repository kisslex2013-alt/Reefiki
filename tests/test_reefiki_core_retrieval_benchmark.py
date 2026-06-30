import json
from datetime import date
from pathlib import Path

import pytest

import scripts.reefiki_core.retrieval_benchmark as benchmark
from scripts.reefiki_core.retrieval_benchmark import (
    print_retrieval_benchmark,
    retrieval_benchmark_payload,
)

pytestmark = [pytest.mark.benchmark, pytest.mark.memory]


def write_page(project: Path, slug: str, title: str, body: str) -> None:
    target = project / "wiki" / "concepts"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{slug}.md").write_text(
        f"""---
id: {slug}
type: concept
title: "{title}"
tags: [benchmark]
useful_when:
  - "testing retrieval benchmark"
date_added: 2026-06-14
use_count: 0
last_used: null
---

{body}
""",
        encoding="utf-8",
    )


def write_qmd_candidate_page(project: Path) -> None:
    target = project / "wiki" / "synthesis"
    target.mkdir(parents=True, exist_ok=True)
    (target / "qmd-retrieval-experiment.md").write_text(
        """---
id: qmd-retrieval-experiment
type: synthesis
title: "qmd retrieval experiment"
tags: [qmd, retrieval]
useful_when:
  - "evaluating qmd as an optional retrieval adapter"
date_added: 2026-06-09
use_count: 0
last_used: null
---

qmd is a sandboxed optional retrieval adapter candidate.
""",
        encoding="utf-8",
    )


def write_fixture_repo(root: Path) -> Path:
    project = root / "projects" / "reefiki"
    project.mkdir(parents=True)
    write_qmd_candidate_page(project)
    write_page(project, "alpha-memory", "Alpha memory", "alpha routing promotion contract")
    write_page(project, "beta-search", "Beta search", "beta markdown retrieval benchmark")
    (project / "golden-queries.yml").write_text(
        """version: 1
project: reefiki
queries:
  - id: lookup-alpha
    kind: lookup
    query: alpha routing
    layer: reefiki
    expect_ids: [alpha-memory]
  - id: lookup-beta
    kind: lookup
    query: beta retrieval
    layer: reefiki
    expect_ids: [beta-search]
  - id: promote-not-included
    kind: promote
    content: should not enter retrieval benchmark
    expect_verdict: promote
""",
        encoding="utf-8",
    )
    return project


def test_qmd_benchmark_compares_fts_and_qmd_results(tmp_path: Path) -> None:
    write_fixture_repo(tmp_path)
    qmd_results = tmp_path / "qmd-results.json"
    qmd_results.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "id": "lookup-alpha",
                        "results": [{"docid": "#abc123", "file": "qmd://reefiki-benchmark/concepts/alpha-memory.md"}],
                    },
                    {
                        "id": "lookup-beta",
                        "results": [{"path": "wiki/concepts/missing.md"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = retrieval_benchmark_payload(tmp_path, "reefiki", "qmd", qmd_results_path=qmd_results)

    assert payload["outcome"] == "benchmark-complete"
    assert payload["fixed_corpus_count"] == 2
    assert payload["summary"]["fts_hits"] == 2
    assert payload["summary"]["qmd_hits"] == 1
    assert payload["summary"]["regressed"] == 1
    assert payload["go_no_go"] == "keep-disabled"
    assert payload["cases"][1]["qmd"]["missing_ids"] == ["beta-search"]


def test_qmd_benchmark_without_qmd_results_is_incomplete(tmp_path: Path) -> None:
    write_fixture_repo(tmp_path)

    payload = retrieval_benchmark_payload(tmp_path, "reefiki", "qmd")

    assert payload["outcome"] == "benchmark-incomplete"
    assert payload["qmd_status"] == "not-run"
    assert payload["summary"]["fts_hits"] == 2
    assert payload["summary"]["qmd_hits"] is None
    assert payload["go_no_go"] == "collect-qmd-results"


def test_qmd_benchmark_cleanup_generated_paths(tmp_path: Path) -> None:
    project = write_fixture_repo(tmp_path)
    generated = project / ".qmd"
    generated.mkdir()
    (generated / "index.sqlite").write_text("generated", encoding="utf-8")

    payload = retrieval_benchmark_payload(tmp_path, "reefiki", "qmd", cleanup_generated=True)

    assert payload["generated_paths_cleanup"]["removed"] == ["projects/reefiki/.qmd"]
    assert payload["generated_paths_cleanup"]["failed"] == []
    assert not generated.exists()


def test_qmd_benchmark_reports_cleanup_failure(monkeypatch, tmp_path: Path) -> None:
    write_fixture_repo(tmp_path)

    def fail_remove(_root: Path, _path: Path) -> bool:
        raise OSError("locked")

    monkeypatch.setattr(benchmark, "_safe_remove", fail_remove)

    payload = retrieval_benchmark_payload(tmp_path, "reefiki", "qmd", cleanup_generated=True)

    assert payload["generated_paths_cleanup"]["failed"][0]["path"] == "projects/reefiki/.qmd"
    assert payload["generated_paths_cleanup"]["failed"][0]["reason"] == "locked"


def test_print_retrieval_benchmark_writes_report(capsys, tmp_path: Path) -> None:
    write_fixture_repo(tmp_path)

    assert print_retrieval_benchmark(tmp_path, "reefiki", "qmd", 5, None, True, True, "json") == 0

    output = capsys.readouterr().out
    assert '"candidate": "qmd"' in output
    report = tmp_path / "docs" / "retrieval" / f"qmd-benchmark-{date.today().isoformat()}.md"
    assert report.exists()
    assert "qmd retrieval benchmark" in report.read_text(encoding="utf-8")
