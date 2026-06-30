import json
from pathlib import Path

from scripts import reefiki
from scripts import validate_frontmatter
from scripts.reefiki_core import init_workspace
from scripts.reefiki_core.connect_check import connect_check_payload
from scripts.reefiki_core.doctor import doctor_payload
from scripts.reefiki_core.git_utils import run_git
from scripts.reefiki_core.index_search import project_local_lookup
from scripts.reefiki_core.init_workspace import init_workspace_payload


def test_init_cli_creates_valid_indexed_project(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "reefiki-workspace"

    code = reefiki.main(
        [
            "init",
            "--workspace",
            str(workspace),
            "--project-name",
            "first-run",
            "--title",
            "First Run",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    project = workspace / "projects" / "first-run"

    assert code == 0
    assert payload["outcome"] == "pass"
    assert payload["schema_version"] == "reefiki.init.v1"
    assert payload["project"]["name"] == "first-run"
    assert "projects/first-run/wiki/concepts/first-run-memory.md" in payload["created_paths"]
    assert "projects/first-run/.reefiki/index.sqlite" in payload["created_paths"]
    assert 'schema_version: "1.0"' in (project / "_domain.md").read_text(encoding="utf-8")
    assert doctor_payload(project)["outcome"] == "pass"
    validation_errors = []
    validation_errors.extend(validate_frontmatter.validate_file_report(project / "wiki" / "concepts" / "first-run-memory.md"))
    validation_errors.extend(validate_frontmatter.validate_index_report(project / "wiki" / "index.md"))
    validation_errors.extend(validate_frontmatter.validate_schema_version_report(project))
    assert validation_errors == []

    hits = project_local_lookup(project, "first-run memory workspace", limit=3)
    assert hits
    assert hits[0]["id"] == "first-run-memory"


def test_init_blocks_invalid_project_name(tmp_path: Path) -> None:
    payload = init_workspace_payload(tmp_path / "workspace", "../bad", None, "product")

    assert payload["outcome"] == "block"
    assert payload["reason"] == "invalid_project_name"
    assert payload["created_paths"] == []


def test_init_blocks_non_portable_project_name(tmp_path: Path) -> None:
    payload = init_workspace_payload(tmp_path / "workspace", "bad:name", None, "product")

    assert payload["outcome"] == "block"
    assert payload["reason"] == "invalid_project_name"
    assert payload["created_paths"] == []


def test_init_blocks_control_character_project_name_without_partial_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    payload = init_workspace_payload(workspace, "bad\nname", None, "product")

    assert payload["outcome"] == "block"
    assert payload["reason"] == "invalid_project_name"
    assert payload["created_paths"] == []
    assert not workspace.exists()


def test_init_blocks_existing_project_without_overwrite(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = init_workspace_payload(workspace, "first-run", None, "product")
    second = init_workspace_payload(workspace, "first-run", None, "product")

    assert first["outcome"] == "pass"
    assert second["outcome"] == "block"
    assert second["reason"] == "project_exists"


def test_init_blocks_non_empty_existing_workspace_without_overwrite(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("existing workspace\n", encoding="utf-8")

    payload = init_workspace_payload(workspace, "first-run", None, "product")

    assert payload["outcome"] == "block"
    assert payload["reason"] == "workspace_exists"
    assert payload["created_paths"] == []
    assert not (workspace / "projects").exists()


def test_init_code_project_without_apply_bridge_does_not_mutate_code_project(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    code_project = tmp_path / "code"
    code_project.mkdir()

    payload = init_workspace_payload(
        workspace,
        "first-run",
        None,
        "product",
        code_project=code_project,
        apply_bridge=False,
    )

    assert payload["outcome"] == "pass"
    assert payload["bridge"]["outcome"] == "not_applied"
    assert not (code_project / ".reefiki").exists()
    assert not (code_project / "_wiki").exists()
    assert not (code_project / ".gitignore").exists()


def test_init_apply_bridge_writes_marker_gitignore_and_passes_connect_check(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    code_project = tmp_path / "code"
    code_project.mkdir()
    run_git(code_project, ["init"])

    def fake_bridge(link: Path, target: Path) -> tuple[bool, str | None]:
        assert target == workspace / "projects" / "first-run"
        link.mkdir()
        (link / "AGENTS.md").write_text(f"linked to {target}\n", encoding="utf-8")
        return True, None

    monkeypatch.setattr(init_workspace, "_create_directory_bridge", fake_bridge)

    payload = init_workspace_payload(
        workspace,
        "first-run",
        None,
        "product",
        code_project=code_project,
        apply_bridge=True,
    )

    assert payload["outcome"] == "pass"
    assert payload["bridge"]["outcome"] == "pass"
    assert (code_project / ".reefiki").is_file()
    assert (code_project / "_wiki").is_dir()
    gitignore = (code_project / ".gitignore").read_text(encoding="utf-8")
    assert "_wiki/" in gitignore
    assert ".reefiki" in gitignore
    assert connect_check_payload(code_project)["status"] == "pass"


def test_init_bridge_unsupported_leaves_no_bridge_partial_files(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    code_project = tmp_path / "code"
    code_project.mkdir()

    def fail_bridge(link: Path, target: Path) -> tuple[bool, str | None]:
        return False, "symlink disabled"

    monkeypatch.setattr(init_workspace, "_create_directory_bridge", fail_bridge)

    payload = init_workspace_payload(
        workspace,
        "first-run",
        None,
        "product",
        code_project=code_project,
        apply_bridge=True,
    )

    assert payload["outcome"] == "warn"
    assert payload["bridge"]["reason"] == "bridge_unsupported"
    assert (workspace / "projects" / "first-run").is_dir()
    assert not (code_project / "_wiki").exists()
    assert not (code_project / ".reefiki").exists()
    assert not (code_project / ".gitignore").exists()


def test_init_bridge_apply_failure_rolls_back_marker_bridge_and_gitignore(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    code_project = tmp_path / "code"
    code_project.mkdir()

    def fake_bridge(link: Path, target: Path) -> tuple[bool, str | None]:
        link.mkdir()
        return True, None

    def fail_connect_check(_path: Path) -> dict[str, object]:
        raise RuntimeError("connect-check failed")

    monkeypatch.setattr(init_workspace, "_create_directory_bridge", fake_bridge)
    monkeypatch.setattr(init_workspace, "connect_check_payload", fail_connect_check)

    payload = init_workspace_payload(
        workspace,
        "first-run",
        None,
        "product",
        code_project=code_project,
        apply_bridge=True,
    )

    assert payload["outcome"] == "warn"
    assert payload["bridge"]["reason"] == "bridge_apply_failed"
    assert not (code_project / "_wiki").exists()
    assert not (code_project / ".reefiki").exists()
    assert not (code_project / ".gitignore").exists()


def test_first_run_public_docs_reference_init_command() -> None:
    doc_paths = [
        Path("README.md"),
        Path("COMMANDS.md"),
        Path("QUICKSTART.md"),
        Path("docs/INSTALL.md"),
        Path("docs/PUBLIC_DEMO.md"),
    ]
    docs = "\n".join(path.read_text(encoding="utf-8") for path in doc_paths)

    for path in doc_paths:
        text = path.read_text(encoding="utf-8")
        assert "reefiki init --workspace" in text, path
        assert "/tmp/reefiki-workspace" in text, path
    assert "reefiki init --workspace" in docs
    assert "/tmp/reefiki-workspace" in docs
    assert "standalone binary" not in docs.lower()
