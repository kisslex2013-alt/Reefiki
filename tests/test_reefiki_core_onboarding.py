from pathlib import Path

from scripts.reefiki_core.onboarding import onboarding_wizard_payload


def test_onboarding_wizard_dry_run_does_not_write(tmp_path: Path) -> None:
    payload = onboarding_wizard_payload(tmp_path)

    assert payload["mode"] == "dry-run"
    assert payload["language"] == "ru"
    assert payload["brand"] == {
        "name": "REEFIKI",
        "mascot": "Рифик",
        "mascot_role": "Рифик, краб-архивариус рифа-вики",
    }
    assert "первый маршрут" in str(payload["headline"])
    assert "ничего не записывает" in str(payload["intro"])
    assert payload["question"] == "Что подтвердил первый источник?"
    assert payload["session_note"] == "Завершён первый запуск REEFIKI."
    assert payload["artifacts"] == []
    assert payload["first_run_commands"] == [
        "reefiki tour",
        "reefiki onboarding",
        "reefiki onboarding --fixture-root <demo-folder>",
        "reefiki --project <demo-folder>/projects/reefiki-onboarding-demo status",
        "reefiki ops-dashboard demo --fixture-root <dashboard-demo-folder>",
        "reefiki ops-dashboard serve --workspace-root <dashboard-demo-folder> --port 7310",
    ]
    assert payload["checkout_fallback_commands"] == [
        "python scripts/reefiki.py tour",
        "python scripts/reefiki.py onboarding",
        "python scripts/reefiki.py onboarding --fixture-root <demo-folder>",
        "python scripts/reefiki.py --project <demo-folder>/projects/reefiki-onboarding-demo status",
        "python scripts/reefiki.py ops-dashboard demo --fixture-root <dashboard-demo-folder>",
        "python scripts/reefiki.py ops-dashboard serve --workspace-root <dashboard-demo-folder> --port 7310",
    ]
    assert [step["step"] for step in payload["steps"]] == [
        "create",
        "save",
        "process",
        "query",
        "harvest",
        "status",
    ]
    assert not (tmp_path / "projects").exists()


def test_onboarding_wizard_supports_english_payload(tmp_path: Path) -> None:
    payload = onboarding_wizard_payload(tmp_path, lang="en")

    assert payload["language"] == "en"
    assert payload["brand"] == {
        "name": "REEFIKI",
        "mascot": "Rifiki",
        "mascot_role": "Rifiki, the reef-wiki archivist crab",
    }
    assert payload["question"] == "What did the onboarding source establish?"
    assert payload["session_note"] == "Finished the first REEFIKI onboarding run."
    assert "safe first-run path" in str(payload["headline"])
    assert payload["steps"][0]["intent"] == "create an isolated REEFIKI project from the template"


def test_onboarding_wizard_fixture_writes_first_run_artifacts(tmp_path: Path) -> None:
    payload = onboarding_wizard_payload(tmp_path, fixture_root=tmp_path)

    assert payload["mode"] == "fixture"
    assert payload["status_command"].endswith("projects/reefiki-onboarding-demo status")
    assert payload["dashboard_demo_command"].endswith("ops-dashboard demo --fixture-root <dashboard-demo-folder>")
    assert payload["checkout_fallback_commands"][0] == "python scripts/reefiki.py tour"
    artifacts = set(payload["artifacts"])
    assert {
        "projects/reefiki-onboarding-demo/AGENTS.md",
        "projects/reefiki-onboarding-demo/_domain.md",
        "projects/reefiki-onboarding-demo/raw/onboarding-source.md",
        "projects/reefiki-onboarding-demo/wiki/concepts/onboarding-first-source.md",
        "projects/reefiki-onboarding-demo/wiki/synthesis/onboarding-session-summary.md",
        "projects/reefiki-onboarding-demo/wiki/index.md",
        "projects/reefiki-onboarding-demo/wiki/log.md",
    }.issubset(artifacts)
    assert payload["transient_artifacts"] == [
        "projects/reefiki-onboarding-demo/inbox/onboarding-source.md"
    ]
    assert not (tmp_path / "projects" / "reefiki-onboarding-demo" / "inbox" / "onboarding-source.md").exists()
    log = (tmp_path / "projects" / "reefiki-onboarding-demo" / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "/save" in log
    assert "/process" in log
    assert "/query" in log
    assert "/harvest" in log
    assert "/status" in log
