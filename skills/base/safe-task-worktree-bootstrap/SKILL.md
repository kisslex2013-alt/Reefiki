---
name: safe-task-worktree-bootstrap
description: Use before starting a non-trivial coding task in an existing git repository, especially when the checkout may be dirty, multiple agents may work in parallel, or coordination files may be touched. Establishes a clean task branch, worktree, base, scope and cleanup boundary.
---

# safe-task-worktree-bootstrap

## When to use

Use before editing a real repository when the task is not a one-line read-only answer.

## Inputs

- Repository root.
- Requested task.
- Project git/worktree rules.
- Expected write scope.

## Workflow

1. Run `git status --short --branch` and `git worktree list`.
2. Identify the base branch, usually `origin/main` unless the project says otherwise.
3. If the current checkout has unrelated dirty files, create a clean task worktree instead of spending time classifying unrelated dirt.
4. Use a scoped branch name, typically `codex/<task-slug>`.
5. State the worktree path, branch, base and write scope before edits.
6. Keep coordination files out of parallel edits unless this task owns them.
7. Before closeout, verify status, diff against base, tests and publish/deploy gates.

## Safety rules

- Do not remove dirty, unmerged or ambiguous worktrees.
- Do not merge stale worktree final trees wholesale into fresh main.
- Do not run destructive git commands unless explicitly requested.
- Do not use broad staging in mixed repositories.

## Verification

- `git status --short --branch`
- `git diff --name-only <base>...HEAD`
- Project-specific tests or docs checks.
- Publish/deploy dry-run if the project requires one.

## Outputs

- Clean task boundary.
- Known branch/base/scope.
- Clear cleanup status at closeout.

## Adapter notes

Adapters may automate branch naming or worktree creation, but they must preserve the same safety checks and cleanup evidence.
