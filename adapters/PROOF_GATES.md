# Adapter proof gates

Use these gates before turning a read-only adapter guide into live runtime wiring.

## Required evidence

1. Canonical workflow remains in `skills/base/*/SKILL.md`.
2. Adapter docs explain how the runtime discovers or references the base skill.
3. Adapter docs state whether they change project config, global config, hooks, commands or rules.
4. Demo prompts prove the runtime chooses the expected base skill for common scenarios.
5. Rollback is clear and does not require deleting durable knowledge.
6. Secret scan and markdown link tests pass.

## Blockers

- Adapter changes skill meaning.
- Adapter requires a new memory runtime.
- Adapter writes global agent config without explicit approval.
- Adapter adds hooks, slash commands, Cursor rules or Hermes runtime prompts without a proof-gated implementation slice.
- Adapter installs marketplace packages before demo/proof evidence exists.

## Minimum proof record

Each adapter proof should record:

- adapter name;
- base skills covered;
- demo prompts;
- expected skill routing;
- commands or files intentionally not created;
- validation commands;
- residual risks.

## Current proof targets

- [Codex adapter proof](codex/proof.md) — no live hook/config install; verifies Codex-facing skill routing and no-config-change boundaries.
