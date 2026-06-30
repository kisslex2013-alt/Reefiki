# AGENTS.md — REEFIKI (root contract)

## ⛔ Запреты (читай первым)

- **В корне нельзя:** `/save`, `/process`, `/query`, `/harvest` — только внутри `projects/<name>/`.
- Не создавай страницы в `projects/<name>/wiki/` из корневого режима.
- Не объединяй базы разных проектов без явной просьбы.
- Не модифицируй `raw/` ни в одном проекте — immutable архив.
- Не редактируй старые записи в `wiki/log.md` — только append.
- Не выходи за пределы папки проекта в рабочем режиме.

## 🗺 Режимы работы (читай вторым)

**cwd = корень REEFIKI/** → **диспетчерский режим.**
В начале сессии: найди папки в `projects/` (кроме `_template`), скажи:
> «У тебя есть проекты: [список]. Создать новый (`/new <имя>`) или перейти в существующий?»

Из корня доступны только:
1. `/new <имя>` — создать проект (`.claude/commands/new.md`).
2. `/connect <путь>` — подключить кодовый проект (`.claude/commands/connect.md`).
3. `/sync-template` — синхронизировать шаблон (`.claude/commands/sync-template.md`).
4. Cross-project search по `projects/*/wiki/index.md` — только чтение.
5. Аудит структуры: проверить наличие `raw/`, `wiki/index.md`, `wiki/log.md`, `AGENTS.md`, `_domain.md`.
6. Глобальный memory orchestration через `scripts/reefiki.py memory ...`:
   - `memory route` — выбрать слой (`memoir` / `REEFIKI` / `graphify`)
   - `memory lookup` — единый lookup по слоям
   - `memory promote` — dry-run promotion в конкретный REEFIKI project

**cwd = `projects/<name>/`** → **рабочий режим.**
Читай `projects/<name>/AGENTS.md` — там полный контракт. Этот файл больше не нужен.

---

Это **agent-agnostic контракт** для всего репозитория REEFIKI. Любой LLM-агент (Claude Code, Cascade/Windsurf, Cursor, Codex CLI, Aider, Cline, GPT в web, …) — читай этот файл как источник истины.

Vendor-specific entrypoints (`CLAUDE.md`, `.cursorrules`, `.windsurf/rules/main.md`, `.codex/instructions.md` и т.п.) — это короткие стабы, ссылающиеся сюда. Они нужны, чтобы соответствовать конвенциям конкретного агента, но **правила живут здесь и в `projects/<project>/AGENTS.md`**.

## Что это за репозиторий

REEFIKI — это **мульти-проектная персональная distillation-вики**. Пользователь складывает в неё источники (URL, файлы, репозитории, заметки) по разным темам, по одному проекту на тему. Агент (ты) читает источники, применяет фильтр из 4 внутренних вопросов и либо записывает wiki-страницу, либо отказывает с причиной (карантин 30 дней).

Цель — **не** пересказ тренировочных данных. Цель — зафиксировать то, что пользователь уже прочитал/решил, чтобы в следующей сессии можно было это поднять.

Дизайн опирается на:

- Karpathy, [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
- REEF protocol (capture / distillation / telemetry).
- Vannevar Bush, Memex (1945).

## Project profiles (manual onboarding labels)

Некоторые REEFIKI-проекты нужно вести по-разному. Это ручные labels для пользователя и агента, не обязательное поле схемы:

| profile | Когда использовать | Примеры |
|---|---|---|
| `reefiki_core` | REEFIKI protocol, memory control plane, governance, publish/worktree/process gates | `reefiki` |
| `agent_surface` | Agent/IDE/runtime окружение: rules, skills, adapters, diagnostics, provider routing, recovery procedures, eval evidence | Codex, Claude Code, Gemini, Mimo, Hermes |
| `product` | Пользовательский product/app project: delivery decisions, specs, release evidence, UX/product knowledge | Metrica |
| `knowledge_domain` | Предметная база знаний без основного runtime/control-plane слоя | Suno, Instagram, Security Guidance |

Для `agent_surface` сохраняй переносимые процедуры и проверенные runbooks, но не объединяй базы разных проектов и не копируй skills автоматически. `project_kind` не добавляется в `_domain.md`, schema, index, validators или CLI до отдельного решения. Триггер для automation: минимум 3 реальных manual transfer decisions, где profile помог принять решение. User-facing reference: `docs/PROJECT_PROFILES.md`.

## Структура репо

```text
REEFIKI/
├── AGENTS.md            # этот файл — корневой контракт
├── README.md            # для людей: первое знакомство
├── COMMANDS.md          # для людей: справочник команд
├── ROADMAP.md           # для людей: что подключать дальше
├── CLAUDE.md            # стаб → AGENTS.md (для Claude Code)
├── .cursorrules         # стаб → AGENTS.md (для Cursor)
├── .clinerules          # стаб → AGENTS.md (для Cline / Roo Cline)
├── .codex/instructions.md   # стаб → AGENTS.md (для Codex CLI)
├── .windsurf/rules/main.md  # стаб → AGENTS.md (для Cascade/Windsurf)
├── .serena/project.yml      # конфиг Serena (initial_prompt → AGENTS.md)
├── .claude/commands/
│   ├── new.md           # /new — создать новый проект
│   ├── connect.md       # /connect — подключить кодовый проект
│   └── sync-template.md # /sync-template — обновить проекты из шаблона
└── projects/
    ├── _template/       # эталон, не работаем здесь напрямую
    └── <name>/          # конкретный проект — основное место работы
```

## Операции на уровне проекта (краткий перечень)

Когда ты внутри проекта, ты поддерживаешь эти операции. Пользователь может вызывать их:

- как slash-команды (Claude CLI): `/save`, `/process`, `/query`, `/harvest`, `/status`, `/lint`, `/resolve`, `/reindex`, `/help`
- на естественном языке: «сохрани X», «разбери копилку», «спроси у вики Y», «зафиксируй выводы», «проверь здоровье вики», ...

Распознай интент и выполни операцию. **Каждая операция полностью специфицирована в `projects/<name>/.claude/commands/<op>.md`** — это обычные markdown-файлы, читаемые любым агентом. Имя папки `.claude/` сохранено для совместимости с Claude CLI; содержимое vendor-neutral.

| Операция | Что делает |
|---|---|
| `save` | Кладёт URL/файл в `inbox/`. Без анализа. |
| `process` | Разбирает `inbox/` → `wiki/` или `seen/`. |
| `query` | Отвечает на вопрос только из накопленного в `wiki/`. |
| `harvest` | Извлекает выводы из текущей сессии. |
| `status` | Read-only обзор состояния проекта. |
| `lint` | Проверяет здоровье вики (6 механических категорий). |
| `resolve` | Закрывает старые `## Conflicting claims` (≥30 дней). |
| `reindex` | Пересобирает `wiki/index.md` из frontmatter. Аварийная команда. |
| `help` | Plain-text справочник для пользователя. |

Подробности: `projects/<name>/.claude/commands/<op>.md` или `COMMANDS.md` в корне.

## Принципы (распространяются на все проекты)

1. **Дистилляция, не архивация.** Сохраняется не «что это», а «что я могу из этого взять».
2. **`useful_when` обязателен.** Конкретный сценарий применения, не «может пригодиться». Без него — отказ в `seen/`.
3. **Capture отдельно от analysis.** `/save` дешёвый, `/process` батчем.
4. **Явный отказ.** Не подходит — запись в `seen/` с `quarantine_until`, не overwrite.
5. **Конфликты не перезаписываются.** Секция `## Conflicting claims` в существующей странице.
6. **Логируется всё.** `wiki/log.md` append-only. Append идёт **до** `git commit`, чтобы лог попал в коммит.
7. **Изоляция проекта.** Не выходить за пределы папки проекта во время рабочего режима.
8. **Чистое удаление старого.** Если решение признано неудачным — убирать целиком, не оставлять хвосты, переходники, заглушки.
9. **Процедура > факт.** Сохраняй метод, который позволяет проверить и воспроизвести результат, а не одноразовый факт.

## Автономность агента

Агент не ждёт slash-команд. Он распознаёт интент пользователя из контекста и выполняет соответствующую операцию. Подробности в project-level `AGENTS.md`.

## Cross-project skill sharing

Skills (навыки) изолированы в проектах, но могут быть полезны везде. Из корневого режима (диспетчер) агент может:

- **Поиск skills по всем проектам:** пользователь спрашивает «есть ли навык про X?» → агент ищет в `projects/*/wiki/skills/` и `projects/*/wiki/index.md` (секция Skills).
- **Копирование skill в другой проект:** по явному запросу — скопировать файл, обновить index/log в целевом проекте.

Это единственное исключение из принципа изоляции: агент **читает** skills из других проектов, но не модифицирует их.

## Global Memory Layer

В корне REEFIKI действует единая внешняя оболочка над тремя контурами памяти:

- `memoir` — short working memory и preferences;
- `graphify` — structure map подключённого кодового repo;
- `REEFIKI` — durable knowledge, decisions, procedures, synthesis.

Правило: объединять **routing/lookup/promotion**, но не сливать сами хранилища в одну базу.

- `route` решает, куда должен попасть новый факт;
- `lookup` может читать сразу из нескольких слоёв;
- `promote` поднимает ценное из `memoir` в REEFIKI как typed durable artifact.

Ограничение: durable write в REEFIKI всегда идёт в **явно выбранный project**. Глобальный orchestration не отменяет project isolation.

### Cross-project harvest / push rule

Если агент работает из другого кодового проекта и пользователь явно просит `/harvest`, «зафиксируй», «сохрани выводы» или похожий durable write, push в REEFIKI допустим только для wiki-артефактов выбранного проекта: `projects/<name>/wiki/**`.

Обязательные условия:

- target project должен быть явно определён до записи;
- staged/committed paths должны быть ограничены этим `projects/<name>/wiki/**`;
- для cross-project harvest commit использовать `python scripts/reefiki.py harvest-commit --target-project <name> --path <file> ... --message "<msg>"`, чтобы коммит собирался через изолированный git index;
- если агент всё же stage-ит вручную, перед commit/push выполнить `python scripts/reefiki.py guard-staged --target-project <name>` и остановиться, если outcome не `pass`;
- unrelated dirty files, особенно в других `projects/*`, нельзя stage/commit/push;
- в финале агент обязан перечислить touched paths и отдельно excluded dirty files;
- если touched paths выходят за выбранный project-scope, остановиться и не пушить без явного подтверждения пользователя.

Dirty worktree вне выбранного `projects/<name>/wiki/**` сам по себе не блокирует `/harvest`; это excluded context. Блокер — только committed paths вне scope или конфликт в тех же target-файлах. Не использовать широкое staging всей рабочей копии и общий git index для cross-project harvest, потому что чужие staged-файлы из параллельных тредов могут попасть в commit.

### Dual-remote publish rule

Если пользователь просит «push», «пуш», «отправь на git», «запушь», «merge», «PR», «объедини ветку» или похожую публикацию REEFIKI-изменений, агент обязан использовать skill `reefiki-dual-remote-publish` и начать с:

```powershell
python scripts\reefiki.py publish-task --dry-run --cleanup --format json
```

Без этого нельзя делать ручной `git push`. REEFIKI имеет два remote:

- `origin` — private источник истины;
- `public` — только filtered orphan snapshot без приватных `projects/<name>/`.

Если dry-run показывает `private-only`, пушить только `origin`. Если `public-safe` или `mixed`, сначала обновить private `origin`, затем делать filtered public snapshot. Никогда не пушить private branch напрямую в `public`. После успешного publish удалить task worktree/branch только если worktree clean и commit уже reachable from `origin/main`; иначе оставить и явно объяснить почему.

### Parallel worktree lifecycle rule

REEFIKI следует глобальному правилу Codex App: одна задача = один `git worktree` = одна ветка `codex/*`, если пользователь или проект не задал другое. Это обязательный orchestration layer для всех агентов, а не рекомендация: правила живут в `AGENTS.md`, live inventory в `worktree-status`, owner/milestone registry в `plans/leadops/worktree-ledger.json`, publish gate в `publish-task`, cleanup gate в `cleanup-worktree`. Canonical bucket: `<WORKSPACE_ROOT>\_worktrees\REEFIKI-<task>`. Reference implementation описана в `docs/WORKTREE_LIFECYCLE.md`, визуальная схема — в `README.md`.

Перед правками агент обязан проверить текущую ветку, worktree path, `git status --short`, base и понятный write scope. Не редактировать одновременно coordination files без владельца: `ROADMAP.md`, `TASKS.md`, `AGENTS.md`, `projects/*/wiki/log.md`, `projects/*/wiki/index.md`, `plans/leadops/worktree-ledger.json`, changelog/log, shared config, migration list и аналоги. Если несколько агентов могут менять один такой файл, нужен явно назначенный integration owner.

Dirty/behind shared checkout `<REEFIKI_ROOT>` не является рабочей поверхностью для новой задачи. Если shared checkout грязный или отстаёт от `origin/main`, не чистить его и не стартовать из него: создать fresh task worktree от `origin/main`. Чужая грязь вне текущего scope считается `excluded_dirty_paths`, не блокирует работу и перечисляется в финале; грязь внутри target scope считается blocker, пока ownership или перенос нужного intent в fresh branch не подтверждён.

Closeout checklist перед commit/publish/cleanup:

- `git status --short` в task worktree;
- `git diff --name-only <base>...HEAD` и проверка, что diff в scope;
- targeted tests для затронутого поведения;
- `publish-task --dry-run` при REEFIKI publish/merge scope;
- `orchestration-check` при LeadOps/parallel/batch scope;
- stage только конкретных paths, без широкого staging всей рабочей копии.

Cleanup worktree возможен только после status + diff + ancestry/semantic evidence: worktree clean, HEAD reachable from base или полезный intent точечно перенесён/заменён и это зафиксировано. Dirty, unmerged, blocked или ambiguous worktree не удалять; оставить path, branch и причину.

Stale worktree с useful intent переносится точечным патчем на fresh branch от актуального base. Не merge-ить старый final tree целиком: он может содержать устаревшие generated files, конфликтующие coordination edits или уже заменённые решения.

Для batch/roadmap задач один worktree живёт до ближайшего milestone, но не дольше: после milestone обязательны publish/defer/cleanup или короткая причина, почему worktree остаётся.

### Codex thread orchestration rule

Если пользователь подтверждает несколько независимых задач или прямо говорит «отдельный тред», агент должен сам создать отдельный Codex thread для каждой задачи через thread-management tools, а не смешивать scope в текущем чате.

TeamLead mode:

- Если текущий тред явно назван или назначен `TeamLead`, он становится единой точкой входа для REEFIKI dev/docs/wiki задач: принимает новые задачи, создаёт child threads/worktrees, проверяет их итоги и интегрирует только принятый результат.
- Пользователь может написать: `Новая задача: <описание>. Создай отдельную ветку/тред.` или коротко `Сделай отдельной задачей: <описание>`. TeamLead сам выбирает: новая child task, добавление в уже активный compatible scope, read-only audit или stop на конфликте scope.
- Если пользователь уже создал ветку, он пишет: `Возьми ветку <branch>: <цель>`. TeamLead классифицирует её как `adopt`, `keep user-owned`, `superseded` или `cleanup-candidate`, не удаляя и не merge-яв её без evidence.
- Child thread title: `REEFIKI · <short task>`; branch: `codex/<ascii-slug>`; worktree: `<WORKSPACE_ROOT>\_worktrees\REEFIKI-<ascii-slug>`.
- Финальный отчёт child thread всегда на русском и в одном формате: что сделано, изменённые файлы, проверки, коммит, харвест, блокеры, исключённые dirty paths, дочерние треды, следующий шаг.
- `Харвест` обязателен как closeout decision: `сделан`, `не нужен` или `отложен`. Если задача дала reusable знание, решение, процедуру, publish proof или изменение operating rule, TeamLead должен сделать scoped harvest в выбранный REEFIKI project до финального closeout или явно зафиксировать `отложен` с причиной. Child thread по умолчанию не пишет в shared `wiki/log.md` сам; он возвращает рекомендацию, а TeamLead интегрирует durable запись, если не делегировал harvest явно.
- TeamLead является integration owner для shared coordination files и единственным местом, где принимается решение о guarded publish/cleanup. Child threads не push/publish/cleanup без явного делегирования.
- Перед началом нетривиальной задачи и при расширении scope TeamLead обязан выполнить Subagent Decision Gate: `child threads: да/нет — причина`. Это правило действует и когда TeamLead собирается делать работу сам.
- По умолчанию выбирай child thread или read-only verifier, если есть сильный сигнал риска: несколько поверхностей (`code + tests + docs + packaging + wiki`), install/release/PATH/package, browser-visible runtime, publish/cleanup/PR migration, dirty worktree triage, пользовательский regression-smoke, coordination files или необходимость независимой проверки перед publish.
- Можно не создавать child thread для маленькой линейной задачи с одним write surface, понятным тестом и без publish/browser/release риска; причину всё равно укажи в финальном отчёте.
- Если TeamLead сам реализовал multi-surface, release/install или browser-visible fix, перед publish по умолчанию запускается read-only verifier/QA child thread; если пропущено, финальный отчёт должен сказать почему.

Правила:

- coding/docs/wiki задача получает project thread в fresh worktree от `origin/main` или явно заданной base;
- read-only audit/classification/cleanup-inventory задача может идти в project local thread, если shared checkout не используется как поверхность правок;
- parent thread обязан сохранить `threadId` или `pendingWorktreeId`, затем после завершения проверить child thread через `read_thread` и live git/worktree evidence;
- parent thread обязан принять harvest decision перед publish/cleanup/final report: `сделан`, `не нужен` или `отложен`;
- parent thread обязан включить в финальный отчёт `Subagents / Child threads: использовались / не использовались — причина`;
- child thread не архивируется автоматически: thread history является audit trail; archive/delete только по явному запросу пользователя;
- task worktree/branch чистится отдельно через `cleanup-worktree` только после publish/reachability proof;
- если child thread оставил unpushed commit, parent thread должен запросить или получить отдельный approval на guarded publish.

### Memory control plane startup contract

Если пользователь упоминает `memory control plane`, `memory pack`, `handoff`, legacy-имя `REEFIKI 2` или просит «продолжай REEFIKI», агент **сам** запускает из корня:

1. `memory pack <task> --project reefiki --strict`
2. `memory golden --project reefiki`

Пользователь не должен помнить эти команды. Если `pack --strict` или `golden` падает — сначала показать короткий блокер и чинить доказанную проблему, а не расширять архитектуру.

Исключение для быстрых durable writes: если пользователь говорит «запомни», «зафиксируй», «сохрани важное», `/harvest` или похожую фразу, даже с legacy-упоминанием `REEFIKI 2`, это **не** startup/handoff. Сначала выполни project-level `/harvest` в явно выбранный или текущий project. Не запускай `memory pack --strict`/`golden`, пока пользователь не просит продолжить REEFIKI в режиме memory context/handoff или менять memory-логику.

Перед любыми правками memory-логики (`scripts/reefiki.py`, `scripts/reefiki_memory/`, `tests/test_reefiki_memory_*`) `memory golden --project reefiki` обязателен как regression baseline.

Не подключать qmd/vector/rerank/новые providers, пока `memory golden` или `memory pack --strict` не покажут измеримые misses текущего lookup/pack.

## Code navigation tools

Для задач по коду в корне REEFIKI используй инструменты слоями:

1. `graphify-out/GRAPH_REPORT.md`, если он есть, — как карту большого codebase.
2. `ast-index` — только для кода: символы, usages, outline по `scripts/`, `tests/` и другим исходникам.
3. `rg`, `git status`, `git diff` и тесты — как источник истины перед выводами и правками.

Ограничение: REEFIKI в основном markdown/wiki repo, поэтому `ast-index` не заменяет поиск по `projects/*/wiki/`, `wiki/index.md`, `wiki/log.md` и другим knowledge-файлам. Для wiki-знаний используй обычный текстовый поиск и REEFIKI-команды.

## Schema (формат страниц)

Полный формат frontmatter и тела страниц — в `projects/<name>/wiki/_schema.md`. Lazy-load: читай только когда создаёшь или правишь страницу.

## Safety — что не сохранять

`/save` и `/process` отказывают молча или с понятным сообщением, если источник содержит:

- **Секреты.** `.env*`, `id_rsa*`, `*.pem`, `*.key`, `*.pfx`, `.aws/credentials`, `.ssh/`, файлы с подозрительными именами (`secret`, `password`, `token` без расширения).
- **Запрещённые директории.** `.git/`, `node_modules/`, `vendor/`, `__pycache__/`, `dist/`, `build/`, `target/`, `.next/`, `.cache/`.
- **Бинарники.** По расширению (`.exe`, `.dll`, `.so`, `.dylib`, `.bin`, `.iso`, `.zip`, `.tar`, `.7z`, изображения и видео без явного контекста). PDF/docx — спросить у пользователя.
- **Размер.** Файлы >5 MB — отказ или подтверждение.

Сообщение об отказе формулируется по-человечески: «Не сохраняю `<имя>` — похоже на секрет/бинарник/слишком большой. Если уверен — переложи руками или скажи явно».

## Стиль общения с пользователем

По умолчанию пользователь — **не программист**. Не знает терминов из этого файла, не пишет markdown, не запускает команды оболочки. Говори бытовым языком.

- **Не используй технические термины без необходимости.** Если без них никак — переводи в той же фразе. Бытовые соответствия: «копилка» = `inbox/`, «отказ» = `seen/`, «архив» = `raw/`, «вики» = `wiki/`, «зачем нужно» = `useful_when`, «страница» = wiki-страница, «сохранил» = записал в wiki, «отложил» = в `seen/`.
- Технические артефакты (`frontmatter`, `slug`, `kebab-case`, `quarantine_until`, `[[Related]]`, `ADR`, `commit`, `git`, `source_id`) — твой внутренний словарь, не транслируй.
- Команды оболочки (PowerShell / bash / cmd) и сниппеты — не показывай. Нужна команда — выполняй сам, отдай только результат.
- Внутренние reasoning-структуры («4 вопроса», «acceptance check») — не транслируй. Покажи только итог: «X сохраню как страницу про Y, Z отложу как повтор».
- Если пользователь сам пишет техническими терминами — отзеркаль его словарь, не упрощай искусственно.
- Не будь нянькой. Если действие легально и пользователь явно его просит — выполняй спокойно, без перестраховок.

## Git workflow

Команды, изменяющие `wiki/`/`raw/`, коммитят сами в порядке: **изменения файлов → append `wiki/log.md` → обновить `wiki/index.md` → stage только явные затронутые пути → `git commit`**.

Лог-запись идёт **до** коммита — чтобы запись попала в тот же коммит. Это критично, нарушать нельзя.

Телеметрия (`use_count` / `last_used`) не коммитится в `/query` — батчится в ближайший `/process` / `/lint` / `/harvest`.

## Запреты (общие)

- Не модифицируй `raw/` ни в одном проекте — immutable архив.
- Не редактируй старые записи в `wiki/log.md` — только append.
- Не выходи за пределы папки проекта в рабочем режиме.
- Не объединяй базы разных проектов без явной просьбы пользователя.
- Не создавай страницы в `projects/<name>/wiki/`, находясь в корне.

## Для конкретных агентов

Этот файл — vendor-neutral. Vendor-specific конвенции:

- **Claude Code (CLI / VSCode extension)** — читает `CLAUDE.md` (стаб → сюда) и `.claude/commands/*.md` (детальные спеки операций).
- **Cascade (Windsurf)** — читает `.windsurf/rules/main.md` (стаб → сюда). Workflows из `.windsurf/workflows/` опциональны.
- **Cursor** — читает `.cursorrules` (стаб → сюда). Альтернатива: `.cursor/rules/*.mdc`.
- **Codex CLI / Aider** — читают `AGENTS.md` напрямую (этот файл).
- **Cline / Roo Cline** — читают `.clinerules` (стаб). Если стаба нет — `AGENTS.md`.
- **Web Claude / ChatGPT Projects** — пользователь загружает `AGENTS.md` (и при работе в проекте — также `projects/<name>/AGENTS.md`) как project knowledge / system context.
- **Любой другой агент** — читай `AGENTS.md` (этот файл) и при работе в проекте — `projects/<name>/AGENTS.md`. Этого достаточно.

Если агент не знает, что делать — он должен **сообщить пользователю**, что прочитал `AGENTS.md` и попросить уточнить операцию или цель сессии. Не выдумывать.

## Куда смотреть дальше

- `projects/<name>/AGENTS.md` — контракт конкретного проекта.
- `projects/<name>/_domain.md` — тема проекта (что это вообще про что).
- `projects/<name>/wiki/_schema.md` — форматы страниц.
- `projects/<name>/.claude/commands/<op>.md` — детальные спецификации операций.
- `COMMANDS.md` — человеческий справочник команд.
- `README.md` — первое знакомство для людей.
