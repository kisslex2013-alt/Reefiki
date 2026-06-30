import pytest

from scripts.reefiki_core.repo_paths import (
    normalize_repo_path,
    normalize_target_project_name,
    repo_path_in_scope,
    resolve_contained_path,
)


def test_repo_path_normalization_is_repo_relative_and_segment_safe() -> None:
    assert normalize_repo_path(r".\projects\reefiki\wiki\..\wiki\skills\guard.md") == "projects/reefiki/wiki/skills/guard.md"
    assert repo_path_in_scope("projects/metrica/wiki/skills/metrica.md", "projects/metrica/wiki")
    assert not repo_path_in_scope("projects/metrica/wiki2/skills/metrica.md", "projects/metrica/wiki")
    assert not repo_path_in_scope("projects/metrica/wiki", "projects/metrica/wiki/skills")


@pytest.mark.parametrize("path", ["", ".", "..", "../outside", "/absolute"])
def test_repo_path_normalization_rejects_non_repo_relative_paths(path: str) -> None:
    with pytest.raises(SystemExit):
        normalize_repo_path(path)


def test_target_project_name_rejects_paths_and_parent_segments() -> None:
    assert normalize_target_project_name(" reefiki ") == "reefiki"
    for name in ["", "projects/reefiki", r"projects\reefiki", "..", "bad..name"]:
        with pytest.raises(SystemExit):
            normalize_target_project_name(name)


def test_resolve_contained_path_accepts_relative_and_absolute_children(tmp_path) -> None:
    root = tmp_path / "project"
    child = root / "wiki" / "page.md"
    child.parent.mkdir(parents=True)
    child.write_text("ok", encoding="utf-8")

    relative_path, relative_reason = resolve_contained_path(root, "wiki/page.md")
    absolute_path, absolute_reason = resolve_contained_path(root, str(child))

    assert relative_path == child.resolve()
    assert relative_reason == "ok"
    assert absolute_path == child.resolve()
    assert absolute_reason == "ok"


def test_resolve_contained_path_blocks_paths_outside_root(tmp_path) -> None:
    root = tmp_path / "project"
    outside = tmp_path / "outside.md"
    root.mkdir()
    outside.write_text("no", encoding="utf-8")

    path, reason = resolve_contained_path(root, str(outside))

    assert path is None
    assert reason == "path-outside-project"
