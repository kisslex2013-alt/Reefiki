import json
import subprocess
from pathlib import Path

from scripts.reefiki_core.graphify_adapter import graphify_artifact_status, graphify_lookup


def write_graph(code: Path, built_at_commit: str = "abc123") -> Path:
    graph_dir = code / "graphify-out"
    graph_dir.mkdir(parents=True)
    (graph_dir / "GRAPH_REPORT.md").write_text("# Graph report\n", encoding="utf-8")
    graph = {
        "built_at_commit": built_at_commit,
        "nodes": [
            {
                "id": "scripts_reefiki_core_memory_lookup_py",
                "label": "memory_lookup.py",
                "source_file": "scripts/reefiki_core/memory_lookup.py",
                "source_location": "L1",
                "file_type": "code",
            },
            {
                "id": "scripts_reefiki_core_code_context_py",
                "label": "code_context.py",
                "source_file": "scripts/reefiki_core/code_context.py",
                "source_location": "L1",
                "file_type": "code",
            },
        ],
        "links": [
            {
                "source": "scripts_reefiki_core_memory_lookup_py",
                "target": "scripts_reefiki_core_code_context_py",
                "relation": "imports",
                "confidence": "EXTRACTED",
                "source_file": "scripts/reefiki_core/memory_lookup.py",
                "source_location": "L8",
            }
        ],
    }
    graph_path = graph_dir / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    return graph_path


def write_project(tmp_path: Path, code: Path) -> Path:
    project = tmp_path / "projects" / "reefiki"
    project.mkdir(parents=True)
    (project / "_domain.md").write_text(f"Путь: `{code}`\n", encoding="utf-8")
    return project


def test_graphify_lookup_returns_ranked_graph_json_neighborhood(tmp_path: Path) -> None:
    code = tmp_path / "code"
    write_graph(code)
    project = write_project(tmp_path, code)

    hits = graphify_lookup(project, "memory lookup graphify", limit=5)

    assert hits[0]["node_id"] == "scripts_reefiki_core_memory_lookup_py"
    assert hits[0]["id"] == "scripts_reefiki_core_memory_lookup_py"
    assert hits[0]["source_file"] == "scripts/reefiki_core/memory_lookup.py"
    assert hits[0]["freshness"]["status"] == "available"
    assert hits[0]["neighbors"][0]["node_id"] == "scripts_reefiki_core_code_context_py"
    assert hits[0]["neighbors"][0]["relation"] == "imports"


def test_graphify_artifact_status_marks_stale_graph(tmp_path: Path) -> None:
    code = tmp_path / "code"
    code.mkdir()
    subprocess.run(["git", "init"], cwd=code, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=code, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=code, check=True)
    (code / "first.txt").write_text("first\n", encoding="utf-8")
    subprocess.run(["git", "add", "first.txt"], cwd=code, check=True)
    subprocess.run(["git", "commit", "-m", "first"], cwd=code, check=True, capture_output=True, text=True)
    built = subprocess.run(["git", "rev-parse", "HEAD"], cwd=code, check=True, capture_output=True, text=True).stdout.strip()
    write_graph(code, built_at_commit=built)
    (code / "second.txt").write_text("second\n", encoding="utf-8")
    subprocess.run(["git", "add", "second.txt"], cwd=code, check=True)
    subprocess.run(["git", "commit", "-m", "second"], cwd=code, check=True, capture_output=True, text=True)
    project = write_project(tmp_path, code)

    status = graphify_artifact_status(project)

    assert status["status"] == "stale_report"
    assert status["built_at_commit"] == built
    assert status["changed_files_since_build"] == 1
