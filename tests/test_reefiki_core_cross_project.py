from pathlib import Path

import pytest

from scripts.reefiki_core.cross_project import cross_project_query_payload


def write_project(root: Path, name: str, slug: str, title: str, body: str) -> Path:
    project = root / "projects" / name
    page_dir = project / "wiki" / "synthesis"
    page_dir.mkdir(parents=True)
    page = page_dir / f"{slug}.md"
    page.write_text(
        f"""---
id: {slug}
type: synthesis
title: "{title}"
abstract: "{title} abstract"
tags: [cross, query]
useful_when:
  - "testing cross project query"
sources:
  - fixture-{name}
date_added: 2026-06-12
use_count: 0
last_used: null
---

# {title}

{body}
""",
        encoding="utf-8",
    )
    (project / "wiki" / "index.md").write_text(
        f"""# Index

Last updated: 2026-06-12
Total pages: 1

## Synthesis

### {slug}
- type: synthesis
- tags: [cross, query]
- useful_when: ["testing cross project query"]
- file: wiki/synthesis/{slug}.md
- date_added: 2026-06-12
- use_count: 0
""",
        encoding="utf-8",
    )
    return project


def list_files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_cross_project_query_returns_read_only_results_with_provenance(tmp_path: Path) -> None:
    write_project(tmp_path, "alpha", "alpha-note", "Alpha Note", "Shared reefiki adapter evidence.")
    write_project(tmp_path, "beta", "beta-note", "Beta Note", "Different adapter evidence.")
    before = list_files(tmp_path)

    payload = cross_project_query_payload(tmp_path, "adapter", limit=5)

    assert payload["read_only"] is True
    assert payload["searched_projects"] == ["alpha", "beta"]
    assert payload["count"] == 2
    assert {item["project"] for item in payload["results"]} == {"alpha", "beta"}
    assert payload["synthesis"]["summary"] == "Top matches span 2 project(s): alpha, beta."
    first = payload["results"][0]
    assert first["provenance"]["page"].endswith("/wiki/synthesis/alpha-note.md") or first["provenance"]["page"].endswith(
        "/wiki/synthesis/beta-note.md"
    )
    assert first["provenance"]["sources"] in {"fixture-alpha", "fixture-beta"}
    assert len(first["provenance"]["sha256"]) == 64
    assert list_files(tmp_path) == before
    assert not (tmp_path / "projects" / "alpha" / ".reefiki").exists()
    assert not (tmp_path / "projects" / "beta" / ".reefiki").exists()


def test_cross_project_query_can_route_to_selected_project(tmp_path: Path) -> None:
    write_project(tmp_path, "alpha", "alpha-note", "Alpha Note", "Needle appears here.")
    write_project(tmp_path, "beta", "beta-note", "Beta Note", "Needle appears here too.")

    payload = cross_project_query_payload(tmp_path, "needle", limit=5, project_names=["beta"])

    assert payload["searched_projects"] == ["beta"]
    assert payload["count"] == 1
    assert payload["results"][0]["project"] == "beta"


def test_cross_project_query_blocks_duplicate_project_filters(tmp_path: Path) -> None:
    write_project(tmp_path, "alpha", "alpha-note", "Alpha Note", "Needle appears here.")

    with pytest.raises(SystemExit, match="Duplicate project filter"):
        cross_project_query_payload(tmp_path, "needle", limit=5, project_names=["alpha", "Alpha"])


def test_cross_project_query_skips_unsafe_index_paths(tmp_path: Path) -> None:
    project = write_project(tmp_path, "alpha", "alpha-note", "Alpha Note", "Needle appears here.")
    (project / "wiki" / "index.md").write_text(
        """# Index

## Synthesis

### escaped
- type: synthesis
- tags: [cross]
- useful_when: ["testing unsafe path"]
- file: ../beta/wiki/synthesis/escaped.md
- date_added: 2026-06-12
- use_count: 0
""",
        encoding="utf-8",
    )

    payload = cross_project_query_payload(tmp_path, "needle", limit=5)

    assert payload["count"] == 0
    assert payload["warnings"] == [
        {
            "project": "alpha",
            "id": "escaped",
            "file": "../beta/wiki/synthesis/escaped.md",
            "reason": "outside_project_wiki",
        }
    ]
