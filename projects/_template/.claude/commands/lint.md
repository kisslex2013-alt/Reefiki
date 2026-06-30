---
description: Проверка здоровья wiki. Запускать раз в N /process или по запросу.
---

# /lint — health check

> Правила валидности — в `wiki/_schema.md`.

## Категории

Только механические проверки. Семантика (похожие страницы, недостающие концепты, разрешение конфликтов) — не задача `/lint`.

| # | Имя | Условие | Fix |
|---|---|---|---|
| 1 | ORPHANS | Файл в `wiki/<sub>/` не упомянут в `index.md` | auto: добавить запись |
| 2 | INDEX_MISMATCH | Запись в `index.md` ссылается на несуществующий файл | auto: удалить запись |
| 3 | BROKEN_LINKS | `[[slug]]` ведёт в никуда | manual |
| 4 | FORMAT | Нет обязательных полей frontmatter (см. `wiki/_schema.md`), `id` не совпадает с именем файла, `_domain.md` не содержит поддерживаемый `schema_version`, или в `index.md` есть запрещённые/устаревшие поля (`importance`) | auto где значение выводится (`use_count: 0`, `last_used: null`, пересборка `index.md`); иначе manual |
| 5 | SEEN_DUPLICATES | Файл в `inbox/` совпадает с записью в `seen/` (по `source_id`/имени) | auto: удалить из `inbox/` |
| 6 | STALE | `use_count: 0` И `date_added` > 60 дней | manual: keep / delete / уточнить `useful_when` |

## Вывод

```text
Lint Report — YYYY-MM-DD
Total: N pages | Sources A | Entities B | Concepts C | Synthesis D | Decisions E | Skills F

ORPHANS (n):         <list>
INDEX_MISMATCH (n):  <list>
BROKEN_LINKS (n):    <list>
FORMAT (n):          <list>
SEEN_DUPLICATES (n): <list>
STALE (n):           <list>

Итого: N проблем. Безопасных автофиксов: M.
```

Затем спросить по-человечески: «Применить безопасные автофиксы? Остальное покажу — решишь сам».

## После

1. Применить выбранные автофиксы.
2. Обновить `wiki/index.md` из текущих frontmatter. Индекс не должен содержать `importance`; `Total pages` должен совпадать с числом реальных страниц.
3. Append в лог: `## [YYYY-MM-DD] /lint | N issues found, M auto-fixed`.
4. Добавить в stage только явные пути, затронутые этим lint run: исправленные wiki-страницы, `wiki/index.md`, `wiki/log.md` и пересобранные `.reefiki` artifacts если они были; затем `git commit -m "<project>: lint fixes (N issues)"`. Будущий машинный guard должен использовать docs/wiki maintenance profile, а не broad staging.
