# Cursor adapter

This is a read-only install guide for using REEFIKI base skills with Cursor-style rules.

## What this adapter may do

- Reference `skills/base/*/SKILL.md` from existing project rules.
- Convert the generic fragment into Cursor rule text after explicit approval.
- Keep rule scopes narrow and repo-local.

## What this MVP does not do

- It does not create `.cursor/rules/*.mdc`.
- It does not modify `.cursorrules`.
- It does not change global Cursor settings.

## Suggested manual wiring

1. Keep canonical skills in `skills/base/`.
2. Add a repo-local rule that tells Cursor to consult the matching skill before acting.
3. Avoid always-on long prompts; reference the skill path and load only when relevant.
4. Add real `.mdc` rules only in a separate proof-gated adapter slice.

## Verification

- Cursor-visible instructions point to the markdown skill paths.
- No global Cursor settings changed.
