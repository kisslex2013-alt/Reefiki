# Public Roadmap

## Русский

Это публичная карта развития REEFIKI. Она показывает продуктовые направления,
которые полезны внешнему пользователю: что уже стабильно, что улучшается сейчас
и что сознательно отложено. Рабочие журналы разработки, внутренние отчёты и
локальное состояние не входят в публичный snapshot.

### Стабильная база

- Local-first markdown wiki для AI-агентов.
- Изоляция проектов через `projects/<name>/`.
- Agent-agnostic правила через `AGENTS.md` и vendor-specific stubs.
- CLI: create/connect/status/health/query/harvest/memory.
- Безопасное разделение локального/private контента и публичных материалов.
- Public demo, install docs, tests, base skills and adapter docs.

### Ближайшие публичные направления

- Сделать first-run путь проще: install -> onboarding -> demo -> connect.
- Держать public repo продуктово чистым: без внутренних отчётов, local state и
  рабочих архивов.
- Улучшать проверяемость agent work: intent checks, source-of-truth diagnostics,
  browser/runtime smoke and durable closeout skills.
- Поддерживать portable agent surfaces без auto-install и без глобальной
  mutation чужих IDE/runtime конфигов.

### Отложено осознанно

- Managed cloud sync, accounts and hosted backend.
- Vector DB / graph runtime as default memory layer.
- Always-on daemon, cron capture and full transcript archive.
- Automatic skill copying across projects.
- Public export of private `projects/*` wiki content.

## English

This is the public-facing REEFIKI roadmap. It describes product directions that
matter to external users: what is stable, what is being polished, and what is
intentionally deferred. Development working logs, private reports, and local
state are not part of the public snapshot.

### Stable Base

- Local-first markdown wiki for AI agents.
- Project isolation through `projects/<name>/`.
- Agent-agnostic rules through `AGENTS.md` and vendor-specific stubs.
- CLI for create/connect/status/health/query/harvest/memory.
- Safe separation between local/private content and public material.
- Public demo, install docs, tests, base skills, and adapter docs.

### Near-Term Public Direction

- Make first run simpler: install -> onboarding -> demo -> connect.
- Keep the public repo product-clean: no private reports, local state, or
  working archives.
- Improve verifiable agent work: intent checks, source-of-truth diagnostics,
  browser/runtime smoke, and durable closeout skills.
- Support portable agent surfaces without auto-installing or mutating global
  IDE/runtime configuration.

### Intentionally Deferred

- Managed cloud sync, accounts, and hosted backend.
- Vector DB / graph runtime as the default memory layer.
- Always-on daemon, cron capture, and full transcript archive.
- Automatic skill copying across projects.
- Public export of private `projects/*` wiki content.

## 中文

这是 REEFIKI 的公开路线图。它只描述对外部用户有用的产品方向：哪些已经稳定，哪些正在打磨，哪些被有意推迟。开发工作日志、内部报告和本地状态不进入 public snapshot。

### 稳定基础

- 面向 AI agent 的 local-first markdown wiki。
- 通过 `projects/<name>/` 隔离项目。
- 通过 `AGENTS.md` 和各类 agent stub 提供 agent-agnostic 规则。
- CLI 覆盖 create/connect/status/health/query/harvest/memory。
- 安全地区分本地/private 内容和公开材料。
- 公开 demo、安装文档、测试、base skills 和 adapter docs。

### 近期公开方向

- 简化首次使用路径：install -> onboarding -> demo -> connect。
- 保持 public repo 产品化、干净：不包含内部报告、local state 或工作归档。
- 提升 agent work 的可验证性：intent checks、source-of-truth diagnostics、browser/runtime smoke 和 durable closeout skills。
- 支持可迁移的 agent surfaces，但不自动安装，也不修改全局 IDE/runtime 配置。

### 有意推迟

- Managed cloud sync、accounts 和 hosted backend。
- 默认启用 vector DB / graph runtime 作为记忆层。
- Always-on daemon、cron capture 和完整 transcript archive。
- 自动跨项目复制 skills。
- 公开导出 private `projects/*` wiki 内容。
