import json
from pathlib import Path

from scripts import reefiki
from scripts.reefiki_core.connect_check import connect_check_payload
from scripts.reefiki_core.git_utils import run_git


def init_repo(path: Path) -> None:
    run_git(path, ["init"])


def write_bridge(path: Path) -> None:
    (path / "_wiki").mkdir()
    (path / "_wiki" / "AGENTS.md").write_text("# Wiki\n", encoding="utf-8")
    (path / ".reefiki").write_text(
        "# REEFIKI connection marker\nproject_name: demo\nwiki_junction: _wiki\n",
        encoding="utf-8",
    )


def test_connect_check_passes_when_bridge_paths_are_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "code"
    repo.mkdir()
    init_repo(repo)
    write_bridge(repo)
    (repo / ".gitignore").write_text("_wiki/\n.reefiki\n", encoding="utf-8")

    payload = connect_check_payload(repo)

    assert payload["status"] == "pass"
    assert payload["read_only"] is True
    assert payload["git"]["status"] == "git_repo"
    assert payload["ignored"] == {"_wiki/": True, ".reefiki": True}
    assert payload["tracked_bridge_paths"] == []
    assert payload["next_actions"] == ["No action needed; bridge paths are ignored and not tracked."]


def test_connect_check_warns_when_gitignore_is_missing_bridge_paths(tmp_path: Path) -> None:
    repo = tmp_path / "code"
    repo.mkdir()
    init_repo(repo)
    write_bridge(repo)

    payload = connect_check_payload(repo)

    assert payload["status"] == "warn"
    assert payload["ignored"] == {"_wiki/": False, ".reefiki": False}
    assert "Add _wiki/ to the target project's .gitignore." in payload["next_actions"]
    assert "Add .reefiki to the target project's .gitignore." in payload["next_actions"]


def test_connect_check_blocks_when_bridge_paths_are_tracked(tmp_path: Path) -> None:
    repo = tmp_path / "code"
    repo.mkdir()
    init_repo(repo)
    write_bridge(repo)
    (repo / ".gitignore").write_text("_wiki/\n.reefiki\n", encoding="utf-8")
    run_git(repo, ["add", "-f", ".reefiki", "_wiki/AGENTS.md"])

    payload = connect_check_payload(repo)

    assert payload["status"] == "block"
    assert payload["ignored"] == {"_wiki/": True, ".reefiki": True}
    assert payload["tracked_bridge_paths"] == [".reefiki", "_wiki/AGENTS.md"]
    assert "Remove bridge paths from the target git index after review, without deleting local files." in payload["next_actions"]


def test_connect_check_passes_non_git_project_with_git_check_skipped(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    project.mkdir()
    write_bridge(project)

    payload = connect_check_payload(project)

    assert payload["status"] == "pass"
    assert payload["git"]["status"] == "not_git_repo"
    assert payload["tracked_bridge_paths"] == []
    assert payload["warnings"] == []
    assert any(check["status"] == "skip" for check in payload["checks"])


def test_connect_check_cli_outputs_json_and_nonzero_for_block(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "code"
    repo.mkdir()
    init_repo(repo)
    write_bridge(repo)
    run_git(repo, ["add", ".reefiki", "_wiki/AGENTS.md"])

    code = reefiki.main(["connect-check", str(repo), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["status"] == "block"
    assert payload["tracked_bridge_paths"] == [".reefiki", "_wiki/AGENTS.md"]


def test_connect_check_docs_reference_post_connect_gate() -> None:
    commands = Path("COMMANDS.md").read_text(encoding="utf-8")
    connect_spec = Path(".claude/commands/connect.md").read_text(encoding="utf-8")

    assert "reefiki.py connect-check" in commands
    assert "connect-check" in connect_spec
