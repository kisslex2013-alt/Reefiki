import pytest

from scripts.reefiki_core.memory_route import memory_route, print_memory_route


def test_memory_route_prefers_graphify_for_structure_queries() -> None:
    result = memory_route("where is the auth module and what files is it connected to?", project_hint="reefiki")

    assert result["layer"] == "graphify"
    assert result["recommended_layer"] == "graphify"
    assert result["project_hint"] == "reefiki"


def test_memory_route_prefers_reefiki_for_durable_decisions() -> None:
    result = memory_route("we decided to keep one routing contract for memory governance")

    assert result["layer"] == "reefiki"
    assert result["target_project"] == "reefiki"
    assert "graphify" in result["secondary_layers"]
    assert result["risk_flags"] == ["durable_write_requires_review"]


def test_memory_route_sends_roadmap_governance_to_reefiki_with_memoir_secondary() -> None:
    result = memory_route("continue REEFIKI roadmap development", project_hint="reefiki")

    assert result["layer"] == "reefiki"
    assert result["target_project"] == "reefiki"
    assert result["secondary_layers"] == ["memoir"]


def test_memory_route_sends_external_dogfood_onboarding_to_reefiki() -> None:
    result = memory_route("Odysseus dogfood external repo onboarding", project_hint="reefiki")

    assert result["layer"] == "reefiki"
    assert result["target_project"] == "reefiki"
    assert result["secondary_layers"] == ["memoir"]
    assert result["reason"] == "external project dogfood/onboarding intent"


def test_memory_route_defaults_short_preferences_to_memoir() -> None:
    result = memory_route("remember that I prefer short replies", project_hint="reefiki")

    assert result["layer"] == "memoir"
    assert result["target_project"] == "reefiki"


def test_memory_route_blocks_empty_content() -> None:
    with pytest.raises(SystemExit, match="Empty content."):
        memory_route(" ")


def test_print_memory_route_json_omits_backward_compatibility_aliases(capsys) -> None:
    assert print_memory_route("we decided to keep promotion inbox", "reefiki", "json") == 0

    output = capsys.readouterr().out
    assert '"recommended_layer": "reefiki"' in output
    assert '"layer"' not in output
    assert '"project_hint"' not in output


def test_print_memory_route_text_stays_readable(capsys) -> None:
    assert print_memory_route("where is auth module", "reefiki", "text") == 0

    output = capsys.readouterr().out
    assert "layer: graphify" in output
    assert "project_hint: reefiki" in output
