# Claude Code — REEFIKI (root)

Полный контракт репозитория: **`AGENTS.md`** в этой же папке. Прочитай его — там структура, операции, принципы, безопасность, стиль общения.

Этот файл — только Claude-specific дополнение для корневого режима.

## Корневой режим (cwd = REEFIKI/)

В начале сессии:

1. Найди папки проектов (всё в `projects/`, кроме `_template`).
2. Скажи: «У тебя есть проекты: [список]. Создать новый (`/new <имя>`) или перейти в существующий?»

Из корня доступны только: `/new`, `/connect`, `/sync-template`, cross-project поиск по index.md, аудит структуры. Остальные команды (`/save`, `/process`, `/query`, …) — только внутри проекта.

## Slash-команды Claude CLI

В корне: `.claude/commands/new.md`, `.claude/commands/connect.md`, `.claude/commands/sync-template.md`.
В проекте: `projects/<name>/.claude/commands/<op>.md` — `/save`, `/process`, `/query`, `/harvest`, `/lint`, `/status`, `/reindex`, `/resolve`, `/help`.
