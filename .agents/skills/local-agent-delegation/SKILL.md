---
name: local-agent-delegation
description: Use when Codex needs to delegate a bounded prompt to installed local agent CLIs or Hermes on the VPS, wait for their answers, collect artifacts, and compare results. Supports Claude Code, Mimo Code, Gemini CLI, Hermes VPS over SSH, and an Odysseus API placeholder. Do not use for web-only agents or for uncontrolled edits; use read-only mode by default and a fresh task worktree for edit scopes.
---

# Local Agent Delegation

Use this skill to fan out one bounded prompt to multiple agent runtimes and collect their outputs for parent-agent review.

## Ground Rules

1. Keep the parent Codex thread responsible for scope, final judgment, commits, publish, and cleanup.
2. Default to read-only prompts. For edit tasks, create a fresh task worktree first and name the allowed files.
3. Do not pass secrets, tokens, private keys, `.env` contents, or broad personal paths into prompts.
4. Do not use local Hermes. Hermes delegation is only through the VPS SSH adapter.
5. Do not use `--yolo`, `--dangerously-skip-permissions`, or equivalent broad approval flags unless the user explicitly scoped that risk.
6. Do not send private project context to web agents. This skill is for local CLIs and Hermes VPS only.

## Adapters

- `claude`: `claude -p ... --output-format json --permission-mode plan`
- `mimo`: `mimo run ... --pure --format json --dir <cwd>`; no hard permission flag is assumed, so keep prompts read-only and rely on the helper's post-run mutation detector
- `gemini`: `gemini -p ... --skip-trust --output-format json --approval-mode plan` with scoped `GEMINI_CLI_TRUST_WORKSPACE=true` for headless trusted-workspace compatibility
- `hermes-vps`: `ssh` using explicit `HERMES_VPS_KEY`, `HERMES_VPS_HOST`, `HERMES_VPS_USER`, optional `HERMES_VPS_CWD`, and optional `HERMES_VPS_EXECUTABLE`, then remote `<hermes-executable> chat -q ... -Q --source tool`
- `odysseus-api`: placeholder only; use after local Odysseus auth/token and API endpoint are verified

There is intentionally no `hermes-local` adapter.

## Workflow

1. Confirm the task scope and decide whether the prompt is read-only or edit-capable.
2. For edit-capable prompts, create or reuse the task worktree and include branch, cwd, allowed files, and forbidden actions in the prompt.
3. Write a concise prompt file. Include the exact output format expected from agents.
4. Run a dry plan first:

For Hermes VPS, configure connection details outside the repo:

```powershell
$env:HERMES_VPS_KEY = "<path-to-private-key>"
$env:HERMES_VPS_HOST = "<host>"
$env:HERMES_VPS_USER = "<user>"
$env:HERMES_VPS_CWD = "/srv/projects"
$env:HERMES_VPS_EXECUTABLE = "/home/codex/.hermes/hermes-agent/venv/bin/hermes"
```

```powershell
python .agents\skills\local-agent-delegation\scripts\local_agent_delegate.py plan --agents claude,mimo,gemini,hermes-vps --prompt-file <prompt.md> --cwd <repo> --output-dir <out>
```

5. Execute only the selected adapters:

```powershell
python .agents\skills\local-agent-delegation\scripts\local_agent_delegate.py run --agents claude,mimo,gemini,hermes-vps --prompt-file <prompt.md> --cwd <repo> --output-dir <out> --timeout 900
```

6. Read each `<out>/<agent>/result.json`, `<out>/<agent>/stdout.txt`, and `<out>/<agent>/stderr.txt`.
7. Compare the answers yourself. Accept only claims backed by live evidence or reproducible reasoning.
8. Summarize accepted findings in the parent thread and list rejected/uncertain findings separately.

## Output Handling

The helper writes a run folder with:

- `manifest.json` - task metadata and adapter list.
- `<agent>/stdout.txt` - raw stdout.
- `<agent>/stderr.txt` - raw stderr.
- `<agent>/result.json` - status, command metadata, timing, and output paths.
- `summary.json` - normalized status for every requested adapter.

The helper does not commit, publish, clean worktrees, or archive threads.

For every `run`, the helper snapshots `git status --porcelain` in the target `--cwd` before and after each adapter. Helper output under `--output-dir` is ignored when that directory is inside the target repo. A clean local cwd keeps the adapter's normal status. A pre-existing dirty target cwd returns `needs_review`, because the helper cannot prove the agent did not touch already-dirty files. Any new untracked, modified, or staged target-cwd change returns `mutated` and makes the run fail closed instead of reporting an ordinary pass.

Hermes VPS is checked only for local cwd mutation. The result payload explicitly marks the remote cwd as `not_checked`; do not treat that as proof that the VPS filesystem stayed unchanged.

## Odysseus

Odysseus is not treated as an installed CLI. Current local evidence shows it is a web app/API in a local checkout with `/api/chat` and `/api/chat_stream`. Keep `odysseus-api` disabled until a separate adapter verifies:

1. server health;
2. auth/token source;
3. selected chat/agent endpoint;
4. safe output capture;
5. no unintended wipe/admin routes.

## Failure Handling

- Timeout or non-zero exit from one adapter is a partial result, not a total task failure.
- If an adapter asks for interactive trust/auth, stop that adapter and record the blocker.
- If Hermes VPS SSH fails, verify the VPS access skill before retrying; do not fall back to local Hermes.
- If outputs conflict, parent Codex decides from evidence and may run a focused follow-up prompt.

## Validation

Before relying on this skill after edits, run:

```powershell
python .agents\skills\local-agent-delegation\scripts\local_agent_delegate.py list-adapters --format json
python -m pytest tests\test_local_agent_delegate.py
```
