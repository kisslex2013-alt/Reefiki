from pathlib import Path

from scripts.reefiki_core.file_utils import numbered_path, slugify, write_unique_text


def test_slugify_preserves_existing_cli_slug_behavior() -> None:
    assert slugify("Example.com/Some Path?a=1") == "example-com-some-path-a-1"
    assert slugify("План проверки") == "план-проверки"
    assert slugify("!!!") == "plan"


def test_numbered_path_and_unique_writer_are_stable(tmp_path: Path) -> None:
    base = tmp_path / "item.md"
    first = write_unique_text(base, "one\n")
    second = write_unique_text(base, "two\n")

    assert first == base
    assert second == numbered_path(base, 2)
    assert first.read_text(encoding="utf-8") == "one\n"
    assert second.read_text(encoding="utf-8") == "two\n"
