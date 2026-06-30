from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

try:
    from reefiki_memory import (
        AccessBoundaryContext,
        MemoryDecisionTrace,
        PromotionCandidate,
        RouteDecision,
    )
except ModuleNotFoundError:  # pragma: no cover - package import fallback for tests
    from scripts.reefiki_memory import (
        AccessBoundaryContext,
        MemoryDecisionTrace,
        PromotionCandidate,
        RouteDecision,
    )

from .duplicates import _normalize_text
from .index_search import build_index
from .markdown import as_text
from .memory_preflight import memory_global_strict_preflight, memory_preflight
from .repo_paths import resolve_contained_path
from .file_utils import slugify, write_new_text, write_unique_text
from .project_paths import find_project, relative
from .wiki_rows import _wiki_rows


def _suggest_target_type(text: str) -> str:
    normalized = text.lower()
    if any(token in normalized for token in ["always", "from now on", "workflow", "rule", "prefer", "step", "procedure"]):
        return "skill"
    if any(token in normalized for token in ["decide", "decision", "tradeoff", "choose", "chose", "because"]):
        return "decision"
    if any(token in normalized for token in ["pattern", "model", "means", "difference", "concept"]):
        return "concept"
    return "synthesis"


def promotion_dry_run(
    project: Path,
    content: str,
    memory_id: str | None = None,
    confidence: float = 0.6,
) -> dict[str, object]:
    text = content.strip()
    if not text:
        raise SystemExit("Empty content.")
    normalized = text.lower()
    duplicate_refs: list[str] = []
    for row in _wiki_rows(project):
        title = _normalize_text(as_text(row["title"]))
        body = _normalize_text(as_text(row["body"]))
        if text and (text[:80].lower() in body or title and title in normalized):
            duplicate_refs.append(as_text(row["id"]))
    duplicate_refs = sorted(set(duplicate_refs))

    memoir_only_markers = ["prefer ", "prefers ", "workflow rule", "from now on"]
    if len(text) < 60 and not duplicate_refs:
        verdict = "memoir-only"
    elif any(marker in normalized for marker in memoir_only_markers) and len(text) < 160 and not duplicate_refs:
        verdict = "memoir-only"
    else:
        verdict = "promote"

    if any(token in normalized for token in ["port ", "running now", "currently", "today only"]):
        verdict = "ignore"

    target_type = _suggest_target_type(text) if verdict == "promote" else None
    review_state = "needs_verification" if verdict == "promote" else None
    return {
        "verdict": verdict,
        "suggested_target_type": target_type,
        "distilled_summary": text[:240],
        "confidence": confidence,
        "review_state": review_state,
        "duplicate_candidate_refs": duplicate_refs,
        "memory_id": memory_id,
    }


def print_promotion_dry_run(
    project: Path,
    content: str,
    memory_id: str | None,
    confidence: float,
    fmt: str,
) -> int:
    result = promotion_dry_run(project, content, memory_id=memory_id, confidence=confidence)
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"verdict: {result['verdict']}")
    if result["suggested_target_type"]:
        print(f"target_type: {result['suggested_target_type']}")
    print(f"confidence: {result['confidence']}")
    if result["review_state"]:
        print(f"review_state: {result['review_state']}")
    if result["duplicate_candidate_refs"]:
        print(f"duplicates: {', '.join(result['duplicate_candidate_refs'])}")
    print(f"summary: {result['distilled_summary']}")
    return 0


def write_promotion_draft(
    project: Path,
    content: str,
    memory_id: str | None = None,
    confidence: float = 0.6,
) -> Path:
    result = promotion_dry_run(project, content, memory_id=memory_id, confidence=confidence)
    drafts = project / "plans"
    drafts.mkdir(exist_ok=True)
    target = as_text(result.get("suggested_target_type")) or "memoir-only"
    slug = slugify(target + "-" + content[:60])
    path = drafts / f"promotion-draft-{slug}.md"
    lines = [
        "# Promotion Draft",
        "",
        f"Date: {date.today().isoformat()}",
        f"Verdict: {result['verdict']}",
        f"Suggested target type: {result['suggested_target_type'] or '-'}",
        f"Confidence: {result['confidence']}",
        f"Review state: {result['review_state'] or '-'}",
        f"Memory ID: {result['memory_id'] or '-'}",
        "",
        "## Distilled summary",
        "",
        as_text(result["distilled_summary"]),
        "",
    ]
    duplicates = result["duplicate_candidate_refs"]
    if duplicates:
        lines.extend(
            [
                "## Duplicate candidates",
                "",
            ]
        )
        lines.extend(f"- {ref}" for ref in duplicates)
        lines.append("")
    lines.extend(
        [
            "## Next step",
            "",
            "- Review this draft before any durable write to REEFIKI.",
            "",
        ]
    )
    return write_unique_text(path, "\n".join(lines))


def parse_promotion_draft(project: Path, draft_path: Path, include_body: bool = False) -> dict[str, object]:
    text = draft_path.read_text(encoding="utf-8")

    def field(label: str) -> str | None:
        match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
        if not match:
            return None
        value = match.group(1).strip()
        return None if value == "-" else value

    summary_match = re.search(r"(?ms)^## Distilled summary\s*\n\n(.*?)(?:\n## |\Z)", text)
    result: dict[str, object] = {
        "path": relative(project, draft_path),
        "date": field("Date"),
        "verdict": field("Verdict"),
        "target_type": field("Suggested target type"),
        "confidence": field("Confidence"),
        "review_state": field("Review state"),
        "memory_id": field("Memory ID"),
        "summary": summary_match.group(1).strip() if summary_match else "",
    }
    if include_body:
        result["body"] = text
    return result


def promotion_inbox(project: Path, show: str | None = None, include_all: bool = False) -> dict[str, object]:
    policy = memory_preflight(
        project=project.name,
        visibility="private",
        operation="promotion-inbox",
        content="",
        paths=[f"projects/{project.name}/plans"],
    )
    result: dict[str, object] = {
        "project": project.name,
        "policy": policy,
    }
    if policy["outcome"] == "block":
        result["total"] = 0
        result["drafts"] = []
        return result

    plans = project / "plans"
    if show:
        draft_path, reason = resolve_contained_path(project, show)
        if draft_path is None:
            raise SystemExit(f"{show}: {reason}")
        result["draft"] = parse_promotion_draft(project, draft_path, include_body=True)
        return result

    drafts = []
    if plans.exists():
        draft_paths = list(plans.glob("promotion-draft-*.md"))
        if include_all:
            draft_paths.extend((plans / "closed").glob("promotion-draft-*.md"))
        for path in sorted(draft_paths):
            if not path.is_file():
                continue
            draft = parse_promotion_draft(project, path)
            if include_all or draft.get("review_state") not in {"applied", "rejected"}:
                drafts.append(draft)
    result["total"] = len(drafts)
    result["drafts"] = drafts
    return result


def promotion_inbox_summary(project: Path) -> dict[str, object]:
    active = promotion_inbox(project, include_all=False)
    all_drafts = promotion_inbox(project, include_all=True)
    closed_items = [
        item for item in all_drafts.get("drafts", [])
        if isinstance(item, dict) and item.get("review_state") in {"applied", "rejected"}
    ]
    closed_counts = {
        state: sum(1 for item in closed_items if item.get("review_state") == state)
        for state in sorted({as_text(item.get("review_state")) for item in closed_items})
    }
    active_count = int(active.get("total", 0))
    closed_count = len(closed_items)
    return {
        "active": active_count,
        "closed": closed_count,
        "total": active_count + closed_count,
        "closed_counts": closed_counts,
    }


def _resolve_project_path(project: Path, path_text: str) -> Path:
    path, reason = resolve_contained_path(project, path_text)
    if path is None:
        raise SystemExit(f"{path_text}: {reason}")
    return path


def update_promotion_draft_review_state(project: Path, draft_path: str, state: str, note: str | None = None) -> Path:
    path = _resolve_project_path(project, draft_path)
    text = path.read_text(encoding="utf-8")
    if re.search(r"^Review state:\s*.+$", text, re.MULTILINE):
        text = re.sub(r"^Review state:\s*.+$", f"Review state: {state}", text, count=1, flags=re.MULTILINE)
    else:
        text = text.replace("Memory ID:", f"Review state: {state}\nMemory ID:", 1)
    if note:
        block = f"\n## Review note\n\n{note.strip()}\n"
        if "## Review note" in text:
            text = re.sub(r"(?ms)^## Review note\s*\n\n.*?(?:\n## |\Z)", block.strip() + "\n", text, count=1)
        else:
            text = text.rstrip() + block
    path.write_text(text, encoding="utf-8")
    return path


def apply_promotion_inbox_draft(project: Path, draft_path: str, yes: bool) -> dict[str, object]:
    page = apply_promotion_draft(project, draft_path, yes=yes)
    draft = update_promotion_draft_review_state(project, draft_path, "applied")
    return {
        "action": "applied",
        "draft_path": relative(project, draft),
        "page_path": relative(project, page),
    }


def reject_promotion_inbox_draft(project: Path, draft_path: str, reason: str | None, yes: bool) -> dict[str, object]:
    if not yes:
        raise SystemExit("Refusing to reject without --yes.")
    draft = update_promotion_draft_review_state(project, draft_path, "rejected", note=reason or "Rejected in promotion inbox review.")
    log = project / "wiki" / "log.md"
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"\n## [{date.today().isoformat()}] meta | promotion draft rejected\n\n"
            f"- draft: {relative(project, draft)}\n"
            f"- reason: {reason or 'not specified'}\n"
        )
    return {
        "action": "rejected",
        "draft_path": relative(project, draft),
        "reason": reason,
    }


def prune_closed_promotion_drafts(project: Path, yes: bool) -> dict[str, object]:
    if not yes:
        raise SystemExit("Refusing to prune without --yes.")
    plans = project / "plans"
    closed = plans / "closed"
    moved: list[dict[str, str]] = []
    if plans.exists():
        closed.mkdir(exist_ok=True)
        for path in sorted(plans.glob("promotion-draft-*.md")):
            if not path.is_file():
                continue
            draft = parse_promotion_draft(project, path)
            if draft.get("review_state") not in {"applied", "rejected"}:
                continue
            destination = closed / path.name
            counter = 2
            while destination.exists():
                destination = closed / f"{path.stem}-{counter}{path.suffix}"
                counter += 1
            path.replace(destination)
            moved.append({"from": relative(project, path), "to": relative(project, destination)})
    if moved:
        log = project / "wiki" / "log.md"
        with log.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                f"\n## [{date.today().isoformat()}] meta | promotion drafts pruned\n\n"
                f"- moved: {len(moved)}\n"
            )
            for draft in moved:
                handle.write(f"- {draft['from']} -> {draft['to']}\n")
    return {
        "action": "pruned",
        "moved": len(moved),
        "drafts": moved,
    }


def _target_subdir(target_type: str) -> str:
    mapping = {
        "concept": "concepts",
        "decision": "decisions",
        "synthesis": "synthesis",
    }
    if target_type not in mapping:
        raise SystemExit(f"Unsupported apply target type: {target_type}")
    return mapping[target_type]


def _promotion_body(target_type: str, summary: str) -> str:
    if target_type == "decision":
        return (
            "## Контекст\n\n"
            f"{summary}\n\n"
            "## Варианты\n\n"
            "- TBD\n\n"
            "## Решение\n\n"
            f"{summary}\n\n"
            "## Последствия\n\n"
            "- needs verification\n"
        )
    if target_type == "concept":
        return (
            "## Суть\n\n"
            f"{summary}\n\n"
            "## Дельта\n\n"
            "Сформировано из promotion draft; требует review.\n\n"
            "## Применение\n\n"
            "- уточнить useful_when и context по результатам review\n"
        )
    return (
        "## Суть\n\n"
        f"{summary}\n\n"
        "## Дельта\n\n"
        "Сформировано из promotion draft; требует review.\n\n"
        "## Применение\n\n"
        "- уточнить practical value по результатам review\n"
    )


def apply_promotion_draft(project: Path, draft_path: str, yes: bool) -> Path:
    if not yes:
        raise SystemExit("Refusing to apply without --yes.")
    path = _resolve_project_path(project, draft_path)
    text = path.read_text(encoding="utf-8")
    verdict_match = re.search(r"^Verdict:\s*(.+)$", text, re.MULTILINE)
    target_match = re.search(r"^Suggested target type:\s*(.+)$", text, re.MULTILINE)
    summary_match = re.search(r"(?ms)^## Distilled summary\s*\n\n(.*?)(?:\n## |\Z)", text)
    if not verdict_match or verdict_match.group(1).strip() != "promote":
        raise SystemExit(f"{relative(project, path)}: draft verdict is not promote")
    if not target_match:
        raise SystemExit(f"{relative(project, path)}: missing target type")
    target_type = target_match.group(1).strip()
    summary = summary_match.group(1).strip() if summary_match else ""
    if not summary:
        raise SystemExit(f"{relative(project, path)}: missing distilled summary")

    base_page_id = slugify(summary[:80])
    subdir = _target_subdir(target_type)
    title = summary[:120]
    body = _promotion_body(target_type, summary)
    counter = 1
    while True:
        page_id = base_page_id if counter == 1 else f"{base_page_id}-{counter}"
        page_path = project / "wiki" / subdir / f"{page_id}.md"
        page_text = (
            "---\n"
            f"id: {page_id}\n"
            f"type: {target_type}\n"
            f'title: "{title}"\n'
            "tags: [memoir, promotion-draft]\n"
            "useful_when:\n"
            '  - "уточнить и принять durable artifact после promotion draft"\n'
            f"date_added: {date.today().isoformat()}\n"
            "use_count: 0\n"
            "last_used: null\n"
        )
        if target_type == "synthesis":
            page_text += "sources: [current-session-2026-05-14]\n"
        page_text += f"---\n\n{body}\n"
        try:
            page_path = write_new_text(page_path, page_text)
            break
        except FileExistsError:
            counter += 1

    log = project / "wiki" / "log.md"
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"\n## [{date.today().isoformat()}] meta | promotion draft applied\n\n"
            f"- draft: {relative(project, path)}\n"
            f"- page: {relative(project, page_path)}\n"
            f"- target_type: {target_type}\n"
        )
    build_index(project)
    return page_path


def print_memory_promotion_inbox(
    root: Path,
    project_name: str,
    show: str | None,
    apply: str | None,
    reject: str | None,
    reason: str | None,
    yes: bool,
    include_all: bool,
    prune_closed: bool,
    fmt: str,
) -> int:
    project = find_project(root, project_name)
    if prune_closed:
        result = prune_closed_promotion_drafts(project, yes=yes)
        if fmt == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"moved: {result['moved']}")
            for draft in result["drafts"]:
                print(f"  - {draft['from']} -> {draft['to']}")
        return 0
    if apply:
        result = apply_promotion_inbox_draft(project, apply, yes=yes)
        if fmt == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"applied: {result['draft_path']}")
            print(f"page: {result['page_path']}")
        return 0
    if reject:
        result = reject_promotion_inbox_draft(project, reject, reason=reason, yes=yes)
        if fmt == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"rejected: {result['draft_path']}")
        return 0
    result = promotion_inbox(project, show=show, include_all=include_all)
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("policy", {}).get("outcome") == "block" else 0
    print(f"project: {result['project']}")
    print(f"policy: {result['policy'].get('outcome')}")
    if result.get("draft"):
        draft = result["draft"]
        print(f"draft: {draft.get('path')}")
        print(f"verdict: {draft.get('verdict')}")
        print(f"target_type: {draft.get('target_type')}")
        print(f"review_state: {draft.get('review_state')}")
        print(f"memory_id: {draft.get('memory_id')}")
        print(f"summary: {draft.get('summary')}")
        return 0
    print(f"drafts: {result.get('total', 0)}")
    for draft in result.get("drafts", []):
        print(f"  - {draft.get('path')}: {draft.get('verdict')} -> {draft.get('target_type')}")
    return 1 if result.get("policy", {}).get("outcome") == "block" else 0


def print_global_promote(
    root: Path,
    content: str,
    target_project: str,
    memory_id: str | None,
    confidence: float,
    write_draft: bool,
    fmt: str,
) -> int:
    policy = memory_global_strict_preflight(
        project=target_project,
        visibility="private",
        operation="promote",
        content=content,
        paths=[f"projects/{target_project}"],
    )
    if policy["outcome"] == "block":
        result: dict[str, object] = {
            "target_project": target_project,
            "policy": policy,
            "verdict": "blocked",
        }
        if fmt == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        print(f"target_project: {target_project}")
        print("policy: block")
        print(f"blocking_reasons: {', '.join(policy['blocking_reasons'])}")
        return 1

    project = find_project(root, target_project)
    result = promotion_dry_run(project, content, memory_id=memory_id, confidence=confidence)
    result["target_project"] = project.name
    result["policy"] = policy
    action = "NOOP"
    if result["verdict"] == "promote":
        action = "DUPLICATE" if result["duplicate_candidate_refs"] else "CREATE"
    candidate = PromotionCandidate(
        content=as_text(result["distilled_summary"]),
        source_layer="memoir",
        target_project=project.name,
        suggested_action=action,
        target_type=as_text(result["suggested_target_type"]) or None,
        duplicate_candidates=[as_text(ref) for ref in result["duplicate_candidate_refs"]],
        review_state=as_text(result["review_state"]) or "noop",
    )
    result["promotion_candidate"] = candidate.to_dict()
    trace = MemoryDecisionTrace(
        operation="promote",
        boundary_context=AccessBoundaryContext(
            project=project.name,
            allowed_scopes=[f"projects/{project.name}"],
            forbidden_scopes=["projects/metrica", "projects/hermes", "secrets", "raw"],
            visibility="private",
        ),
        route_decision=RouteDecision(
            recommended_layer="reefiki" if result["verdict"] == "promote" else "memoir",
            reason="global promotion gate",
            target_project=project.name,
            risk_flags=["durable_write_requires_review"] if result["verdict"] == "promote" else [],
        ),
        policy_checks=[policy],
        promotion_candidates=[candidate],
        safety_outcome="needs_review" if result["verdict"] == "promote" else "pass",
    )
    result["trace"] = trace.to_dict()
    if write_draft:
        draft = write_promotion_draft(project, content, memory_id=memory_id, confidence=confidence)
        result["draft_path"] = relative(project, draft)
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"target_project: {project.name}")
    print(f"verdict: {result['verdict']}")
    if result["suggested_target_type"]:
        print(f"target_type: {result['suggested_target_type']}")
    print(f"confidence: {result['confidence']}")
    if result["review_state"]:
        print(f"review_state: {result['review_state']}")
    if result["duplicate_candidate_refs"]:
        print(f"duplicates: {', '.join(result['duplicate_candidate_refs'])}")
    if write_draft:
        print(f"draft: {result['draft_path']}")
    print(f"summary: {result['distilled_summary']}")
    return 0
