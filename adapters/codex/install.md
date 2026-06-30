# Codex adapter

This is a read-only install guide for REEFIKI base skills in Codex-style environments.

## What this adapter may do

- Point Codex at `skills/base/*/SKILL.md`.
- Copy selected base skills into a local Codex skills directory when explicitly approved.
- Add project instructions that tell Codex when to use the base skills.

## What this MVP does not do

- It does not create or modify `.codex/hooks.json`.
- It does not change `C:\Users\<user>\.codex\config.toml`.
- It does not install marketplace packages.
- It does not overwrite existing user skills.

## Suggested manual wiring

1. Keep canonical skills in `skills/base/`.
2. Add `adapters/generic-agents/AGENTS.md.fragment` to the repo instruction contract if the project has no equivalent.
3. If a local Codex skill install is desired, copy one skill folder at a time and validate it separately.
4. Add hooks only in a separate proof-gated implementation slice.

## Verification

- Codex can name the relevant base skill for worktree, source-of-truth, publish, harvest and browser-smoke scenarios.
- No global config file changed during this adapter setup.
