---
name: staged-scope-and-publish-guard
description: Use before commit, push, publish, release, harvest, or handoff in dirty, multi-project or public/private repositories. Checks staged paths, generated artifacts, private/public boundaries and project publish gates.
---

# staged-scope-and-publish-guard

## When to use

Use before any meaningful commit or publication.

## Inputs

- Declared task scope.
- Staged paths.
- Base branch.
- Project publish rules.

## Workflow

1. Run `git diff --cached --name-only`.
2. Compare staged files with the declared write scope.
3. Stage explicit paths only.
4. Reject broad staging such as `git add -A` in mixed repositories.
5. Run project-specific staged guards when available.
6. Run publish dry-run before apply/push when the project has a publish workflow.
7. Report touched paths and excluded dirty files.

## Safety rules

- Do not commit unrelated dirty files.
- Do not mix project wiki harvest files with root code/docs unless the task explicitly owns both.
- Do not push private branches to public remotes.
- Treat dry-run as diagnostic, not publication.

## Verification

- Staged file list is within scope.
- Diff class and publish actions are understood.
- Private/public exclusions are checked when relevant.

## Outputs

- Pass/block decision.
- Staged path evidence.
- Publish action summary.

## Adapter notes

Adapters can turn this into hooks or command wrappers, but they must remain conservative and explain how to bypass only with explicit project approval.
