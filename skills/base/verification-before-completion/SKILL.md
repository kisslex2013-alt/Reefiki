---
name: verification-before-completion
description: Use before declaring a task done, especially after code, docs, adapters, data, release, deployment or infrastructure changes. Maps every completion claim to fresh evidence and calls out missing proof.
---

# verification-before-completion

## When to use

Use at closeout before saying the task is complete.

## Inputs

- User request and acceptance criteria.
- Changed files.
- Tests, commands, rendered output or runtime behavior.
- Known project gates.

## Workflow

1. List concrete claims the change makes.
2. Map each claim to evidence that would prove it.
3. Run the narrowest check that proves each claim.
4. Run broader checks when shared behavior could regress.
5. Check non-functional risks such as privacy, data retention, generated files, public exposure and failure paths.
6. Report missing evidence instead of hiding it behind confidence.

## Safety rules

- Do not treat compilation as behavior proof when runtime behavior matters.
- Do not call work complete if an important claim is unverified.
- Do not skip project-specific gates because a narrower test passed.

## Verification

- Each claim has a command, file inspection, runtime smoke or explicit residual risk.
- Fresh checks were run after the final edit.

## Outputs

- Claims verified.
- Evidence run.
- Evidence missing.
- Residual risk.
- Ready or not ready status.

## Adapter notes

Adapters may provide default test commands, but the agent must still derive claims from the actual task.
