# README block: Agent Readiness

Этот файл сохраняет README-блок Agent Readiness как reference/source для синхронизации `README.md`, `README.en.md` и `README.zh-CN.md`.

Статус: блок применён в корневых README после read-only MVP proof 2026-06-10.

Scope remains read-only: this block must not imply auto-install, target repo mutation, marketplace packaging, paid gating, live hooks/adapters, or global runtime config changes.

Note: links in this reference file are local to `docs/skill-products/`; root README files keep `docs/skill-products/...` paths.

## RU

````md
## Agent Readiness

REEFIKI может анализировать git-репозиторий и предлагать, какие skills, rules, adapters и hooks нужны, чтобы AI-агенты работали безопасно именно в этом проекте.

Пример:

```powershell
python scripts\reefiki.py agent-readiness --repo D:\Projects\MyApp
```

Результат — Agent Readiness Plan:

- какие базовые skills подключить;
- какие repo rules добавить;
- какие adapters нужны для Codex, Claude Code, Cursor, Qwen, DeepSeek, Hermes;
- какие hooks стоит включить для deterministic safety;
- какие custom skills стоит создать под конкретный repo.

MVP работает read-only: REEFIKI сначала объясняет риски и рекомендации, а не меняет проект автоматически.

Подробнее: [Agent Readiness spec](AGENT_READINESS_SPEC.md).
````

## EN

````md
## Agent Readiness

REEFIKI can analyze a git repository and recommend which skills, rules, adapters, and hooks are needed for AI agents to work safely in that specific project.

Example:

```powershell
python scripts\reefiki.py agent-readiness --repo D:\Projects\MyApp
```

The result is an Agent Readiness Plan:

- which base skills to enable;
- which repo rules to add;
- which adapters are useful for Codex, Claude Code, Cursor, Qwen, DeepSeek, Hermes;
- which hooks should enforce deterministic safety;
- which custom skills should be drafted for this repo.

The MVP is read-only: REEFIKI explains risks and recommendations before it changes anything.

Read more: [Agent Readiness spec](AGENT_READINESS_SPEC.md).
````

## ZH-CN

````md
## Agent Readiness

REEFIKI 可以分析一个 git 仓库，并推荐这个项目需要哪些 skills、rules、adapters 和 hooks，才能让 AI Agent 安全地工作。

示例：

```powershell
python scripts\reefiki.py agent-readiness --repo D:\Projects\MyApp
```

输出结果是 Agent Readiness Plan：

- 需要启用哪些基础 skills；
- 需要添加哪些 repo rules；
- Codex、Claude Code、Cursor、Qwen、DeepSeek、Hermes 需要哪些 adapters；
- 哪些 hooks 应该负责 deterministic safety；
- 哪些 custom skills 值得为这个 repo 创建 draft。

MVP 是 read-only：REEFIKI 会先解释风险和建议，不会自动修改项目。

更多信息：[Agent Readiness spec](AGENT_READINESS_SPEC.md)。
````
