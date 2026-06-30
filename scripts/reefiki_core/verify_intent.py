from __future__ import annotations

import json
import re
from pathlib import Path

from .markdown import as_text


VERIFY_INTENT_SIGNAL_KEYS = ("missing_scope", "unrelated_artifact", "over_broad_diff")
STOPWORDS = {
    "add",
    "and",
    "for",
    "from",
    "into",
    "the",
    "this",
    "with",
}


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def _term_tokens(term: str) -> list[str]:
    return [token for token in _normalized(term).split() if token and token not in STOPWORDS]


def _term_present(term: str, text: str) -> bool:
    normalized_text = _normalized(text)
    normalized_term = _normalized(term)
    if normalized_term and normalized_term in normalized_text:
        return True
    tokens = _term_tokens(term)
    return bool(tokens) and all(token in normalized_text for token in tokens)


def _derive_expected_terms(brief: str, limit: int = 8) -> list[str]:
    tokens = []
    for token in _term_tokens(brief):
        if token not in tokens:
            tokens.append(token)
    return tokens[:limit]


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _path_matches_prefix(path: str, prefix: str) -> bool:
    normalized_path = _normalize_path(path)
    normalized_prefix = _normalize_path(prefix)
    return normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + "/")


def _term_sources(term: str, report: str, changed_paths: list[str], artifacts: dict[str, str]) -> list[str]:
    sources: list[str] = []
    if _term_present(term, report):
        sources.append("report")
    for path in changed_paths:
        if _term_present(term, path):
            sources.append(f"path:{path}")
    for path, content in artifacts.items():
        if _term_present(term, content):
            sources.append(f"artifact:{path}")
    return sources


def verify_intent_payload(
    brief: str,
    report: str = "",
    changed_paths: list[str] | None = None,
    artifacts: dict[str, str] | None = None,
    expected_terms: list[str] | None = None,
    expected_paths: list[str] | None = None,
    allowed_paths: list[str] | None = None,
) -> dict[str, object]:
    changed = [_normalize_path(path) for path in (changed_paths or []) if as_text(path)]
    artifact_map = {path: content for path, content in (artifacts or {}).items() if as_text(path)}
    terms = [term for term in (expected_terms or []) if as_text(term)] or _derive_expected_terms(brief)
    path_prefixes = [_normalize_path(path) for path in (expected_paths or []) if as_text(path)]
    allowed_prefixes = [_normalize_path(path) for path in (allowed_paths or []) if as_text(path)] or path_prefixes

    term_evidence: dict[str, dict[str, object]] = {}
    missing_scope: list[dict[str, object]] = []
    for term in terms:
        sources = _term_sources(term, report, changed, artifact_map)
        term_evidence[term] = {"present": bool(sources), "sources": sources}
        if not sources:
            missing_scope.append(
                {
                    "term": term,
                    "reason": "expected term not found in report, artifacts or changed paths",
                    "evidence": sources,
                }
            )

    path_evidence: dict[str, list[str]] = {}
    over_broad_diff: list[dict[str, object]] = []
    for prefix in path_prefixes:
        path_evidence[prefix] = [path for path in changed if _path_matches_prefix(path, prefix)]
        if not path_evidence[prefix]:
            missing_scope.append(
                {
                    "path": prefix,
                    "reason": "expected path has no changed path evidence",
                    "evidence": [],
                }
            )
    if allowed_prefixes:
        for path in changed:
            if not any(_path_matches_prefix(path, prefix) for prefix in allowed_prefixes):
                over_broad_diff.append(
                    {
                        "path": path,
                        "reason": "changed path is outside expected paths",
                        "allowed_paths": allowed_prefixes,
                        "evidence": [path],
                    }
                )

    unrelated_artifact: list[dict[str, object]] = []
    for path, content in artifact_map.items():
        term_sources = [
            term for term in terms if _term_present(term, content)
        ]
        path_related = not path_prefixes or any(_path_matches_prefix(path, prefix) for prefix in path_prefixes)
        if not term_sources and not path_related:
            unrelated_artifact.append(
                {
                    "path": path,
                    "reason": "artifact has no expected term or expected path evidence",
                    "expected_terms": terms,
                    "expected_paths": path_prefixes,
                    "allowed_paths": allowed_prefixes,
                    "evidence": [],
                }
            )

    if missing_scope:
        status = "block"
    elif unrelated_artifact or over_broad_diff:
        status = "warn"
    else:
        status = "pass"

    return {
        "schema_version": 1,
        "read_only": True,
        "status": status,
        "inputs": {
            "brief": brief,
            "expected_terms": terms,
            "expected_paths": path_prefixes,
            "allowed_paths": allowed_prefixes,
            "changed_paths": changed,
            "artifact_paths": list(artifact_map),
        },
        "summary": {
            "missing_scope": len(missing_scope),
            "unrelated_artifact": len(unrelated_artifact),
            "over_broad_diff": len(over_broad_diff),
        },
        "signals": {
            "missing_scope": missing_scope,
            "unrelated_artifact": unrelated_artifact,
            "over_broad_diff": over_broad_diff,
        },
        "evidence": {
            "term_evidence": term_evidence,
            "path_evidence": path_evidence,
        },
        "actions": [],
    }


def _read_optional_file(path: str | None) -> str:
    if not path:
        return ""
    candidate = Path(path)
    if not candidate.exists():
        raise SystemExit(f"Missing verify-intent input file: {path}")
    if candidate.is_dir():
        raise SystemExit(f"verify-intent input is a directory, not a text file: {path}")
    if candidate.stat().st_size > 5 * 1024 * 1024:
        raise SystemExit(f"verify-intent input is larger than 5 MB: {path}")
    return candidate.read_text(encoding="utf-8")


def _artifact_map(paths: list[str]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise SystemExit(f"Missing verify-intent artifact: {raw_path}")
        if path.is_dir():
            raise SystemExit(f"verify-intent artifact is a directory, not a text file: {raw_path}")
        if path.stat().st_size > 5 * 1024 * 1024:
            raise SystemExit(f"verify-intent artifact is larger than 5 MB: {raw_path}")
        artifacts[raw_path] = path.read_text(encoding="utf-8")
    return artifacts


def _print_verify_intent_text(payload: dict[str, object]) -> None:
    print(f"verify intent: {payload['status']}")
    for signal_name in VERIFY_INTENT_SIGNAL_KEYS:
        items = payload["signals"][signal_name]
        if items:
            print(f"- {signal_name}: {len(items)}")
            for item in items:
                label = item.get("term") or item.get("path")
                print(f"  {label}: {item['reason']}")


def print_verify_intent(
    brief: str | None,
    brief_file: str | None,
    report: str,
    report_file: str | None,
    artifact_paths: list[str],
    changed_paths: list[str],
    expected_terms: list[str],
    expected_paths: list[str],
    allowed_paths: list[str],
    fail_on: str,
    fmt: str,
) -> int:
    brief_text = as_text(brief) or _read_optional_file(brief_file)
    if not brief_text:
        raise SystemExit("verify-intent requires --brief or --brief-file.")
    report_text = "\n".join(text for text in [as_text(report), _read_optional_file(report_file)] if text)
    payload = verify_intent_payload(
        brief=brief_text,
        report=report_text,
        changed_paths=changed_paths,
        artifacts=_artifact_map(artifact_paths),
        expected_terms=expected_terms,
        expected_paths=expected_paths,
        allowed_paths=allowed_paths,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_verify_intent_text(payload)
    if payload["status"] == "block":
        return 1
    if payload["status"] == "warn" and fail_on == "warn":
        return 1
    return 0
