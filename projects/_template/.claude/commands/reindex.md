---
description: Пересобрать wiki/index.md из frontmatter всех страниц. Восстановление после порчи.
---

# /reindex — rebuild index.md

Когда `wiki/index.md` побит, ушёл из синхронизации с файлами или потерян — собери его заново из frontmatter всех страниц `wiki/<sub>/*.md`.

Эта команда **не правит сами страницы**. Только перезаписывает `index.md`.

## Шаги

1. Сделать бэкап: переименовать текущий `wiki/index.md` → `wiki/index.md.bak` (если файл существует).
2. Собрать список всех `wiki/sources/*.md`, `wiki/entities/*.md`, `wiki/concepts/*.md`, `wiki/synthesis/*.md`, `wiki/decisions/*.md`, `wiki/skills/*.md`.
3. Для каждого файла прочитать frontmatter. Если `id`, `type`, `tags`, `useful_when`, `date_added` отсутствуют — добавить файл в отчёт «битые страницы», не включать в индекс.
4. Сгруппировать по `type` в порядке: `## Sources` → `## Entities` → `## Concepts` → `## Synthesis` → `## Decisions` → `## Skills`.
5. Внутри группы — сортировка по `id` (алфавит).
6. Записать в `wiki/index.md` каждую запись по формату из `wiki/_schema.md`:

   ```markdown
   ### <id>
   - type: <type>
   - tags: [...]
   - useful_when: ["..."]
   - file: wiki/<subdir>/<id>.md
   - date_added: YYYY-MM-DD
   - use_count: N
   ```

7. Append в `wiki/log.md`: `## [YYYY-MM-DD] /reindex | rebuilt index from N pages, M broken`.
8. Добавить в stage только явные затронутые пути: пересобранный `wiki/index.md`, дополненный `wiki/log.md` и `wiki/index.md.bak`, если бэкап был создан или обновлён; затем `git commit -m "<project>: reindex (N pages, M broken)"`.
9. Пользователю по-человечески:

   ```text
   Индекс пересобран: N страниц.
   Старая копия — в wiki/index.md.bak.
   Битые страницы (без обязательных полей): M (см. список ниже).
   ```

   Список битых — c путями. Не правь их в `/reindex` — это задача `/lint` (категория `FORMAT`) или ручная.

## Ограничения

- НЕ пересобирает телеметрию: `use_count`/`last_used` берутся как есть из frontmatter каждой страницы.
- НЕ удаляет `index.md.bak` — пользователь сам решит после сверки.
- НЕ создаёт новые страницы и не правит старые.
