---
description: Подключить кодовый проект к REEFIKI. Создаёт junction, маркер и wiki-проект если нужно. Запускать из корня.
---

# /connect [путь-к-проекту] [имя-проекта]

Аргументы:
- `[путь-к-проекту]` — абсолютный путь к кодовому проекту (например, `H:\Projects\MyApp`). Если не указан, используй текущую рабочую папку как кодовый проект.
- `[имя-проекта]` — опционально, kebab-case. Если не указано — берётся имя папки в lower-case.

Важно: `/connect` всегда означает «подключить кодовый проект к REEFIKI». Это не команда для «поднять контекст» и не `/query`.

Важно: файл лежит в `.claude/` исторически, но это vendor-neutral spec. Его должны одинаково применять Codex, Claude Code, Cursor, Windsurf, Gemini, Mimo и другие агенты, которые читают `AGENTS.md`.

## Шаги

1. **Проверки.**
   - Найди REEFIKI root: текущий cwd, родительские папки, `.reefiki` marker или известный путь из project knowledge. Root валиден только если в нём есть `projects/_template/` и `AGENTS.md`.
   - Если root не найден → спроси один блокирующий вопрос: «Где находится корень REEFIKI?».
   - Определи code project path: аргумент команды или текущий cwd.
   - Если code project path совпадает с REEFIKI root → остановись: из корня REEFIKI `/connect` требует путь к внешнему кодовому проекту.
   - Если путь не существует → сообщи и остановись.
   - Если `<путь>/_wiki` уже существует → проверь, что это junction/symlink на `REEFIKI/projects/<имя>`. Если да — сообщи: «Этот проект уже подключён. Вики доступна в `_wiki/`». Если нет — остановись и не перезаписывай.

2. **Определить имя проекта.**
   - Из аргумента или из имени папки (lower-case, пробелы → дефисы).
   - Если пользователь явно говорит `agent surface`, `agent/runtime`, `IDE/runtime`, `product` или `knowledge domain`, используй это как ручной project profile в описании домена и финальном ответе. Не добавляй обязательное schema-поле `project_kind`.

3. **Создать wiki-проект если нет.**
   - Если `projects/<имя>/` не существует → создать из `projects/_template/` по логике `/new`.
   - Если пользователь уже дал домен в текущем контексте, заполни `_domain.md` из него. Если нет — задай только 3 вопроса из `/new`.
   - Если существует → пропустить.
   - После создания или первого подключения пересобери локальный индекс и проверь проект:
     - `python scripts/reefiki.py --project projects/<имя> index`
     - `python scripts/reefiki.py --project projects/<имя> doctor`

4. **Создать junction.**
   - Windows: `cmd /c mklink /J "<путь>\_wiki" "<REEFIKI>\projects\<имя>"`
   - Linux/macOS: `ln -s "<REEFIKI>/projects/<имя>" "<путь>/_wiki"`

5. **Зафиксировать git-bridge contract в кодовом проекте.**
   - В `.gitignore` кодового проекта добавить `_wiki/` и `.reefiki`, если их там ещё нет.
   - Если `_wiki/**` уже tracked в кодовом repo, вывести их из индекса (`git rm --cached -r _wiki`) без удаления локальных файлов.
   - Канон: `_wiki/` — только bridge/junction для чтения и локальной работы, не часть git-истории кодового проекта.
   - После ручной или автоматической правки проверь contract read-only:
     - `python scripts/reefiki.py connect-check "<путь>" --format json`
   - `connect-check` не меняет кодовый проект: для git repo он проверяет ignore coverage и tracked leakage по `_wiki/` / `.reefiki`; для non-git repo честно помечает git-check как not applicable.

6. **Обновить шаблонные поля и `_domain.md`.**
   - Заменить шаблонные `PROJECT`, `NAME`, `PROJECT_NAME` в `AGENTS.md`, `CLAUDE.md`, `_domain.md`, `wiki/index.md`, `wiki/log.md`, `wiki/_dashboard.md`.
   - Добавить в `_domain.md` секцию `## Кодовый проект` с путём и описанием junction, если секции ещё нет.
   - В `_domain.md` не записывать персональные absolute paths из home/profile/cache, если это не сам подключаемый project path. Для Codex home/user profile пиши нейтрально: `Global Codex home`, `local Codex profile`, `user-level Codex config`.

7. **Создать маркер `.reefiki`** в корне кодового проекта:

   ```yaml
   # REEFIKI connection marker
   # Этот файл сообщает агенту, что проект подключён к персональной базе знаний.
   REEFIKI_path: <абсолютный путь к REEFIKI>
   project_name: <имя>
   wiki_junction: _wiki
   ```

   После создания marker повтори `connect-check`, если до этого marker ещё не существовал.

8. **Добавить wiki-инструкции в AGENTS.md кодового проекта** (если файл существует).
   Вставить в конец файла (перед `## Запреты` если есть, иначе в самый конец):

   ```markdown
   ## Персональная база знаний (REEFIKI)

   Этот проект подключён к REEFIKI — персональной distillation-вики.
   Вики доступна в `_wiki/` (junction). Правила работы — в `_wiki/AGENTS.md`.

   **Git contract:**
   - `_wiki/` — только bridge/junction для чтения и локальной работы, не часть git-истории этого кодового проекта.
   - durable knowledge changes из `_wiki/**` коммитить и пушить только в repo `REEFIKI`, не в этот кодовый repo.
   - в кодовом repo коммитить только код, локальные docs и bridge contract (`AGENTS.md`), но не `_wiki/**`.
   - `.reefiki` marker держать локальным и не пушить.

   **Порядок работы:**
   - перед поиском в коде сначала читай локальные docs, если они есть;
   - затем читай релевантные страницы в `_wiki/`;
   - только после этого переходи к коду.

   **Что сохранять в вики (автоматически предлагай):**
   - Архитектурные решения → `_wiki/wiki/decisions/`
   - Найденные паттерны и концепты → `_wiki/wiki/concepts/`
   - Проверенные пошаговые процедуры → `_wiki/wiki/skills/`
   - Выводы из длинных сессий → `_wiki/wiki/synthesis/`

   **Что НЕ сохранять:** код, конфиги, node_modules, бинарники. Только знания.

   **Триггеры:**
   - «Сохрани в вики» / «запомни» → выполнить save/harvest в `_wiki/`
   - Принято архитектурное решение → предложить записать
   - Отлажен сложный баг → предложить сохранить как навык
   - Конец длинной сессии → предложить harvest

   **Перед завершением задачи:** если в `_wiki/` есть относящееся к работе знание, сначала используй его, потом отвечай.
   ```

   Если подключаемый проект — agent/IDE/runtime surface (например Codex, Claude Code, Gemini, Mimo, Hermes), добавь в ту же секцию короткий блок:

   ```markdown
   **Agent surface profile:**
   - сохраняй переносимые rules, adapters, diagnostics, provider/runtime notes и recovery procedures в REEFIKI;
   - не объединяй wiki этого проекта с другими agent/runtime проектами;
   - не копируй skills автоматически без explicit decision и проверки совместимости.
   ```

   Если `AGENTS.md` не существует — создать минимальный с этой секцией.

9. **Лог и коммит.**
   - Append в `projects/<имя>/wiki/log.md`: `## [YYYY-MM-DD] meta | connected to <путь>`
   - Если пишешь в REEFIKI repo, stage только файлы нового/изменённого `projects/<имя>/` и command/docs, не чужие dirty changes.
   - Коммит делай только если пользователь просил коммит/пуш или это явно принято для текущего потока.

10. **Финал.** Сказать:
   > Готово. Проект подключён к вики. Теперь при работе в `<путь>` агент видит `_wiki/` и может сохранять знания. Просто скажи «запомни это» или «сохрани решение» — и оно попадёт в вики.

   Для non-git проектов не требуй Ops Dashboard как обязательное доказательство подключения: dashboard может не показать папку без git-сигнала. Достаточно `_wiki` junction, `.reefiki` marker, успешного `detect`, `status` и `doctor`.
