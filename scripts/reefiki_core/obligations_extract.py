from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from .markdown import as_text


OBLIGATION_GROUPS = (
    "next_action",
    "blocker",
    "evidence",
    "owner_boundary",
    "deferred_follow_up",
)

GROUP_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("blocker", ("blocker", "blocked", "blocking")),
    ("evidence", ("evidence required", "required evidence", "verification evidence", "proof required", "validation")),
    ("owner_boundary", ("owner boundary", "boundary", "owner")),
    ("deferred_follow_up", ("deferred follow-up", "deferred", "follow-up", "later")),
    ("next_action", ("next action", "action", "todo", "scope", "required next step")),
)

CONTEXT_PREFIXES = ("trigger", "context", "background", "rationale", "why")


def _clean_line(line: str) -> str:
    value = line.strip()
    value = re.sub(r"^[-*+]\s+", "", value)
    value = re.sub(r"^\d+[.)]\s+", "", value)
    value = re.sub(r"^\[[ xX]\]\s+", "", value)
    return value.strip()


def _strip_group_prefix(text: str, group: str) -> str:
    for candidate_group, prefixes in GROUP_PREFIXES:
        if candidate_group != group:
            continue
        for prefix in prefixes:
            pattern = re.compile(rf"^{re.escape(prefix)}\s*:\s*", re.IGNORECASE)
            stripped = pattern.sub("", text, count=1).strip()
            if stripped != text:
                return stripped
    return text


def _classify(text: str, raw_line: str) -> tuple[str | None, float]:
    lower = text.lower()
    if any(term in lower for term in ("no direct follow-up", "no follow-up", "not an obligation")):
        return None, 0.0
    if any(lower.startswith(prefix + ":") for prefix in CONTEXT_PREFIXES):
        return None, 0.0
    for group, prefixes in GROUP_PREFIXES:
        if any(lower.startswith(prefix + ":") for prefix in prefixes):
            return group, 0.95
    if re.match(r"^[-*+]\s+\[\s\]\s+", raw_line.strip()):
        return "next_action", 0.9
    if any(term in lower for term in ("blocker", "blocked", "blocking", "cannot proceed", "do not publish until")):
        return "blocker", 0.8
    if any(term in lower for term in ("evidence", "proof", "verification", "validation", "must verify")):
        return "evidence", 0.78
    if any(term in lower for term in ("owner boundary", "must not push", "must not publish", "must not cleanup", "parent", "child verifier", "subagent")):
        return "owner_boundary", 0.78
    if any(term in lower for term in ("deferred", "defer", "follow up", "follow-up", "later")):
        return "deferred_follow_up", 0.75
    return None, 0.0


def _owner_class(text: str, owner_hint: str = "") -> str:
    hint = as_text(owner_hint)
    if hint:
        return hint
    lower = text.lower()
    if "user" in lower:
        return "user"
    if "teamlead" in lower or "parent" in lower:
        return "teamlead"
    if "child" in lower or "subagent" in lower or "verifier" in lower:
        return "child_agent"
    if "agent" in lower:
        return "agent"
    return "unspecified"


def _due_trigger(text: str, group: str) -> str:
    match = re.search(r"\b(before|until|after)\b\s+([^.;]+)", text, re.IGNORECASE)
    if match:
        return f"{match.group(1).lower()} {match.group(2).strip()}"
    defaults = {
        "next_action": "next review",
        "blocker": "before unblocking",
        "evidence": "before acceptance",
        "owner_boundary": "during handoff",
        "deferred_follow_up": "after current scope",
    }
    return defaults[group]


def _required_evidence(text: str, group: str) -> str:
    defaults = {
        "next_action": "completion evidence",
        "blocker": "blocker resolution evidence",
        "evidence": text,
        "owner_boundary": "owner boundary honored",
        "deferred_follow_up": "deferred follow-up decision",
    }
    return defaults[group]


def _status_for_group(group: str) -> str:
    if group == "blocker":
        return "blocked"
    if group == "deferred_follow_up":
        return "deferred"
    return "open"


def _iter_obligations(source_artifact: str, content: str, owner_hint: str = "") -> list[dict[str, object]]:
    obligations: list[dict[str, object]] = []
    heading = ""
    in_fence = False
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            continue

        text = _clean_line(raw_line)
        if not text:
            continue
        group, confidence = _classify(text, raw_line)
        if group is None:
            continue
        obligation_text = _strip_group_prefix(text, group)
        obligations.append(
            {
                "text": obligation_text,
                "group": group,
                "owner_class": _owner_class(obligation_text, owner_hint),
                "due_trigger": _due_trigger(obligation_text, group),
                "required_evidence": _required_evidence(obligation_text, group),
                "source_artifact": source_artifact,
                "line": line_number,
                "heading": heading,
                "status": _status_for_group(group),
                "confidence": confidence,
            }
        )
    return obligations


def obligations_extract_payload(
    sources: dict[str, str],
    owner_hint: str = "",
    source_hint: str = "",
) -> dict[str, object]:
    obligations: list[dict[str, object]] = []
    for source_artifact, content in sources.items():
        obligations.extend(_iter_obligations(source_artifact, content, owner_hint))

    by_group = Counter(as_text(item.get("group")) for item in obligations)
    groups = {
        group: [item for item in obligations if item["group"] == group]
        for group in OBLIGATION_GROUPS
    }
    return {
        "schema_version": 1,
        "read_only": True,
        "status": "ok",
        "inputs": {
            "source_artifacts": list(sources),
            "owner_hint": as_text(owner_hint) or None,
            "source_hint": as_text(source_hint) or None,
        },
        "summary": {
            "total": len(obligations),
            "by_group": {group: by_group.get(group, 0) for group in OBLIGATION_GROUPS},
        },
        "groups": groups,
        "obligations": obligations,
        "report_path": None,
        "actions": [],
    }


def _read_source_file(path: str) -> tuple[str, str]:
    candidate = Path(path)
    if not candidate.exists():
        raise SystemExit(f"Missing obligations source file: {path}")
    if candidate.is_dir():
        raise SystemExit(f"Obligations source is a directory, not a text file: {path}")
    if candidate.stat().st_size > 5 * 1024 * 1024:
        raise SystemExit(f"Obligations source is larger than 5 MB: {path}")
    return path, candidate.read_text(encoding="utf-8")


def _sources_from_inputs(source_paths: list[str], inline_text: str, source_hint: str) -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in source_paths:
        source_artifact, content = _read_source_file(path)
        sources[source_artifact] = content
    text = as_text(inline_text)
    if text:
        sources[as_text(source_hint) or "inline"] = text
    if not sources:
        raise SystemExit("obligations-extract requires --source or --text.")
    return sources


def _default_report_path(root: Path) -> Path:
    return root / "docs" / "obligations" / f"obligations-{date.today().isoformat()}.md"


def _render_report(payload: dict[str, object]) -> str:
    lines = [
        "# Obligations Extract",
        "",
        f"Total: {payload['summary']['total']}",
        "",
    ]
    groups = payload["groups"]
    for group in OBLIGATION_GROUPS:
        items = groups[group]
        lines.append(f"## {group}")
        lines.append("")
        if not items:
            lines.append("- none")
        for item in items:
            lines.append(
                f"- {item['text']} "
                f"(owner={item['owner_class']}; status={item['status']}; "
                f"source={item['source_artifact']}:{item['line']})"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _print_obligations_text(payload: dict[str, object]) -> None:
    print(f"obligations: {payload['summary']['total']}")
    for group in OBLIGATION_GROUPS:
        items = payload["groups"][group]
        print(f"- {group}: {len(items)}")
        for item in items:
            print(f"  {item['source_artifact']}:{item['line']} {item['text']}")
    if payload.get("report_path"):
        print(f"report: {payload['report_path']}")


def print_obligations_extract(
    root: Path,
    source_paths: list[str],
    inline_text: str,
    owner_hint: str,
    source_hint: str,
    write_report: bool,
    report_path: str | None,
    fmt: str,
) -> int:
    payload = obligations_extract_payload(
        _sources_from_inputs(source_paths, inline_text, source_hint),
        owner_hint,
        source_hint,
    )
    if write_report:
        target = Path(report_path) if report_path else _default_report_path(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_render_report(payload), encoding="utf-8")
        payload["read_only"] = False
        payload["report_path"] = str(target)
        payload["actions"] = ["write_report"]
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_obligations_text(payload)
    return 0
