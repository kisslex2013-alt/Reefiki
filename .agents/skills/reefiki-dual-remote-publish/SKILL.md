---
name: reefiki-dual-remote-publish
description: Use when publishing REEFIKI work to git, including "push", "пуш", "отправь на git", merge, PR, public snapshot, cleanup of task worktrees, or any dual private/public remote publication.
---

# REEFIKI Dual-Remote Publish

Use this before any REEFIKI publish action. Do not treat `git push` as a single command: REEFIKI has private `origin` and filtered public `public`.

## Default Flow

1. Run dry-run from the task worktree or current repo:

```powershell
python scripts\reefiki.py publish-task --dry-run --cleanup --format json
```

2. Read the result:
- `private-only`: push to `origin` only.
- `public-safe`: push to `origin`, then filtered `public` snapshot.
- `mixed`: push private first, then filtered `public` snapshot.
- `block`: stop and report the reason. Do not force-push or merge by hand.

3. If dry-run passes and the user asked to publish, run:

```powershell
python scripts\reefiki.py publish-task --apply --cleanup --format json
```

If private push already succeeded but public snapshot failed due to network, resume only the public side:

```powershell
python scripts\reefiki.py publish-task --apply --public-snapshot --format json
```

## Rules

- Never push a private task branch directly to `public`.
- Never publish from a dirty worktree.
- If the task branch is not fast-forward over the base, create or ask for PR flow; do not force-push `origin/main`.
- Public publication must be a filtered orphan snapshot with private projects removed.
- Private project folders are defined by `scripts/public-snapshot.private-projects.txt`.
- Until the Python runtime path gets a fail-closed inventory guard, treat `scripts/public-snapshot.private-projects.txt` as a critical manual invariant: missing, empty, renamed, or omitted project entries are a P0 risk.
- Until content scanning exists, treat `public-safe` as path-based only, not proof that public files contain no secret/private content.
- After successful merge/publish, remove task worktrees/branches only when clean and already merged.

## Cleanup

If a task worktree remains after publish, verify:

```powershell
python scripts\reefiki.py cleanup-worktree --worktree <worktree> --dry-run --format json
```

Only then remove it:

```powershell
python scripts\reefiki.py cleanup-worktree --worktree <worktree> --apply --format json
```

Do not delete a dirty worktree or a branch with commits not reachable from `origin/main`.
