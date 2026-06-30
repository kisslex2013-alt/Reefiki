import json
from pathlib import Path

from scripts import reefiki
from scripts.reefiki_core.verify_intent import verify_intent_payload


def test_verify_intent_passes_when_terms_and_paths_match() -> None:
    payload = verify_intent_payload(
        brief="Add visibility audit over agent-facing knowledge.",
        report="Implemented visibility audit with answerable weak missing groups.",
        changed_paths=[
            "scripts/reefiki_core/visibility_audit.py",
            "tests/test_reefiki_core_visibility_audit.py",
        ],
        artifacts={},
        expected_terms=["visibility audit", "answerable", "missing"],
        expected_paths=["scripts/reefiki_core", "tests"],
    )

    assert payload["status"] == "pass"
    assert payload["signals"] == {
        "missing_scope": [],
        "unrelated_artifact": [],
        "over_broad_diff": [],
    }
    assert payload["evidence"]["term_evidence"]["visibility audit"]["present"] is True
    assert payload["evidence"]["path_evidence"]["scripts/reefiki_core"] == [
        "scripts/reefiki_core/visibility_audit.py"
    ]


def test_verify_intent_blocks_missing_requested_scope() -> None:
    payload = verify_intent_payload(
        brief="Add verify-intent for brief-vs-artifact review.",
        report="Implemented a generic status report.",
        changed_paths=["scripts/reefiki_core/verify_intent.py"],
        artifacts={},
        expected_terms=["brief artifact evidence"],
        expected_paths=["scripts/reefiki_core"],
    )

    assert payload["status"] == "block"
    assert payload["signals"]["missing_scope"] == [
        {
            "term": "brief artifact evidence",
            "reason": "expected term not found in report, artifacts or changed paths",
            "evidence": [],
        }
    ]


def test_verify_intent_warns_on_unrelated_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "notes" / "random.md"
    artifact.parent.mkdir()
    artifact.write_text("Unrelated release note about a music workflow.", encoding="utf-8")

    payload = verify_intent_payload(
        brief="Add verify-intent for brief-vs-artifact review.",
        report="verify-intent compares brief artifact evidence.",
        changed_paths=["scripts/reefiki_core/verify_intent.py"],
        artifacts={str(artifact): artifact.read_text(encoding="utf-8")},
        expected_terms=["verify-intent", "brief artifact evidence"],
        expected_paths=["scripts/reefiki_core"],
    )

    assert payload["status"] == "warn"
    assert payload["signals"]["unrelated_artifact"][0]["path"] == str(artifact)
    assert payload["signals"]["unrelated_artifact"][0]["evidence"] == []


def test_verify_intent_warns_on_over_broad_diff() -> None:
    payload = verify_intent_payload(
        brief="Add verify-intent for brief-vs-artifact review.",
        report="verify-intent compares brief artifact evidence.",
        changed_paths=[
            "scripts/reefiki_core/verify_intent.py",
            "projects/Suno/wiki/log.md",
        ],
        artifacts={},
        expected_terms=["verify-intent", "brief artifact evidence"],
        expected_paths=["scripts/reefiki_core"],
    )

    assert payload["status"] == "warn"
    assert payload["signals"]["over_broad_diff"] == [
        {
            "path": "projects/Suno/wiki/log.md",
            "reason": "changed path is outside expected paths",
            "allowed_paths": ["scripts/reefiki_core"],
            "evidence": ["projects/Suno/wiki/log.md"],
        }
    ]


def test_verify_intent_separates_expected_paths_from_allowed_paths() -> None:
    payload = verify_intent_payload(
        brief="Add verify-intent for brief-vs-artifact review.",
        report="verify-intent compares brief artifact evidence.",
        changed_paths=[
            "scripts/reefiki_core/verify_intent.py",
            "tests/test_reefiki_core_verify_intent.py",
        ],
        artifacts={},
        expected_terms=["verify-intent", "brief artifact evidence"],
        expected_paths=["scripts/reefiki_core/verify_intent.py"],
        allowed_paths=["scripts/reefiki_core", "tests"],
    )

    assert payload["status"] == "pass"
    assert payload["evidence"]["path_evidence"] == {
        "scripts/reefiki_core/verify_intent.py": ["scripts/reefiki_core/verify_intent.py"]
    }


def test_verify_intent_cli_reports_block_with_nonzero_exit(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text("Generic artifact without required scope.", encoding="utf-8")

    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "verify-intent",
            "--brief",
            "Add verify-intent for brief-vs-artifact review.",
            "--report",
            "Generic status report.",
            "--artifact",
            str(artifact),
            "--changed-path",
            "scripts/reefiki_core/verify_intent.py",
            "--expect-term",
            "brief artifact evidence",
            "--expect-path",
            "scripts/reefiki_core",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["status"] == "block"
    assert payload["signals"]["missing_scope"][0]["term"] == "brief artifact evidence"


def test_verify_intent_cli_can_fail_on_warning(tmp_path: Path, capsys) -> None:
    code = reefiki.main(
        [
            "--project",
            str(tmp_path),
            "verify-intent",
            "--brief",
            "Add verify-intent for brief-vs-artifact review.",
            "--report",
            "verify-intent compares brief artifact evidence.",
            "--changed-path",
            "scripts/reefiki_core/verify_intent.py",
            "--changed-path",
            "projects/Suno/wiki/log.md",
            "--expect-term",
            "verify-intent",
            "--expect-term",
            "brief artifact evidence",
            "--expect-path",
            "scripts/reefiki_core",
            "--fail-on",
            "warn",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["status"] == "warn"
    assert payload["signals"]["over_broad_diff"][0]["path"] == "projects/Suno/wiki/log.md"
