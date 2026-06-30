from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .markdown import as_text
from .project_paths import find_project, relative


def _lookup_hit_id(item: dict[str, object]) -> str:
    return as_text(item.get("id")) or as_text(item.get("node_id")) or as_text(item.get("path"))


def _lookup_hits_for_layer(lookup: dict[str, object], layer: str) -> list[dict[str, object]]:
    if layer == "graphify":
        return [item for item in lookup.get("graphify", []) if isinstance(item, dict)]
    if layer == "memoir":
        memoir = lookup.get("memoir", {})
        memories = memoir.get("memories", []) if isinstance(memoir, dict) else []
        return [item for item in memories if isinstance(item, dict)]
    hits = [item for item in lookup.get("reefiki", []) if isinstance(item, dict)]
    if layer == "all":
        hits.extend(item for item in lookup.get("graphify", []) if isinstance(item, dict))
    return hits


def _parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]


def load_golden_queries(path: Path) -> dict[str, object]:
    if not path.exists():
        raise SystemExit(f"Missing golden query file: {path}")
    data: dict[str, object] = {"queries": []}
    current: dict[str, object] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "queries:":
            continue
        if stripped.startswith("- "):
            if current is not None:
                data["queries"].append(current)  # type: ignore[union-attr]
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        value = raw_value.strip()
        parsed: object
        if value.startswith("[") and value.endswith("]"):
            parsed = _parse_inline_list(value)
        elif value.lower() == "null":
            parsed = None
        elif value.isdigit():
            parsed = int(value)
        else:
            parsed = value.strip("\"'")
        if current is None:
            data[key.strip()] = parsed
        else:
            current[key.strip()] = parsed
    if current is not None:
        data["queries"].append(current)  # type: ignore[union-attr]
    return data


def run_golden_queries(
    root: Path,
    project_name: str,
    project_local_lookup_fn: Callable[..., list[dict[str, object]]],
    global_lookup_fn: Callable[..., dict[str, object]],
    promotion_dry_run_fn: Callable[..., dict[str, object]],
    memory_pack_fn: Callable[..., dict[str, object]],
    path: Path | None = None,
) -> dict[str, object]:
    project = find_project(root, project_name)
    golden_path = path or project / "golden-queries.yml"
    config = load_golden_queries(golden_path)
    cases: list[dict[str, object]] = []
    misses: list[dict[str, object]] = []
    for case in config.get("queries", []):
        if not isinstance(case, dict):
            continue
        case_id = as_text(case.get("id")) or "unnamed"
        kind = as_text(case.get("kind"))
        errors: list[str] = []
        details: dict[str, object] = {}
        if kind == "lookup":
            layer = as_text(case.get("layer")) or "reefiki"
            if layer == "reefiki":
                lookup_hits = project_local_lookup_fn(project, as_text(case.get("query")), limit=5)
            else:
                lookup = global_lookup_fn(
                    root,
                    query=as_text(case.get("query")),
                    project=project_name,
                    include_memoir=layer in {"all", "memoir"},
                    include_reefiki=layer == "all",
                    include_graph=layer in {"all", "graphify"},
                    limit=5,
                )
                lookup_hits = _lookup_hits_for_layer(lookup, layer)
            actual_ids = [_lookup_hit_id(item) for item in lookup_hits]
            expected_ids = [as_text(item) for item in case.get("expect_ids", [])]
            missing = [expected for expected in expected_ids if expected not in actual_ids]
            if missing:
                errors.append(f"missing_ids:{','.join(missing)}")
                misses.append(
                    {
                        "case_id": case_id,
                        "missing_ids": missing,
                        "actual_ids": actual_ids,
                        "expected_ids": expected_ids,
                        "query": as_text(case.get("query")),
                    }
                )
            details = {"actual_ids": actual_ids, "expected_ids": expected_ids}
        elif kind == "promote":
            result = promotion_dry_run_fn(
                project,
                as_text(case.get("content")),
                confidence=0.8,
            )
            expected_verdict = as_text(case.get("expect_verdict"))
            expected_type = as_text(case.get("expect_target_type"))
            if expected_verdict and result["verdict"] != expected_verdict:
                errors.append(f"verdict:{result['verdict']}")
            if expected_type and result["suggested_target_type"] != expected_type:
                errors.append(f"target_type:{result['suggested_target_type']}")
            details = {
                "verdict": result["verdict"],
                "suggested_target_type": result["suggested_target_type"],
            }
        elif kind == "pack":
            result = memory_pack_fn(
                root,
                project_name,
                as_text(case.get("task")),
                limit=8,
                include_golden=False,
            )
            actual_ids = [
                as_text(item.get("id"))
                for item in result.get("contents", [])
                if isinstance(item, dict)
            ]
            expected_ids = [as_text(item) for item in case.get("expect_ids", [])]
            missing = [expected for expected in expected_ids if expected not in actual_ids]
            if missing:
                errors.append(f"missing_ids:{','.join(missing)}")
                misses.append(
                    {
                        "case_id": case_id,
                        "missing_ids": missing,
                        "actual_ids": actual_ids,
                        "expected_ids": expected_ids,
                        "task": as_text(case.get("task")),
                    }
                )
            expected_route = as_text(case.get("expect_route_layer"))
            actual_route = as_text(
                result.get("task_route", {})
                .get("route_decision", {})
                .get("recommended_layer")
                if isinstance(result.get("task_route"), dict)
                else ""
            )
            if expected_route and actual_route != expected_route:
                errors.append(f"route_layer:{actual_route}")
            expected_pack_layers = [as_text(item) for item in case.get("expect_pack_layers", [])]
            actual_pack_layers = [
                as_text(item)
                for item in (
                    result.get("assembly_trace", {})
                    .get("pack_scope", {})
                    .get("source_layers", [])
                    if isinstance(result.get("assembly_trace"), dict)
                    else []
                )
            ]
            if expected_pack_layers and actual_pack_layers != expected_pack_layers:
                errors.append(f"pack_layers:{','.join(actual_pack_layers)}")
            details = {
                "actual_ids": actual_ids,
                "expected_ids": expected_ids,
                "route_layer": actual_route,
                "pack_layers": actual_pack_layers,
            }
        else:
            errors.append(f"unsupported_kind:{kind}")
        cases.append(
            {
                "id": case_id,
                "kind": kind,
                "status": "pass" if not errors else "fail",
                "errors": errors,
                "details": details,
            }
        )
    failed = len([case for case in cases if case["status"] != "pass"])
    return {
        "project": project_name,
        "path": relative(project, golden_path) if golden_path.is_relative_to(project) else str(golden_path),
        "total": len(cases),
        "passed": len(cases) - failed,
        "failed": failed,
        "misses": misses,
        "eval": {
            "outcome": "pass" if failed == 0 else "fail",
            "miss_count": len(misses),
        },
        "cases": cases,
    }


def print_memory_golden_result(result: dict[str, object], fmt: str) -> int:
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"project: {result['project']}")
        print(f"golden: {result['passed']}/{result['total']} passed")
        for case in result["cases"]:
            print(f"  - {case['status']}: {case['id']}")
    return 1 if result["failed"] else 0
