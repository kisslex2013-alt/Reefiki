from scripts.reefiki_core.code_context import graphify_graph_path, graphify_report_path, project_code_path


def test_project_code_path_reads_domain_path_forms(tmp_path) -> None:
    code = tmp_path / "code"
    project = tmp_path / "project"
    project.mkdir()
    (project / "_domain.md").write_text(f"Путь: `{code}`\n", encoding="utf-8")

    assert project_code_path(project) == code

    (project / "_domain.md").write_text(f"- Путь: `{code}`\n", encoding="utf-8")
    assert project_code_path(project) == code


def test_project_code_path_falls_back_to_repo_root_for_reefiki_project(tmp_path) -> None:
    repo = tmp_path / "repo"
    project = repo / "projects" / "reefiki"
    project.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("# Contract\n", encoding="utf-8")
    (project / "_domain.md").write_text("# Domain\n", encoding="utf-8")

    assert project_code_path(project) == repo


def test_graphify_report_path_requires_existing_report(tmp_path) -> None:
    code = tmp_path / "code"
    report = code / "graphify-out" / "GRAPH_REPORT.md"
    report.parent.mkdir(parents=True)
    report.write_text("# Graph\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "_domain.md").write_text(f"Путь: `{code}`\n", encoding="utf-8")

    assert graphify_report_path(project) == report

    report.unlink()
    assert graphify_report_path(project) is None


def test_graphify_graph_path_requires_existing_graph_json(tmp_path) -> None:
    code = tmp_path / "code"
    graph = code / "graphify-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text('{"nodes": [], "links": []}', encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "_domain.md").write_text(f"Путь: `{code}`\n", encoding="utf-8")

    assert graphify_graph_path(project) == graph

    graph.unlink()
    assert graphify_graph_path(project) is None
