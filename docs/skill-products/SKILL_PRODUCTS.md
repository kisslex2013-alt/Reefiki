# Продуктовые skill-пакеты REEFIKI

Этот документ фиксирует, какие REEFIKI skills должны входить в базовый markdown-native слой, а какие стоит держать опциональными или превращать в кастомные платные пакеты.

Продукт — не "папка промптов". Продукт — безопасный операционный слой для AI-агентов в реальном репозитории: повторяемые workflows, проверки source of truth, scoped git-поведение, verification gates и durable memory capture.

## Позиционирование

REEFIKI skills нужно продавать через результат:

- агент не теряет контекст проекта;
- агент не коммитит чужие или несвязанные файлы;
- агент не пушит приватный контент в публичный remote;
- агент не повторяет уже принятые решения;
- команда получает предсказуемый handoff, closeout и recovery flow.

Не стоит позиционировать это как "кастомные промпты". Промпты легко скопировать. Проверенный workflow с gates, тестами, repo-specific boundaries и операционной документацией заменить сложнее.

## Базовые skills

Базовые skills входят в default REEFIKI operating layer. Они должны быть полезны почти каждому пользователю REEFIKI, оставаться маленькими, проверяемыми и без тяжёлых зависимостей.

| Skill | Назначение | Почему в базе |
|---|---|---|
| `source-of-truth-diagnostics` | Проверять live config, файлы, логи, версии и доступные tools перед ответами на drift-prone вопросы. | Убирает уверенные, но устаревшие ответы. |
| `safe-task-worktree-bootstrap` | Запускать нетривиальные coding-задачи в изолированном `codex/*` worktree. | Защищает от dirty checkout damage и конфликтов параллельных агентов. |
| `staged-scope-and-publish-guard` | Требовать explicit staging, project scope и publish preflight. | Защищает git history и private/public boundaries. |
| `reefiki-experience-monitor` | Перед нетривиальной работой читать релевантные decisions, skills, concepts, synthesis и logs из wiki. | Делает REEFIKI активной durable memory, а не пассивным архивом. |
| `durable-harvest-closeout` | Переводить важные итоги сессии в wiki/log/ADR artifacts. | Не даёт ценным решениям остаться только в чате. |
| `verification-before-completion` | Требовать свежие доказательства перед статусом "готово". | Снижает false-complete отчёты. |
| `browser-runtime-smoke-gate` | Проверять browser-visible изменения в реальном браузере. | Достаточно частый сценарий для modern projects, но включается только по типу задачи. |

Базовые skills лучше держать в plain markdown. Сила REEFIKI в том, что любой совместимый coding agent может прочитать и применить эти правила без proprietary runtime.

## Опциональные бесплатные расширения

Опциональные skills полезны широко, но не должны быть mandatory gates для каждого проекта. Их стоит включать только по форме проекта или конкретному риску.

| Skill | Триггер | Комментарий |
|---|---|---|
| `codegraph-navigation` | Средний/большой codebase, auth/API/shared logic edits, impact analysis. | Disposable navigation layer, не durable memory. |
| `graphify-map-refresh` | Большой незнакомый repo или существенные архитектурные изменения. | Даёт structure map, но не становится четвёртым memory layer. |
| `release-readiness-gates` | Release, deploy, public handoff, package publish. | Более строгий checklist, чем обычный completion gate. |
| `security-best-practices` | Auth, secrets, sandboxing, user data, remote execution. | Включать по risk trigger, не always-on. |
| `legacy-migration-audit` | Data/schema migration с риском потери данных. | Специализированный, но переиспользуемый workflow. |
| `benchmark-optimization-loop` | Performance, cost, latency, throughput improvements. | Требует baseline, metric и budget. |

Эти skills могут оставаться open-source examples или community packs. Они помогают adoption, но не заставляют пользователя покупать кастомизацию слишком рано.

## Платные и кастомные skill-пакеты

Платные skills должны быть привязаны к конкретному repo, команде или бизнес-процессу. Ценность не в тексте skill, а в том, что workflow подогнан под реальные failure modes и проверен на этом проекте.

### 1. Repo Safety Pack

Для команд, которые используют AI-агентов в существующих репозиториях.

Состав:

- кастомный `AGENTS.md`;
- task worktree policy;
- staged path guard;
- publish/PR preflight;
- private/public leak rules;
- repo-specific "do not touch" paths;
- verification checklist и smoke commands.

Лучше всего подходит командам, где несколько разработчиков или агентов работают в одном repo.

### 2. Durable Knowledge Pack

Для пользователей, которые хотят использовать REEFIKI как долгосрочную проектную память.

Состав:

- project-specific `reefiki-experience-monitor`;
- domain-specific harvest rules;
- шаблоны decisions/concepts/skills;
- wiki health gates;
- stale/duplicate/conflict review queues;
- handoff pack command docs.

Лучше всего подходит solo builders, research-heavy projects и долгим продуктовым проектам.

### 3. Dual-Remote Publication Pack

Для репозиториев, где есть private source и public-safe snapshot.

Состав:

- private project inventory;
- public snapshot exclusions;
- dry-run/apply workflow;
- secret/content scan gates;
- cleanup rules;
- public/private verification script;
- документация "что никогда не попадает в public".

Лучше всего подходит open-core проектам, personal wiki и клиентским проектам с разделением private/public docs.

### 4. Team Agent Workflow Pack

Для команд, которые координируют несколько AI-агентов.

Состав:

- branch/worktree naming policy;
- integration-owner rules;
- conflict ownership rules;
- review lanes;
- closeout report format;
- PR description template;
- CI verification map.

Лучше всего подходит small teams, которые внедряют Codex, Claude Code или Cursor agents параллельно.

### 5. Domain-Specific Operator Pack

Для конкретного бизнес-домена.

Примеры:

- SaaS support operations pack;
- security-review pack;
- data-migration pack;
- release-manager pack;
- content/localization pack;
- product-research distillation pack.

Лучше всего подходит для paid consulting: generic templates здесь недостаточно. У каждого домена свои source-of-truth surfaces, risk gates и evidence requirements.

## Продуктовая лестница

| Уровень | Оффер | Цена | Deliverable |
|---|---|---|---|
| Free | Базовые REEFIKI skills | $0 | Markdown skills и templates. |
| Starter | Agent-safe repo pack | Низкий one-time | Installable pack + setup guide. |
| Pro | Custom repo workflow | Средний one-time | Repo audit, custom skills, hooks, verification commands. |
| Team | Multi-agent operating model | Высокий one-time или retainer | Policies, CI gates, training, integration workflow. |
| Enterprise | Regulated/private workflows | Custom | Security review, private/public separation, compliance evidence. |

## Что не стоит делать платным

Не нужно прятать за paywall:

- базовые идеи worktree safety;
- source-of-truth diagnostics pattern;
- правило publish dry-run first;
- базовый durable harvest rule;
- простые markdown templates.

Это должно оставаться бесплатным, потому что создаёт доверие, adoption и общий словарь. Платная ценность начинается там, где workflow адаптирован под реальный repo и проверен против его рисков.

## MVP-пакет

Первый публичный продукт должен быть маленьким:

`agent-safe-repo-pack`

Состав:

- `safe-task-worktree-bootstrap`;
- `staged-scope-and-publish-guard`;
- `source-of-truth-diagnostics`;
- `durable-harvest-closeout`;
- минимальный `AGENTS.md` template;
- пример `.codex/hooks.json`;
- before/after demo repository;
- verification checklist.

Критерии успеха:

- ставится в свежий repo меньше чем за 30 минут;
- блокирует broad staging и unsafe manual push в demo;
- создаёт понятный closeout report;
- не требует нового memory runtime;
- работает как markdown-инструкции, даже если конкретный agent runtime изменится.

## Roadmap

1. Стабилизировать базовый skill set внутри REEFIKI.
2. Упаковать `agent-safe-repo-pack` как публичный reference.
3. Сделать demo с тремя failure modes: dirty checkout, broad staging, stale source-of-truth answer.
4. Добавить платный repo adaptation checklist.
5. Провести один кастомный pilot на реальном внешнем repo.
6. Только после pilot evidence делать pricing и landing page.

## Открытые решения

- Поставлять packs как plain markdown, Codex skills, Claude skills или multi-agent bundles.
- Включать ли в paid packs поддержку/maintenance или только initial setup.
- Упоминать ли REEFIKI напрямую в публичных examples или использовать нейтральный бренд вроде "Agent Safe Repo Pack".
- Должны ли custom packs писать обратно в REEFIKI wiki по умолчанию или только после explicit harvest.
