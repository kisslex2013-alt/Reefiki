# Memory Reflection

## Status

First read-only CLI slice implemented: `reefiki.py memory reflect`.

Do not add a background daemon, cron job, IDE API, automatic transcript capture, or automatic wiki mutation from this document alone. Further expansion must go through `ROADMAP.md`, `TASKS.md`, tests, and the normal worktree workflow.

## Why This Exists

The "dreaming" idea from ChatGPT/Claude-style memory systems is useful for REEFIKI only if it is narrowed into REEFIKI's existing model:

- REEFIKI is a durable, review-first wiki, not an always-on agent memory database.
- `memoir` handles short working memory and preferences.
- REEFIKI handles durable decisions, procedures, synthesis, and project governance.
- Existing commands already cover much of the need: `memory pack`, `memory golden`, `memory diff`, `memory status`, `dashboard`, `review-queues`, `promote-dry-run`, and `promotion-inbox`.

The useful part of dreaming is periodic consolidation: find stale facts, contradictions, duplicate durable knowledge, missing links, and promotion candidates. The dangerous part is automatic rewriting of memory without clear evidence and review.

## Correct Shape for REEFIKI

Use "memory reflection" rather than autonomous dreaming.

The current implementation is read-only by default:

```text
reefiki.py memory reflect --project <name> --since <ref-or-date> --format text|json
reefiki.py memory reflect --project <name> --since <ref-or-date> --write-report
```

It should assemble a report from existing gates:

- `memory diff` for changed durable wiki paths.
- `health` for practical project health.
- `review-queues --summary` for stale/orphan/duplicate/conflict candidates.
- `memory status --summary` for open governance gates.
- `memory pack --strict` for task-specific context quality.
- `promotion-inbox` for existing review drafts.

`--write-report` may write only a review artifact under `plans/`, for example `plans/reflection-YYYY-MM-DD.md`. It must not write wiki pages, edit `raw/`, stage files, commit, push, or delete anything.

## Non-Goals

Do not implement these without a separate, evidence-backed decision:

- Automatic full session transcript capture.
- Writing session files into `raw/sessions/`.
- Adding global `status:` frontmatter to all wiki page types.
- Adding `expires:` as a required schema field.
- Cron/nightly execution.
- IDE side panel or local HTTP/WebSocket API.
- Automatic apply, merge, delete, or rewrite of wiki knowledge.
- New vector database, reranker, MCP server, or memory runtime.

## Source Capture Boundary

Do not use `raw/` for automatic session summaries. In REEFIKI, `raw/` is an immutable source archive, and automatic conversation capture risks secrets, noise, and daily-note bloat.

If a session contains durable knowledge, use the existing explicit flow:

- `/harvest` for durable wiki knowledge.
- `memoir` for short working memory and preferences.
- `memory promote --write-draft` for reviewable promotion from working memory into a REEFIKI project.
- `plans/` for temporary handoff/review artifacts.

Only introduce a session-capture source format after a separate privacy/security review and a concrete use case that existing `wiki/log.md`, `memory pack`, and `/harvest` cannot cover.

## Staleness Boundary

Do not add schema-wide `status:` or `expires:` fields now.

Current REEFIKI staleness tools already exist:

- `use_count` and `last_used` for page usage.
- `verified` for skills.
- `review-queues` for `stale_review`, `needs_verification`, duplicates, orphans, and conflicts.
- `health` and `dashboard` for operator-level summary.

If these become insufficient, prefer a narrow optional field such as `review_after` for specific page types, not a global `status` migration. Any schema change must include validator updates and migration tests.

## Trigger to Implement

The first implementation was allowed because at least one trigger was true:

- `dashboard` or `memory status --summary` repeatedly requires the operator to manually combine 3+ existing reports.
- `review-queues --summary` remains noisy after bounded triage and needs a single prioritized report.
- `memory pack --strict` passes but still leaves unclear next actions across diff, queues, and promotion drafts.
- A project has enough durable pages that manual weekly consolidation becomes error-prone.

Without one of these triggers, keep the idea documented and do not add code.

## Safety Contract

The first implementation must obey these constraints:

- Read-only by default.
- Report-only write mode under `plans/`.
- No writes to `wiki/`, `raw/`, `seen/`, `_user/`, config, source code, or git state.
- No automatic apply path.
- No new background process.
- No external service dependency.
- Tests must use synthetic projects and synthetic git history.
- JSON output must expose included sources, exclusions, candidate actions, and risk reasons.

## Candidate Output Shape

```json
{
  "project": "reefiki",
  "since": "origin/main",
  "outcome": "review",
  "included": {
    "changed_paths": [],
    "health": {},
    "review_queues": {},
    "promotion_inbox": {},
    "pack_quality": {}
  },
  "candidate_actions": [
    {
      "action": "run review-queues --type missing_backlink --limit 10",
      "reason": "highest open queue",
      "risk": "low"
    }
  ],
  "blocked_actions": [
    {
      "action": "auto-apply wiki changes",
      "reason": "reflection is report-only"
    }
  ]
}
```

## External Inspiration Boundary

OpenAI and Claude-style memory systems are useful references for the pattern of background consolidation and reviewable memory, but REEFIKI should not copy their product architecture directly.

Use the references as inspiration only:

- OpenAI memory/dreaming: background memory synthesis and user-reviewable memory summaries.
- Claude Code memory docs: local project memory and editable markdown instructions.
- Community memory tools: possible patterns for compaction, timeline, and search, but not a reason to add another runtime.

For REEFIKI, the rule is: keep the smallest local-first slice that improves existing governance gates.
