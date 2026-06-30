# Agent adapters для REEFIKI skills

REEFIKI skills должны быть portable-first: core workflow живёт в markdown, а agent-specific подключение делается тонкими adapters.

Цель: один и тот же базовый skill должен быть применим в Codex, Claude Code, Cursor, Qwen, DeepSeek, Hermes и будущих agents без переписывания всей логики.

## Архитектура

```text
canonical markdown skill
        ↓
thin adapter for agent/runtime
        ↓
optional hooks / commands / rules
```

Core skill отвечает за смысл:

- когда применять;
- какие источники читать;
- какие границы соблюдать;
- какие проверки запускать;
- какой результат оставить.

Adapter отвечает только за подключение:

- куда положить файл;
- как агент его обнаруживает;
- как включить hooks;
- какие runtime-specific команды доступны.

## Матрица совместимости

| Agent / IDE | Основной способ подключения | Что адаптировать |
|---|---|---|
| Codex | `AGENTS.md`, local skills, `.codex/hooks.json` | Hooks, worktree policy, publish gates, tool-specific wording. |
| Claude Code | `CLAUDE.md`, `.claude/commands`, markdown skills | Slash-command docs, project instructions, closeout workflow. |
| Cursor | `.cursorrules`, `.cursor/rules/*.mdc`, repo docs | Rules format, file glob scopes, lightweight prompts. |
| Qwen / DeepSeek wrappers | `AGENTS.md`, repo docs, CLI prompt files | Generic markdown contract, minimal assumptions about tools. |
| Hermes | Runtime prompt, tool policy, REEFIKI wiki bridge | Operator rules, memory bridge, safe tool boundaries. |
| Generic agents | `AGENTS.md` + `skills/base/*/SKILL.md` | Human-readable workflow and explicit verification steps. |

## Рекомендуемая структура

```text
skills/
  base/
    safe-task-worktree-bootstrap/SKILL.md
    source-of-truth-diagnostics/SKILL.md
    staged-scope-and-publish-guard/SKILL.md
    reefiki-experience-monitor/SKILL.md
    durable-harvest-closeout/SKILL.md

adapters/
  codex/
    hooks.json
    install.md
  claude-code/
    commands.md
    install.md
  cursor/
    rules.mdc
    install.md
  generic-agents/
    AGENTS.md.fragment
  hermes/
    runtime-prompt.md
    install.md
```

## Правила для adapters

1. Adapter не должен менять смысл skill.
2. Adapter не должен добавлять новую durable memory layer.
3. Adapter не должен требовать глобального runtime install без отдельного proof gate.
4. Adapter должен быть минимальным и удаляемым.
5. Adapter должен явно описывать, какие команды или hooks он включает.

## Что делать первым

Минимальный MVP:

1. Описать canonical base skills в `skills/base/`.
2. Сделать `adapters/generic-agents/AGENTS.md.fragment`.
3. Сделать Codex adapter: `.codex/hooks.json` + install guide.
4. Сделать Claude Code adapter: `.claude/commands` mapping.
5. Сделать Cursor adapter: `.cursor/rules` mapping.
6. Проверить всё на demo repo с dirty checkout, broad staging и stale context answer.

## Маркетинговая формулировка

> REEFIKI skills are portable agent workflows: write once in markdown, adapt to Codex, Claude Code, Cursor, Qwen, DeepSeek, Hermes, and future agents.

Русская версия:

> REEFIKI skills — это переносимые workflows для AI-агентов: один раз описываются в markdown и подключаются к Codex, Claude Code, Cursor, Qwen, DeepSeek, Hermes и будущим агентам через тонкие adapters.
