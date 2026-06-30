import subprocess
import json
from pathlib import Path

from scripts.reefiki_core import memory_lookup


def test_memory_lookup_uses_dedicated_memoir_timeout(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_memoir_with_timeout(
        store: Path,
        args: list[str],
        timeout_seconds: int,
    ) -> dict[str, object]:
        calls.append(
            {
                "store": store,
                "args": args,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"memories": []}

    monkeypatch.setattr(memory_lookup, "MEMOIR_LOOKUP_TIMEOUT_SECONDS", 4)
    monkeypatch.setattr(memory_lookup, "run_memoir_with_timeout", fake_run_memoir_with_timeout)

    assert memory_lookup.run_memoir(Path("store"), ["recall", "needle"]) == {"memories": []}
    assert calls == [
        {
            "store": Path("store"),
            "args": ["recall", "needle"],
            "timeout_seconds": 4,
        }
    ]


def test_global_lookup_preserves_other_layers_when_memoir_times_out(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    report = tmp_path / "GRAPH_REPORT.md"
    report.write_text("needle graph line\n", encoding="utf-8")

    def timeout_memoir(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise subprocess.TimeoutExpired(cmd=["memoir", "recall"], timeout=120)

    def fake_project_lookup(
        project_path: Path,
        query: str,
        limit: int,
    ) -> list[dict[str, object]]:
        return [
            {
                "project": project_path.name,
                "id": "routing",
                "title": "Routing",
                "file": "wiki/concepts/routing.md",
                "score": 0.1,
            }
        ]

    monkeypatch.setattr(memory_lookup, "run_memoir", timeout_memoir)
    monkeypatch.setattr(memory_lookup, "project_local_lookup", fake_project_lookup)
    monkeypatch.setattr(memory_lookup, "graphify_report_path", lambda _project_path: report)

    result = memory_lookup.global_lookup(
        tmp_path,
        query="needle",
        project="reefiki",
        include_memoir=True,
        include_reefiki=True,
        include_graph=True,
        limit=5,
    )

    assert isinstance(result["memoir"], dict)
    assert result["memoir"]["provider"] == "memoir"
    assert result["memoir"]["error_type"] == "TimeoutExpired"
    assert "timed out" in str(result["memoir"]["error"])
    assert result["reefiki"][0]["id"] == "routing"
    assert result["graphify"][0]["text"] == "needle graph line"


def test_global_lookup_blocked_private_project_reports_project_local_next_action(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def provider_must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("blocked lookup must not read providers")

    monkeypatch.setattr(memory_lookup, "run_memoir", provider_must_not_run)
    monkeypatch.setattr(memory_lookup, "project_local_lookup", provider_must_not_run)
    monkeypatch.setattr(memory_lookup, "graphify_lookup", provider_must_not_run)

    result = memory_lookup.global_lookup(
        tmp_path,
        query="sync bootstrap",
        project="metrica",
        include_memoir=True,
        include_reefiki=True,
        include_graph=True,
        limit=3,
    )

    assert result["policy"]["outcome"] == "block"
    assert "forbidden_scope:projects/metrica" in result["policy"]["blocking_reasons"]
    assert result["memoir"] is None
    assert result["reefiki"] == []
    assert result["graphify"] == []
    assert result["next_action"] == (
        "global memory lookup keeps private project scopes isolated; "
        "use project-local search/query instead: "
        "python scripts/reefiki.py --project projects/metrica search \"<query>\" "
        "--limit 3 --format json"
    )


def test_global_lookup_blocks_private_project_case_insensitively(tmp_path: Path) -> None:
    result = memory_lookup.global_lookup(
        tmp_path,
        query="sync bootstrap",
        project="Metrica",
        include_memoir=False,
        include_reefiki=True,
        include_graph=False,
        limit=5,
    )

    assert result["policy"]["outcome"] == "block"
    assert "forbidden_scope:projects/metrica" in result["policy"]["blocking_reasons"]
    assert result["next_action"] == (
        "global memory lookup keeps private project scopes isolated; "
        "use project-local search/query instead: "
        "python scripts/reefiki.py --project projects/metrica search \"<query>\" "
        "--limit 5 --format json"
    )


def test_global_lookup_blocked_secret_query_does_not_suggest_rerun(tmp_path: Path) -> None:
    result = memory_lookup.global_lookup(
        tmp_path,
        query="api_" + "key=secret",
        project="metrica",
        include_memoir=False,
        include_reefiki=True,
        include_graph=False,
        limit=5,
    )

    assert result["policy"]["outcome"] == "block"
    assert "secret_like_content" in result["policy"]["blocking_reasons"]
    assert "next_action" not in result


def test_global_lookup_without_project_excludes_private_projects(
    monkeypatch,
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "projects"
    for name in ["reefiki", "metrica", "Hermes", "suno"]:
        (projects_dir / name).mkdir(parents=True)

    seen_projects: list[str] = []

    def fake_project_lookup(
        project_path: Path,
        query: str,
        limit: int,
    ) -> list[dict[str, object]]:
        seen_projects.append(project_path.name)
        return []

    monkeypatch.setattr(memory_lookup, "project_local_lookup", fake_project_lookup)

    result = memory_lookup.global_lookup(
        tmp_path,
        query="memory",
        project=None,
        include_memoir=False,
        include_reefiki=True,
        include_graph=False,
        limit=5,
    )

    assert result["policy"]["outcome"] == "pass"
    assert seen_projects == ["reefiki", "suno"]


def test_print_global_lookup_text_includes_private_project_next_action(
    capsys,
    tmp_path: Path,
) -> None:
    code = memory_lookup.print_global_lookup(
        tmp_path,
        query="sync bootstrap",
        project="metrica",
        include_memoir=False,
        include_reefiki=True,
        include_graph=False,
        limit=5,
        fmt="text",
    )

    output = capsys.readouterr().out
    assert code == 1
    assert "policy: block" in output
    assert "forbidden_scope:projects/metrica" in output
    assert "next_action:" in output
    assert 'python scripts/reefiki.py --project projects/metrica search "<query>"' in output


def test_global_lookup_uses_graph_json_adapter_for_graphify_hits(tmp_path: Path) -> None:
    code = tmp_path / "code"
    graph_dir = code / "graphify-out"
    graph_dir.mkdir(parents=True)
    (graph_dir / "GRAPH_REPORT.md").write_text("report without query phrase\n", encoding="utf-8")
    (graph_dir / "graph.json").write_text(
        json.dumps(
            {
                "built_at_commit": "abc123",
                "nodes": [
                    {
                        "id": "scripts_reefiki_core_memory_lookup_py",
                        "label": "memory_lookup.py",
                        "source_file": "scripts/reefiki_core/memory_lookup.py",
                        "source_location": "L1",
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    (project / "_domain.md").write_text(f"Путь: `{code}`\n", encoding="utf-8")

    result = memory_lookup.global_lookup(
        tmp_path,
        query="memory lookup",
        project="reefiki",
        include_memoir=False,
        include_reefiki=False,
        include_graph=True,
        limit=5,
    )

    assert result["graphify"][0]["node_id"] == "scripts_reefiki_core_memory_lookup_py"
    assert result["graphify"][0]["source_file"] == "scripts/reefiki_core/memory_lookup.py"
