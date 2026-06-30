# REEFIKI Public Demo

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Это публичная demo-поверхность REEFIKI. Её можно публиковать, потому что она описывает продуктовый flow, CLI-проверки и public docs без копирования приватных wiki-проектов.

Короткий сценарий demo:

1. Установить CLI или открыть checkout fallback.
2. Создать первый workspace через `reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run`.
3. Проверить `doctor` и `status` на созданном проекте.
4. Опционально запустить onboarding/dashboard demo.
5. После демо подключить настоящий проект через явный bridge или создать новую wiki.

Подробная canonical-страница ниже на английском.

## English

This is the static public demo surface for REEFIKI. It is safe to publish because it describes the product flow, CLI checks, and public docs without copying private wiki projects.

## 中文

这是 REEFIKI 的公开 demo 页面。它可以安全发布，因为它只描述产品流程、CLI 检查和公开文档，不复制私有 wiki 项目。

简短 demo 流程：

1. 安装 CLI，或使用 checkout fallback。
2. 运行 `reefiki init --workspace /tmp/reefiki-workspace --project-name first-run`。
3. 对新项目运行 `doctor` 和 `status`。
4. 可选：运行 onboarding/dashboard demo。
5. 之后再连接真实代码项目，或创建新的 wiki。

下面继续保留英文 canonical 页面。

## What REEFIKI Shows

REEFIKI is a local-first memory control plane for AI agents. It keeps useful knowledge in markdown, rejects low-value archive noise and gives the next agent a bounded context pack.

The demo story has five steps:

1. Install the CLI or use the checkout fallback.
2. Create the first workspace with `reefiki init --workspace <path> --project-name first-run`.
3. Run `doctor` and `status` on the initialized project.
4. Optionally create the synthetic dashboard workspace and open the local Ops Board.
5. After the demo, connect a real project with an explicit bridge or create a new wiki.

## Try The Local Demo

The init command creates a minimal real workspace from built-in templates:

```powershell
reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run status
reefiki ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
reefiki ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

POSIX:

```bash
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run status
reefiki ops-dashboard demo --fixture-root /tmp/reefiki-dashboard-demo
reefiki ops-dashboard serve --workspace-root /tmp/reefiki-dashboard-demo --port 7310
```

For checkout development, the same init-first flow works without a global install:

```powershell
python scripts\reefiki.py init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
python scripts\reefiki.py --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
python scripts\reefiki.py --project C:\Temp\reefiki-workspace\projects\first-run status
python scripts\reefiki.py ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo --format json
python scripts\reefiki.py ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

The public repository also includes a small built-in demo wiki project. It is
safe for CI and release checks because it contains only public-safe pages:

```powershell
python scripts\reefiki.py memory golden --project reefiki-demo --format json
python scripts\reefiki.py --project projects\reefiki-demo doctor --format json
python scripts\reefiki.py --project projects\reefiki-demo review-queues --summary --format json
```

The initialized workspace is local to the supplied temp folder. The dashboard fixture creates only synthetic git repositories under its own temp folder and marks the workspace as demo-only, so the activity feed does not include live REEFIKI wiki log headings.

## Public-Safe Capabilities

| Capability | Public demo proof | Boundary |
|---|---|---|
| Daily wiki cycle | `reefiki init --workspace` creates a valid local project | No private `projects/*` export |
| Retrieval quality | documented memory checks track stable lookup expectations | No vector or hybrid search runtime |
| Handoff context | bounded context packs keep the next session focused | No new storage layer |
| Read-only dashboard | `dashboard` and `ops-dashboard` summarize local state | No remote mutation or cloud dashboard |

## Safe Links

- [Quickstart](../QUICKSTART.md)
- [Command reference](../COMMANDS.md)
- [Recovery guide](RECOVERY.md)
- [Public roadmap](PUBLIC_ROADMAP.md)
- [Public backlog](PUBLIC_BACKLOG.md)

## Private Boundary

The public snapshot excludes private wiki projects and working reports. This demo must not embed private wiki pages, raw sources, inbox items, seen records, local usernames, tokens or unpublished project notes.

Allowed public material:

- root docs and command references;
- generated screenshots or fixture outputs that contain only demo data;
- CLI examples using placeholder paths such as `C:\Temp\reefiki-workspace` or `/tmp/reefiki-workspace`;
- product claims already backed by public docs and tests.

Not allowed:

- `projects/reefiki/wiki/**` content copied into public docs;
- private project names used as examples beyond the documented boundary list;
- managed sync backend, hosted dashboard, marketplace submission, MCP server or vector search claims;
- real local paths from someone's machine as demo evidence.

## Demo Page Checklist

When this page changes, check the public-facing story:

- links resolve inside the public repository;
- no private wiki content is copied into the demo;
- feature claims match current `README.md`, `COMMANDS.md`, `docs/PUBLIC_BACKLOG.md` and `docs/PUBLIC_ROADMAP.md`;
- future items remain labelled as future work, not implemented features.

Repository publication checks are separate from the local demo and are not required to try it.
