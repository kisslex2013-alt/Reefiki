---
name: browser-runtime-smoke-gate
description: Use after frontend, route, page, component, form, layout, auth, sync, local web app, deployed web app, or browser-visible behavior changes. Verifies real browser behavior with console and page error gates.
---

# browser-runtime-smoke-gate

## When to use

Use when build or unit tests do not prove what the user sees in a browser.

## Inputs

- Target URL or local app command.
- Minimal user route and flow.
- Expected visible state.
- Browser automation tool available to the agent.

## Workflow

1. Start or select the correct app target deliberately.
2. Subscribe to browser `pageerror` and `console.error`.
3. Open the minimal route.
4. Perform real user actions: click, type, submit, navigate or resize as needed.
5. Verify visible state after interaction.
6. Check the page is not blank and key UI remains visible.
7. Classify any runtime error before passing the gate.
8. Avoid testing stale production when a local target was intended.

## Safety rules

- Do not commit generated traces or screenshots unless they are deliberate evidence artifacts.
- Do not ignore browser errors just because tests passed.
- Do not interact with production systems unless explicitly intended.

## Verification

- Browser route loaded.
- Key visible state verified.
- Console/page errors are absent or classified.
- Target environment is recorded.

## Outputs

- Browser smoke result.
- Error classification.
- Residual risk if full flow was not covered.

## Adapter notes

Adapters may bind this skill to Playwright, an in-app browser, Chrome, or a mobile browser, but the base gate remains behavior-first.
