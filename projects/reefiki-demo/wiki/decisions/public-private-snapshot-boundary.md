---
id: public-private-snapshot-boundary
type: decision
title: "Public/private snapshot boundary"
abstract: "Private project folders are filtered from the public remote; the public demo project is explicitly allowed so CI and first-run checks have safe data."
tags: [public, snapshot, privacy, release]
useful_when:
  - "explaining why the public repository contains a demo project while private projects stay filtered out"
sources: [scripts/public-snapshot.private-projects.txt, scripts/public-snapshot.public-projects.txt, scripts/public-snapshot.exclude.txt]
date_added: 2026-06-29
use_count: 0
last_used: null
---

## Context

REEFIKI is developed in a private source repository but published as a filtered
public snapshot. Public users need runnable examples, while private project
folders must never leak into the public remote.

## Options

1. Keep all real projects private and leave the public repository without a wiki
   project. This protects privacy but makes CI and first-run checks shallow.
2. Publish one reviewed demo project and keep every other real project listed as
   private. This gives the public repository safe data without exposing private
   work.

## Decision

Use a small explicit public allowlist for `reefiki-demo`. Keep private projects
in the private-project inventory and fail closed when a real project is neither
private nor public.

## Consequences

Public CI can run wiki and memory checks on safe demo data. Adding any new real
project now requires a classification decision before a public snapshot can
pass.

## Related

[[public-first-run-flow]] - uses the public demo as the first runnable project.
[[public-release-verification]] - verifies the boundary before publish.
