from pathlib import Path

from scripts import reefiki


def test_onboarding_cli_runs_from_non_reefiki_cwd(tmp_path: Path, monkeypatch, capsys) -> None:
    outside = tmp_path / "outside"
    fixture_root = tmp_path / "first-run"
    outside.mkdir()
    monkeypatch.chdir(outside)

    assert reefiki.main(["onboarding", "--format", "json"]) == 0
    out = capsys.readouterr().out
    assert '"mode": "dry-run"' in out
    assert '"language": "ru"' in out
    assert '"mascot": "Рифик"' in out

    assert reefiki.main(["onboarding", "--no-interactive"]) == 0
    out = capsys.readouterr().out
    assert "╭─ REEFIKI · Рифик" in out
    assert "  (.)---(.)" in out
    assert " /  \\_/  \\" in out
    assert " \\_______/" in out
    assert "  /_/ \\_\\" in out
    assert "Добро пожаловать в REEFIKI" in out
    assert "Пошаговый режим: reefiki onboarding --interactive" in out
    assert "Показать все команды: reefiki onboarding --show-commands" in out
    assert "## Маршрут" not in out
    assert "reefiki ops-dashboard serve" not in out

    assert reefiki.main(["onboarding", "--lang", "en", "--no-interactive"]) == 0
    out = capsys.readouterr().out
    assert "╭─ REEFIKI · Rifiki" in out
    assert "Welcome to REEFIKI" in out
    assert "Step-by-step mode: reefiki onboarding --interactive" in out

    assert reefiki.main(["onboarding", "--no-interactive", "--show-commands"]) == 0
    out = capsys.readouterr().out
    assert "Команды:" in out
    assert "reefiki ops-dashboard serve --workspace-root <dashboard-demo-folder> --port 7310" in out
    assert "Запасной запуск нужен только если команда reefiki не найдена." in out
    assert out.count("Запасной запуск нужен только если команда reefiki не найдена.") == 1

    responses = iter(["1", "4"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert reefiki.main(["onboarding", "--interactive"]) == 0
    out = capsys.readouterr().out
    assert "Команды первого запуска" in out
    assert "╭─ REEFIKI " in out
    assert "REEFIKI · Rifiki / Рифик" not in out
    assert out.count("  (.)---(.)") == 1
    assert out.count("Запасной запуск нужен только если команда reefiki не найдена.") == 1

    interactive_root = tmp_path / "interactive-demo"
    responses = iter(["1", "1", str(interactive_root), "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert reefiki.main(["onboarding", "--interactive"]) == 0
    out = capsys.readouterr().out
    assert "Выберите язык / Choose language" in out
    assert out.count("  (.)---(.)") == 1
    assert "Что хотите сделать сейчас?" in out
    assert "Демо создано" in out
    assert (interactive_root / "projects" / "reefiki-onboarding-demo" / "wiki" / "index.md").exists()

    assert reefiki.main(["onboarding", "--fixture-root", str(fixture_root), "--format", "json"]) == 0
    out = capsys.readouterr().out
    assert '"mode": "fixture"' in out
    assert (fixture_root / "projects" / "reefiki-onboarding-demo" / "wiki" / "index.md").exists()


def test_ops_dashboard_demo_cli_runs_from_non_reefiki_cwd(tmp_path: Path, monkeypatch, capsys) -> None:
    outside = tmp_path / "outside"
    fixture_root = tmp_path / "dashboard"
    outside.mkdir()
    monkeypatch.chdir(outside)

    assert reefiki.main(["ops-dashboard", "demo", "--fixture-root", str(fixture_root), "--format", "json"]) == 0
    out = capsys.readouterr().out
    assert '"mode": "fixture"' in out
    assert (fixture_root / ".reefiki-dashboard-demo").exists()


def test_ops_dashboard_serve_cli_reaches_server_from_non_reefiki_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    outside = tmp_path / "outside"
    workspace_root = tmp_path / "workspace"
    outside.mkdir()
    workspace_root.mkdir()
    monkeypatch.chdir(outside)

    calls: dict[str, object] = {}

    def fake_serve_ops_dashboard(
        workspace: Path,
        reefiki_root: Path,
        port: int,
        allow_log_paths: list[str] | None = None,
        ui: str = "current",
    ) -> int:
        calls["workspace"] = workspace
        calls["reefiki_root"] = reefiki_root
        calls["port"] = port
        calls["allow_log_paths"] = allow_log_paths
        calls["ui"] = ui
        return 0

    monkeypatch.setattr(reefiki, "serve_ops_dashboard", fake_serve_ops_dashboard)

    assert (
        reefiki.main(
            [
                "ops-dashboard",
                "serve",
                "--workspace-root",
                str(workspace_root),
                "--port",
                "7319",
            ]
        )
        == 0
    )
    assert calls == {
        "workspace": workspace_root,
        "reefiki_root": outside.resolve(),
        "port": 7319,
        "allow_log_paths": [],
        "ui": "current",
    }

    assert (
        reefiki.main(
            [
                "ops-dashboard",
                "serve",
                "--workspace-root",
                str(workspace_root),
                "--port",
                "7320",
                "--ui",
                "next",
            ]
        )
        == 0
    )
    assert calls == {
        "workspace": workspace_root,
        "reefiki_root": outside.resolve(),
        "port": 7320,
        "allow_log_paths": [],
        "ui": "next",
    }
