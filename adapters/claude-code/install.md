# Claude Code adapter

This is a read-only install guide for using REEFIKI base skills with Claude Code-style project instructions.

## What this adapter may do

- Reference `skills/base/*/SKILL.md` from `CLAUDE.md` or `AGENTS.md`.
- Map existing slash-command docs to the relevant base skill.
- Keep project-specific command behavior in project docs.

## What this MVP does not do

- It does not create `.claude/commands/*`.
- It does not rewrite existing command docs.
- It does not install global Claude Code config.

## Suggested manual wiring

1. Keep the canonical skills in `skills/base/`.
2. Add the generic fragment to `CLAUDE.md` or the repo agent contract if explicit approval is given.
3. Map existing commands conceptually:
   - worktree/bootstrap tasks -> `safe-task-worktree-bootstrap`
   - save/harvest closeout -> `durable-harvest-closeout`
   - publish/merge -> `staged-scope-and-publish-guard`
4. Implement real slash-command files only in a separate adapter implementation slice.

## Verification

- Claude Code reads the project instruction file and can locate `skills/base/*/SKILL.md`.
- Existing command behavior remains unchanged.
