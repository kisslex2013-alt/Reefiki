---
name: reefiki-experience-monitor
description: Use before non-trivial work on a project that has REEFIKI wiki records. Retrieves relevant durable skills, decisions, concepts, synthesis and log entries so the agent does not repeat known mistakes or ignore project-specific rules.
---

# reefiki-experience-monitor

## When to use

Use before starting substantial work in a project with accumulated REEFIKI history.

## Inputs

- Target project name.
- Task keywords.
- REEFIKI root path.
- Project-specific AGENTS or command docs.

## Workflow

1. Determine the target `projects/<name>` record.
2. Search durable wiki surfaces first: `wiki/skills`, `wiki/decisions`, `wiki/concepts`, `wiki/synthesis`, `wiki/log.md`, `wiki/index.md`.
3. Open only the few pages needed for the task.
4. Extract operational constraints, known pitfalls, required gates and useful procedures.
5. Continue the implementation; do not turn monitoring into a broad wiki audit.
6. Use durable harvest closeout if the new work produces reusable knowledge.

## Safety rules

- Do not edit `raw/`.
- Do not create pages in the wrong project.
- Do not cross project boundaries unless the user explicitly asks for cross-project search or skill sharing.

## Verification

- Relevant wiki pages were checked.
- The work plan reflects applicable project rules.
- Any skipped history source is intentionally out of scope.

## Outputs

- Compact task-specific context.
- Constraints and gates to apply.
- Known conflicts or stale assumptions.

## Adapter notes

Adapters may prefill project paths or search commands, but they must keep REEFIKI durable knowledge separate from short working memory and graph/index layers.
