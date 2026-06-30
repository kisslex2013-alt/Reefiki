from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "local-agent-delegation"
    / "scripts"
    / "local_agent_delegate.py"
)
SKILL_PATH = SCRIPT_PATH.parents[1] / "SKILL.md"


def load_module():
    spec = importlib.util.spec_from_file_location("local_agent_delegate", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)


def test_adapters_intentionally_exclude_local_hermes():
    module = load_module()

    assert "hermes-local" not in module.ADAPTERS
    assert module.ADAPTERS["hermes-vps"].transport == "ssh"


def test_hermes_vps_invocation_uses_ssh_and_prompt_stdin():
    module = load_module()

    invocation = module.build_invocation(
        "hermes-vps",
        "Return exactly: ok",
        Path("D:/Projects/REEFIKI"),
        title="smoke",
        hermes_key="C:/ssh/hermes_vps_id_rsa",
        hermes_host="example.invalid",
        hermes_user="agent",
        hermes_remote_cwd="/srv/projects",
        hermes_executable="/home/codex/.hermes/hermes-agent/venv/bin/hermes",
    )

    command_text = " ".join(invocation.command)
    assert invocation.command[0] == "ssh"
    assert "agent@example.invalid" in invocation.command
    assert "/home/codex/.hermes/hermes-agent/venv/bin/hermes" in command_text
    assert "chat" in command_text
    assert "hermes.exe" not in command_text.lower()
    assert invocation.stdin == "Return exactly: ok"
    assert "-q Return exactly: ok" not in command_text
    assert "C:/ssh/hermes_vps_id_rsa" not in invocation.redacted_command()


def test_hermes_vps_requires_explicit_connection_details():
    module = load_module()

    with pytest.raises(SystemExit, match="Hermes VPS requires --hermes-key"):
        module.build_invocation(
            "hermes-vps",
            "Return exactly: ok",
            Path("."),
            title="smoke",
            hermes_key="",
            hermes_host="",
            hermes_user="",
        )


def test_read_only_cli_flags_are_used_for_claude_and_gemini():
    module = load_module()

    claude = module.build_invocation("claude", "review only", Path("."), title="review")
    gemini = module.build_invocation("gemini", "review only", Path("."), title="review")

    assert "--permission-mode" in claude.command
    assert "plan" in claude.command
    assert "--skip-trust" in gemini.command
    assert "--approval-mode" in gemini.command
    assert "plan" in gemini.command
    assert gemini.env == {"GEMINI_CLI_TRUST_WORKSPACE": "true"}


def test_mimo_does_not_use_dangerous_skip_permissions():
    module = load_module()

    invocation = module.build_invocation("mimo", "review only", Path("."), title="review")

    assert "run" in invocation.command
    assert "--pure" in invocation.command
    assert "--format" in invocation.command
    assert "json" in invocation.command
    assert "--dangerously-skip-permissions" not in invocation.command


def test_mimo_prompt_is_redacted_from_plan_output():
    module = load_module()

    invocation = module.build_invocation("mimo", "secret prompt text", Path("."), title="review")

    redacted = invocation.redacted_command()
    assert "secret prompt text" not in redacted
    run_index = redacted.index("run")
    assert redacted[run_index + 1] == "<redacted>"


@pytest.mark.parametrize("agent", ["claude", "gemini"])
def test_prompt_flag_agents_redact_prompt_from_plan_output(agent):
    module = load_module()

    invocation = module.build_invocation(agent, "secret prompt text", Path("."), title="review")

    redacted = invocation.redacted_command()
    assert "secret prompt text" not in redacted
    assert "<redacted>" in redacted


def test_odysseus_adapter_is_visible_but_disabled_until_api_flow_exists():
    module = load_module()

    assert "odysseus-api" in module.ADAPTERS
    assert module.ADAPTERS["odysseus-api"].enabled is False
    with pytest.raises(SystemExit, match="Disabled adapter"):
        module.parse_agents("odysseus-api")


def test_skill_doc_does_not_expose_local_absolute_paths():
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "S:\\" not in text
    assert "H:\\" not in text
    assert "C:\\Users\\" not in text


def test_windows_resolution_prefers_cmd_wrappers(monkeypatch):
    module = load_module()

    monkeypatch.setattr(module, "IS_WINDOWS", True)

    def fake_which(command: str) -> str | None:
        return {
            "mimo.cmd": "C:/Users/example/AppData/Roaming/npm/mimo.cmd",
            "gemini.cmd": "C:/Users/example/AppData/Roaming/npm/gemini.cmd",
        }.get(command)

    monkeypatch.setattr(module.shutil, "which", fake_which)

    mimo = module.build_invocation("mimo", "review only", Path("."), title="review")
    gemini = module.build_invocation("gemini", "review only", Path("."), title="review")

    assert mimo.command[0].endswith("/mimo.cmd")
    assert gemini.command[0].endswith("/gemini.cmd")


def test_read_only_run_passes_when_git_status_stays_clean(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    out_dir = repo / ".reefiki" / "agent-runs" / "clean"
    invocation = module.Invocation(
        agent="claude",
        command=(sys.executable, "-c", "print('ok')"),
        cwd=repo,
    )

    payload = module._run_invocation(invocation, out_dir, timeout=10)

    assert payload["status"] == "pass"
    assert payload["mutation"]["status"] == "clean"
    assert payload["mutation"]["changed_entries"] == []
    assert payload["mutation"]["ignored_paths"] == [".reefiki/agent-runs/clean"]


@pytest.mark.parametrize(
    ("script", "expected_fragment"),
    [
        ("from pathlib import Path; Path('untracked.txt').write_text('x')", "?? untracked.txt"),
        (
            "from pathlib import Path; Path('tracked.txt').write_text('changed')",
            " M tracked.txt",
        ),
        (
            "from pathlib import Path; import subprocess; Path('staged.txt').write_text('x'); subprocess.run(['git','add','staged.txt'], check=True)",
            "A  staged.txt",
        ),
    ],
)
def test_read_only_run_reports_untracked_modified_and_staged_mutations(
    tmp_path: Path,
    script: str,
    expected_fragment: str,
):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "tracked.txt").write_text("original", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True, text=True)
    invocation = module.Invocation(
        agent="claude",
        command=(sys.executable, "-c", script),
        cwd=repo,
    )

    payload = module._run_invocation(invocation, tmp_path / "out", timeout=10)

    assert payload["status"] == "mutated"
    assert payload["mutation"]["status"] == "mutated"
    assert expected_fragment in payload["mutation"]["changed_entries"]


def test_mimo_run_without_hard_read_only_flag_is_still_post_checked(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    invocation = module.Invocation(
        agent="mimo",
        command=(sys.executable, "-c", "from pathlib import Path; Path('mimo-change.txt').write_text('x')"),
        cwd=repo,
    )

    payload = module._run_invocation(invocation, tmp_path / "out", timeout=10)

    assert payload["status"] == "mutated"
    assert payload["mutation"]["status"] == "mutated"
    assert "?? mimo-change.txt" in payload["mutation"]["changed_entries"]


def test_mutation_status_overrides_adapter_failure_but_preserves_adapter_status(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    invocation = module.Invocation(
        agent="claude",
        command=(
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; Path('changed-before-fail.txt').write_text('x'); sys.exit(2)",
        ),
        cwd=repo,
    )

    payload = module._run_invocation(invocation, tmp_path / "out", timeout=10)

    assert payload["status"] == "mutated"
    assert payload["adapter_status"] == "fail"
    assert payload["returncode"] == 2
    assert "?? changed-before-fail.txt" in payload["mutation"]["changed_entries"]


def test_dirty_baseline_is_fail_closed_as_needs_review(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    (repo / "preexisting.txt").write_text("dirty", encoding="utf-8")
    invocation = module.Invocation(
        agent="claude",
        command=(sys.executable, "-c", "print('ok')"),
        cwd=repo,
    )

    payload = module._run_invocation(invocation, tmp_path / "out", timeout=10)

    assert payload["status"] == "needs_review"
    assert payload["mutation"]["status"] == "needs_review"
    assert payload["mutation"]["reason"] == "baseline_dirty"
    assert "?? preexisting.txt" in payload["mutation"]["before_entries"]


def test_hermes_vps_result_declares_remote_mutation_boundary(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    init_git_repo(repo)
    invocation = module.Invocation(
        agent="hermes-vps",
        command=(sys.executable, "-c", "print('ok')"),
        cwd=repo,
    )

    payload = module._run_invocation(invocation, tmp_path / "out", timeout=10)

    assert payload["status"] == "pass"
    assert payload["mutation"]["status"] == "clean"
    assert payload["mutation"]["coverage"]["scope"] == "local_cwd"
    assert payload["mutation"]["coverage"]["remote_cwd"] == "not_checked"
