---
id: public-first-run-flow
type: concept
title: "Public first-run flow"
abstract: "A fresh public REEFIKI clone should install, show the CLI help, run tests, and query the public demo project without private data."
tags: [public, onboarding, install, demo]
useful_when:
  - "checking that a fresh public clone can run a meaningful REEFIKI demo without private project data"
sources: [README.md, docs/INSTALL.md, docs/PUBLIC_DEMO.md]
date_added: 2026-06-29
use_count: 0
last_used: null
---

## Essence

The public first-run path is a small proof that REEFIKI works after clone and
install. It should not depend on private projects such as the operator's core
wiki or product wikis. The proof uses this demo project as the safe knowledge
surface.

## Delta

This page defines the public user path as a repository behavior, not as a local
operator shortcut. The expected route is: install the package, run the CLI help,
run the tests, then query and inspect `projects/reefiki-demo`.

## Application

Use this page when changing CI, packaging, docs, or public snapshot filters. If
the public first-run path needs a private project to pass, the public packaging
is not self-contained.

## Related

[[public-private-snapshot-boundary]] - explains why the public demo exists in the snapshot.
[[public-release-verification]] - turns this flow into a repeatable release check.
