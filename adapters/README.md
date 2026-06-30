# REEFIKI skill adapters

Adapters connect markdown-first REEFIKI base skills to a concrete agent runtime.

This MVP is intentionally read-only documentation. It does not install hooks, commands, Cursor rules, global Codex config, marketplace packages or Hermes runtime prompts.

## Adapter rules

- Keep the canonical workflow in `skills/base/*/SKILL.md`.
- Do not change skill meaning in an adapter.
- Do not add a new memory runtime.
- Do not write global agent config without explicit approval.
- Make every adapter removable.
- Treat live hooks and command registration as a separate proof-gated slice.

## Proof gates

Before any live adapter wiring, run the adapter through [proof gates](PROOF_GATES.md). The first concrete proof target is the [Codex adapter proof](codex/proof.md), which validates skill routing and no-config-change boundaries without installing hooks.

See [agent adapter design](../docs/skill-products/AGENT_ADAPTERS.md).
