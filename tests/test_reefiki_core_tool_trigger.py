from scripts.reefiki_core.tool_trigger import print_tool_trigger, tool_trigger_payload


def test_tool_trigger_payload_recommends_sandbox_for_visual_graph_need() -> None:
    payload = tool_trigger_payload(
        "Understand-Anything",
        "need visual onboarding graph for a large unknown codebase",
    )

    assert payload["tool"] == "Understand-Anything"
    assert payload["outcome"] == "sandbox-recommended"
    assert "graph" in payload["matched_triggers"]
    assert "unknown codebase" in payload["matched_triggers"]


def test_tool_trigger_payload_keeps_understand_anything_on_watch_without_trigger() -> None:
    payload = tool_trigger_payload("Understand-Anything", "normal REEFIKI query and harvest workflow")

    assert payload["outcome"] == "watch"
    assert payload["matched_triggers"] == []


def test_tool_trigger_payload_keeps_ecc_reference_only() -> None:
    payload = tool_trigger_payload("ECC", "need readiness gates and external tool security checklist")

    assert payload["tool"] == "ECC"
    assert payload["outcome"] == "reference-only"
    assert "borrow_patterns_only" in payload["guards"]


def test_print_tool_trigger_returns_failure_for_unsupported_tool(capsys) -> None:
    assert print_tool_trigger("unknown-tool", "anything", "text") == 1

    output = capsys.readouterr().out
    assert "tool: unknown-tool" in output
    assert "outcome: unsupported" in output
