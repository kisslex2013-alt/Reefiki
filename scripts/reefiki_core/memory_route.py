from __future__ import annotations

import json

try:
    from reefiki_memory import RouteDecision
except ModuleNotFoundError:  # pragma: no cover - package import fallback for tests
    from scripts.reefiki_memory import RouteDecision


def memory_route(text: str, project_hint: str | None = None) -> dict[str, object]:
    normalized = text.strip().lower()
    if not normalized:
        raise SystemExit("Empty content.")
    if any(token in normalized for token in ["where is", "где леж", "структур", "file", "module", "repo map"]):
        return _route_payload(
            RouteDecision(
                recommended_layer="graphify",
                reason="structure/navigation intent",
                target_project=project_hint,
            )
        )
    if _is_external_dogfood_intent(normalized):
        return _route_payload(
            RouteDecision(
                recommended_layer="reefiki",
                secondary_layers=["memoir"],
                reason="external project dogfood/onboarding intent",
                target_project=project_hint or "reefiki",
            )
        )
    if any(
        token in normalized
        for token in ["decide", "decision", "решили", "процедур", "policy", "contract", "pack", "handoff"]
    ):
        return _route_payload(
            RouteDecision(
                recommended_layer="reefiki",
                secondary_layers=["graphify"],
                reason="durable decision/procedure intent",
                target_project=project_hint or "reefiki",
                risk_flags=["durable_write_requires_review"],
            )
        )
    if any(
        token in normalized
        for token in ["roadmap", "roadmap.md", "tasks.md", "backlog", "sprint", "phase", "review queue", "review-queue", "health gate"]
    ):
        return _route_payload(
            RouteDecision(
                recommended_layer="reefiki",
                secondary_layers=["memoir"],
                reason="project roadmap/governance intent",
                target_project=project_hint or "reefiki",
            )
        )
    if len(normalized) < 160 and any(
        token in normalized for token in ["prefer", "prefers", "from now on", "remember", "предпоч", "правило"]
    ):
        return _route_payload(
            RouteDecision(
                recommended_layer="memoir",
                reason="working preference/rule intent",
                target_project=project_hint,
            )
        )
    return _route_payload(
        RouteDecision(
            recommended_layer="memoir",
            reason="default short working memory",
            target_project=project_hint,
        )
    )


def _is_external_dogfood_intent(normalized: str) -> bool:
    if any(token in normalized for token in ["odysseus", "dogfood", "agent-readiness", "agent readiness"]):
        return True
    if "roadmap" in normalized and "trigger" in normalized:
        return True
    external_scope = any(token in normalized for token in ["external", "внешн", "repo", "repository", "project"])
    onboarding_scope = any(token in normalized for token in ["onboarding", "онборд", "readiness", "готовност"])
    return external_scope and onboarding_scope


def _route_payload(decision: RouteDecision) -> dict[str, object]:
    payload = decision.to_dict()
    payload["layer"] = payload["recommended_layer"]
    payload["project_hint"] = payload["target_project"]
    return payload


def print_memory_route(text: str, project_hint: str | None, fmt: str) -> int:
    result = memory_route(text, project_hint=project_hint)
    if fmt == "json":
        contract_result = {
            key: value
            for key, value in result.items()
            if key not in {"layer", "project_hint"}
        }
        print(json.dumps(contract_result, ensure_ascii=False, indent=2))
        return 0
    print(f"layer: {result['recommended_layer']}")
    print(f"reason: {result['reason']}")
    if result.get("target_project"):
        print(f"project_hint: {result['target_project']}")
    return 0
