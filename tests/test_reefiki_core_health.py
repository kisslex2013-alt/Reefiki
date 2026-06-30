import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from reefiki_core.health import dashboard_next_action, knowledge_health_payload


def write_page(project, relative_path, text):
    path = project / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_health_payload_reports_inbox_and_zero_use_warning(tmp_path):
    project = tmp_path / "reefiki"
    write_page(
        project,
        "wiki/concepts/example.md",
        """---
id: example
type: concept
title: "Example"
tags: [health]
useful_when:
  - "checks health payload warning behavior with enough practical words for this focused package test"
sources: [local-test]
date_added: 2026-05-14
use_count: 0
last_used: null
---
Body.
""",
    )
    (project / "inbox").mkdir(parents=True)
    (project / "inbox" / "source.md").write_text("pending", encoding="utf-8")
    (project / "seen").mkdir()
    (project / "seen" / "old.md").write_text("seen", encoding="utf-8")

    payload = knowledge_health_payload(project)

    assert payload["size"]["wiki_pages"] == 1
    assert payload["size"]["inbox_items"] == 1
    assert payload["usage"]["zero_use_pages"] == 1
    assert {warning["code"] for warning in payload["warnings"]} >= {"high_zero_use_ratio", "inbox_pending"}


def test_dashboard_next_action_prefers_doctor_then_queue_then_inbox():
    assert dashboard_next_action({"outcome": "fail", "warnings": []}, {"queues": []}, 2) == "run doctor and fix integrity issues"
    assert dashboard_next_action(
        {"outcome": "warn", "warnings": [{"code": "broken_links"}]},
        {"queues": [{"queue_type": "orphan_review"}]},
        2,
    ) == "run review-queues --type placeholder_link --limit 2"
    assert dashboard_next_action(
        {"outcome": "warn", "warnings": [], "size": {"inbox_items": 1}},
        {"queues": []},
        2,
    ) == "run process on inbox items"
