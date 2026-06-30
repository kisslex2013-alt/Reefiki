# COMMANDS — справочник команд

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Агент работает **автономно** — не ждёт slash-команд. Просто скажи по-человечески, что хочешь, и он сделает. Этот файл — справочник на случай, если хочется вспомнить, что какая команда делает.

Если ты новый пользователь, начни с `reefiki init`, затем `doctor`/`status`. `reefiki onboarding` и `reefiki tour` остаются demo/guide командами после первого workspace. Редкие operator/maintainer-команды для publish, cleanup и staged scope вынесены в [docs/OPERATOR_COMMANDS.md](docs/OPERATOR_COMMANDS.md#русский).

## English

The agent works **autonomously** and does not require slash commands. Tell it what you want in plain language, and it maps the request to the correct REEFIKI operation.

Most-used intents:

| Intent | Say this |
|---|---|
| First local workspace | `reefiki init --workspace /tmp/reefiki-workspace --project-name first-run` |
| Import existing markdown notes | `reefiki --project /tmp/reefiki-workspace/projects/first-run import /tmp/my-notes --from markdown` |
| Create a wiki project | "Create a new project `<name>` about `<topic>`" |
| Connect a code project | "Connect `<path>` to the wiki" |
| Save a link/file for later | "Put this in the inbox" |
| Process saved material | "Process the inbox" |
| Ask accumulated knowledge | "What did we decide about `<topic>`?" |
| Capture conclusions | "Capture the session conclusions" |
| Check health | "Show project status" / "Run a health check" |

The detailed canonical command reference continues below in Russian.

## 中文

代理会**自主工作**，不需要你记住 slash commands。你可以用自然语言说明目标，代理会映射到正确的 REEFIKI 操作。

常用意图：

| 意图 | 可以这样说 |
|---|---|
| 第一个本地 workspace | `reefiki init --workspace /tmp/reefiki-workspace --project-name first-run` |
| 创建 wiki 项目 | “创建一个名为 `<name>` 的新项目，主题是 `<topic>`” |
| 连接代码项目 | “把 `<path>` 连接到 wiki” |
| 保存链接/文件以后处理 | “把这个放进收件箱” |
| 处理已保存材料 | “处理收件箱” |
| 查询已有知识 | “我们对 `<topic>` 做过什么决定？” |
| 记录会话结论 | “记录本次会话结论” |
| 检查健康状态 | “显示项目状态” / “运行健康检查” |

下面继续保留俄语的详细 canonical command reference。

Плюс агент сам предлагает действия: разобрать копилку, записать выводы, сохранить навык, проверить здоровье вики — когда видит, что пора.

Полные инструкции для агента — в `.claude/commands/<имя>.md` (в корне для `/new`, в проекте для остальных).
Имя папки `.claude/` историческое: эти markdown-спеки vendor-neutral и применимы для Codex, Claude Code, Cursor, Windsurf, Gemini, Mimo и других агентов, которые читают `AGENTS.md`.

Заметные изменения проекта ведутся в `CHANGELOG.md`.

Для первого запуска и восстановления смотри:
`QUICKSTART.md`, `docs/obsidian-setup.md`, `docs/mobile-capture.md`, `docs/RECOVERY.md`.

После локальной установки можно вызывать CLI как `reefiki`:

```powershell
pipx install git+https://github.com/kisslex2013-alt/reefiki.git
pipx ensurepath
Get-Command reefiki
where.exe reefiki
reefiki --help
reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run status
reefiki --project C:\Temp\reefiki-workspace\projects\first-run import C:\Temp\my-notes --from markdown --format json
```

POSIX пример:

```bash
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run status
```

Из checkout без установки остаётся рабочим прежний путь:
`python scripts/reefiki.py init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json`.

Если `reefiki` не найден в текущем shell, используй checkout fallback:

```powershell
python scripts\reefiki.py --help
python scripts\reefiki.py init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
```

## Workspace-команды

`reefiki init` работает из установленного CLI или checkout fallback. Остальные команды этого раздела запускаются из корня `REEFIKI/` (там, где этот файл), когда ты работаешь с самим репозиторием.

### `reefiki init --workspace <path> --project-name <name>`

**Что делает.** Создаёт новый локальный REEFIKI workspace из встроенных шаблонов, без чтения private-only файлов из репозитория.
**Когда нужна.** Первый запуск после установки: нужен настоящий локальный wiki-проект, который сразу проходит `doctor` и `status`.
**Что произойдёт.** Создаст `projects/<name>/AGENTS.md`, `_domain.md`, `inbox/`, `raw/`, `seen/`, `wiki/index.md`, `wiki/log.md`, starter overview pages и первый concept page. Если workspace уже содержит файлы или проект уже существует, команда остановится без `--force`.
**JSON-режим.** Возвращает `outcome`, `workspace`, `project`, `created_paths`, `next_actions` и `bridge`.

```powershell
reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run status
```

```bash
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run status
```

**Profiles.** `--profile product|agent_surface|knowledge_domain|reefiki_core` задаёт ручной onboarding label.

**Bridge.** По умолчанию кодовый проект не меняется. Для явного подключения:

```powershell
reefiki init --workspace C:\Temp\my-reefiki --project-name my-app --code-project H:\Projects\MyApp --apply-bridge --format json
reefiki connect-check H:\Projects\MyApp --format json
```

Если symlink/junction недоступен, команда вернёт `bridge_unsupported` и не оставит частично созданные `_wiki`, `.reefiki` или `.gitignore` в кодовом проекте.

### `reefiki --project <project> import <path> --from markdown|obsidian|logseq`

**Что делает.** Кладёт существующие `.md` заметки в `inbox/` выбранного проекта, не создавая wiki-страницы напрямую.
**Когда нужна.** После первого `reefiki init`, если уже есть Obsidian, Logseq или обычная папка Markdown и нужно снять cold start.
**Что произойдёт.** Команда читает один `.md` файл или папку, пропускает `.git`, `.obsidian`, build/cache директории, блокирует secret-like content/path, пишет только importable files в `inbox/` и добавляет одну append-only запись в `wiki/log.md`.
**JSON-режим.** Возвращает `outcome`, `candidate_count`, `imported_count`, `skipped_count`, `imported`, `skipped`, `created_paths` и `next_actions`.

```powershell
reefiki --project C:\Temp\reefiki-workspace\projects\first-run import C:\Temp\my-notes --from obsidian --format json
```

```bash
reefiki --project /tmp/reefiki-workspace/projects/first-run import /tmp/my-notes --from markdown --format json
```

Для большой папки сначала используй `--dry-run`; default batch limit — `--max-files 100`. После импорта попроси агента разобрать копилку или запусти обычный `/process`.

### `/new <имя>`

**Что делает.** Создаёт новый проект из шаблона `projects/_template/`.
**Когда нужна.** Хочешь начать новую базу знаний по отдельной теме.
**Как сказать по-человечески.** «Создай новый проект `<имя>` про `<тему>`».
**Что произойдёт.** Скопируется шаблон в `projects/<имя>/`, агент задаст 3 вопроса про домен, заполнит `_domain.md`, сделает git-коммит. После — открой папку проекта в любом IDE.

**Project profile.** Если проект про agent/IDE/runtime окружение, скажи это сразу: «Создай проект `codex` как agent/runtime surface». Сейчас это ручной onboarding label, а не schema field. Подробно: [docs/PROJECT_PROFILES.md](docs/PROJECT_PROFILES.md#русский).

### `/connect <путь> [имя]`

**Что делает.** Подключает кодовый проект к вики. Создаёт junction `_wiki/` в кодовом проекте, маркер `.reefiki`, обновляет AGENTS.md кодового проекта и фиксирует git-bridge contract: `_wiki/` и `.reefiki` не должны жить в git-истории кодового проекта. Если вики-проект не существует — создаёт через `/new`.
**Когда нужна.** Хочешь вести вики для существующего кодового проекта.
**Как сказать по-человечески.** «Подключи проект `<путь>` к вики».

**Agent/runtime проекты.** Для Codex, Claude Code, Gemini, Mimo, Hermes и похожих окружений можно сказать: «Подключи `<путь>` как agent surface». Тогда агент будет вести правила, adapters, diagnostics и recovery procedures как переносимую память, без объединения wiki-проектов и без auto-copy skills.

**Post-connect check.** После подключения можно read-only проверить git-bridge contract:

```powershell
python scripts\reefiki.py connect-check "D:\Projects\MyApp" --format json
```

Для git-проектов команда проверяет, что `_wiki/` и `.reefiki` ignored и не tracked. Для non-git проектов git-check помечается как not applicable; доказательством подключения остаются `_wiki`, `.reefiki`, `detect`, `status` и `doctor`.

### `/sync-template`

**Что делает.** Синхронизирует обновления из `_template` во все проекты (команды, schema, правила).
**Когда нужна.** После обновления шаблона — новые команды, изменения формата, новые типы страниц.
**Как сказать по-человечески.** «Обнови все проекты из шаблона».

## Команды проекта — ежедневные

Запускаются изнутри `projects/<имя>/`.

### `/save <ссылка или путь>`

**Что делает.** Кладёт URL или файл в `inbox/` (копилку) **без анализа**. Дешёвая операция, нулевое трение.
**Когда нужна.** Увидел что-то стоящее, не хочешь сейчас разбирать — просто чтобы не потерялось.
**Как сказать по-человечески.** «Сохрани `<ссылка или путь>`», «положи это в копилку».
**Что произойдёт.** Файл скопируется в `inbox/` (или создастся стаб с URL). Перед записью агент проверит дубликаты: тот же URL, то же имя в `inbox/`, exact content hash для файла. **Не сохраняет**: секреты, бинарники, файлы >5 MB.

### `/process`

**Что делает.** Разбирает всё, что лежит в `inbox/`. Каждый источник либо превращается в страницу в `wiki/`, либо отправляется в `seen/` с причиной отказа (карантин 30 дней).
**Когда нужна.** Когда копилка набралась (агент сам напомнит при ≥1 файле в начале сессии).
**Как сказать по-человечески.** «Разбери копилку», «обработай что я насохранял».
**Что произойдёт.** Агент прочитает каждый файл, применит внутренние 4 вопроса (дельта / сценарий / тип / решение) + acceptance check, покажет тебе план («X сохраню как страницу про Y, Z отложу как повтор»), спросит подтверждение, потом запишет всё. URL без локального текста — попросит сохранить через Web Clipper.

### `/query <вопрос>`

**Что делает.** Отвечает на вопрос **только** на основе того, что уже есть в `wiki/` твоего проекта. Не из общих знаний.
**Когда нужна.** Хочешь поднять накопленное по теме.
**Как сказать по-человечески.** «Вики, что у нас по `<тема>`?», «спроси у вики `<вопрос>`».
**Что произойдёт.** Агент пройдёт по `wiki/index.md`, найдёт релевантные страницы, прочитает их и составит ответ со ссылками на источники. Обновит счётчики использования (`use_count`).

### `/harvest`

**Что делает.** Извлекает выводы из текущей сессии: решения («выбрал X»), синтез («оказалось что…»), повторяющиеся приёмы.
**Когда нужна.** К концу содержательной сессии — особенно если было «решил…», «выяснили что…», или повторил приём 2+ раза.
**Как сказать по-человечески.** «Запиши выводы из сессии», «зафиксируй что мы поняли».
**Что произойдёт.** Агент пересмотрит ход разговора, предложит сохранить ключевые моменты как страницы (`decisions/`, `synthesis/`, `concepts/`). Ты подтверждаешь — он пишет.

### `/status`

**Что делает.** Показывает состояние проекта одним экраном. Read-only — ничего не меняет.
**Когда нужна.** «Что у нас тут происходит?»
**Как сказать по-человечески.** «Покажи статус», «что у нас».
**Что произойдёт.** Агент посчитает: сколько в копилке, сколько страниц по типам, сколько давно не открывалось, есть ли просроченные карантины, давно ли был `/lint`.
**JSON-режим.** `python scripts\reefiki.py --project projects\<name> status --format json` возвращает тот же snapshot как `project`, `inbox`, `seen`, `wiki`, `last_lint`.

### `reefiki.py doctor` / integrity check

**Что делает.** Проверяет базовую целостность проекта и SQLite-индекса. Read-only — ничего не меняет.
**Когда нужна.** Перед publish/release, после сбоя, или если поиск/индекс ведёт себя странно.
**Как сказать по-человечески.** «Проверь индекс проекта», «проверь целостность».
**Что произойдёт.** Агент проверит обязательные папки и файлы, выполнит SQLite `integrity_check`, сравнит число wiki-страниц с индексом и вернёт `pass` или список проблем.

### `reefiki.py health` / practical knowledge health metrics

**Что делает.** Показывает read-only практические метрики здоровья durable wiki: размер, distillation ratio, использование, orphan/broken links, conflicts, warnings и recommendations.
**Когда нужна.** После batch `/process`/`/harvest`, перед cleanup, перед roadmap phase switch или когда база начинает расти.
**Как сказать по-человечески.** «Проверь здоровье базы знаний», «какие есть тревожные сигналы по wiki?».
**Что произойдёт.** Агент выполнит `doctor` как под-блок, посчитает practical metrics и вернёт `pass`/`warn`/`fail`. `warn` не блокирует работу, но даёт следующий ручной triage step.

### `reefiki.py dashboard` / read-only operator dashboard

**Что делает.** Показывает один короткий read-only экран: practical health, ключевые warning-сигналы, review queue summary и следующий операторский шаг.
**Когда нужна.** Перед ручным triage, после `health`, при вопросе «что дальше по wiki?» или когда полный `review-queues` слишком шумный.
**Как сказать по-человечески.** «Покажи dashboard», «что сейчас делать по базе?», «дай короткий gate status».
**Что произойдёт.** Агент переиспользует `health` и `review-queues --summary`, ничего не пишет и не меняет. `--limit N` ограничивает примеры очередей; JSON-режим отдаёт тот же payload для automation.

### `reefiki.py ops-dashboard` / Codex Workspace Ops Board

**Что делает.** Показывает локальный read-only обзор всех git-проектов Codex workspace на одном экране, а REEFIKI использует как enrichment layer для подключённых проектов.
**Когда нужна.** Когда нужно быстро увидеть состояние всех локальных проектов под выбранным workspace root, например `D:\Projects`: clean/dirty, branch, ahead/behind, stack, AGENTS/CI/tests indicators, REEFIKI mapping и последние wiki log entries.
**Как сказать по-человечески.** «Покажи Codex Workspace Ops Board», «открой локальную доску проектов», «дай JSON snapshot workspace».
**Что произойдёт.** Команда discover-ит только git repos на 1 уровень глубины внутри явного `--workspace-root`, выполняет только read-only git/status/metadata checks, не запускает package scripts, не делает fetch/pull/push в target projects и не читает `.env*`, `raw/`, `.git/objects`, `node_modules`, `dist`, `build`, `.next`, `target`.
**JSON snapshot.** `python scripts\reefiki.py ops-dashboard --workspace-root D:\Projects --format json`
**Synthetic demo.** `python scripts\reefiki.py ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo --format json`
**Локальная web-доска.** `python scripts\reefiki.py ops-dashboard serve --workspace-root D:\Projects --port 7310`
**UI.** Web-доска поддерживает переключение языка `ru/en` и темы `dark/light`; выбор хранится локально в браузере. Верхний блок `First run` показывает guided tour state из snapshot: onboarding, demo fixture, status, local board и safe `/connect` handoff; `Current Work` показывает активные агентские ветки, dirty projects, worktree/warning signals и безопасный следующий шаг; `Recent activity` даёт фильтр по всем найденным проектам, включая plain git projects без REEFIKI log.
**Ограничение MVP.** Web server bind-ится только на `127.0.0.1`; UI не содержит publish/apply/cleanup buttons. Будущие действия показываются только как read-only status или recommended command.

### `reefiki.py tour` / guided first-run checklist

**Что делает.** Печатает read-only checklist первого запуска: что уже готово, какой шаг текущий и что заблокировано до demo fixture или safe `/connect` handoff.
**Когда нужна.** Первый запуск, проверка onboarding/demo/dashboard route или короткий статус без создания файлов.
**Как сказать по-человечески.** «Покажи guided tour», «что сейчас делать в первом запуске».
**Что произойдёт.** Команда ничего не пишет. `--fixture-root`, `--workspace-root` и `--connect-path` только добавляют evidence для статусов.
**Проверка.**

```powershell
python scripts\reefiki.py tour --format json
python scripts\reefiki.py tour --fixture-root C:\Temp\reefiki-demo --workspace-root C:\Temp\reefiki-dashboard-demo --format json
```

### `reefiki.py onboarding` / first-run wizard

**Что делает.** В интерактивном терминале открывает пошаговый onboarding wizard: выбор языка, ASCII-Рифик, выбор действия и только затем нужные команды. В non-TTY режиме показывает компактный первый экран без простыни команд. English output доступен через `--lang en`.
**Когда нужна.** Первый запуск или проверка установки без чтения больших README/AGENTS.
**Как сказать по-человечески.** «Покажи первый запуск REEFIKI», «создай demo onboarding flow».
**Что произойдёт.** Без `--fixture-root` non-interactive режим ничего не пишет. В interactive wizard демо создаётся только после выбора действия, папки и подтверждения. С `--fixture-root <папка>` создаёт deterministic demo project в этой папке: raw source, wiki concept, harvest synthesis, index и log; inbox остаётся пустым после simulated process.
**Полезные флаги.** `--interactive` форсирует wizard, `--no-interactive` печатает компактный экран, `--show-commands` раскрывает ручной маршрут, `--plain` отключает рамки/визуал, `--yes` подтверждает создание демо в interactive mode.
**Проверка.**

```powershell
python scripts\reefiki.py tour --format json
python scripts\reefiki.py onboarding --format json
python scripts\reefiki.py onboarding --fixture-root C:\Temp\reefiki-demo --format json
python scripts\reefiki.py --project C:\Temp\reefiki-demo\projects\reefiki-onboarding-demo status
python scripts\reefiki.py ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo --format json
python scripts\reefiki.py ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

### `reefiki.py adapter-call` / local MCP/REST-ready adapter

**Что делает.** Даёт минимальный локальный JSON entrypoint для будущих MCP/REST wrappers: `reefiki_query`, `reefiki_status`, `reefiki_save`.
**Когда нужна.** Когда агенту или интеграции нужен stable tool-like вызов без парсинга human CLI output.
**Как сказать по-человечески.** «Вызови REEFIKI как adapter tool», «проверь query/status/save через JSON adapter».
**Что произойдёт.** Команда выбирает только явный REEFIKI project из `projects/<name>`. `reefiki_query` и `reefiki_status` read-only. `reefiki_save` пишет только через существующий `/save` path и блокируется без `--allow-write`.

```powershell
python scripts\reefiki.py adapter-call reefiki_status --project reefiki-demo
python scripts\reefiki.py adapter-call reefiki_query --project reefiki-demo --payload "{\"query\":\"public snapshot\",\"limit\":3}"
python scripts\reefiki.py adapter-call reefiki_save --project reefiki-demo --payload "{\"source\":\"https://example.com\"}" --allow-write
```

**Rollback.** Это не daemon, не network server и не runtime config. Чтобы откатить adapter surface, достаточно убрать `adapter-call` wiring и `scripts/reefiki_core/adapters.py`; durable wiki/raw/config не создаются, кроме явного `reefiki_save --allow-write` в выбранном проекте.

### `reefiki.py cross-query` / read-only cross-project lookup

**Что делает.** Ищет по `projects/*/wiki/index.md` и указанным там wiki-страницам без создания общей базы, SQLite index или durable write.
**Когда нужна.** Когда нужно найти совпадения и собрать короткую deterministic synthesis по нескольким REEFIKI projects, сохраняя project isolation.
**Как сказать по-человечески.** «Поищи по всем проектам REEFIKI», «собери read-only cross-project evidence».
**Что произойдёт.** Команда читает только wiki index/page markdown, возвращает source project/page/sources/sha256 provenance и предупреждает о небезопасных index paths. Запись в wiki не делается.

```powershell
python scripts\reefiki.py cross-query "adapter provenance" --limit 5
python scripts\reefiki.py cross-query "adapter provenance" --project-name reefiki --format json
python scripts\reefiki.py cross-query "Odysseus dogfood external project onboarding roadmap trigger" --project-name reefiki --format json
```

Для dogfood/onboarding внешнего проекта формулируй запрос узко: называй внешний test-case, сценарий и gate, например `Odysseus dogfood external project onboarding roadmap trigger`. Не используй общий `control plane` wording, если нужна именно dogfood-проверка: он намеренно тянет более широкие control-plane страницы.

**Rollback.** Это read-only CLI surface. Чтобы откатить, достаточно убрать `cross-query` wiring и `scripts/reefiki_core/cross_project.py`; wiki/raw/config не меняются.

### `reefiki.py agent-readiness` / read-only repo skill advisor

**Что делает.** Анализирует внешний git-репозиторий или обычную папку и выдаёт Agent Readiness Plan: какие `Skills`, `Rules`, `Adapters` и `Hooks` нужны агентам для безопасной работы.
**Когда нужна.** Перед подключением нового кодового проекта, перед выдачей задачи AI-агенту, при грязном worktree, нескольких remotes, frontend/auth/deploy/migration surface или непонятных agent rules.
**Как сказать по-человечески.** «Проверь, какие навыки и правила нужны этому репозиторию», «сделай Agent Readiness Plan для `<путь>`».
**Что произойдёт.** Команда read-only: не запускает package scripts, не устанавливает skills/hooks/adapters, не меняет target repo и не читает secret-like файлы глубже path/name checks. JSON/text output содержит `reason`, `evidence`, `severity` и `confidence` для каждой рекомендации. Alias: `reefiki.py skills recommend --repo <path>`.

### `/review-queues` (или `reefiki.py review-queues`) / read-only governance scan

**Что делает.** Показывает candidates для governance-очередей durable knowledge: stale, orphan, duplicate, needs verification, conflict.
**Когда нужна.** После крупных `/harvest`, batch `/process`, перед cleanup или когда база растёт.
**Как сказать по-человечески.** «Покажи проблемные страницы durable-слоя», «что у нас stale/orphan/duplicate?».
**Что произойдёт.** Агент выполнит read-only scan и покажет queue type, причину, связанные страницы и suggested action. Ничего автоматически не меняет.
**Дополнительно.** Режим `--summary` даёт компактные counts, sample pages, top pages и next action по типам очередей. Режим `--type <queue>` фильтрует одну очередь, например `placeholder_link` или `missing_backlink`; text output показывает короткий список и уважает `--limit N`. Для осознанных one-way inbound links target page может содержать секцию `## Intentional one-way inbound links` с plain source ids. Режим `--write-report` пишет полный markdown-отчёт в `plans/review-queues-YYYY-MM-DD.md` для ручного triage. Агент должен использовать его, когда очередь не пустая и cleanup не закрывается сразу, нужен handoff или пользователь просит план/артефакт.
**Stale-процедура.** Устаревшие страницы разбираются только вручную: `use_count=0` без входящих ссылок → кандидат в `seen/` с `reason: stale`; `use_count=0` с входящими ссылками → освежить `useful_when`/связи; `use_count>0` и давно не проверялась → verification источника или процедуры.

### `reefiki.py backlinks` / generated backlink index

**Что делает.** Строит read-only граф связей поверх текущих wiki-страниц: incoming/outgoing links, orphans, broken links.
**Когда нужна.** Перед cleanup, review очередей, поиском осиротевших страниц или проверкой связности durable wiki.
**Как сказать по-человечески.** «Покажи граф ссылок», «найди битые wiki-ссылки», «кто на кого ссылается?».
**Что произойдёт.** Агент выполнит команду без изменения markdown-страниц. Режим `--write` пишет generated artifact `wiki/_backlinks.json`, который можно пересобрать из wiki.

### `reefiki.py search` / frontmatter + link + heading query

**Что делает.** Ищет по wiki через SQLite FTS5 и rebuildable index поверх markdown.
**Когда нужна.** Когда нужен быстрый технический lookup: по типу, тегу, ссылкам, orphan-состоянию или конкретной секции страницы.
**Как сказать по-человечески.** «Найди skill про память», «покажи страницы, которые ссылаются на X», «найди orphan skills».
**Что произойдёт.** Агент выполнит read-only поиск. Фильтры: `--type`, `--tag`, `--link-to`, `--linked-by`, `--orphan`. Режим `--chunks` ищет по heading-aware chunks и возвращает matched heading. Для progressive disclosure в JSON используй `--output compact` без полного body или `--output files` как список `docid`/`path` для точечного чтения.

### `reefiki.py tool-trigger` / read-only gate для внешних tool candidates

**Что делает.** Проверяет, есть ли уже достаточный сигнал для sandbox smoke внешнего инструмента, не устанавливая его.
**Когда нужна.** Когда в сессии звучит “большой незнакомый codebase”, “нужна визуальная карта”, “wiki graph”, “interactive onboarding” или похожий сигнал.
**Как сказать по-человечески.** «Проверь, пора ли тестировать Understand-Anything», «нужна визуальная карта проекта».
**Что произойдёт.** Агент выполнит `tool-trigger Understand-Anything --signal "<сигнал>"` и получит `watch` или `sandbox-recommended`.
**Ограничение.** Даже при `sandbox-recommended` это не установка в основной workspace: только isolated sandbox, без global install, без auto-update hooks, с сравнением против graphify/codegraph/REEFIKI.

### `reefiki.py capture-evidence` / typed evidence draft

**Что делает.** Превращает ручную заметку, browser smoke, DOM selector, screenshot path, command summary или diff summary в reviewable evidence draft. По умолчанию команда пишет только stdout JSON/text; markdown draft создаётся только с `--write-draft`.
**Когда нужна.** Перед финальным отчётом, wiki harvest, review handoff или publish decision, когда proof иначе остался бы только в чате.
**Как сказать по-человечески.** «Зафиксируй это как evidence», «сделай evidence draft по этому smoke», «сохрани proof из команды без полного transcript».
**Что произойдёт.** Команда создаст draft с `kind`, `source`, `captured_at`, `claim`, `evidence`, `limits`, `redactions` и `related_paths`. Secret-like text редактируется, forbidden/secret-like paths блокируются, screenshot/video bytes не копируются и full command transcripts не сохраняются.
**Evidence citation.** В финальном отчёте или wiki/log ссылайся на claim + source + related path: `Evidence: <claim> — <source_artifact or task_id>, <related_path>`. Если draft записан файлом, укажи `draft_path`; если только stdout, цитируй summary и limits, не вставляй raw secret-bearing output.

### `reefiki.py notify` / low-noise artifact notification

**Что делает.** Создаёт dry-run notification payload для состояний `review_ready`, `blocked` или `failed`. По умолчанию no-network: команда ничего не отправляет, не пишет background state и не требует Telegram/Codex/plugin dependency.
**Когда нужна.** Когда TeamLead, verifier или publish gate должен явно показать, что artifact готов к review, заблокирован или упал, но без шумных heartbeat-сообщений.
**Как сказать по-человечески.** «Собери notify payload по этому blocker», «покажи review-ready уведомление по handoff», «зафиксируй failed status без отправки наружу».
**Что произойдёт.** Payload содержит `event`, `source_artifact`, `reason`, `next_action`, `evidence_pointer`, severity и deterministic fingerprint. Для повторного неизменного состояния передай `--previous-fingerprint`; команда вернёт `already_reported`. `--adapter-config` только фиксирует явную adapter reference в dry-run payload, но не отправляет сетью.

### `/promote-dry-run` (или `reefiki.py promote-dry-run`) / dry-run promotion из memoir

**Что делает.** Делает сухой прогон `memoir -> REEFIKI`: стоит ли поднимать knowledge в durable wiki и в какой target type.
**Когда нужна.** Когда есть memory item/вывод и нужно понять: оставить в memoir, игнорировать или оформить как `decision/concept/skill/synthesis`.
**Как сказать по-человечески.** «Проверь, стоит ли это поднимать из memoir в REEFIKI», «сделай promotion dry-run».
**Что произойдёт.** Агент покажет verdict (`ignore` / `memoir-only` / `promote`), suggested type, confidence, review_state и duplicate candidates. Без записи в wiki.
**Дополнительно.** Режим `--write-draft` пишет markdown draft в `plans/` для ручного review перед durable write. Агент должен использовать его, если материал выглядит durable, но нужен typed review, есть риск дубля или источник пришёл из memoir/другого слоя.
**Ещё шаг.** Режим `--apply-draft <путь> --yes` создаёт реальную wiki-страницу из promotion draft. Это mutating шаг, выполнять только по явному подтверждению.

### `reefiki.py memory route` / глобальный router

**Что делает.** Выбирает, в какой контур памяти должен идти новый факт: `memoir`, `REEFIKI` или `graphify`.
**Когда нужна.** Когда неочевидно, это временное правило, durable решение или structural/navigation запрос.
**Как сказать по-человечески.** «Куда это класть: в память агента, в вики или в граф?».
**Что произойдёт.** Агент покажет выбранный слой и короткую причину. Ничего не записывает.
**JSON-режим.** `--format json` возвращает стабильный `RouteDecision`: `recommended_layer`, `secondary_layers`, `reason`, `target_project`, `risk_flags`, `needs_user_confirmation`.

### `reefiki.py memory explain` / объяснение routing и источников

**Что делает.** Объясняет, почему для запроса выбран конкретный слой памяти и какие источники исключены.
**Когда нужна.** Когда нужно понять не только ответ, но и маршрут: REEFIKI wiki, memoir или graphify.
**Routing note.** Roadmap/backlog/phase/review-queue/health-gate запросы считаются REEFIKI governance context; memoir может быть secondary для рабочего контекста.
**Как сказать по-человечески.** «Объясни, почему это пойдёт в такой слой памяти», «почему graphify не используется?».
**Что произойдёт.** Агент покажет route decision, policy preflight, source decisions, excluded sources и next action. Ничего не записывает.
**JSON-режим.** `--format json` возвращает стабильный explain payload для handoff/audit.

### `reefiki.py memory status` / registry, health summary и open-queue gate

**Что делает.** Показывает provider registry и короткий health summary для выбранного REEFIKI project.
**Когда нужна.** Перед реализацией/отладкой unified memory flow: понять, какие слои доступны, какие capabilities они объявляют и есть ли открытые очереди.
**Как сказать по-человечески.** «Покажи registry слоёв памяти», «что умеют memoir/graphify/wiki?», «проверь memory status Metrica», «покажи status всех проектов».
**Что произойдёт.** Агент покажет providers `reefiki`, `memoir`, `graphify`, graphify status, review queue counts и promotion inbox counts для `--project <name>`. С `--all-projects` покажет totals и per-project summary; `--only-open` оставит только проекты с open review queues или active promotion drafts. `--summary` уберёт provider details для компактной проверки и покажет `next_action`, если есть open gate. `--fail-on-open` завершит команду ошибкой, если есть open review queues или active promotion drafts. `--format jsonl` отдаёт один project status на строку для automation. Ничего не меняет.

### `reefiki.py memory preflight` / policy safety check

**Что делает.** Проверяет boundary перед lookup/promote/export/pack: project scope, forbidden paths, public visibility и секретоподобный текст.
**Когда нужна.** Перед public/export/handoff или если есть риск смешать проекты.
**Как сказать по-человечески.** «Проверь, безопасно ли это отдавать/паковать/публиковать».
**Что произойдёт.** Агент вернёт `pass` или `block` с причинами. Ничего не меняет.

### `reefiki.py memory lookup` / единый lookup по слоям

**Что делает.** Ищет по `memoir`, `REEFIKI` и `graphify` через одну точку входа.
**Когда нужна.** Когда нужно быстро понять: «что у нас вообще уже есть по этой теме».
**Как сказать по-человечески.** «Посмотри во всех слоях памяти по X».
**Что произойдёт.** Агент сначала выполнит policy preflight, затем вернёт hits по working memory, durable wiki и graph-report, если он есть у подключённого проекта. Запросы в forbidden project scope блокируются до чтения providers.

### `reefiki.py memory promote` / глобальный promotion flow

**Что делает.** Делает dry-run promotion из глобального working-memory контекста в выбранный REEFIKI project.
**Когда нужна.** Когда вывод уже выглядит durable, но ещё нужно понять: стоит ли поднимать его в wiki и в каком типе страницы.
**Как сказать по-человечески.** «Подготовь это к подъёму в durable knowledge проекта X».
**Что произойдёт.** Агент выполнит policy preflight и такой же gate, как `promote-dry-run`, но через глобальную корневую точку входа. С `--write-draft` запишет review draft в `plans/`; durable wiki page без явного apply не создаёт.

### `reefiki.py memory promotion-inbox` / review drafts

**Что делает.** Показывает promotion drafts из `plans/`, раскрывает draft для review, применяет или отклоняет его явным действием.
**Когда нужна.** Когда `memory promote --write-draft` уже создал drafts, и нужно закрыть review без ручного поиска файлов.
**Как сказать по-человечески.** «Покажи promotion inbox», «прими этот promotion draft», «отклони этот promotion draft».
**Что произойдёт.** Агент выполнит policy preflight и вернёт список активных drafts или один draft через `--show <path>`. `--apply <path> --yes` создаёт durable wiki page и помечает draft applied. `--reject <path> --reason ... --yes` помечает draft rejected и пишет причину в draft/log. `--prune-closed --yes` переносит закрытые drafts в `plans/closed/`; `--all` показывает active + closed archive.

### `reefiki.py memory golden` / baseline memory checks

**Что делает.** Прогоняет `projects/<name>/golden-queries.yml` как контрольный набор lookup/promote cases.
**Когда нужна.** Перед qmd/vector/graph upgrades, `memory diff` и `memory pack`, чтобы измерять качество на стабильных вопросах.
**Как сказать по-человечески.** «Прогони золотые вопросы REEFIKI».
**Что произойдёт.** Агент вернёт pass/fail по cases и не будет писать wiki/draft-файлы. При работе с REEFIKI 2 агент запускает это сам перед изменениями memory-логики.

### `reefiki.py memory diff` / durable wiki diff

**Что делает.** Показывает git-based diff только по `projects/<name>/wiki/**`.
**Когда нужна.** Перед handoff, pack или review: понять, какие durable pages реально изменились.
**Как сказать по-человечески.** «Покажи, что изменилось в памяти проекта», «что изменилось с 2026-05-21?».
**Что произойдёт.** Агент выполнит policy preflight и вернёт changed files/counts между `--from` и worktree/`--to`, либо с baseline по `--since-date YYYY-MM-DD`.

### `reefiki.py memory reflect` / read-only memory reflection report

**Что делает.** Собирает один review report из существующих gates: `memory diff`, `health`, `review-queues --summary`, `memory status --summary`, `memory pack --strict` и `promotion-inbox`.
**Когда нужна.** Когда оператор вручную склеивает 3+ отчёта, queues/diff/promotion дают шумный next-step или нужен компактный weekly/handoff review без durable write.
**Как сказать по-человечески.** «Собери reflection report», «сведи memory diff, health и очереди в один отчёт».
**Что произойдёт.** Агент выполнит read-only сборку и покажет `candidate_actions`, `blocked_actions`, included/excluded sources. `--write-report` пишет только `plans/reflection-YYYY-MM-DD.md`; wiki/raw/seen/config/git не меняются.

### `reefiki.py memory pack` / task handoff bundle

**Что делает.** Собирает компактный context pack для задачи из durable wiki, quality/strict verdict, golden summary, diff summary и open queues.
**Когда нужна.** Перед новым тредом, handoff другому агенту или сборкой следующего этапа REEFIKI 2.
**Как сказать по-человечески.** «Собери пакет контекста по задаче X».
**Что произойдёт.** Агент выполнит policy preflight, подберёт релевантные wiki pages с `why_included`, покажет quality/strict status, open queues, exclusions и не будет писать файлы. `task_route` показывает классификацию текста задачи, а `assembly_trace.pack_scope` отдельно показывает реальный scope сборки pack. При упоминании REEFIKI 2 агент запускает `memory pack --strict` сам. Storage/index ошибки lookup/golden возвращаются как structured strict fail, а не raw traceback.

## Operator / maintainer-команды

Редкие команды для publish, cleanup, staged scope, secret scan, worktree inventory и evidence matrix вынесены в [docs/OPERATOR_COMMANDS.md](docs/OPERATOR_COMMANDS.md#русский). Для first-run, demo и ежедневной wiki-работы они не нужны.

### `reefiki.py policy-evidence` / explanatory evidence matrix

**Что делает.** Собирает компактные rows из JSON-выводов `guard-staged`, `publish-task --dry-run`, `cleanup-worktree --dry-run`, `secret-scan` и `worktree-status`.
**Когда нужна.** Когда нужно объяснить, почему publish/guard/cleanup разрешён или заблокирован, не повторяя вручную все исходные gate outputs.
**Что произойдёт.** Команда только читает переданные JSON-файлы и показывает evidence pointers. Она не обходит guard, не выдаёт approval и не заменяет исходные gates.

### `reefiki.py confidence-pass` / repeatable maintainer confidence recipe

**Что делает.** Собирает один safe report из `git status`, `orchestration-check`, `doctor`, `review-queues --summary`, `memory golden`, optional `pytest` и `publish-task --dry-run --cleanup`.
**Когда нужна.** Перед publish/cleanup значимого task, чтобы не собирать Full Confidence Pass вручную.
**Что произойдёт.** Без `--include-pytest` вернёт `review` и покажет recipe; с `--include-pytest` прогонит локальный test gate. Команда не stage-ит, не commit-ит, не push-ит и не cleanup-ит текущий worktree; `publish-task --dry-run` может создать временный public snapshot worktree. Delegated verifier не запускается из CLI и остаётся ручным TeamLead шагом.

## Команды проекта — обслуживание

Нужны редко.

### `/lint`

**Что делает.** Проверяет здоровье вики по механическим категориям: битый frontmatter, `id` vs filename, schema_version проекта, дубли, осиротевшие ссылки, истёкшие карантины, устаревшие страницы, пропавшие связи.
**Когда нужна.** Раз в месяц или после большого батча `/process`. Агент сам напомнит после 10 операций `/process`.
**Как сказать по-человечески.** «Проверь здоровье вики», «прогон линта».
**Что произойдёт.** Агент пройдёт по wiki, покажет список проблем по категориям, для каждой предложит fix. Ничего не меняет без подтверждения.
**JSON-режим.** Для CI/агентов можно запускать `scripts/validate_frontmatter.py --format json ...`; ошибки содержат `path`, `code`, `message`, `line`, `column`, `expected`, `actual`.

### `/resolve`

**Что делает.** Закрывает старые конфликты в страницах (блоки `## Conflicting claims` старше 30 дней).
**Когда нужна.** Если `/status` сообщает про невыключенные конфликты, или сам помнишь, что давно был спорный момент.
**Как сказать по-человечески.** «Закрой старые споры», «разреши конфликты в вики».
**Что произойдёт.** Для каждого конфликта старше 30 дней агент покажет старое и новое утверждение, спросит: оставить старое / новое / оба / нужно копнуть. По выбору правит страницу и логирует решение.

### `/reindex`

**Что делает.** Пересобирает `wiki/index.md` из frontmatter всех страниц. **Аварийная команда** — для восстановления.
**Когда нужна.** Индекс рассинхронился с реальными файлами или испорчен.
**Как сказать по-человечески.** «Пересобери индекс», «восстанови оглавление вики».
**Что произойдёт.** Текущий `index.md` сохранится как `index.md.bak`, новый соберётся заново из всех страниц. Битые страницы (без обязательных полей) попадут в отчёт — их нужно чинить вручную или через `/lint`.

## Discovery

### `/help`

**Что делает.** Показывает список команд на простом языке (специально для случая «забыл, что умеешь»).
**Когда нужна.** Запутался; объясняешь кому-то третьему как этим пользоваться.
**Как сказать по-человечески.** «Что ты умеешь?», «помоги», «как этим пользоваться».
**Что произойдёт.** Агент выдаст короткий plain-text список с ежедневными командами и пометкой про обслуживающие. Без модификаций.

## Шпаргалка одним экраном

| Хочу…                          | Команда                 |
| ------------------------------ | ----------------------- |
| Создать новый проект           | `/new <имя>` (из корня) |
| Сохранить ссылку/файл          | `/save <что-то>`        |
| Разобрать копилку              | `/process`              |
| Спросить у вики                | `/query <вопрос>`       |
| Зафиксировать выводы из сессии | `/harvest`              |
| Посмотреть состояние           | `/status`               |
| Проверить здоровье             | `/lint`                 |
| Закрыть старые споры           | `/resolve`              |
| Восстановить индекс            | `/reindex`              |
| Объяснение команд              | `/help`                 |

В 90% случаев хватает `/save` и `/query` — остальное Claude напомнит сам в нужный момент.
