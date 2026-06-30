import json
from textwrap import dedent

from scripts import reefiki
from scripts.reefiki_core.obligations_extract import obligations_extract_payload


def test_obligations_extract_groups_fixture_obligations() -> None:
    markdown = dedent(
        """\
        # Handoff

        - Next action: create a fresh worktree for T-152.
        - Blocker: do not publish until guard-staged passes.
        - Evidence required: full pytest output and publish dry-run JSON.
        - Owner boundary: child verifier must not push, publish or cleanup.
        - Deferred follow-up: add notification adapter after the core report exists.
        - Context only: Sprint 28 is local-first.
        """
    )

    payload = obligations_extract_payload({"handoff.md": markdown})

    assert payload["summary"]["total"] == 5
    assert payload["summary"]["by_group"] == {
        "next_action": 1,
        "blocker": 1,
        "evidence": 1,
        "owner_boundary": 1,
        "deferred_follow_up": 1,
    }
    first = payload["obligations"][0]
    assert first["text"] == "create a fresh worktree for T-152."
    assert first["source_artifact"] == "handoff.md"
    assert first["line"] == 3
    assert first["heading"] == "Handoff"
    assert first["owner_class"] == "unspecified"
    assert first["due_trigger"] == "next review"
    assert first["required_evidence"] == "completion evidence"
    assert first["status"] == "open"
    assert first["confidence"] == 0.95
    blocker = payload["groups"]["blocker"][0]
    assert blocker["status"] == "blocked"
    assert blocker["due_trigger"] == "until guard-staged passes"
    assert blocker["required_evidence"] == "blocker resolution evidence"
    boundary = payload["groups"]["owner_boundary"][0]
    assert boundary["owner_class"] == "child_agent"
    assert {item["group"] for item in payload["obligations"]} == set(payload["groups"])


def test_obligations_extract_ignores_non_obligation_text() -> None:
    payload = obligations_extract_payload(
        {
            "notes.md": dedent(
                """\
                # Notes

                This page describes the background.
                It has useful context but no direct follow-up.
                """
            )
        }
    )

    assert payload["summary"]["total"] == 0
    assert payload["obligations"] == []
    assert all(not rows for rows in payload["groups"].values())


def test_obligations_extract_keeps_real_tasks_excerpt_context() -> None:
    payload = obligations_extract_payload(
        {
            "TASKS.md": dedent(
                """\
                ## Sprint 28

                - [ ] **T-152** Add `obligations extract` for plans, handoffs and decisions
                  - Trigger: REEFIKI plans and TeamLead reports often contain implicit next actions, blockers, evidence needs and owner boundaries.
                  - Scope: extract obligation text, owner class, due trigger, required evidence, source artifact and status into a reviewable local artifact.
                  - Validation: fixture markdown plans/decisions plus one real roadmap/handoff sample.
                """
            )
        }
    )

    assert payload["summary"]["total"] >= 2
    assert payload["obligations"][0]["source_artifact"] == "TASKS.md"
    assert payload["obligations"][0]["heading"] == "Sprint 28"
    assert any(item["group"] == "evidence" for item in payload["obligations"])
    assert all(not item["text"].startswith("Trigger:") for item in payload["obligations"])
    assert all(item["group"] != "blocker" for item in payload["obligations"])


def test_obligations_extract_cli_defaults_to_stdout_only(tmp_path, capsys) -> None:
    source = tmp_path / "handoff.md"
    source.write_text("- Next action: run the verifier before closeout.\n", encoding="utf-8")

    code = reefiki.main(
        [
            "obligations-extract",
            "--source",
            str(source),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["summary"]["total"] == 1
    assert payload["report_path"] is None
    assert not (tmp_path / "docs" / "obligations").exists()


def test_obligations_extract_cli_uses_source_hint_for_inline_text(capsys) -> None:
    code = reefiki.main(
        [
            "obligations-extract",
            "--text",
            "- Next action: accept verifier evidence.",
            "--source-hint",
            "teamlead-closeout",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["inputs"]["source_hint"] == "teamlead-closeout"
    assert payload["inputs"]["source_artifacts"] == ["teamlead-closeout"]
    assert payload["obligations"][0]["source_artifact"] == "teamlead-closeout"


def test_obligations_extract_cli_writes_report_only_when_requested(tmp_path, capsys) -> None:
    source = tmp_path / "handoff.md"
    report = tmp_path / "drafts" / "obligations.md"
    source.write_text("- Blocker: wait for publish dry-run evidence.\n", encoding="utf-8")

    code = reefiki.main(
        [
            "obligations-extract",
            "--source",
            str(source),
            "--write-report",
            "--report-path",
            str(report),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["report_path"] == str(report)
    assert report.exists()
    assert "wait for publish dry-run evidence" in report.read_text(encoding="utf-8")
