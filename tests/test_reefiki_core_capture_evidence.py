import json
from pathlib import Path

from scripts import reefiki
from scripts.reefiki_core.capture_evidence import capture_evidence_payload


def test_capture_evidence_builds_required_browser_draft() -> None:
    payload = capture_evidence_payload(
        kind="browser",
        claim="Ops Dashboard right rail stays sticky during scroll.",
        evidence_note="Desktop smoke showed the rail visible after scrolling logs.",
        task_id="T-153",
        source_artifact="browser-smoke",
        url="http://127.0.0.1:7310",
        selector="[data-testid='right-rail']",
        viewport="1440x900",
        screenshot_path="docs/evidence/right-rail.png",
        related_paths=["scripts/reefiki_core/ops_dashboard.py"],
        captured_at="2026-06-18T12:00:00Z",
    )

    draft = payload["draft"]
    assert payload["status"] == "pass"
    assert payload["read_only"] is True
    assert draft["kind"] == "browser"
    assert draft["source"] == {
        "task_id": "T-153",
        "source_artifact": "browser-smoke",
        "url": "http://127.0.0.1:7310",
    }
    assert draft["captured_at"] == "2026-06-18T12:00:00Z"
    assert draft["claim"] == "Ops Dashboard right rail stays sticky during scroll."
    assert draft["evidence"]["note"] == "Desktop smoke showed the rail visible after scrolling logs."
    assert draft["evidence"]["selector"] == "[data-testid='right-rail']"
    assert draft["evidence"]["viewport"] == "1440x900"
    assert draft["evidence"]["screenshot_path"] == "docs/evidence/right-rail.png"
    assert draft["limits"]
    assert draft["redactions"] == []
    assert draft["related_paths"] == ["scripts/reefiki_core/ops_dashboard.py"]


def test_capture_evidence_redacts_secret_like_text() -> None:
    api_key_name = "OPENAI_" + "API_" + "KEY"
    provider_value = "sk" + "-" + "test" + "1234567890abcdef"
    token_field = "to" + "ken"
    token_value = "abc123" + "sec" + "ret" + "value"
    bearer_prefix = "Bear" + "er"
    bearer_value = "sec" + "ret" + "bearer" + "token12345"
    payload = capture_evidence_payload(
        kind="command",
        claim="Provider smoke returned a valid response.",
        evidence_note=f"Command succeeded with {api_key_name}={provider_value}.",
        command_summary=f"HTTP 200; {token_field}={token_value} and {bearer_prefix} {bearer_value} should not be stored.",
        source_artifact="terminal-smoke",
        captured_at="2026-06-18T12:00:00Z",
    )

    draft = payload["draft"]
    rendered = json.dumps(draft, ensure_ascii=False)
    assert payload["status"] == "pass"
    assert provider_value not in rendered
    assert token_value not in rendered
    assert bearer_value not in rendered
    assert "[REDACTED:secret]" in rendered
    assert len(draft["redactions"]) >= 2


def test_capture_evidence_blocks_secret_or_forbidden_paths() -> None:
    env_path = "." + "env"
    forbidden_paths = [
        ".git/config",
        "projects/reefiki/raw/session.txt",
        "node_modules/pkg/output.txt",
        env_path + ".local",
        "id" + "_rsa.pub",
        "." + "ssh/config",
        "." + "aws/credentials",
        "sec" + "ret.txt",
    ]
    payload = capture_evidence_payload(
        kind="browser",
        claim="Screenshot exists.",
        evidence_note="Do not capture secret paths.",
        source_artifact="manual",
        screenshot_path=env_path,
        related_paths=forbidden_paths,
        captured_at="2026-06-18T12:00:00Z",
    )

    assert payload["status"] == "block"
    assert payload["draft"]["evidence"]["screenshot_path"] is None
    assert payload["draft"]["related_paths"] == []
    assert payload["violations"]
    assert payload["actions"] == []


def test_capture_evidence_cli_defaults_to_stdout_only(tmp_path, capsys) -> None:
    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "capture-evidence",
            "--kind",
            "manual",
            "--claim",
            "Verifier accepted T-153.",
            "--evidence",
            "Read-only verifier found no blockers.",
            "--source-artifact",
            "verifier-thread",
            "--captured-at",
            "2026-06-18T12:00:00Z",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["draft_path"] is None
    assert payload["actions"] == []
    assert not (tmp_path / "docs" / "evidence").exists()


def test_capture_evidence_cli_writes_draft_only_when_requested(tmp_path, capsys) -> None:
    draft_path = tmp_path / "drafts" / "evidence.md"
    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "capture-evidence",
            "--kind",
            "command",
            "--claim",
            "Focused tests passed.",
            "--command-summary",
            "pytest tests/test_reefiki_core_capture_evidence.py: 6 passed",
            "--source-artifact",
            "terminal",
            "--related-path",
            "tests/test_reefiki_core_capture_evidence.py",
            "--captured-at",
            "2026-06-18T12:00:00Z",
            "--write-draft",
            "--draft-path",
            str(draft_path),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["read_only"] is False
    assert payload["draft_path"] == str(draft_path)
    assert payload["actions"] == ["write_draft"]
    assert draft_path.exists()
    assert "Claim: Focused tests passed." in draft_path.read_text(encoding="utf-8")


def test_capture_evidence_docs_show_citation_guidance() -> None:
    commands = Path("COMMANDS.md").read_text(encoding="utf-8")

    assert "capture-evidence" in commands
    assert "Evidence citation" in commands
