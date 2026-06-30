from __future__ import annotations

import json
from pathlib import Path

from .project_paths import find_project, iter_pages, relative


QMD_REQUIRED_GATES = [
    "run_memory_golden",
    "compare_against_current_fts",
    "fixed_small_corpus",
    "ignore_and_cleanup_generated_qmd_paths",
    "no_global_install",
    "no_mcp_daemon",
    "no_model_downloads_without_explicit_approval",
]

QMD_BLOCKED_ACTIONS = [
    "runtime_adoption",
    "query_path_switch",
    "mcp_daemon",
    "embeddings_models",
    "global_install",
    "durable_source_of_truth_change",
]

QMD_ALLOWED_ACTIONS = [
    "sandbox_smoke",
    "benchmark_against_current_fts",
    "write_report",
]


def _find_qmd_candidate_page(project: Path) -> str | None:
    for page in iter_pages(project):
        if page.stem == "qmd-retrieval-experiment":
            return relative(project, page)
    return None


def retrieval_preflight_payload(
    root: Path,
    project_name: str,
    candidate: str,
    observed_misses: int = 0,
    allow_runtime_eval: bool = False,
) -> dict[str, object]:
    normalized_candidate = candidate.strip().lower()
    if normalized_candidate != "qmd":
        return {
            "candidate": candidate,
            "outcome": "unsupported",
            "runtime_adoption": "blocked",
            "blocking_reasons": ["unsupported_candidate"],
            "allowed_actions": [],
            "blocked_actions": QMD_BLOCKED_ACTIONS,
            "required_gates": [],
            "evidence": {},
            "next_action": "create a candidate-specific preflight rule before experimentation",
        }

    project = find_project(root, project_name)
    durable_page = _find_qmd_candidate_page(project)
    required_gates = list(QMD_REQUIRED_GATES)
    allowed_actions = list(QMD_ALLOWED_ACTIONS)
    blocking_reasons: list[str] = []

    if durable_page is None:
        outcome = "watch"
        runtime_adoption = "blocked"
        blocking_reasons.append("missing_durable_candidate_page")
        required_gates.insert(0, "create_or_link_durable_candidate_page")
        next_action = "link or create qmd durable candidate page before running another smoke"
    elif observed_misses > 0 and allow_runtime_eval:
        outcome = "runtime-eval-ready"
        runtime_adoption = "evaluate-only"
        allowed_actions.append("runtime_eval")
        next_action = "run bounded qmd comparison on the fixed miss set; do not switch query path automatically"
    else:
        outcome = "experiment-ready"
        runtime_adoption = "blocked"
        next_action = "run sandbox smoke or benchmark only; keep qmd disabled by default"

    return {
        "candidate": "qmd",
        "project": project.name,
        "outcome": outcome,
        "runtime_adoption": runtime_adoption,
        "observed_misses": max(0, observed_misses),
        "allow_runtime_eval": allow_runtime_eval,
        "blocking_reasons": blocking_reasons,
        "allowed_actions": allowed_actions,
        "blocked_actions": QMD_BLOCKED_ACTIONS,
        "required_gates": required_gates,
        "evidence": {
            "durable_page": durable_page,
            "wiki_pages": len(iter_pages(project)),
        },
        "next_action": next_action,
    }


def print_retrieval_preflight(
    root: Path,
    project_name: str,
    candidate: str,
    observed_misses: int,
    allow_runtime_eval: bool,
    fmt: str,
) -> int:
    payload = retrieval_preflight_payload(
        root,
        project_name,
        candidate,
        observed_misses=observed_misses,
        allow_runtime_eval=allow_runtime_eval,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"candidate: {payload['candidate']}")
        print(f"project: {payload.get('project', project_name)}")
        print(f"outcome: {payload['outcome']}")
        print(f"runtime_adoption: {payload['runtime_adoption']}")
        print(f"next: {payload['next_action']}")
    return 0 if payload["outcome"] != "unsupported" else 1
