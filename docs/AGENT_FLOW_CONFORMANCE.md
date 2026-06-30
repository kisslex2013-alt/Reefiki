# Agent Flow Conformance Checklist

This checklist is the deterministic, no-LLM-judge gate for agents that operate REEFIKI command contracts.

## Supported agents

- Codex CLI/Desktop: reads `AGENTS.md`, project `AGENTS.md` and `.codex/instructions.md`.
- Claude Code: reads `CLAUDE.md`, `AGENTS.md` and `.claude/commands/*.md`.
- Cursor: reads `.cursorrules` plus `AGENTS.md`.
- Windsurf/Cascade: reads `.windsurf/rules/main.md` plus `AGENTS.md`.
- Cline/Roo Cline: reads `.clinerules` plus `AGENTS.md`.
- Generic LLM agent: must be pointed at root `AGENTS.md`, project `AGENTS.md` and the relevant `.claude/commands/<op>.md` file.

## Required contract surfaces

- `/save`: uses `python scripts/reefiki.py --project projects/<name> save <source>`, writes only `inbox/` plus append-only `wiki/log.md`, refuses unsafe paths and does not create wiki pages.
- `/process`: runs privacy/safety checks, consumes fixture `inbox/` inputs into `raw/` plus `wiki/` or `seen/`, updates `wiki/index.md` and appends `wiki/log.md`; it must not mutate `raw/` outside the selected project.
- `/query`: builds or refreshes the local index, searches with JSON provenance, answers only from wiki/raw evidence, and batches telemetry unless a synthesis page is explicitly saved.
- `/harvest`: performs bounded durable capture from session evidence, writes only selected project wiki artifacts, updates index/log and uses `harvest-commit` for cross-project harvest commits.
- `/status`: is read-only and reports inbox, seen/quarantine, wiki counts, stale pages and lint/search state.
- `guard-staged`: blocks staged paths outside the selected operation profile. Default `harvest` preserves wiki-only behavior; `process` allows inbox/seen/wiki/index/log plus raw create-only paths; `docs` and `code` never allow `projects/*/raw/**`.
- `publish-task`: preflights dirty state, base ancestry, private/public diff class, secret scan and public snapshot leakage before any push.

## Deterministic harness

Run:

```powershell
python -m pytest tests/test_agent_flow_e2e.py
```

The harness uses synthetic temporary projects and repos only. It proves:

- save -> status writes the expected fixture files and leaves `raw/` untouched;
- staged-scope guard blocks mixed target-wiki and non-wiki paths, non-append log edits and raw modification/deletion;
- publish preflight blocks dirty repos without mutation;
- markdown command contracts contain the required agent-facing surfaces for `/save`, `/process`, `/query`, `/harvest` and `/status`.

## Non-goals

- No live LLM judge in CI.
- No mutation of real project wiki fixtures.
- No external service dependency.
- No replacement for the project-level `AGENTS.md` contracts.
