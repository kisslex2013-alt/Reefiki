# Hermes adapter

This is a read-only install guide for using REEFIKI base skills with Hermes-style agent runtimes.

## What this adapter may do

- Reference `skills/base/*/SKILL.md` from a Hermes runtime prompt or project instructions.
- Keep REEFIKI as durable knowledge and Hermes as runtime execution context.
- Describe safe tool boundaries before automation.

## What this MVP does not do

- It does not create a Hermes `runtime-prompt.md`.
- It does not change Hermes config.
- It does not add host bridges, new memory providers or daemon behavior.

## Suggested manual wiring

1. Keep canonical skills in `skills/base/`.
2. Add only a short runtime prompt reference to the base skill paths after explicit approval.
3. Treat durable writes as REEFIKI operations, not Hermes memory runtime changes.
4. Validate with a harmless dry-run task before enabling any live operations.

## Verification

- Hermes can identify which base skill applies to a task.
- No Hermes host/runtime config changed during adapter setup.
