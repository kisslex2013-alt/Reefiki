import json
from pathlib import Path

from scripts import reefiki
from scripts.reefiki_core.notify import notify_payload


def test_notify_payload_builds_review_ready_dry_run() -> None:
    payload = notify_payload(
        event="review-ready",
        task_id="T-154",
        source_artifact="verify-intent.json",
        reason="Verifier accepted the implementation report.",
        next_action="Parent TeamLead can review and publish.",
        evidence_pointer="verify-intent.json#/outcome",
    )

    notification = payload["notification"]
    assert payload["status"] == "ready"
    assert payload["read_only"] is True
    assert payload["actions"] == []
    assert notification["event"] == "review_ready"
    assert notification["severity"] == "info"
    assert notification["task_id"] == "T-154"
    assert notification["source_artifact"] == "verify-intent.json"
    assert notification["reason"] == "Verifier accepted the implementation report."
    assert notification["next_action"] == "Parent TeamLead can review and publish."
    assert notification["evidence_pointer"] == "verify-intent.json#/outcome"
    assert notification["fingerprint"]
    assert payload["delivery"]["mode"] == "dry_run"
    assert payload["delivery"]["network"] == "disabled"
    assert payload["delivery"]["sent"] is False


def test_notify_payload_marks_repeated_unchanged_status_as_already_reported() -> None:
    first = notify_payload(
        event="blocked",
        source_artifact="publish-dry-run.json",
        reason="Public snapshot scan blocked a secret-like path.",
        next_action="Remove the path and rerun publish dry-run.",
        evidence_pointer="publish-dry-run.json#/blocking_paths/0",
    )
    repeated = notify_payload(
        event="blocked",
        source_artifact="publish-dry-run.json",
        reason="Public snapshot scan blocked a secret-like path.",
        next_action="Remove the path and rerun publish dry-run.",
        evidence_pointer="publish-dry-run.json#/blocking_paths/0",
        previous_fingerprints=[first["notification"]["fingerprint"]],
    )

    assert repeated["status"] == "already_reported"
    assert repeated["dedupe"]["already_reported"] is True
    assert repeated["notification"]["fingerprint"] == first["notification"]["fingerprint"]


def test_notify_cli_defaults_to_stdout_only(capsys, tmp_path) -> None:
    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "notify",
            "--event",
            "failed",
            "--source-artifact",
            "pytest.log",
            "--reason",
            "Focused tests failed.",
            "--next-action",
            "Fix the regression and rerun tests.",
            "--evidence-pointer",
            "pytest.log#L12",
            "--task-id",
            "T-154",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["notification"]["event"] == "failed"
    assert payload["notification"]["severity"] == "error"
    assert payload["delivery"]["network"] == "disabled"
    assert payload["delivery"]["sent"] is False
    assert payload["actions"] == []
    assert not (tmp_path / "docs" / "notifications").exists()


def test_notify_cli_accepts_previous_fingerprint_for_dedupe(capsys) -> None:
    first = notify_payload(
        event="review_ready",
        source_artifact="handoff.md",
        reason="Review queue is ready.",
        next_action="Review the handoff.",
        evidence_pointer="handoff.md#closeout",
    )
    code = reefiki.main(
        [
            "notify",
            "--event",
            "review_ready",
            "--source-artifact",
            "handoff.md",
            "--reason",
            "Review queue is ready.",
            "--next-action",
            "Review the handoff.",
            "--evidence-pointer",
            "handoff.md#closeout",
            "--previous-fingerprint",
            first["notification"]["fingerprint"],
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "already_reported"
    assert payload["dedupe"]["already_reported"] is True


def test_notify_adapter_config_is_dry_run_reference_only() -> None:
    payload = notify_payload(
        event="review_ready",
        source_artifact="handoff.md",
        reason="Review queue is ready.",
        next_action="Review the handoff.",
        evidence_pointer="handoff.md#closeout",
        adapter_config="telegram://teamlead-alerts",
    )

    assert payload["delivery"]["adapter_config"] == "telegram://teamlead-alerts"
    assert payload["delivery"]["mode"] == "dry_run"
    assert payload["delivery"]["network"] == "disabled"
    assert payload["delivery"]["sent"] is False
    assert payload["actions"] == []


def test_notify_docs_show_no_network_contract() -> None:
    commands = Path("COMMANDS.md").read_text(encoding="utf-8")

    assert "reefiki.py notify" in commands
    assert "no-network" in commands
