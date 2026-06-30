from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


def _not_configured(*args: object, **kwargs: object) -> object:
    raise RuntimeError("project command dependency is not configured")


@dataclass(frozen=True)
class ProjectCommandDeps:
    build_index: Callable[..., object] = _not_configured
    relative: Callable[..., str] = _not_configured
    db_path: Callable[..., Path] = _not_configured
    print_search: Callable[..., int] = _not_configured
    privacy_scan: Callable[..., int] = _not_configured
    dedup_check: Callable[..., int] = _not_configured
    save_source: Callable[..., int] = _not_configured
    status: Callable[..., int] = _not_configured
    print_doctor: Callable[..., int] = _not_configured
    print_health: Callable[..., int] = _not_configured
    print_dashboard: Callable[..., int] = _not_configured
    plan_create: Callable[..., int] = _not_configured
    plan_check: Callable[..., int] = _not_configured
    timeline: Callable[..., int] = _not_configured
    write_review_queue_report: Callable[..., Path] = _not_configured
    print_review_queues: Callable[..., int] = _not_configured
    print_backlink_index: Callable[..., int] = _not_configured
    apply_promotion_draft: Callable[..., Path] = _not_configured
    write_promotion_draft: Callable[..., Path] = _not_configured
    print_promotion_dry_run: Callable[..., int] = _not_configured


def dispatch_project_command(args: argparse.Namespace, project: Path, deps: ProjectCommandDeps) -> int:
    if args.cmd == "index":
        count = deps.build_index(project)
        print(f"Indexed {count} page(s): {deps.relative(project, deps.db_path(project))}")
        return 0
    if args.cmd == "search":
        return deps.print_search(
            project,
            args.query,
            args.limit,
            args.format,
            args.output,
            args.page_type,
            args.tag,
            args.link_to,
            args.linked_by,
            args.orphan,
            args.chunks,
        )
    if args.cmd == "privacy":
        return deps.privacy_scan(project)
    if args.cmd == "dedup":
        return deps.dedup_check(project, args.source)
    if args.cmd == "save":
        return deps.save_source(project, args.source)
    if args.cmd == "status":
        return deps.status(project, args.format)
    if args.cmd == "doctor":
        return deps.print_doctor(project, args.format)
    if args.cmd == "health":
        return deps.print_health(project, args.format)
    if args.cmd == "dashboard":
        return deps.print_dashboard(project, args.stale_days, args.limit, args.format)
    if args.cmd == "plan":
        if args.plan_cmd == "create":
            return deps.plan_create(project, args.title)
        if args.plan_cmd == "check":
            return deps.plan_check(project, args.path)
    if args.cmd == "timeline":
        return deps.timeline(project, args.limit, args.format)
    if args.cmd == "review-queues":
        if args.write_report:
            report = deps.write_review_queue_report(project, args.stale_days)
            print(deps.relative(project, report))
            return 0
        return deps.print_review_queues(
            project,
            args.stale_days,
            args.format,
            args.queue_type,
            summary=args.summary,
            limit=args.limit,
            changed_paths=getattr(args, "changed_path", []),
            fail_on_changed_missing_backlink=getattr(args, "fail_on_changed_missing_backlink", False),
            fail_on_new_missing_backlink=getattr(args, "fail_on_new_missing_backlink", False),
            baseline_ref=getattr(args, "baseline_ref", "HEAD"),
        )
    if args.cmd == "backlinks":
        return deps.print_backlink_index(project, args.format, args.write)
    if args.cmd == "promote-dry-run":
        if args.apply_draft:
            page = deps.apply_promotion_draft(project, args.apply_draft, yes=args.yes)
            print(deps.relative(project, page))
            return 0
        if args.write_draft:
            draft = deps.write_promotion_draft(
                project,
                args.content,
                memory_id=args.memory_id,
                confidence=args.confidence,
            )
            print(deps.relative(project, draft))
            return 0
        return deps.print_promotion_dry_run(
            project,
            args.content,
            args.memory_id,
            args.confidence,
            args.format,
        )
    return 2
