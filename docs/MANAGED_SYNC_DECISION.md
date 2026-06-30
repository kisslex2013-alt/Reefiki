# Managed Sync Decision

Status: decision/spec, no implementation.

REEFIKI should keep the current local-first git sync model as the default and postpone any managed sync backend until product demand proves that private, encrypted, multi-device or team sync is worth the extra operational risk.

## Decision

Current default:

- private `origin` remains the complete source of truth;
- public `public` remains a filtered snapshot for safe public docs and infrastructure;
- `publish-task --dry-run --cleanup --format json` remains the required preflight before publication;
- `publish-task --apply --cleanup --format json` remains the canonical apply path.

Future managed sync is allowed only as a separate gated product slice. It must start with encrypted private sync and threat-model proof, not a hosted database or account system.

## Options

| Option | Use now | Why |
|---|---:|---|
| Local-first git sync | Yes | Already works, keeps markdown as source of truth, has rollback through git history and requires no backend. |
| Filtered public snapshot | Yes | Already implemented for public docs, removes private projects and scans public payloads before push. |
| Encrypted private sync | Later | Potentially useful for multi-device or backup, but needs key management, restore proof and leak testing. |
| Managed service backend | No | Adds accounts, hosting, data custody, incident response and privacy obligations before demand is proven. |

## Threat Model

Primary risks:

- private project content leaks into public docs or snapshots;
- sync conflict overwrites `wiki/log.md` or durable pages;
- a background daemon commits or publishes without operator intent;
- hosted storage becomes a new secret/data custody surface;
- rollback is unclear after a bad sync.

Required controls before encrypted/private sync:

- end-to-end encryption design with documented key ownership;
- append-only log conflict handling;
- raw archive immutability preservation;
- explicit project allowlist;
- dry-run diff before apply;
- restore drill from an isolated temp clone;
- public/private content scan before any outward publication.

## Private Boundary

Managed sync must not weaken the current project isolation model:

- private project folders stay private by default;
- public snapshot exclusions remain fail-closed;
- durable writes still target one explicit project;
- cross-project synthesis remains read-only until a target project is selected;
- no background sync may write `raw/` or rewrite existing `wiki/log.md` entries.

## Rollback

Rollback must be possible without a provider:

1. Stop the sync process.
2. Clone or restore from private git `origin`.
3. Run `reefiki doctor`, `reefiki health` and `review-queues --summary`.
4. Compare affected markdown diffs.
5. Re-publish through `publish-task`, never with manual public push.

## First Safe Future Slice

If demand appears, the first implementation slice should be a no-network sync simulator:

- fixture project only;
- local encrypted bundle file;
- dry-run restore into a temp folder;
- conflict report for `wiki/log.md`, `wiki/index.md` and wiki pages;
- no daemon, account, server, hosted database or auto-apply.

Go/no-go criteria:

- two or more real user workflows need multi-device/private sync beyond git;
- restore drill passes from an isolated temp folder;
- public/private leak tests pass;
- conflict handling is deterministic and documented;
- operator can disable/remove the sync layer without losing markdown truth.

Until those criteria are met, managed sync remains documentation/spec only.
