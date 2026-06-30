# Schema — форматы записей

Читай только когда создаёшь/правишь страницу.

## Project schema version

`_domain.md` содержит project-level frontmatter `schema_version: "1.0"`. Это версия схемы проекта, а не поле каждой wiki-страницы. Validator блокирует отсутствующую или неподдержанную версию, чтобы будущие миграции были явными.

## Frontmatter wiki-страницы

| Поле | Тип | Обязательно | Заметки |
|---|---|---|---|
| `id` | string | да | == имя файла без `.md`, kebab-case. Validator блокирует mismatch. Для URL/репо вычисляется по правилу `source_id` (см. `process.md`) для дедупликации. |
| `type` | enum | да | `source` \| `entity` \| `concept` \| `synthesis` \| `decision` \| `skill` |
| `title` | string | да | человекочитаемый |
| `abstract` | string | нет | L0 summary: 1-2 предложения для `/query`, чтобы сначала читать краткое резюме, а не всю страницу |
| `tags` | list | да | минимум 1 |
| `useful_when` | list | **да** | ≥1 конкретный сценарий применения — без этого поля страница не создаётся |
| `sources` | list | для `source`/`synthesis` | имена файлов из `raw/` или URL |
| `verified` | YYYY-MM-DD \| null | для `skill` | дата последней проверки процедуры |
| `date_added` | YYYY-MM-DD | да | |
| `use_count` | int | да | стартует с 0, +1 в `/query` (батчится в ближайший `/process`/`/lint`/`/harvest`) |
| `last_used` | YYYY-MM-DD \| null | да | обновляется вместе с `use_count` |

## Confidence markers for links

В теле страницы допустимы короткие маркеры уверенности для ссылок и связей:

- `[EXTRACTED]` — связь прямо взята из источника или существующей страницы.
- `[INFERRED]` — связь выведена из контекста, но не названа явно.
- `[AMBIGUOUS]` — связь возможна, но требует ручной проверки.

Маркер нужен только там, где он помогает понять качество связи. Это подсказка для чтения и triage, а не отдельное поле и не автозаполнение.

## Правило валидности

Страница валидна, если `useful_when` содержит ≥1 конкретный сценарий применения — не `TBD`, не «может пригодиться».

Знание без сценария применения = заметка, не wiki-страница. Это главный фильтр против разрастания «мысии».

Если на `/process` `useful_when` сформулировать не получается:

1. Спроси пользователя одной фразой: «Когда эта страница пригодится?»
2. Если молчит / «не знаю» → отправь источник в `seen/` с `reason: unclear-use`. Не сохраняй в wiki.

`abstract` должен отвечать на вопрос "о чём эта страница и когда её читать" без пересказа всей страницы. Если кратко сформулировать нельзя — поле лучше не добавлять.

`related`/`[[Related]]` — расставляются в теле страницы в секции `## Related`. Во frontmatter не дублируются.

Если новая или обновлённая страница получает 3+ ссылок на уже существующие страницы, перед closeout нужен короткий review на reciprocal vs intentional one-way кандидатов. Это review only: не добавлять обратные ссылки автоматически.

Для новых страниц предпочитай source-side фиксацию: если новая страница ссылается на старую и reciprocal backlink не нужен, отметь связь прямо в её `## Related` строке как `intentional one-way` или добавь старый page id в `## Intentional one-way outbound links`. Старый target page править не обязательно.

## Тело страницы

Базовые секции для всех типов:

- `## Суть` — что и как (2–4 предложения)
- `## Дельта` — что уникального относительно wiki
- `## Применение` — конкретный сценарий
- `## Conflicting claims` — только при конфликте: каждый блок начинается со строки `[YYYY-MM-DD]` (дата фиксации), затем `<тезис new> (source: new) vs <тезис old> (source: old)`. Закрывается через `/resolve` после ≥30 дней.
- `## Related` — `[[slug]] — короткое объяснение связи`
- Для intentional one-way связей добавляй фразу `intentional one-way` в `## Related` строку или используй секцию `## Intentional one-way outbound links`. Секция `## Intentional one-way inbound links` остаётся для legacy/manual случаев, когда решение фиксируется на target page.

**Для `source`** дополнительно: `## Ключевые тезисы` (3–7 пунктов) и `## Цитата-ссылка: raw/<file> (lines X–Y)`.

**Для `decision` (ADR)** тело заменяется на: `## Контекст` / `## Варианты` / `## Решение` / `## Последствия`.

**Для `skill`** тело заменяется на: `## Когда применять` / `## Шаги` (нумерованный список) / `## Проверено` (дата + где проверено). Опционально: `## Подводные камни`.

## Запись в `seen/`

```yaml
---
source: <filename или URL>
date: YYYY-MM-DD
reason: duplicate | off-topic | low-value | no-access | unclear-use
duplicate_of: <slug>   # только если reason=duplicate
quarantine_until: YYYY-MM-DD   # date + 30 дней
---
```

По истечении `quarantine_until` запись попадает в отчёт `/status` (истёкшие). Пересмотр — manual: вернуть источник в `inbox/` или продлить `quarantine_until` в `seen/<slug>.md`. Без auto-renewal.

## Запись в `wiki/index.md`

```markdown
### <id>
- type: <type>
- tags: [...]
- useful_when: ["..."]
- file: wiki/<subdir>/<id>.md
- date_added: YYYY-MM-DD
- use_count: N
```

Группировка по типам: `## Sources`, `## Entities`, `## Concepts`, `## Synthesis`, `## Decisions`, `## Skills`.

## Лог

Append-only: `## [YYYY-MM-DD] <op> | <краткий результат>`. `op` ∈ `/save | /process | /query | /harvest | /lint | /status | /new | /reindex | /resolve | conflict | refactor | meta`.

## Имена

- Wiki-страницы и файлы в `raw/`: `lowercase-with-hyphens` + расширение.
- Wiki-ссылки: `[[lowercase-with-hyphens]]`.
- `id` == имя файла без `.md`.
