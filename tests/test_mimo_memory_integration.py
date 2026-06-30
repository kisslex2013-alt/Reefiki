import subprocess
import sys

from scripts.mimo_memory_integration import detect_reefiki_connection, get_reefiki_root


def test_detect_uses_project_name_from_reefiki_marker(tmp_path) -> None:
    project = tmp_path / "CODEX"
    project.mkdir()
    (project / ".reefiki").write_text(
        "# REEFIKI connection marker\nproject_name: codex\nwiki_junction: _wiki\n",
        encoding="utf-8",
    )

    result = detect_reefiki_connection(str(project))

    assert result["connected"] is True
    assert result["marker"] == ".reefiki"
    assert result["project_name"] == "codex"


def test_detect_cli_prints_marker_project_name(tmp_path) -> None:
    project = tmp_path / "CODEX"
    project.mkdir()
    (project / ".reefiki").write_text("project_name: codex\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/mimo_memory_integration.py", "detect", str(project)],
        cwd=".",
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Connected: True" in result.stdout
    assert "Marker: .reefiki" in result.stdout
    assert "Project: codex" in result.stdout


def test_get_reefiki_root_prefers_valid_env_root(monkeypatch, tmp_path) -> None:
    root = tmp_path / "portable-reefiki"
    (root / "scripts").mkdir(parents=True)
    (root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (root / "scripts" / "reefiki.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setenv("REEFIKI_ROOT", str(root))

    assert get_reefiki_root() == root.resolve()


def test_get_reefiki_root_discovers_upward_from_cwd(monkeypatch, tmp_path) -> None:
    root = tmp_path / "portable-reefiki"
    nested = root / "subdir" / "tool"
    (root / "scripts").mkdir(parents=True)
    nested.mkdir(parents=True)
    (root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (root / "scripts" / "reefiki.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.delenv("REEFIKI_ROOT", raising=False)
    monkeypatch.chdir(nested)

    assert get_reefiki_root() == root.resolve()
