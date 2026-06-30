import json

from scripts.reefiki_core.plans import plan_check, plan_create, timeline


def test_plan_create_writes_checksummed_plan_and_check_passes(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()

    assert plan_create(project, "Ship Local Install") == 0
    create_output = capsys.readouterr().out
    assert "plans/ship-local-install.md" in create_output

    plan_path = project / "plans" / "ship-local-install.md"
    assert plan_path.exists()
    assert "reefiki-plan-sha256:" in plan_path.read_text(encoding="utf-8")

    assert plan_check(project, "plans/ship-local-install.md") == 0
    assert "checksum OK" in capsys.readouterr().out


def test_plan_check_refuses_path_outside_project(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")

    assert plan_check(project, str(outside)) == 2
    assert "Refused: path-outside-project" in capsys.readouterr().out


def test_timeline_prints_last_entries(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    wiki = project / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "log.md").write_text(
        """# Log

## [2026-06-09] first

- first entry

## [2026-06-10] second

- second entry
""",
        encoding="utf-8",
    )

    assert timeline(project, limit=1) == 0

    output = capsys.readouterr().out
    assert "second" in output
    assert "first entry" not in output


def test_timeline_json_prints_last_entries(tmp_path, capsys) -> None:
    project = tmp_path / "project"
    wiki = project / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "log.md").write_text(
        """# Log

## [2026-06-09] first

- first entry

## [2026-06-10] /harvest | second

- second entry
""",
        encoding="utf-8",
    )

    assert timeline(project, limit=1, fmt="json") == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == "project"
    assert payload["limit"] == 1
    assert payload["total"] == 2
    assert payload["returned"] == 1
    assert payload["entries"] == [
        {
            "date": "2026-06-10",
            "title": "/harvest | second",
            "heading": "## [2026-06-10] /harvest | second",
            "body": "- second entry",
            "text": "## [2026-06-10] /harvest | second\n\n- second entry",
        }
    ]
