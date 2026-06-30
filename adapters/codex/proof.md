# Codex adapter proof

This proof keeps the Codex adapter read-only. It validates that Codex can route common tasks to the portable base skills without creating hooks, changing global config or installing marketplace packages.

## Adapter name

`codex`

## Covered base skills

- `safe-task-worktree-bootstrap`
- `source-of-truth-diagnostics`
- `staged-scope-and-publish-guard`
- `reefiki-experience-monitor`
- `durable-harvest-closeout`
- `verification-before-completion`
- `browser-runtime-smoke-gate`

## Demo prompts

| Prompt | Expected base skill |
|---|---|
| "Start a non-trivial repo change while the checkout has unrelated dirty files." | `safe-task-worktree-bootstrap` |
| "Tell me which MCP tools and model/runtime config are actually available." | `source-of-truth-diagnostics` |
| "Commit and publish this REEFIKI change safely." | `staged-scope-and-publish-guard` |
| "Before changing this project, check what REEFIKI already knows about it." | `reefiki-experience-monitor` |
| "Save the reusable result of this production fix." | `durable-harvest-closeout` |
| "Before saying done, prove the change works." | `verification-before-completion` |
| "This frontend route changed; verify it in a browser." | `browser-runtime-smoke-gate` |

## Files intentionally not created

- `adapters/codex/hooks.json`
- `.codex/hooks.json`
- global Codex config under `C:\Users\<user>\.codex\config.toml`

## Validation commands

```powershell
python -m pytest tests\test_skill_products_layout.py
python scripts\reefiki.py secret-scan --format json adapters skills tests\test_skill_products_layout.py
```

## Pass criteria

- Every demo prompt maps to an existing base skill.
- Markdown links resolve.
- Runtime-specific hook/config files are absent.
- Adapter docs say live hooks or global config changes require a separate explicit approval.

## Residual risks

- This proof does not install the adapter into a live Codex runtime.
- It does not prove hook behavior; hooks are a later implementation slice.
- It does not update global user skills.
