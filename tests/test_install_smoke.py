from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def installed_script(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "reefiki.exe"
    return venv / "bin" / "reefiki"


def installed_bin_dir(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts"
    return venv / "bin"


def installed_env(venv: Path) -> dict[str, str]:
    keep = [
        "SystemRoot",
        "SYSTEMROOT",
        "ComSpec",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
    ]
    env = {name: os.environ[name] for name in keep if name in os.environ}
    env["PATH"] = str(installed_bin_dir(venv)) + os.pathsep + os.environ.get("PATH", "")
    env["PYTHONUTF8"] = "1"
    return env


def reefiki_command(*args: str) -> list[str]:
    if os.name == "nt":
        return ["cmd.exe", "/c", "reefiki", *args]
    return ["reefiki", *args]


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def run_captured(args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )


def copy_install_source(destination: Path) -> None:
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".pytest_cache",
            ".reefiki",
            "__pycache__",
            "build",
            "dist",
            "reefiki.egg-info",
        ),
    )


def write_fixture_project(project: Path) -> None:
    (project / "wiki" / "concepts").mkdir(parents=True)
    (project / "inbox").mkdir(parents=True)
    (project / "seen").mkdir(parents=True)
    (project / "raw").mkdir(parents=True)
    (project / "wiki" / "log.md").write_text("", encoding="utf-8")
    (project / "wiki" / "index.md").write_text(
        """# Index

Last updated: 2026-06-11
Total pages: 1

## Sources
## Entities
## Concepts

### install-smoke
- type: concept
- tags: [install]
- useful_when: ["checking installed CLI status"]
- file: wiki/concepts/install-smoke.md
- date_added: 2026-06-11
- use_count: 0

## Synthesis
## Decisions
## Skills
""",
        encoding="utf-8",
    )
    (project / "wiki" / "concepts" / "install-smoke.md").write_text(
        """---
id: install-smoke
title: Install Smoke
type: concept
tags: [install]
useful_when:
  - "checking installed CLI status"
date_added: 2026-06-11
use_count: 0
last_used:
---

# Install Smoke
""",
        encoding="utf-8",
    )


def test_local_package_install_entrypoint_status_and_uninstall() -> None:
    with tempfile.TemporaryDirectory(prefix="reefiki-install-test-") as temp:
        temp_path = Path(temp)
        venv = temp_path / "venv"
        project = temp_path / "fixture"
        outside_cwd = temp_path / "outside-cwd"
        install_source = temp_path / "source"
        write_fixture_project(project)
        copy_install_source(install_source)
        outside_cwd.mkdir()

        run_captured([sys.executable, "-m", "venv", str(venv)], check=True)
        python = venv_python(venv)
        reefiki = installed_script(venv)

        run_captured([str(python), "-m", "pip", "install", str(install_source)], check=True)
        env = installed_env(venv)

        assert reefiki.exists()
        resolved = shutil.which("reefiki", path=env["PATH"])
        assert resolved is not None
        assert os.path.normcase(resolved) == os.path.normcase(str(reefiki))

        help_result = run_captured(reefiki_command("--help"), cwd=outside_cwd, env=env, check=True)
        assert "REEFIKI local tools" in help_result.stdout

        tour_result = run_captured(reefiki_command("tour", "--format", "json"), cwd=outside_cwd, env=env, check=True)
        assert '"schema_version": "reefiki.guided-tour.v1"' in tour_result.stdout
        assert '"read_only": true' in tour_result.stdout

        onboarding_result = run_captured(reefiki_command("onboarding", "--format", "json"), cwd=outside_cwd, env=env, check=True)
        assert '"mode": "dry-run"' in onboarding_result.stdout

        first_run_workspace = temp_path / "reefiki-workspace"
        init_result = run_captured(
            reefiki_command(
                "init",
                "--workspace",
                str(first_run_workspace),
                "--project-name",
                "first-run",
                "--format",
                "json",
            ),
            cwd=outside_cwd,
            env=env,
            check=True,
        )
        assert '"schema_version": "reefiki.init.v1"' in init_result.stdout
        assert '"outcome": "pass"' in init_result.stdout

        first_run_project = first_run_workspace / "projects" / "first-run"
        doctor_result = run_captured(
            reefiki_command("--project", str(first_run_project), "doctor", "--format", "json"),
            env=env,
            check=True,
        )
        assert '"outcome": "pass"' in doctor_result.stdout
        status_result = run_captured(reefiki_command("--project", str(first_run_project), "status"), env=env, check=True)
        assert "Project: first-run" in status_result.stdout

        imported_vault = temp_path / "imported-vault"
        imported_vault.mkdir()
        (imported_vault / "first-note.md").write_text("# First imported note\n", encoding="utf-8")
        import_result = run_captured(
            reefiki_command(
                "--project",
                str(first_run_project),
                "import",
                str(imported_vault),
                "--from",
                "markdown",
                "--format",
                "json",
            ),
            cwd=outside_cwd,
            env=env,
            check=True,
        )
        assert '"schema_version": "reefiki.import.v1"' in import_result.stdout
        assert '"imported_count": 1' in import_result.stdout
        assert (first_run_project / "inbox" / "first-note.md").exists()

        dashboard_root = temp_path / "dashboard-demo"
        dashboard_result = run_captured(
            reefiki_command("ops-dashboard", "demo", "--fixture-root", str(dashboard_root), "--format", "json"),
            cwd=outside_cwd,
            env=env,
            check=True,
        )
        assert '"mode": "fixture"' in dashboard_result.stdout
        assert (dashboard_root / ".reefiki-dashboard-demo").exists()
        server = subprocess.Popen(
            [
                str(reefiki),
                "ops-dashboard",
                "serve",
                "--workspace-root",
                str(dashboard_root),
                "--port",
                "0",
            ],
            cwd=outside_cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert server.stdout is not None
            line = server.stdout.readline().strip()
            assert line.startswith("REEFIKI Ops Dashboard v2: http://127.0.0.1:")
            url = line.removeprefix("REEFIKI Ops Dashboard v2: ").strip()
            html = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
            assert "REEFIKI Ops Dashboard v2" in html
            assert "REEFIKI Ops Dashboard" in html
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

        status_result = run_captured(reefiki_command("--project", str(project), "status"), env=env, check=True)
        assert "Project: fixture" in status_result.stdout
        assert "Wiki: concept=1" in status_result.stdout

        run_captured([str(python), "-m", "pip", "uninstall", "-y", "reefiki"], check=True)
        show_result = run_captured([str(python), "-m", "pip", "show", "reefiki"], check=False)
        assert show_result.returncode != 0
