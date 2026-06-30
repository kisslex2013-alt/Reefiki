from scripts.reefiki_core.save_paths import inbox_base_path, source_slug, unique_inbox_path


def test_source_slug_uses_url_host_and_path_or_file_stem() -> None:
    assert source_slug("https://Example.com/docs/page?b=2") == "example-com-docs-page"
    assert source_slug("notes/My File.md") == "my-file"


def test_inbox_base_path_creates_inbox_with_expected_suffix(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    url_path = inbox_base_path(project, "https://example.com/path")
    file_path = inbox_base_path(project, "notes/source.txt")

    assert url_path == project / "inbox" / "example-com-path.md"
    assert file_path == project / "inbox" / "source.txt"
    assert (project / "inbox").is_dir()


def test_unique_inbox_path_numbers_existing_base_path(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first = inbox_base_path(project, "https://example.com/path")
    first.write_text("existing", encoding="utf-8")

    assert unique_inbox_path(project, "https://example.com/path") == project / "inbox" / "example-com-path-2.md"
