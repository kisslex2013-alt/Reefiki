# Dashboard

> Требует плагин Dataview. Авто-обновляется при открытии.

---

## Битые страницы (нет useful_when)

```dataview
TABLE title, type, date_added
FROM "projects/PROJECT_NAME/wiki"
WHERE !useful_when OR useful_when = ""
AND file.name != "_dashboard" AND file.name != "_schema" AND file.name != "index" AND file.name != "log"
SORT date_added ASC
```

---

## Кандидаты на архивацию (use_count = 0, старше 60 дней)

```dataview
TABLE title, type, date_added, use_count
FROM "projects/PROJECT_NAME/wiki"
WHERE ((use_count = 0) OR (!use_count)) AND date(date_added) < date(today) - dur(60 days)
AND file.name != "_dashboard" AND file.name != "_schema" AND file.name != "index" AND file.name != "log"
SORT date_added ASC
```

---

## Навыки без проверки (verified = null или не задан)

```dataview
TABLE title, verified, date_added
FROM "projects/PROJECT_NAME/wiki/skills"
WHERE !verified OR verified = ""
SORT date_added ASC
```

---

## Изолированные страницы (нет входящих ссылок)

```dataview
TABLE title, type
FROM "projects/PROJECT_NAME/wiki"
WHERE length(file.inlinks) = 0
AND file.name != "_dashboard" AND file.name != "_schema" AND file.name != "index" AND file.name != "log"
AND type
SORT type ASC
```

---

## Backlinks count

```dataview
TABLE title, type, length(file.inlinks) AS "in", length(file.outlinks) AS "out"
FROM "projects/PROJECT_NAME/wiki"
WHERE type
AND file.name != "_dashboard" AND file.name != "_schema" AND file.name != "index" AND file.name != "log"
SORT length(file.inlinks) ASC, length(file.outlinks) ASC
```

---

## Cross-reference density

```dataview
TABLE title, type, length(file.outlinks) AS "outlinks", file.size AS "bytes"
FROM "projects/PROJECT_NAME/wiki"
WHERE type
AND file.name != "_dashboard" AND file.name != "_schema" AND file.name != "index" AND file.name != "log"
SORT length(file.outlinks) ASC, file.size DESC
```

---

## Content freshness

```dataview
TABLE title, type, date_added, last_used, verified
FROM "projects/PROJECT_NAME/wiki"
WHERE type
AND file.name != "_dashboard" AND file.name != "_schema" AND file.name != "index" AND file.name != "log"
AND (
  date(date_added) < date(today) - dur(90 days)
  OR (last_used AND date(last_used) < date(today) - dur(90 days))
  OR (verified AND date(verified) < date(today) - dur(90 days))
)
SORT date_added ASC
```

---

## Краткие страницы (< 150 слов)

```dataview
TABLE title, type, file.size AS "размер (байт)"
FROM "projects/PROJECT_NAME/wiki"
WHERE file.size < 800
AND file.name != "_dashboard" AND file.name != "_schema" AND file.name != "index" AND file.name != "log"
SORT file.size ASC
```

---

## Статистика проекта

```dataview
TABLE WITHOUT ID
  length(rows) AS "всего страниц",
  length(filter(rows, (r) => r.type = "source")) AS source,
  length(filter(rows, (r) => r.type = "entity")) AS entity,
  length(filter(rows, (r) => r.type = "concept")) AS concept,
  length(filter(rows, (r) => r.type = "synthesis")) AS synthesis,
  length(filter(rows, (r) => r.type = "decision")) AS decision,
  length(filter(rows, (r) => r.type = "skill")) AS skill
FROM "projects/PROJECT_NAME/wiki"
WHERE type
GROUP BY true
```
