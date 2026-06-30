from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from scripts import reefiki
from scripts.reefiki_core.markdown_import import markdown_import_payload


def _project(root: Path) -> Path:
    project = root / "project"
    (project / "inbox").mkdir(parents=True)
    (project / "wiki").mkdir()
    (project / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    return project


def test_markdown_import_writes_markdown_files_to_flat_inbox_and_log(tmp_path) -> None:
    project = _project(tmp_path)
    vault = tmp_path / "vault"
    (vault / "folder").mkdir(parents=True)
    (vault / "folder" / "Note One.md").write_text("# Note One\n\nUseful content.\n", encoding="utf-8")
    (vault / "folder" / "Note Two.md").write_text("# Note Two\n\nMore content.\n", encoding="utf-8")
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "config.md").write_text("ignored\n", encoding="utf-8")

    payload = markdown_import_payload(project, vault, source_kind="obsidian")

    assert payload["outcome"] == "pass"
    assert payload["imported_count"] == 2
    assert payload["skipped_count"] == 0
    destinations = {item["destination"] for item in payload["imported"]}
    assert destinations == {"inbox/folder-note-one.md", "inbox/folder-note-two.md"}
    assert (project / "inbox" / "folder-note-one.md").read_text(encoding="utf-8").startswith("# Note One")
    assert "/import | obsidian vault -> inbox (2 imported, 0 skipped)" in (
        project / "wiki" / "log.md"
    ).read_text(encoding="utf-8")


def test_markdown_import_dry_run_reports_destinations_without_writing(tmp_path) -> None:
    project = _project(tmp_path)
    source = tmp_path / "note.md"
    source.write_text("# Draft\n", encoding="utf-8")

    payload = markdown_import_payload(project, source, dry_run=True)

    assert payload["outcome"] == "pass"
    assert payload["imported"] == [{"source_path": "note.md", "destination": "inbox/note.md"}]
    assert payload["created_paths"] == []
    assert not (project / "inbox" / "note.md").exists()
    assert (project / "wiki" / "log.md").read_text(encoding="utf-8") == "# Log\n"


def test_markdown_import_skips_secret_content_and_secret_like_path(tmp_path) -> None:
    project = _project(tmp_path)
    vault = tmp_path / "vault"
    (vault / ".ssh").mkdir(parents=True)
    (vault / ".ssh" / "config.md").write_text("# SSH config\n", encoding="utf-8")
    (vault / "safe.md").write_text("# Safe\n", encoding="utf-8")
    aws_key = "AKIA" + "1234567890ABCDEF"
    (vault / "key.md").write_text(f"AWS key {aws_key}\n", encoding="utf-8")

    payload = markdown_import_payload(project, vault, source_kind="markdown")

    assert payload["outcome"] == "warn"
    assert payload["imported_count"] == 1
    assert payload["skipped_count"] == 2
    assert payload["imported"] == [{"source_path": "safe.md", "destination": "inbox/safe.md"}]
    assert {item["reason"] for item in payload["skipped"]} == {
        "secret_like_content",
        "secret_like_path",
    }
    assert payload["next_actions"][0].startswith("Create a redacted copy")
    assert not (project / "inbox" / "key.md").exists()


def test_markdown_import_cli_json(tmp_path) -> None:
    project = _project(tmp_path)
    source = tmp_path / "note.md"
    source.write_text("# CLI note\n", encoding="utf-8")
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        code = reefiki.main(
            [
                "--project",
                str(project),
                "import",
                str(source),
                "--from",
                "markdown",
                "--format",
                "json",
            ]
        )

    assert code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["schema_version"] == "reefiki.import.v1"
    assert payload["outcome"] == "pass"
    assert payload["created_paths"] == ["inbox/note.md", "wiki/log.md"]
