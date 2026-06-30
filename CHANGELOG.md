# CHANGELOG

История заметных изменений REEFIKI. Формат: коротко, по фазам, без пересказа каждого коммита.

## Unreleased

### Fixed

- **Agent-agnostic contract hardening.** Контракт стал одинаково понятен всем LLM-агентам, не только GPT 5.4.
  - Созданы spec-файлы для `review-queues` и `promote-dry-run` (были в таблице операций без спецификации — агент падал при попытке прочитать spec).
  - `git add -A` заменён на `git add` конкретных путей в `/process`, `/lint`, `/reindex`, `/resolve` (и в шаблоне). Раньше агент мог закоммитить чужие dirty changes.
  - Добавлены fallback-процедуры для `reefiki.py` в `/query`, `/harvest`, `/status`. Теперь агент без CLI-скрипта может работать вручную.
  - Создан `.clinerules` stub для Cline/Roo Cline (единственный vendor без stub-файла).
  - Заполнен Serena `initial_prompt` (Serena-агент теперь автоматически загружает контракт).
  - Исправлен drift `.agents/skills/source-command-new` (не заменял `PROJECT_NAME`).
  - Документирован формат `plans/*.md` (`plans/README.md`).
  - Обновлён корневой `AGENTS.md`: дерево репо теперь показывает все vendor stubs.

### Added

- REEFIKI 2.0: добавлен global memory control plane поверх `memoir`, durable REEFIKI wiki и `graphify`.
- Добавлены команды `memory status`, `memory preflight`, `memory route`, `memory lookup`, `memory promote`, `memory golden`, `memory diff`, `memory pack --strict`.
- Добавлены README-схемы REEFIKI 2.0 control plane для RU/EN/ZH.
- Добавлен startup contract: при упоминании REEFIKI 2 агент сам запускает `memory pack --strict` и `memory golden`.
- Добавлен локальный CLI `scripts/reefiki.py` для операций `index`, `search`, `privacy`, `status`, `timeline`, `plan create`, `plan check`.
- Добавлен пересобираемый SQLite FTS5 индекс `.reefiki/index.sqlite` поверх `wiki/*.md`; markdown остаётся источником истины.
- `/query` переведён на progressive disclosure: сначала top-K поиск, затем нужные страницы, затем timeline/полная страница по запросу.
- В поиск добавлен provenance: страница, sources и sha256 содержимого.
- Добавлены рабочие plan-файлы `plans/<task>.md` с checksum recovery для длинных задач.
- Добавлены `plans/.gitkeep` в template и проект `reefiki`.

### Changed

- README обновлён под REEFIKI 2.0: три слоя памяти, strict handoff, golden checks и public/private workflow.
- README-визуалы исправлены под REEFIKI 2.0; в источники идеи добавлены ссылки на Memex, Obsidian, memoir и graphify.
- `/save` и `/process` усилены privacy guard: секреты, forbidden dirs, бинарники и файлы >5 MB блокируются до обработки.
- `/process` и `/harvest` теперь пересобирают локальный индекс после изменений wiki.
- `/status` показывает состояние локального поиска и активных планов.
- `/harvest` перед записью выводов учитывает активные планы и последние записи timeline.
- `ROADMAP.md` и `TASKS.md` обновлены Phase 0g и отложенными задачами MCP/REST и vector/graph слоя.
- ASCII-диаграммы в README заменены на SVG-картинки в едином тёмном стиле Catppuccin Mocha. ASCII-таблицы заменены на Markdown-таблицы.

### Removed

- **Удалены пилоты Dream Review и MYBD board.** Оба были обёртками над существующими командами (`memory status`, `memory diff`, `review-queues`) без уникальной ценности. Dream Review — after-action отчёт из operational traces, MYBD board — SQLite-зеркало memory status. Замена: `/harvest` для реальных кандидатов, `review-queues` для stale/orphan, `memory status` для состояния.
  - Удалены: `scripts/reefiki_dream_review.py`, `scripts/reefiki_mybd_pilot.py`, `docs/DREAM_REVIEW_PILOT.md`, `docs/MYBD_PILOT.md`.
  - Удалены подкоманды `memory dream-review` и `memory ops-refresh` из `scripts/reefiki.py`.
  - Удалены тесты: `test_reefiki_dream_review.py`, `test_reefiki_mybd_pilot.py`, `test_reefiki_ops_refresh.py`.
  - Удалена MYBD SQLite база `.reefiki/mybd-board/table-manager.db`.
  - Убраны упоминания из README (RU/EN/ZH-CN), COMMANDS.md, CHANGELOG.md.

### Deferred

- MCP/REST API отложен до стабильного локального `/query` и provenance.
- Vector/graph search layer отложен до реальных промахов FTS5.
- Auto-forgetting, decay и team/shared memory не внедряются без отдельного решения.

## 2026-05-10

### Added

- Добавлены README-визуалы и локализованные README: RU, EN, ZH.
- Добавлена процедура безопасного public snapshot через `scripts/push-public.ps1`.

### Changed

- README стал более понятным для первого знакомства: workflow, команды, Obsidian, public/private model.
- Wiki integrity обновлена после README/public-snapshot работ.

### Security

- Public push переведён на filtered snapshot: приватные проекты исключаются через `scripts/public-snapshot.private-projects.txt`.
- `push-public.ps1` использует `--force-with-lease` и интерактивное подтверждение.

## 2026-05-09

### Added

- Sprint 5 audit fixes: security, integrity, template drift, validator.
- `validate_frontmatter.py` усилен проверкой `index.md`: `Total pages`, секции, missing files, forbidden `importance`.
- Добавлена поддержка `skills` в integrity semantics.

### Changed

- Template и живые проекты синхронизированы по command specs и dashboard.
- Root/project `AGENTS.md` приведены к более строгому режиму чтения правил перед работой.

## 2026-05-02

### Added

- Добавлен `scripts/push-public.ps1` и public remote workflow.
- В ROADMAP/TASKS зафиксирован разбор graphify как отложенного/условного слоя.

### Fixed

- Исправлен cleanup public snapshot workflow после force checkout.

## 2026-05-01

### Added

- Sprint 1: integrity gate: frontmatter validator, pre-commit, `.gitignore`, save dedupe spec.
- Sprint 2: agent metrics: harvest trigger logging, query relevance tracking, resolve supersession.
- Sprint 3: Obsidian Dataview dashboard.
- Sprint 4: mobile capture через GitHub Actions/Pipedream flow.
- `wiki/skills/` и тип `skill` для воспроизводимых процедур.
- `TASKS.md` и фазовый `ROADMAP.md` после research audit.

### Changed

- Проект переименован из `reef` в `reefiki`.
- Команды `/save`, `/process`, `/query`, `/harvest`, `/status`, `/lint`, `/resolve`, `/reindex` оформлены как agent-readable specs.
- Wiki schema закрепила обязательный `useful_when`.

### Fixed

- Исправлены Dataview dashboard queries.
- Исправлены env vars в workflow для Unicode note support.

## 2026-04-30

### Added

- Начальный README с connect workflow, Obsidian section и ASCII diagrams.
- Первые wiki-страницы и проектная структура REEFIKI.
