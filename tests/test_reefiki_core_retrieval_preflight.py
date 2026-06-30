from pathlib import Path

from scripts.reefiki_core.retrieval_preflight import (
    print_retrieval_preflight,
    retrieval_preflight_payload,
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


def write_fixture_repo(root: Path) -> None:
    project = root / "projects" / "reefiki"
    (project / "wiki").mkdir(parents=True, exist_ok=True)
    write_qmd_candidate_page(project)


def test_qmd_preflight_is_experiment_ready_without_runtime_adoption(tmp_path: Path) -> None:
    write_fixture_repo(tmp_path)

    payload = retrieval_preflight_payload(tmp_path, "reefiki", "qmd")

    assert payload["candidate"] == "qmd"
    assert payload["outcome"] == "experiment-ready"
    assert payload["runtime_adoption"] == "blocked"
    assert payload["evidence"]["durable_page"] == "wiki/synthesis/qmd-retrieval-experiment.md"
    assert "sandbox_smoke" in payload["allowed_actions"]
    assert "mcp_daemon" in payload["blocked_actions"]


def test_qmd_preflight_requires_misses_and_explicit_flag_for_runtime_eval(tmp_path: Path) -> None:
    write_fixture_repo(tmp_path)

    payload = retrieval_preflight_payload(
        tmp_path,
        "reefiki",
        "qmd",
        observed_misses=3,
        allow_runtime_eval=True,
    )

    assert payload["outcome"] == "runtime-eval-ready"
    assert payload["runtime_adoption"] == "evaluate-only"
    assert "compare_against_current_fts" in payload["required_gates"]


def test_qmd_preflight_marks_missing_durable_page_as_watch(tmp_path: Path) -> None:
    (tmp_path / "projects" / "reefiki" / "wiki").mkdir(parents=True)

    payload = retrieval_preflight_payload(tmp_path, "reefiki", "qmd")

    assert payload["outcome"] == "watch"
    assert payload["runtime_adoption"] == "blocked"
    assert payload["evidence"]["durable_page"] is None
    assert "create_or_link_durable_candidate_page" in payload["required_gates"]


def test_print_retrieval_preflight_json(capsys, tmp_path: Path) -> None:
    write_fixture_repo(tmp_path)

    assert print_retrieval_preflight(tmp_path, "reefiki", "qmd", 0, False, "json") == 0

    output = capsys.readouterr().out
    assert '"candidate": "qmd"' in output
    assert '"outcome": "experiment-ready"' in output
