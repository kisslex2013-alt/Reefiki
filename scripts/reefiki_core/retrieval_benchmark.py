from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from .index_search import search
from .markdown import as_text
from .memory_golden import load_golden_queries
from .project_paths import find_project
from .retrieval_preflight import retrieval_preflight_payload


GENERATED_QMD_PATHS = [
    "projects/{project}/.qmd",
    ".cache/qmd-benchmark",
]


def _lookup_cases(project: Path) -> list[dict[str, object]]:
    config = load_golden_queries(project / "golden-queries.yml")
    cases: list[dict[str, object]] = []
    for case in config.get("queries", []):
        if not isinstance(case, dict):
            continue
        if as_text(case.get("kind")) != "lookup":
            continue
        if as_text(case.get("layer")) != "reefiki":
            continue
        query = as_text(case.get("query"))
        expected_ids = [as_text(item) for item in case.get("expect_ids", [])]
        if not query or not expected_ids:
            continue
        cases.append(
            {
                "id": as_text(case.get("id")) or f"lookup-{len(cases) + 1}",
                "query": query,
                "expected_ids": expected_ids,
            }
        )
    return cases


def _result_id_from_path(path_text: str) -> str:
    path = Path(path_text.replace("\\", "/"))
    return path.stem


def _qmd_result_ids(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        explicit_id = as_text(item.get("id") or item.get("docid"))
        path_id = _result_id_from_path(as_text(item.get("path") or item.get("file")))
        result_id = path_id or explicit_id
        if result_id:
            ids.append(result_id)
    return ids


def _load_qmd_results(path: Path | None) -> dict[str, list[str]] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    by_case: dict[str, list[str]] = {}
    if isinstance(data, dict) and isinstance(data.get("queries"), list):
        for case in data["queries"]:
            if isinstance(case, dict):
                by_case[as_text(case.get("id"))] = _qmd_result_ids(case.get("results"))
        return by_case
    if isinstance(data, dict):
        for case_id, value in data.items():
            if isinstance(value, dict):
                by_case[case_id] = _qmd_result_ids(value.get("results"))
            else:
                by_case[case_id] = _qmd_result_ids(value)
    return by_case


def _safe_remove(root: Path, path: Path) -> bool:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_root not in [resolved_path, *resolved_path.parents]:
        raise SystemExit(f"Refusing to clean generated path outside repo: {path}")
    if not resolved_path.exists():
        return False
    if resolved_path.is_dir():
        shutil.rmtree(resolved_path)
    else:
        resolved_path.unlink()
    return True


def _generated_cleanup_payload(root: Path, project: Path, cleanup_generated: bool) -> dict[str, object]:
    checked: list[str] = []
    removed: list[str] = []
    remaining: list[str] = []
    failed: list[dict[str, str]] = []
    for pattern in GENERATED_QMD_PATHS:
        repo_relative = pattern.format(project=project.name)
        path = root / repo_relative
        checked.append(repo_relative)
        if cleanup_generated:
            try:
                if _safe_remove(root, path):
                    removed.append(repo_relative)
            except OSError as exc:
                failed.append({"path": repo_relative, "reason": str(exc)})
        if path.exists():
            remaining.append(repo_relative)
    return {
        "checked": checked,
        "removed": removed,
        "remaining": remaining,
        "failed": failed,
    }


def _case_payload(
    project: Path,
    case: dict[str, object],
    limit: int,
    qmd_results: dict[str, list[str]] | None,
) -> dict[str, object]:
    query = as_text(case.get("query"))
    expected_ids = [as_text(item) for item in case.get("expected_ids", [])]
    fts_ids = [as_text(row["id"]) for row in search(project, query, limit)]
    fts_missing = [expected for expected in expected_ids if expected not in fts_ids]

    qmd_payload: dict[str, object] = {
        "status": "not-run",
        "actual_ids": None,
        "missing_ids": None,
        "hit": None,
    }
    if qmd_results is not None:
        qmd_ids = qmd_results.get(as_text(case.get("id")), [])
        qmd_missing = [expected for expected in expected_ids if expected not in qmd_ids]
        qmd_payload = {
            "status": "ok",
            "actual_ids": qmd_ids,
            "missing_ids": qmd_missing,
            "hit": not qmd_missing,
        }

    return {
        "id": case["id"],
        "query": query,
        "expected_ids": expected_ids,
        "fts5": {
            "actual_ids": fts_ids,
            "missing_ids": fts_missing,
            "hit": not fts_missing,
        },
        "qmd": qmd_payload,
    }


def _summary(cases: list[dict[str, object]], qmd_results: dict[str, list[str]] | None) -> dict[str, object]:
    fts_hits = sum(1 for case in cases if case["fts5"]["hit"])  # type: ignore[index]
    if qmd_results is None:
        return {
            "fts_hits": fts_hits,
            "qmd_hits": None,
            "same": None,
            "improved": None,
            "regressed": None,
        }

    qmd_hits = sum(1 for case in cases if case["qmd"]["hit"])  # type: ignore[index]
    same = 0
    improved = 0
    regressed = 0
    for case in cases:
        fts_hit = bool(case["fts5"]["hit"])  # type: ignore[index]
        qmd_hit = bool(case["qmd"]["hit"])  # type: ignore[index]
        if fts_hit == qmd_hit:
            same += 1
        elif qmd_hit and not fts_hit:
            improved += 1
        elif fts_hit and not qmd_hit:
            regressed += 1
    return {
        "fts_hits": fts_hits,
        "qmd_hits": qmd_hits,
        "same": same,
        "improved": improved,
        "regressed": regressed,
    }


def _go_no_go(summary: dict[str, object], qmd_results: dict[str, list[str]] | None) -> str:
    if qmd_results is None:
        return "collect-qmd-results"
    if int(summary["regressed"] or 0) > 0:
        return "keep-disabled"
    if int(summary["improved"] or 0) > 0:
        return "continue-eval"
    return "no-adoption-benefit"


def benchmark_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# qmd retrieval benchmark",
        "",
        f"- project: {payload['project']}",
        f"- candidate: {payload['candidate']}",
        f"- outcome: {payload['outcome']}",
        f"- go_no_go: {payload['go_no_go']}",
        f"- qmd_status: {payload['qmd_status']}",
        f"- fixed_corpus_count: {payload['fixed_corpus_count']}",
        "",
        "## Summary",
        "",
        f"- FTS5 hits: {payload['summary']['fts_hits']}",
        f"- qmd hits: {payload['summary']['qmd_hits']}",
        f"- improved: {payload['summary']['improved']}",
        f"- regressed: {payload['summary']['regressed']}",
        "",
        "## Cases",
        "",
    ]
    for case in payload["cases"]:
        lines.extend(
            [
                f"### {case['id']}",
                "",
                f"- query: {case['query']}",
                f"- expected: {', '.join(case['expected_ids'])}",
                f"- FTS5 actual: {', '.join(case['fts5']['actual_ids']) or '-'}",
                f"- FTS5 missing: {', '.join(case['fts5']['missing_ids']) or '-'}",
                f"- qmd actual: {', '.join(case['qmd']['actual_ids'] or []) or '-'}",
                f"- qmd missing: {', '.join(case['qmd']['missing_ids'] or []) or '-'}",
                "",
            ]
        )
    cleanup = payload["generated_paths_cleanup"]
    lines.extend(
        [
            "## Generated Path Cleanup",
            "",
            f"- checked: {', '.join(cleanup['checked'])}",
            f"- removed: {', '.join(cleanup['removed']) or '-'}",
            f"- remaining: {', '.join(cleanup['remaining']) or '-'}",
            f"- failed: {json.dumps(cleanup['failed'], ensure_ascii=False) if cleanup['failed'] else '-'}",
            "",
            "## Decision",
            "",
            "Keep qmd disabled by default unless a future fixed miss set shows repeatable improvement without regressions.",
            "",
        ]
    )
    return "\n".join(lines)


def retrieval_benchmark_payload(
    root: Path,
    project_name: str,
    candidate: str,
    limit: int = 5,
    qmd_results_path: Path | None = None,
    cleanup_generated: bool = False,
) -> dict[str, object]:
    normalized_candidate = candidate.strip().lower()
    if normalized_candidate != "qmd":
        return {
            "candidate": candidate,
            "outcome": "unsupported",
            "go_no_go": "unsupported",
            "cases": [],
            "summary": {},
        }
    project = find_project(root, project_name)
    preflight = retrieval_preflight_payload(root, project_name, "qmd")
    qmd_results = _load_qmd_results(qmd_results_path)
    cases = [_case_payload(project, case, limit, qmd_results) for case in _lookup_cases(project)]
    summary = _summary(cases, qmd_results)
    go_no_go = _go_no_go(summary, qmd_results)
    return {
        "candidate": "qmd",
        "project": project.name,
        "outcome": "benchmark-complete" if qmd_results is not None else "benchmark-incomplete",
        "qmd_status": "results-loaded" if qmd_results is not None else "not-run",
        "runtime_adoption": "blocked",
        "preflight_outcome": preflight["outcome"],
        "fixed_corpus_count": len(cases),
        "limit": limit,
        "summary": summary,
        "go_no_go": go_no_go,
        "cases": cases,
        "blocked_actions": preflight["blocked_actions"],
        "required_gates": preflight["required_gates"],
        "generated_paths_cleanup": _generated_cleanup_payload(root, project, cleanup_generated),
        "next_action": (
            "capture qmd BM25/lex results for the same fixed corpus"
            if qmd_results is None
            else "keep qmd disabled unless future fixed misses justify another eval"
        ),
    }


def write_benchmark_report(root: Path, payload: dict[str, Any]) -> str:
    reports = root / "docs" / "retrieval"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"qmd-benchmark-{date.today().isoformat()}.md"
    path.write_text(benchmark_report_markdown(payload), encoding="utf-8")
    return path.relative_to(root).as_posix()


def print_retrieval_benchmark(
    root: Path,
    project_name: str,
    candidate: str,
    limit: int,
    qmd_results_path: Path | None,
    write_report: bool,
    cleanup_generated: bool,
    fmt: str,
) -> int:
    payload = retrieval_benchmark_payload(
        root,
        project_name,
        candidate,
        limit=limit,
        qmd_results_path=qmd_results_path,
        cleanup_generated=cleanup_generated,
    )
    if write_report:
        payload["report_path"] = write_benchmark_report(root, payload)
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"candidate: {payload['candidate']}")
        print(f"project: {payload.get('project', project_name)}")
        print(f"outcome: {payload['outcome']}")
        print(f"go_no_go: {payload['go_no_go']}")
        print(f"qmd_status: {payload.get('qmd_status', '-')}")
        if "report_path" in payload:
            print(f"report: {payload['report_path']}")
    return 0 if payload["outcome"] != "unsupported" else 1
