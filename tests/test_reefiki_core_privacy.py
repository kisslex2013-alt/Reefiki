from pathlib import Path

from scripts.reefiki_core.privacy import (
    canonical_url,
    classify_path,
    dedup_check,
    extract_urls,
    inbox_items,
    is_url,
)


def test_canonical_url_normalizes_scheme_host_path_and_query() -> None:
    assert canonical_url("http://www.Example.com/path/?b=2&a=1") == "https://example.com/path?a=1&b=2"


def test_extract_urls_strips_trailing_punctuation() -> None:
    assert extract_urls("See https://example.com/a?b=1, then https://example.org/x.") == [
        "https://example.com/a?b=1",
        "https://example.org/x",
    ]


def test_classify_path_blocks_outside_secret_binary_and_large_files(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    guarded_path = project / ("." + "env")
    guarded_path.write_text("placeholder", encoding="utf-8")
    binary = project / "archive.zip"
    binary.write_text("zip", encoding="utf-8")

    assert classify_path(str(outside), project) == (False, "path-outside-project")
    assert classify_path(str(guarded_path), project) == (False, "secret-name")
    assert classify_path(str(binary), project) == (False, "binary-file:.zip")
    assert classify_path("https://example.com/file.pdf", project) == (False, "binary-url:.pdf")


def test_dedup_check_detects_canonical_url_duplicate(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    page = project / "wiki" / "concepts" / "source.md"
    page.parent.mkdir(parents=True)
    page.write_text("source: http://www.example.com/path/?b=2&a=1\n", encoding="utf-8")
    (project / "inbox").mkdir()
    (project / "seen").mkdir()

    code = dedup_check(project, "https://example.com/path?a=1&b=2")

    assert code == 1
    assert "url:wiki/concepts/source.md" in capsys.readouterr().out


def test_inbox_items_ignores_gitkeep(tmp_path) -> None:
    inbox = tmp_path / "project" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / ".gitkeep").write_text("", encoding="utf-8")
    (inbox / "source.md").write_text("ok", encoding="utf-8")

    assert [path.name for path in inbox_items(tmp_path / "project")] == ["source.md"]
    assert is_url("https://example.com")
    assert not is_url(str(Path("local.md")))
