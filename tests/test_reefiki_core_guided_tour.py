import json
from pathlib import Path

from scripts import reefiki
from scripts.reefiki_core.guided_tour import guided_tour_payload
from scripts.reefiki_core.onboarding import onboarding_wizard_payload


def test_guided_tour_blocks_status_dashboard_and_connect_without_fixture(tmp_path: Path) -> None:
    payload = guided_tour_payload(tmp_path)

    by_id = {step["id"]: step for step in payload["steps"]}
    assert payload["read_only"] is True
    assert by_id["onboarding"]["status"] == "done"
    assert by_id["fixture"]["status"] == "current"
    assert by_id["status"]["status"] == "blocked"
    assert by_id["dashboard"]["status"] == "blocked"
    assert by_id["connect"]["status"] == "blocked"
    assert payload["next_action"] == "reefiki onboarding --fixture-root <demo-folder>"


def test_guided_tour_marks_fixture_and_status_done(tmp_path: Path) -> None:
    fixture_root = tmp_path / "demo"
    onboarding_wizard_payload(tmp_path, fixture_root=fixture_root)

    payload = guided_tour_payload(tmp_path, fixture_root=fixture_root)
    by_id = {step["id"]: step for step in payload["steps"]}

    assert by_id["fixture"]["status"] == "done"
    assert by_id["status"]["status"] == "done"
    assert by_id["dashboard"]["status"] == "current"


def test_guided_tour_connect_step_uses_connect_check(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "_wiki").mkdir()
    (repo / ".reefiki").write_text("project_name: demo\n", encoding="utf-8")

    payload = guided_tour_payload(tmp_path, connect_path=repo)
    by_id = {step["id"]: step for step in payload["steps"]}

    assert by_id["connect"]["status"] == "done"
    assert by_id["connect"]["evidence"] == "connect-check=pass"


def test_guided_tour_cli_json_and_text(tmp_path: Path, capsys) -> None:
    assert reefiki.main(["tour", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "reefiki.guided-tour.v1"
    assert payload["summary"]["outcome"] == "blocked"

    assert reefiki.main(["tour"]) == 0
    out = capsys.readouterr().out
    assert "guided tour: blocked" in out
    assert "reefiki onboarding --fixture-root <demo-folder>" in out
