from __future__ import annotations

import json


UNDERSTAND_ANYTHING_TRIGGERS = {
    "visual",
    "graph",
    "knowledge graph",
    "onboarding",
    "large codebase",
    "unknown codebase",
    "wiki graph",
    "understand-knowledge",
    "interactive",
}


def tool_trigger_payload(tool: str, signal: str) -> dict[str, object]:
    normalized_tool = tool.strip().lower()
    normalized_signal = signal.strip().lower()
    guards = [
        "do_not_install_globally",
        "isolated_sandbox_only",
        "no_auto_update_hooks",
        "do_not_commit_generated_graph_without_review",
        "compare_against_graphify_codegraph_reefiki",
    ]
    if normalized_tool not in {"understand-anything", "understand anything"}:
        if normalized_tool == "ecc":
            return {
                "tool": "ECC",
                "outcome": "reference-only",
                "matched_triggers": [],
                "guards": [
                    "do_not_install",
                    "borrow_patterns_only",
                    "avoid_hooks_and_memory_layer_duplication",
                    "keep_reefiki_as_governance_layer",
                ],
                "next_action": "use as pattern reference for trigger gates, readiness snapshots, security checklist or selective install design",
            }
        return {
            "tool": tool,
            "outcome": "unsupported",
            "matched_triggers": [],
            "guards": guards,
            "next_action": "no automation rule exists for this tool",
        }
    matched = sorted(trigger for trigger in UNDERSTAND_ANYTHING_TRIGGERS if trigger in normalized_signal)
    if matched:
        return {
            "tool": "Understand-Anything",
            "outcome": "sandbox-recommended",
            "matched_triggers": matched,
            "guards": guards,
            "next_action": "run isolated sandbox smoke; do not install globally or enable auto-update hooks",
        }
    return {
        "tool": "Understand-Anything",
        "outcome": "watch",
        "matched_triggers": [],
        "guards": guards,
        "next_action": "keep documented as candidate; do not run sandbox smoke yet",
    }


def print_tool_trigger(tool: str, signal: str, fmt: str) -> int:
    payload = tool_trigger_payload(tool, signal)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["outcome"] != "unsupported" else 1
    print(f"tool: {payload['tool']}")
    print(f"outcome: {payload['outcome']}")
    if payload["matched_triggers"]:
        print(f"matched: {', '.join(payload['matched_triggers'])}")
    print(f"next: {payload['next_action']}")
    return 0 if payload["outcome"] != "unsupported" else 1
