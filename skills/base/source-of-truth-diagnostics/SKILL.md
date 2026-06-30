---
name: source-of-truth-diagnostics
description: Use when a user asks about config, installed tools, model/runtime capabilities, MCP/plugins, paths, versions, logs, health, access, or any fact likely to drift. Verifies the live source of truth before answering from memory.
---

# source-of-truth-diagnostics

## When to use

Use when the answer depends on current local or remote state.

## Inputs

- Named file, config, endpoint, command, tool namespace or runtime.
- User claim or question.
- Project rules about allowed inspection.

## Workflow

1. Identify the authoritative source: config file, docs, tool discovery, logs, executable, endpoint, manifest or official source.
2. Inspect the named source first when the user provides one.
3. Prefer live checks over memory when verification is cheap.
4. For parse errors, inspect raw bytes before assuming semantic invalidity.
5. For path claims, verify the current canonical path instead of relying on old aliases.
6. Separate verified facts, inference and remaining checks in the response.

## Safety rules

- Do not print secrets or token values.
- Do not broaden from a named source to unrelated clients unless needed.
- Do not answer capability or access questions from memory when live discovery is available.

## Verification

- Command output or file content proves the claim.
- Source timestamp/version is captured when relevant.
- Any unverifiable claim is marked as inference or residual risk.

## Outputs

- Current verified state.
- Narrow conclusion.
- Explicit unknowns when evidence is incomplete.

## Adapter notes

Adapters may provide runtime-specific source locations, but the base workflow remains: named source first, live evidence before memory.
