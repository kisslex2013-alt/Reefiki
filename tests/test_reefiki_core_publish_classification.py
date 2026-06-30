from scripts.reefiki_core.publish_classification import (
    classify_publish_diff,
    private_project_inventory_payload,
    private_project_names,
    public_project_names,
    real_project_names,
)


def test_real_and_private_project_names_ignore_template_and_comments(tmp_path) -> None:
    repo = tmp_path / "repo"
    (repo / "projects" / "_template").mkdir(parents=True)
    (repo / "projects" / "reefiki").mkdir()
    (repo / "projects" / "Hermes").mkdir()
    config = repo / "scripts" / "public-snapshot.private-projects.txt"
    config.parent.mkdir()
    config.write_text("# comment\nreefiki\n\nHermes\n", encoding="utf-8")
    public_config = repo / "scripts" / "public-snapshot.public-projects.txt"
    public_config.write_text("# public demo\nreefiki-demo\n", encoding="utf-8")

    assert real_project_names(repo) == ["Hermes", "reefiki"]
    assert private_project_names(repo) == ["reefiki", "Hermes"]
    assert public_project_names(repo) == ["reefiki-demo"]


def test_private_project_inventory_reports_missing_empty_incomplete_and_pass(tmp_path) -> None:
    repo = tmp_path / "repo"
    (repo / "projects" / "reefiki").mkdir(parents=True)

    assert private_project_inventory_payload(repo)["reason"] == "private_project_inventory_missing"

    config = repo / "scripts" / "public-snapshot.private-projects.txt"
    config.parent.mkdir()
    config.write_text("# empty\n", encoding="utf-8")
    assert private_project_inventory_payload(repo)["reason"] == "private_project_inventory_empty"

    config.write_text("Hermes\n", encoding="utf-8")
    incomplete = private_project_inventory_payload(repo)
    assert incomplete["reason"] == "private_project_inventory_incomplete"
    assert incomplete["missing_private_projects"] == ["reefiki"]

    config.write_text("reefiki\n", encoding="utf-8")
    assert private_project_inventory_payload(repo)["outcome"] == "pass"


def test_private_project_inventory_allows_explicit_public_projects(tmp_path) -> None:
    repo = tmp_path / "repo"
    (repo / "projects" / "reefiki").mkdir(parents=True)
    (repo / "projects" / "reefiki-demo").mkdir()
    private_config = repo / "scripts" / "public-snapshot.private-projects.txt"
    public_config = repo / "scripts" / "public-snapshot.public-projects.txt"
    private_config.parent.mkdir()
    private_config.write_text("reefiki\n", encoding="utf-8")
    public_config.write_text("reefiki-demo\n", encoding="utf-8")

    payload = private_project_inventory_payload(repo)

    assert payload["outcome"] == "pass"
    assert payload["private_projects"] == ["reefiki"]
    assert payload["public_projects"] == ["reefiki-demo"]
    assert payload["real_projects"] == ["reefiki", "reefiki-demo"]


def test_classify_publish_diff_separates_private_public_mixed_and_empty() -> None:
    private_projects = ["reefiki", "Hermes"]

    assert classify_publish_diff([], private_projects) == "empty"
    assert classify_publish_diff(["README.md"], private_projects) == "public-safe"
    assert classify_publish_diff(["projects/reefiki/wiki/log.md"], private_projects) == "private-only"
    assert classify_publish_diff(["README.md", "projects/Hermes/wiki/log.md"], private_projects) == "mixed"
