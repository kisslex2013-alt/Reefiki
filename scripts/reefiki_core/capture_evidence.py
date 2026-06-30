from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from .markdown import as_text


EVIDENCE_KINDS = ("browser", "command", "diff", "manual")
SUMMARY_LIMIT = 1600

FORBIDDEN_PATH_PARTS = {
    ".cache",
    ".aws",
    ".git",
    ".next",
    ".ssh",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "raw",
    "target",
    "vendor",
}

SECRET_FILE_SUFFIXES = {".key", ".pem", ".pfx"}
SECRET_FILE_NAMES = {".env", "id_rsa"}
SECRET_NAME_TERMS = ("password", "secret", "token")

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "key_value",
        re.compile(r"\b(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,;]+)", re.IGNORECASE),
    ),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE)),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalized_path(path: str) -> str:
    return as_text(path).replace("\\", "/").strip()


def _path_violation(path: str, field: str) -> dict[str, object] | None:
    normalized = _normalized_path(path)
    if not normalized:
        return None
    parts = [part.lower() for part in normalized.strip("/").split("/") if part]
    if any(part in FORBIDDEN_PATH_PARTS for part in parts):
        return {
            "field": field,
            "path": normalized,
            "reason": "forbidden directory path is not allowed in evidence drafts",
        }
    name = parts[-1] if parts else normalized.lower()
    suffix = Path(name).suffix.lower()
    stem = Path(name).stem.lower()
    if name.startswith(".env") or name.startswith("id_rsa") or name in SECRET_FILE_NAMES or suffix in SECRET_FILE_SUFFIXES:
        return {
            "field": field,
            "path": normalized,
            "reason": "secret-like file path is not allowed in evidence drafts",
        }
    if any(term in stem for term in SECRET_NAME_TERMS):
        return {
            "field": field,
            "path": normalized,
            "reason": "secret-like file name is not allowed in evidence drafts",
        }
    return None


def _redact_text(value: str, field: str, redactions: list[dict[str, str]]) -> str:
    text = as_text(value)
    if not text:
        return ""

    def replace_key_value(match: re.Match[str]) -> str:
        redactions.append({"field": field, "kind": "secret", "pattern": "key_value"})
        return f"{match.group(1)}=[REDACTED:secret]"

    text = SECRET_PATTERNS[0][1].sub(replace_key_value, text)

    for pattern_name, pattern in SECRET_PATTERNS[1:]:
        def replace_secret(match: re.Match[str], name: str = pattern_name) -> str:
            redactions.append({"field": field, "kind": "secret", "pattern": name})
            return "[REDACTED:secret]"

        text = pattern.sub(replace_secret, text)
    return text


def _summary(value: str, field: str, redactions: list[dict[str, str]], limits: list[str]) -> str:
    text = _redact_text(value, field, redactions)
    if len(text) <= SUMMARY_LIMIT:
        return text
    limits.append(f"{field} truncated to {SUMMARY_LIMIT} characters; store summaries, not raw transcripts")
    return text[:SUMMARY_LIMIT].rstrip() + " ... [truncated]"


def _source(task_id: str, source_artifact: str, url: str) -> dict[str, str]:
    source: dict[str, str] = {}
    if as_text(task_id):
        source["task_id"] = as_text(task_id)
    if as_text(source_artifact):
        source["source_artifact"] = as_text(source_artifact)
    if as_text(url):
        source["url"] = as_text(url)
    return source


def _sanitize_paths(paths: list[str], field: str, violations: list[dict[str, object]]) -> list[str]:
    clean: list[str] = []
    for path in paths:
        normalized = _normalized_path(path)
        if not normalized:
            continue
        violation = _path_violation(normalized, field)
        if violation:
            violations.append(violation)
            continue
        clean.append(normalized)
    return clean


def capture_evidence_payload(
    kind: str,
    claim: str,
    evidence_note: str = "",
    task_id: str = "",
    source_artifact: str = "",
    url: str = "",
    selector: str = "",
    viewport: str = "",
    screenshot_path: str = "",
    command_summary: str = "",
    diff_summary: str = "",
    related_paths: list[str] | None = None,
    captured_at: str = "",
) -> dict[str, object]:
    normalized_kind = as_text(kind).lower()
    if normalized_kind not in EVIDENCE_KINDS:
        raise SystemExit(f"capture-evidence kind must be one of: {', '.join(EVIDENCE_KINDS)}")

    redactions: list[dict[str, str]] = []
    violations: list[dict[str, object]] = []
    limits = [
        "No raw screenshot or video bytes are copied; screenshot paths are references only.",
        "Command outputs and diffs must be supplied as summaries or selected excerpts.",
        "Secret-like text is redacted and secret-bearing or forbidden paths are blocked.",
    ]

    clean_screenshot = None
    screenshot = _normalized_path(screenshot_path)
    if screenshot:
        violation = _path_violation(screenshot, "screenshot_path")
        if violation:
            violations.append(violation)
        else:
            clean_screenshot = screenshot

    draft = {
        "kind": normalized_kind,
        "source": _source(task_id, source_artifact, url),
        "captured_at": as_text(captured_at) or _utc_now(),
        "claim": _redact_text(claim, "claim", redactions),
        "evidence": {
            "note": _summary(evidence_note, "evidence.note", redactions, limits),
            "selector": as_text(selector) or None,
            "viewport": as_text(viewport) or None,
            "screenshot_path": clean_screenshot,
            "command_summary": _summary(command_summary, "evidence.command_summary", redactions, limits),
            "diff_summary": _summary(diff_summary, "evidence.diff_summary", redactions, limits),
        },
        "limits": limits,
        "redactions": redactions,
        "related_paths": _sanitize_paths(related_paths or [], "related_paths", violations),
    }

    return {
        "schema_version": 1,
        "read_only": True,
        "status": "block" if violations else "pass",
        "draft": draft,
        "violations": violations,
        "draft_path": None,
        "actions": [],
    }


def _default_draft_path(root: Path) -> Path:
    return root / "docs" / "evidence" / f"evidence-{date.today().isoformat()}.md"


def _render_markdown(payload: dict[str, object]) -> str:
    draft = payload["draft"]
    evidence = draft["evidence"]
    source = draft["source"]
    lines = [
        "# Evidence Capture",
        "",
        f"Kind: {draft['kind']}",
        f"Captured at: {draft['captured_at']}",
        f"Claim: {draft['claim']}",
        "",
        "## Source",
        "",
    ]
    if source:
        for key, value in source.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- unspecified")
    lines.extend(["", "## Evidence", ""])
    for key, value in evidence.items():
        if value:
            lines.append(f"- {key}: {value}")
    if not any(evidence.values()):
        lines.append("- none")
    lines.extend(["", "## Related Paths", ""])
    related = draft["related_paths"]
    if related:
        lines.extend(f"- {path}" for path in related)
    else:
        lines.append("- none")
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {limit}" for limit in draft["limits"])
    if draft["redactions"]:
        lines.extend(["", "## Redactions", ""])
        for redaction in draft["redactions"]:
            lines.append(f"- {redaction['field']}: {redaction['pattern']}")
    if payload["violations"]:
        lines.extend(["", "## Violations", ""])
        for violation in payload["violations"]:
            lines.append(f"- {violation['field']}: {violation['reason']} ({violation['path']})")
    return "\n".join(lines).rstrip() + "\n"


def _print_text(payload: dict[str, object]) -> None:
    draft = payload["draft"]
    print(f"capture evidence: {payload['status']}")
    print(f"- kind: {draft['kind']}")
    print(f"- claim: {draft['claim']}")
    if payload.get("draft_path"):
        print(f"- draft: {payload['draft_path']}")
    for violation in payload["violations"]:
        print(f"- block: {violation['field']}: {violation['reason']} ({violation['path']})")


def print_capture_evidence(
    root: Path,
    kind: str,
    claim: str,
    evidence_note: str,
    task_id: str,
    source_artifact: str,
    url: str,
    selector: str,
    viewport: str,
    screenshot_path: str,
    command_summary: str,
    diff_summary: str,
    related_paths: list[str],
    captured_at: str,
    write_draft: bool,
    draft_path: str | None,
    fmt: str,
) -> int:
    payload = capture_evidence_payload(
        kind=kind,
        claim=claim,
        evidence_note=evidence_note,
        task_id=task_id,
        source_artifact=source_artifact,
        url=url,
        selector=selector,
        viewport=viewport,
        screenshot_path=screenshot_path,
        command_summary=command_summary,
        diff_summary=diff_summary,
        related_paths=related_paths,
        captured_at=captured_at,
    )
    if write_draft and payload["status"] == "pass":
        target = Path(draft_path) if draft_path else _default_draft_path(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_render_markdown(payload), encoding="utf-8")
        payload["read_only"] = False
        payload["draft_path"] = str(target)
        payload["actions"] = ["write_draft"]
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 1 if payload["status"] == "block" else 0
