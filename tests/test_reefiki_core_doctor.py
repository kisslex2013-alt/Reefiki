from scripts.reefiki_core.doctor import doctor_payload
from scripts.reefiki_core.index_search import build_index


def test_doctor_payload_reports_missing_required_paths(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    payload = doctor_payload(project)

    assert payload["outcome"] == "fail"
    assert "missing_required_path" in {issue["code"] for issue in payload["issues"]}
    assert payload["index"]["status"] == "missing"


def test_doctor_payload_passes_with_current_index(tmp_path) -> None:
    project = tmp_path / "project"
    for directory in ["raw", "inbox", "seen", "wiki/concepts"]:
        (project / directory).mkdir(parents=True, exist_ok=True)
    (project / "AGENTS.md").write_text("# Contract\n", encoding="utf-8")
    (project / "_domain.md").write_text("# Domain\n", encoding="utf-8")
    (project / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")
    (project / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    (project / "wiki" / "concepts" / "runbook.md").write_text(
        """---
id: runbook
type: concept
title: "Runbook"
tags: [test]
useful_when:
  - "checking doctor payload against a freshly rebuilt sqlite index"
date_added: 2026-06-11
use_count: 0
---
Body.
""",
        encoding="utf-8",
    )
    build_index(project)

    payload = doctor_payload(project)

    assert payload["outcome"] == "pass"
    assert payload["issues"] == []
    assert payload["index"]["status"] == "ok"
    assert payload["index"]["page_count"] == 1
    assert payload["index"]["wiki_page_count"] == 1
