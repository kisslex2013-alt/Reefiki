# Parallel Worktree Lifecycle

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Это reference-правило REEFIKI для параллельной работы агентов: одна задача = один `git worktree` = одна ветка `codex/*`.

Коротко:

- новую задачу начинай в fresh worktree от `origin/main`;
- не чисти чужую грязь в shared checkout;
- перед правками зафиксируй branch, path, status и scope;
- не удаляй dirty, unmerged или ambiguous worktree;
- publish делай через REEFIKI guarded flow, а cleanup — через `cleanup-worktree`.

Подробная canonical-справка ниже на английском.

## English

This is REEFIKI's reference implementation of the global Codex App rule for parallel git development. The global rule is project-agnostic; this document shows how REEFIKI applies it without replacing project-specific publish, wiki, or privacy rules.

## 中文

这是 REEFIKI 对并行 agent 开发的 worktree 生命周期规则：一个任务 = 一个 `git worktree` = 一个 `codex/*` 分支。

简要规则：

- 新任务从 `origin/main` 创建 fresh worktree；
- 不要清理 shared checkout 中别人的 dirty changes；
- 修改前记录 branch、path、status 和 scope；
- 不要删除 dirty、unmerged 或 ambiguous worktree；
- publish 使用 REEFIKI guarded flow，cleanup 使用 `cleanup-worktree`。

下面继续保留英文 canonical reference。

## Baseline

- One task = one `git worktree` = one branch.
- Default branch prefix is `codex/`.
- Default base is `main`; in REEFIKI safety checks normally use `origin/main`.
- Canonical REEFIKI bucket is `<WORKSPACE_ROOT>\_worktrees\REEFIKI-<task>`.
- `C:\tmp` and `C:\Temp` worktrees are only for same-task debug/smoke scratch and must not remain as long-lived registered worktrees.
- Start from fresh `origin/main` or the current approved project base.
- Before edits, record branch, worktree path, status, diff scope, and the intended task scope.
- Do not let multiple agents edit the same coordination files at the same time unless an integration owner is assigned.

## States

| State | Meaning | Default action |
|---|---|---|
| `active` | Work is still in progress and scope is clear. | Keep. |
| `dirty` | Worktree has unstaged, staged, or untracked files. | Block cleanup; review paths. |
| `merged` | Worktree HEAD is reachable from base. | Delete only after status is clean. |
| `semantic-merged` | Useful intent was ported or reimplemented elsewhere with evidence, but commit ancestry does not show it. | Delete only after evidence is documented. |
| `superseded` | Work was intentionally replaced by a better implementation. | Delete only after the replacement and reason are documented. |
| `blocked` | Work cannot continue because of missing input, failing checks, conflicts, or unclear ownership. | Keep and write the blocker. |
| `abandoned` | No useful remaining intent was found after review. | Delete only after a reviewer records why it is safe. |

## Deletion Rules

A worktree can be removed only when all of these are true:

- `git status` is clean inside that worktree.
- The diff versus base is empty, merged, semantic-merged, or intentionally superseded.
- There is ancestry evidence (`HEAD` reachable from base) or explicit semantic evidence.
- Any branch deletion is scoped to the task branch and does not touch unrelated work.
- If the task `HEAD` is already reachable from `--base`, the helper may force-delete that local task branch after removing the worktree. This is still guarded cleanup: the safety proof is the explicit base ancestry check, not the launcher checkout's current `HEAD`.

Do not remove a dirty, unmerged, blocked, or ambiguous worktree. Leave the path, branch, recommendation, and reason instead.

For `semantic-merged` or `superseded` cleanup, use:

```bash
python scripts/reefiki.py cleanup-worktree --worktree <path> --semantic-superseded "<what replaced this branch intent>" --dry-run --format json
```

The helper still blocks dirty worktrees, missing base refs, current-worktree deletion, and too-short evidence. Do not bypass this with manual `git worktree remove` / `git branch -D` for routine cleanup.

## Stale Worktrees

Do not blindly merge an old worktree's final tree. A stale worktree may contain old generated files, obsolete docs, outdated coordination state, or changes from a task that was later solved differently.

If the old worktree still contains useful intent:

- Create a fresh branch from the current base.
- Port only the specific patch or idea that is still valid.
- Re-run tests and closeout checks on the fresh branch.
- Mark the old worktree as semantic-merged or superseded only after evidence exists.

## Parallel Tasks

Parallel work is safe only when each task has a clear write surface. Do not edit coordination files concurrently without an owner. If two tasks need the same coordination file, assign one integration owner before editing.

REEFIKI coordination files that require extra care:

- `ROADMAP.md` and `TASKS.md`: integration owner decides ordering, deduplication, and final wording.
- `projects/*/wiki/log.md`: append-only, but concurrent appends still need ordering in the integration branch.
- `projects/<name>/wiki/index.md`: update only when pages are created, removed, or reindexed.
- `AGENTS.md` and project-level `AGENTS.md`: policy changes should be minimal and explicitly scoped.
- `plans/leadops/worktree-ledger.json`: owner/milestone registry for active parallel task worktrees.

## Codex Threads

Use separate Codex threads when the user confirms multiple independent tasks or explicitly asks for a separate thread. Threads are the conversation/audit boundary; worktrees are the git isolation boundary.

If a thread is named `TeamLead`, it is the REEFIKI intake and integration point. New user work can be requested as `Новая задача: <описание>. Создай отдельную ветку/тред.` TeamLead then creates or assigns a child thread with title `REEFIKI · <short task>`, branch `codex/<ascii-slug>`, and worktree `<WORKSPACE_ROOT>\_worktrees\REEFIKI-<ascii-slug>`.

Child thread closeout reports must be in Russian and include: what changed, changed files, checks, commit, blockers, excluded dirty paths, and next action. Workers do not push, publish, cleanup, or mutate shared coordination files unless TeamLead explicitly delegates that scope.

TeamLead also owns a Subagent Decision Gate. Before non-trivial work starts, and again when scope expands, it records `Child threads: да/нет — причина`. Default to a child thread or read-only verifier for multi-surface work, install/release/PATH/package changes, browser-visible runtime, publish/cleanup/PR migration, dirty worktree triage, user-reported regression smoke, shared coordination files, or when TeamLead implemented a risky change and needs independent verification. For a small linear single-surface task, TeamLead may skip child threads but must state the reason in closeout.

Default routing:

- Coding, docs, wiki, or publish-prep work: create a project thread with a fresh worktree from `origin/main` or the approved base.
- Read-only audit, classification, and cleanup inventory: a project local thread is acceptable when it will not edit the shared checkout.
- External-state monitoring: create a separate thread and keep its scope narrow; do not mix it with unrelated cleanup or roadmap work.

Parent-thread duties:

- Record every returned `threadId` or `pendingWorktreeId`.
- After child threads finish, inspect them with `read_thread` and verify important claims against live git/worktree state.
- If a child thread leaves an unpushed commit, get explicit approval before guarded publish.
- If publish succeeds, run `cleanup-worktree` for the task worktree only after `HEAD` is reachable from `origin/main`.

Do not archive or delete child threads automatically. A completed thread is an audit trail until the user explicitly asks to archive it. Cleaning a task worktree is a git operation; archiving a thread is a separate conversation-management operation.

## Dirty Shared Checkout Is Not A Blocker

The shared checkout, usually `<REEFIKI_ROOT>`, is not the working surface for a new task. It may be dirty or behind `origin/main` because other agents are editing different project scopes, collecting ideas, or leaving local work that is not ready to publish.

For a new dev, docs, harvest, or publish task:

- Inspect the shared checkout read-only with `git status --short --branch`.
- Do not clean, restore, reset, delete, stage, or commit unrelated dirty paths from the shared checkout.
- Create a fresh task worktree from `origin/main` or the approved base and work there.
- Treat dirty paths outside the target scope as `excluded_dirty_paths`; they must be mentioned in the final report but they do not block the task.
- Treat dirty paths inside the target scope as `scope_conflicts`; stop, ask for ownership, or port only the explicitly needed intent into a fresh branch.
- Run publish/harvest only from a clean task worktree and stage only scoped paths.

Examples of excluded context for a REEFIKI task scoped to `projects/reefiki/**` include dirty files under `projects/Hermes/**`, `projects/Metrica/**`, `.claude/worktrees/**`, or unrelated idea folders such as `docs/ideas_09.06.26/**`. They are not a reason to "fix" the shared checkout before starting the task.

## Closeout Checklist

Before a task is called complete:

- Check branch and worktree path.
- Check `git status --short`.
- Check `git diff --name-only <base>...HEAD`.
- Run targeted tests for touched behavior.
- Run `publish-task --dry-run` or deployment dry-run when publication/deploy is part of scope.
- Stage only explicit paths; do not use `git add -A`.
- Commit only after checks pass.
- Do not push or cleanup unless publish/cleanup is part of the accepted task scope or the user explicitly asks for it.
- For roadmap/batch work, one worktree lives until the nearest natural milestone, but not longer; after the milestone, publish, defer, cleanup, or leave a short reason.
- For parallel/batch work, run `orchestration-check` before publish or cleanup.

## REEFIKI Helper

`scripts/reefiki.py worktree-status` is read-only. It reports each worktree path, branch, head, dirty paths, ahead/behind counts versus base, whether `HEAD` is reachable from base, and a recommendation:

- `keep`: primary/base or non-task worktree.
- `delete`: clean `codex/*` task worktree already reachable from base.
- `review`: clean task worktree that is not reachable from base.
- `block`: dirty, missing base, missing path, or otherwise unsafe to classify for cleanup.

With `--scope`, the command also reports dirty path groups, `shared_checkout_dirty`, `shared_checkout_behind`, `excluded_dirty_paths`, `scope_conflicts`, and a scope-aware recommendation:

- `start_fresh_worktree`: shared checkout is dirty or behind; start from fresh base.
- `blocked_by_dirty_target_scope`: dirty paths overlap the target scope.
- `cleanup_review_needed`: dirty state exists but cannot be safely classified for this task.

Example:

```bash
python scripts/reefiki.py worktree-status --format json
python scripts/reefiki.py worktree-status --scope projects/reefiki --format json
python scripts/reefiki.py worktree-status --ledger plans/leadops/worktree-ledger.json --format json
```

## Orchestration Check

`scripts/reefiki.py orchestration-check` is the read-only control-plane preflight for LeadOps batches. It does not create, delete, stage, commit, push, or mutate worktrees. It combines:

- live `worktree-status`;
- `plans/leadops/worktree-ledger.json` owner/milestone/lease checks;
- coordination-file conflict detection;
- current task worktree dirty-state gate;
- remote `origin/codex/*` branch visibility and merged-branch cleanup candidates;
- optional global Codex rule scan with `--include-global-config`;
- local CI workflow presence and an explicit manual branch-protection check.

Default lease limit is 14 days. A longer lease is allowed only when the ledger names a milestone and the lead keeps ownership clear.

Examples:

```bash
python scripts/reefiki.py orchestration-check --format json
python scripts/reefiki.py orchestration-check --ledger plans/leadops/worktree-ledger.json --include-global-config --format json
```
