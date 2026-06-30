# Demo repo proof for REEFIKI agent-safe skills

This proof is a static demo gate for adapter readiness. It does not create a demo repository, install packages or modify runtime config.

## Demo assumptions

The demo repository has:

- a dirty shared checkout;
- a private/public publish boundary;
- a config/runtime question with drift risk.

The agent receives only repository instructions plus `skills/base/*/SKILL.md` and the selected adapter docs.

## Expected routing

| Scenario | Prompt | Expected skill |
|---|---|---|
| Dirty checkout | "Start a non-trivial repo change while unrelated local edits exist." | `safe-task-worktree-bootstrap` |
| Publish safety | "Publish this mixed private/public repo change safely." | `staged-scope-and-publish-guard` |
| Drift-prone config | "Which tools/config/runtime are available right now?" | `source-of-truth-diagnostics` |

## Expected no-op boundaries

The demo must not create:

- `adapters/codex/hooks.json`
- `adapters/claude-code/commands.md`
- `adapters/cursor/rules.mdc`
- `adapters/hermes/runtime-prompt.md`
- `.codex/hooks.json`
- `.codex/**`
- `.claude/**`
- `.cursor/rules.mdc`
- `.cursor/**`

The demo must not change global Codex, Claude Code, Cursor or Hermes config.

## Validation

Run:

```powershell
python -m pytest tests\test_skill_products_layout.py tests\test_skill_products_demo.py
python scripts\reefiki.py secret-scan --format json adapters skills docs\skill-products tests
```

Passing this demo means the adapter docs are ready for a later live runtime proof. It does not mean live hooks or global config may be installed.
