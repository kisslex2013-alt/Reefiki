---
id: public-release-verification
type: skill
title: "Public release verification"
abstract: "Run a repeatable public release confidence path before publishing changes that affect CI, packaging, secret scan, or public snapshot filters."
tags: [public, release, verification, ci]
useful_when:
  - "running the public release confidence path after changing packaging, CI, or snapshot filters"
verified: 2026-06-29
date_added: 2026-06-29
use_count: 0
last_used: null
---

## When To Apply

Use this after changing public packaging, CI, demo data, secret scanning, public
snapshot exclusions, or dual-remote publish behavior.

## Steps

1. Run targeted tests for the changed release surface.
2. Run the full private test suite.
3. Inspect the public snapshot in dry-run mode and confirm private projects are
   absent.
4. In a temporary public snapshot checkout, run install, CLI help, tests, memory
   golden, doctor, and review queue checks against `reefiki-demo`.
5. Publish only through the guarded private-first publish flow.

## Verified

2026-06-29 - Added as the public demo release gate for the P0 public hardening
batch.

## Pitfalls

- A passing private project golden baseline is not a public packaging proof.
- Snapshot exclusions must remove generated cache files as well as private docs.
- A demo project is safe only while it contains public-safe content.

## Related

[[public-first-run-flow]] - defines the user-facing first-run proof.
[[public-private-snapshot-boundary]] - defines which project data may reach the public remote.
