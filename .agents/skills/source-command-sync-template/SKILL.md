---
name: "source-command-sync-template"
description: "Синхронизировать обновления из _template в существующие проекты. Запускать из корня после правок шаблона."
---

# source-command-sync-template

Use this skill when the user asks to run the migrated source command `sync-template`.

## Command Template

# /sync-template — синхронизация шаблона

> Запускать из корня `REEFIKI/` после обновления файлов в `projects/_template/`.

## Что синхронизируется

Только инфраструктурные файлы (не контент проекта):

- `.claude/commands/*.md` — спецификации операций
- `wiki/_schema.md` — формат страниц
- `wiki/_dashboard.md` — Dataview-дашборд (с заменой `PROJECT_NAME` на имя проекта)
- `AGENTS.md` — контракт проекта (с заменой `NAME` на имя проекта)
- `CLAUDE.md` — стаб (с заменой `NAME`)

## Что НЕ синхронизируется

- `_domain.md` — уникален для каждого проекта
- `wiki/index.md`, `wiki/log.md` — содержат данные проекта
- `inbox/`, `raw/`, `seen/`, `wiki/<type>/` — контент

## Шаги

1. Найти все проекты: папки в `projects/`, кроме `_template`.
2. Для каждого проекта показать diff изменённых файлов (кратко: «обновлены N команд, schema, AGENTS.md»).
3. Спросить: «Применить ко всем проектам? (всё / выборочно / отмена)»
4. Для каждого выбранного проекта:
   - Скопировать `.claude/commands/*.md` из `_template`.
   - Скопировать `wiki/_schema.md`.
   - Скопировать `wiki/_dashboard.md` с заменой `PROJECT_NAME` → имя проекта.
   - Скопировать `AGENTS.md` и `CLAUDE.md` с заменой `NAME` → имя проекта.
5. Append в лог каждого затронутого проекта: `## [YYYY-MM-DD] meta | sync-template`.
6. `git add -A ; git commit -m "sync-template to N projects"`.

## Когда запускать

- После любого изменения в `_template/` (новая команда, обновление schema, новый тип страницы).
- Агент может предложить: «Шаблон обновлён, но проекты ещё нет. Запустить синхронизацию?»
