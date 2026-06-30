# REEFIKI base skills

These are portable, markdown-first workflows for AI agents working in real repositories.

The canonical workflow lives in each `SKILL.md`. Runtime-specific integration belongs in `adapters/` and must not change the skill meaning.

## Included skills

- `safe-task-worktree-bootstrap` — start work in a clean scoped worktree.
- `source-of-truth-diagnostics` — verify drift-prone facts from live sources.
- `staged-scope-and-publish-guard` — keep commits and publish scope narrow.
- `reefiki-experience-monitor` — load durable project history before non-trivial work.
- `durable-harvest-closeout` — preserve reusable results in REEFIKI.
- `verification-before-completion` — prove claims before saying a task is done.
- `browser-runtime-smoke-gate` — verify browser-visible changes in a real runtime.

## Rules

- Keep base skills plain markdown.
- Do not require a specific agent runtime.
- Do not store secrets, tokens, local account names or machine-only config here.
- Put Codex, Claude Code, Cursor, Hermes or other runtime wiring in `adapters/`.

See also: [base skill rationale](../../docs/skill-products/BASE_SKILLS.md) and [adapter rules](../../docs/skill-products/AGENT_ADAPTERS.md).
