# REEFIKI Dashboard Demo

This page turns the existing local dashboard into a product-facing demo path without adding a hosted dashboard, cloud sync, remote mutation or publish buttons.

## What The Dashboard Demonstrates

REEFIKI has two local dashboard surfaces:

| Surface | Command | Demo value |
|---|---|---|
| Project governance dashboard | `reefiki --project projects/reefiki-demo dashboard` | Shows wiki health, review queues and the next safe action for one public-safe REEFIKI project. |
| Codex Workspace Ops Board | `reefiki ops-dashboard --workspace-root <folder>` | Shows one-level git repositories, branch/dirty state, stack hints, REEFIKI mapping and local activity signals. |

The product demo focuses on the Ops Board because it is visual, read-only and easy to explain: it shows what an agent should inspect before changing code.

## Safe Demo Setup

Use the built-in synthetic workspace command, not the operator's real project folder:

```powershell
$demo = "C:\Temp\reefiki-dashboard-demo"
reefiki ops-dashboard demo --fixture-root $demo
reefiki ops-dashboard --workspace-root $demo --format json
reefiki ops-dashboard serve --workspace-root $demo --port 7310
```

Then open:

```text
http://127.0.0.1:7310/
```

Expected visible elements:

- `Codex Workspace Ops Board` heading;
- `First run` strip;
- `Current Work` lane;
- project inventory;
- Recent activity panel;
- Project details panel;
- REEFIKI Control panel;
- language and theme controls.

## Safety Boundary

The dashboard is a local read-only viewer:

- binds only to `127.0.0.1`;
- discovers only one-level git repositories under the explicit `--workspace-root`;
- synthetic demo workspaces contain `.reefiki-dashboard-demo`, `DemoApp` and `AgentTask` only;
- synthetic demo activity does not include live REEFIKI wiki log headings;
- does not run package scripts in target projects;
- does not run git fetch, pull, push, publish, apply or cleanup in target projects;
- skips secret-like paths, `.git/objects`, `_wiki/`, `raw/`, `node_modules`, `dist`, `build`, `.next` and `target`;
- uses synthetic demo data for public proof.

Not included in this demo:

- hosted/cloud dashboard;
- remote project mutation;
- publish/apply buttons;
- account system;
- managed sync backend;
- marketplace submission.

## Verification

Minimal non-browser smoke:

```powershell
reefiki ops-dashboard --workspace-root $demo --format json
python -m pytest tests\test_reefiki_core_ops_dashboard.py
```

Browser smoke:

1. Start `reefiki ops-dashboard serve --workspace-root $demo --port 7310`.
2. Open `http://127.0.0.1:7310/`.
3. Confirm the page is nonblank and the expected panels are visible.
4. Open `http://127.0.0.1:7310/api/snapshot` and confirm it returns `ops-dashboard.v2` JSON.

Do not commit screenshots or traces unless a later release pack explicitly needs them.
