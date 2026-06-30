---
name: durable-harvest-closeout
description: Use when completed work produces a reusable procedure, decision, synthesis, debug runbook, audit outcome, release proof, project rule, or when the user says harvest, save, remember, фиксируй, сохрани, or запомни. Stores durable knowledge in the correct REEFIKI project.
---

# durable-harvest-closeout

## When to use

Use at closeout when the result should survive the chat and guide future agents.

## Inputs

- Completed work summary.
- Target REEFIKI project.
- Existing wiki pages.
- Project schema and log rules.

## Workflow

1. Determine the target project before writing.
2. Search existing pages to avoid duplicates.
3. Choose the durable artifact type: skill, decision, concept, synthesis or log-only update.
4. Write only distilled reusable knowledge, not raw transcript.
5. Add required frontmatter for new pages.
6. Append `wiki/log.md`.
7. Update `wiki/index.md` only when a new page or index-relevant metadata requires it.
8. Run validation and staged-scope guard before commit/publish.

## Safety rules

- Do not store secrets, raw credentials, private dumps or one-off facts.
- Do not edit old log entries.
- Do not touch `raw/`.
- Do not write into an ambiguous target project.

## Verification

- Duplicate check completed.
- Artifact follows project schema.
- Log entry is append-only.
- Scope guard passes before commit.

## Outputs

- Durable wiki artifact or explicit log entry.
- Validation evidence.
- Publish/commit summary.

## Adapter notes

Adapters may add convenience commands, but durable writes must still require a clear target project and scoped validation.
