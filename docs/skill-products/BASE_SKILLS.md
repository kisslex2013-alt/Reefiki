# Базовые skills REEFIKI

Базовые skills — это переносимые markdown-workflows, которые делают работу AI-агента в репозитории безопаснее и предсказуемее.

Они не заменяют агента и не требуют отдельного runtime. Агент читает skill как операционную инструкцию: когда его применять, какие источники проверить, какие файлы нельзя трогать, какие gates пройти и какой результат оставить.

## Зачем они нужны

Без базовых skills агент часто действует как "умный autocomplete":

- начинает работу в грязном shared checkout;
- отвечает по памяти вместо live source of truth;
- коммитит слишком широкий diff;
- забывает сохранить важное решение;
- объявляет задачу завершённой без свежей проверки;
- повторяет уже принятые решения, потому что не поднял project wiki.

Базовые skills превращают агента в repo operator: он сначала проверяет состояние, затем действует в правильном scope, затем оставляет доказуемый результат.

## Базовый набор

| Skill | Что делает | Когда включать |
|---|---|---|
| `source-of-truth-diagnostics` | Проверяет live config, docs, logs, versions и доступные tools. | Вопросы про config, MCP/plugins, model/runtime, версии, paths, health. |
| `safe-task-worktree-bootstrap` | Создаёт или выбирает чистый `codex/*` worktree для задачи. | Любая нетривиальная coding-задача, особенно при dirty shared checkout. |
| `staged-scope-and-publish-guard` | Проверяет staged paths, publish scope и запрет broad staging. | Commit, push, publish, harvest, multi-project repo. |
| `reefiki-experience-monitor` | Поднимает релевантные decisions, concepts, skills, synthesis и logs из REEFIKI wiki. | Перед нетривиальной работой в проекте с накопленной wiki. |
| `durable-harvest-closeout` | Переводит важные выводы сессии в durable artifacts. | После решения, повторяемого workflow, production fix, audit или исследования. |
| `verification-before-completion` | Требует свежую проверку перед статусом "готово". | Любая dev-задача, где важно реальное поведение. |
| `browser-runtime-smoke-gate` | Проверяет browser-visible изменения в реальном браузере. | Frontend, UI, forms, routes, browser games, local web apps. |

## Принцип portable-first

Базовый skill должен быть написан так, чтобы его мог применить любой агент:

- Codex;
- Claude Code;
- Cursor;
- Qwen/DeepSeek через совместимый CLI/IDE wrapper;
- Hermes;
- другой LLM-agent, который умеет читать markdown.

Поэтому core skill не должен зависеть от конкретного UI или plugin API. Runtime-specific часть выносится в adapter.

## Формат canonical skill

Рекомендуемый формат:

```md
# skill-name

## When to use

## Inputs

## Workflow

## Safety rules

## Verification

## Outputs

## Adapter notes
```

Такой формат проще проверять, переносить и продавать как часть custom pack.

## Что не должно попадать в базу

Не нужно делать базовыми:

- узкие domain workflows;
- интеграции с конкретным SaaS;
- heavyweight memory/runtime слои;
- enterprise-only compliance;
- project-specific secrets/policies;
- экспериментальные tools без smoke evidence.

Они должны жить в optional или paid packs.

## Критерий включения в базу

Skill можно включать в базовый слой, если он:

1. нужен в большинстве coding repos;
2. снижает высокий риск;
3. не требует нового runtime;
4. работает как plain markdown;
5. имеет понятный verification gate;
6. не дублирует уже существующий REEFIKI/memoir/graphify слой.
