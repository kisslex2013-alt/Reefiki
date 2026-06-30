# Монетизация REEFIKI skills

Этот документ развивает продуктовую гипотезу из `SKILL_PRODUCTS.md`: монетизировать не сами markdown skills, а установку безопасного agent workflow в реальные репозитории.

## Главная гипотеза

Пользователь платит не за "skill-файл". Пользователь платит за снижение риска:

- агент не ломает git history;
- агент не пушит приватное в public;
- агент не коммитит чужую грязь;
- агент не теряет проектный контекст;
- агент не объявляет задачу готовой без проверки;
- команда получает повторяемый процесс работы с AI coding agents.

Короткая формула:

> Сделать репозиторий безопасным для AI coding agents.

## Целевая аудитория

### 1. Solo founders с production repo

Боль:

- активно используют Codex, Claude Code, Cursor или похожих агентов;
- хотят давать агенту больше автономии;
- боятся, что агент случайно сломает проект.

Лучший оффер:

- Agent Safe Repo Pack;
- быстрая установка;
- одна сессия настройки.

### 2. Малые AI-native команды

Боль:

- несколько разработчиков и агентов работают параллельно;
- появляются stale branches, dirty worktrees, конфликтующие PR;
- нет единого правила, что агенту можно трогать.

Лучший оффер:

- Team Agent Workflow Pack;
- branch/worktree policy;
- integration-owner workflow;
- review/closeout стандарт.

### 3. Open-source и open-core проекты

Боль:

- есть private и public surfaces;
- есть риск утечки приватных project files;
- public docs надо обновлять без ручного хаоса.

Лучший оффер:

- Dual-Remote Publication Pack;
- public snapshot guard;
- private/public verification.

### 4. Agencies и AI consultants

Боль:

- много клиентских repo;
- нужен повторяемый setup;
- важно не тратить каждый раз время на базовые guardrails.

Лучший оффер:

- white-label Agent Ops Pack;
- repo adaptation checklist;
- training по установке.

### 5. Research-heavy builders

Боль:

- много решений и источников;
- агент забывает контекст;
- знания остаются в чатах.

Лучший оффер:

- Durable Knowledge Pack;
- `reefiki-experience-monitor`;
- harvest/decision/synthesis rules.

## Лестница офферов

### Free: публичный базовый слой

Цена: $0.

Состав:

- базовые markdown skills;
- `AGENTS.md` template;
- `AI_AGENT_REPO_SAFETY_CHECKLIST.md`;
- demo failure cases;
- короткие статьи и examples.

Цель:

- доверие;
- adoption;
- SEO;
- вход в paid audits.

### Starter: Agent Safe Repo Pack

Цена: $29-$99.

Состав:

- installable pack;
- `safe-task-worktree-bootstrap`;
- `staged-scope-and-publish-guard`;
- `source-of-truth-diagnostics`;
- `durable-harvest-closeout`;
- `.codex/hooks.json` example;
- setup guide;
- verification checklist.

Формат:

- Gumroad, Lemon Squeezy, GitHub Sponsors или private repo access;
- без кастомной поддержки;
- optional paid setup call.

### Audit: AI Agent Repo Safety Audit

Цена: $300-$700.

Что делается:

- read-only repo review;
- поиск agent failure modes;
- анализ dirty-tree, publish, private/public, CI, docs и source-of-truth risks;
- краткий prioritised report.

Deliverable:

- `AGENT_SAFETY_AUDIT.md`;
- список P0/P1 fixes;
- рекомендации skills/hooks;
- опционально patch branch.

Это самый простой первый paid service, потому что не требует сразу продавать большой implementation.

### Pro: Agent-Safe Repo Setup

Цена: $1k-$3k.

Что внедряется:

- custom `AGENTS.md`;
- repo-specific skills;
- worktree policy;
- staged path guard;
- publish/PR preflight;
- source-of-truth diagnostics;
- verification gates;
- closeout/handoff docs.

Deliverable:

- рабочий branch/PR;
- verification report;
- короткое обучение владельца repo.

### Team: Multi-Agent Workflow Setup

Цена: $3k-$10k.

Что добавляется:

- multi-agent branch ownership;
- integration owner rules;
- conflict resolution policy;
- PR/review lanes;
- CI enforcement;
- release readiness gates;
- team training.

Deliverable:

- team operating manual;
- configured repo;
- review workflow;
- pilot run с 1-2 задачами.

### Retainer: Agent Ops Maintenance

Цена: $500-$3k/month.

Что входит:

- обновление skills;
- разбор agent incidents;
- поддержка новых repo gates;
- monthly workflow review;
- адаптация под изменения Codex/Claude/Cursor;
- помощь при onboarding новых проектов.

Этот уровень важен, если рынок начнёт быстро менять runtimes и conventions.

## Упаковка лендинга

### Заголовок

> Make your repo safe for AI coding agents.

Альтернативы:

- Stop AI agents from committing the wrong files.
- Turn Codex/Claude/Cursor into safe repo operators.
- Guardrails, memory, and publish gates for AI coding agents.

### Первый экран

Проблема:

- AI coding agents are powerful, but most repos are not agent-safe.
- They lose context, stage unrelated files, miss source-of-truth docs, and can push private content.

Решение:

- REEFIKI Agent Ops Pack installs repo-specific skills, worktree rules, publish gates, and durable memory workflows.

CTA:

- Book a repo safety audit.
- Download the free checklist.
- Install the starter pack.

## Demo strategy

Нужен demo repo с тремя поломками:

1. Dirty checkout: агент пытается работать в shared tree с чужими файлами.
2. Broad staging: агент делает `git add -A` и захватывает лишнее.
3. Stale context: агент отвечает без чтения source-of-truth docs.

Потом показывается REEFIKI pack:

- создаёт clean worktree;
- блокирует broad staging;
- требует publish dry-run;
- читает project memory;
- выдаёт closeout report.

Demo должен быть коротким и визуальным: до/после, без долгой теории.

## Каналы продаж

### 1. Devtools content

Темы:

- "Your repo is not ready for AI agents";
- "Why AI agents break git workflows";
- "How to make Codex safe in a real repo";
- "The missing operating model for AI coding agents";
- "Worktree discipline for multi-agent development".

### 2. GitHub examples

Публичные templates:

- minimal `AGENTS.md`;
- staged guard example;
- safe publish checklist;
- demo repo.

### 3. Direct outreach

Кому писать:

- founders, которые публично используют Cursor/Codex;
- open-source maintainers с private/public split;
- agencies, которые продают AI development;
- small teams с большим количеством AI-generated PR.

Сообщение:

> Я проверяю repo на риски AI coding agents: dirty commits, private leaks, stale context, unsafe publish. Могу бесплатно показать 2-3 риска по вашему public repo.

### 4. Marketplace later

Не начинать с marketplace. Сначала доказать paid consulting/pilot. Marketplace имеет смысл только после повторяемого pack.

## Pricing logic

Цена должна зависеть не от количества markdown-файлов, а от риска:

- один solo repo: низкий чек;
- production repo с deploy: средний чек;
- team workflow: высокий чек;
- private/public/compliance: custom.

Пример:

| Сценарий | Цена |
|---|---:|
| Starter pack без поддержки | $49 |
| Repo safety audit | $500 |
| Setup для одного repo | $1,500 |
| Multi-agent team setup | $5,000 |
| Monthly maintenance | $1,000/month |

## Что проверять в pilot

Первые 3-5 клиентов должны дать ответы:

- Понимают ли они боль "agent-safe repo" без объяснений?
- Что им важнее: git safety, context memory, private/public или team workflow?
- Готовы ли платить за audit отдельно от implementation?
- Какие агенты они реально используют?
- Нужны ли им Codex-specific skills или agent-agnostic markdown?
- Достаточно ли plain markdown, или нужен installer?

## Главные риски

### Рынок не ищет "skills"

Решение: продавать не skills, а repo safety / agent ops.

### Слишком много кастомной работы

Решение: начинать с audit checklist и reusable base pack.

### Быстро меняются agent runtimes

Решение: держать base layer в markdown, а runtime-specific adapters делать тонкими.

### Пользователь боится давать доступ к private repo

Решение: предлагать read-only audit, sanitized report, local-run checklist.

### Сложно доказать ценность до инцидента

Решение: demo с намеренно сломанными scenarios и quick risk scan по repo.

## Что делать дальше

1. Создать бесплатный `AI_AGENT_REPO_SAFETY_CHECKLIST.md`.
2. Собрать demo repo с тремя failure modes.
3. Упаковать `agent-safe-repo-pack`.
4. Провести 3 pilot audits.
5. После pilots обновить pricing и landing copy.
6. Только потом думать про marketplace или платный каталог skills.

## Рабочая формулировка оффера

> I make your repository safe for AI coding agents: clean worktrees, scoped staging, source-of-truth checks, publish preflights, and durable memory capture.

Русская версия:

> Я настраиваю репозиторий так, чтобы AI-агенты могли работать безопасно: без чужих файлов в коммитах, без приватных утечек, без потери контекста и без publish вслепую.
