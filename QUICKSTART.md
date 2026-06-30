# QUICKSTART

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Короткий старт для REEFIKI без знания деталей команд.

## English

Quick start for REEFIKI without learning command details.

1. Install or open a checkout.
2. Run `reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json`.
3. Run `reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json`.
4. Run `reefiki --project /tmp/reefiki-workspace/projects/first-run status`.
5. Then use `reefiki onboarding --lang en`, the dashboard demo, or an explicit code-project bridge.

The detailed canonical runbook continues below in Russian.

## 中文

REEFIKI 快速开始，不需要先学习命令细节。

1. 安装 CLI，或打开 checkout。
2. 运行 `reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json`。
3. 运行 `reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json`。
4. 运行 `reefiki --project /tmp/reefiki-workspace/projects/first-run status`。
5. 然后再运行 onboarding、dashboard demo，或显式连接代码项目。

下面继续保留俄语的详细 canonical runbook。

## 1. Открой REEFIKI

### CLI-first: создать первый workspace

`reefiki init` создаёт минимальную локальную REEFIKI-вики из встроенных шаблонов. Это первый путь после установки: сначала реальный workspace и health check, потом демо или подключение к коду.

Если CLI установлен:

```powershell
pipx ensurepath
Get-Command reefiki
where.exe reefiki
reefiki --help
reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run status
reefiki --project C:\Temp\reefiki-workspace\projects\first-run import C:\Temp\my-notes --from markdown --format json
```

Если `Get-Command reefiki` не находит команду после `pipx ensurepath`, открой новый терминал и повтори проверку.

POSIX:

```bash
reefiki --help
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run status
reefiki --project /tmp/reefiki-workspace/projects/first-run import /tmp/my-notes --from markdown --format json
```

Если `reefiki` не найден в shell, используй запасной запуск из папки репозитория:

```powershell
python scripts\reefiki.py init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
python scripts\reefiki.py --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
python scripts\reefiki.py --project C:\Temp\reefiki-workspace\projects\first-run status
```

`reefiki init` не перезаписывает существующий проект. Bridge в кодовый проект создаётся только если ты явно добавил `--code-project ... --apply-bridge`.

Если у тебя уже есть папка с Markdown, Obsidian или Logseq заметками, начни не с автосоздания wiki-страниц, а с безопасного импорта в копилку:

```powershell
reefiki --project C:\Temp\reefiki-workspace\projects\first-run import C:\Temp\my-notes --from obsidian --format json
```

```bash
reefiki --project /tmp/reefiki-workspace/projects/first-run import /tmp/my-notes --from markdown --format json
```

Команда кладёт `.md` файлы в `inbox/`, пропускает секреты и подозрительные пути, а потом обычный `/process` решает, что действительно достойно durable wiki.

### Demo после первого workspace

Когда health check прошёл, можно посмотреть demo route:

```powershell
reefiki onboarding
reefiki onboarding --fixture-root C:\Temp\reefiki-demo
reefiki --project C:\Temp\reefiki-demo\projects\reefiki-onboarding-demo status
reefiki ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
reefiki ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

Открой `http://127.0.0.1:7310/`. Это локальная read-only доска: она показывает только demo workspace и не публикует ничего наружу.

### Agent-first: работать с настоящим проектом

Открой папку `REEFIKI/` в Codex, Claude Code, Cursor, Windsurf или другом агенте, который читает `AGENTS.md`.

Если агент находится в корне REEFIKI, это диспетчерский режим: здесь создают или подключают проекты, но не пишут wiki-страницы напрямую.

Если проект относится к agent/IDE/runtime окружению, скажи это сразу:

```text
Создай проект codex как agent/runtime surface
Подключи H:\Projects\CODEX к REEFIKI как agent surface
```

Так агент будет сохранять rules, adapters, diagnostics, provider notes и recovery procedures как переносимую память, но не будет объединять wikis разных проектов. Подробнее: [docs/PROJECT_PROFILES.md](docs/PROJECT_PROFILES.md).

## 2. Создай или подключи проект

CLI-путь для новой вики:

```powershell
reefiki init --workspace C:\Temp\my-reefiki --project-name metrica --title "Product Analytics" --profile product
```

Если уже есть кодовый проект, скажи агенту:

```text
Подключи проект H:\Projects\MyApp к вики
```

Агент создаст wiki-проект и ссылку `_wiki/` в кодовом проекте.

CLI-путь для явного bridge:

```powershell
reefiki init --workspace C:\Temp\my-reefiki --project-name my-app --code-project H:\Projects\MyApp --apply-bridge --format json
reefiki connect-check H:\Projects\MyApp --format json
```

Если проекта ещё нет, скажи:

```text
Создай новый проект metrica про продуктовую аналитику
```

Агент создаст папку `projects/metrica/` из шаблона.

## 3. Работай бытовыми фразами

| Что хочешь | Как сказать |
|---|---|
| Сохранить ссылку на потом | "положи это в копилку" |
| Разобрать сохранённое | "разбери копилку" |
| Зафиксировать решение | "запомни это как решение" |
| Сохранить повторяемый приём | "сохрани как навык" |
| Поднять старое знание | "что у нас по sync?" |
| Проверить состояние | "покажи статус" |

Агент сам выберет нужную операцию и обновит wiki/log/index там, где это положено.

## 4. Что где лежит

| Папка | Простое значение |
|---|---|
| `inbox/` | копилка: сохранено, но ещё не разобрано |
| `wiki/` | долговременная база знаний проекта |
| `seen/` | отложено или отказано с причиной |
| `raw/` | неизменяемый архив исходников |
| `plans/` | рабочие заметки и материалы на проверку |

Не редактируй `raw/`. Старые строки в `wiki/log.md` тоже не переписываются: новые события добавляются в конец.

## 5. Проверь здоровье перед важной работой

Перед публикацией, большим разбором копилки или восстановлением после сбоя попроси:

```text
сделай health check проекта
```

Агент проверит индекс, структуру wiki, битые ссылки, зависшие элементы в копилке и очереди на ручной разбор.

## 6. Obsidian и мобильный capture

- Настрой Obsidian по [docs/obsidian-setup.md](docs/obsidian-setup.md).
- Для сохранения ссылок с телефона смотри [docs/mobile-capture.md](docs/mobile-capture.md).
- Для восстановления после проблем смотри [docs/RECOVERY.md](docs/RECOVERY.md).
- Полная карта команд и возможностей — в [COMMANDS.md](COMMANDS.md).

Главное правило: REEFIKI лучше работает, когда агент пишет durable pages, а Obsidian используется как viewer/editor с осторожностью.
