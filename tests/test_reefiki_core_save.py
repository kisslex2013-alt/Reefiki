import contextlib
import io

from scripts.reefiki_core.save import append_save_log, save_source


def test_append_save_log_creates_append_only_entry(tmp_path) -> None:
    append_save_log(tmp_path, "https://example.com/source")

    log = (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "/save | https://example.com/source" in log


def test_save_source_url_writes_inbox_and_log(tmp_path) -> None:
    project = tmp_path
    (project / "wiki").mkdir()
    (project / "wiki" / "log.md").write_text("Append-only log\n", encoding="utf-8")
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        code = save_source(project, "https://example.com/path?a=1")

    assert code == 0
    assert "Saved: inbox/example-com-path.md" in stdout.getvalue()
    assert "Inbox entries: 1" in stdout.getvalue()
    assert (project / "inbox" / "example-com-path.md").read_text(encoding="utf-8") == "https://example.com/path?a=1\n"
    assert "/save | https://example.com/path?a=1" in (project / "wiki" / "log.md").read_text(encoding="utf-8")


def test_save_source_refuses_forbidden_path_without_log(tmp_path) -> None:
    project = tmp_path
    (project / "wiki").mkdir()
    (project / "wiki" / "log.md").write_text("Append-only log\n", encoding="utf-8")
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        code = save_source(project, ".env")

    assert code == 2
    assert "Refused:" in stdout.getvalue()
    assert (project / "wiki" / "log.md").read_text(encoding="utf-8") == "Append-only log\n"


def test_save_source_refuses_relative_traversal_outside_project(tmp_path) -> None:
    workspace = tmp_path
    project = workspace / "project"
    outside = workspace / "outside.md"
    outside.write_text("external content\n", encoding="utf-8")
    (project / "wiki").mkdir(parents=True)
    (project / "wiki" / "log.md").write_text("Append-only log\n", encoding="utf-8")
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        code = save_source(project, "../outside.md")

    assert code == 2
    assert "Refused: path-outside-project" in stdout.getvalue()
    assert not (project / "inbox" / "outside.md").exists()
    assert (project / "wiki" / "log.md").read_text(encoding="utf-8") == "Append-only log\n"
