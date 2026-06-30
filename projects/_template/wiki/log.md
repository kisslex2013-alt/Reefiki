# Log — PROJECT

Append-only журнал операций.

Формат: `## [YYYY-MM-DD] <op> | <краткий результат>`. Op ∈ `/save | /process | /query | /harvest | /lint | /status | /new | /reindex | /resolve | conflict | refactor | meta`.

Чтобы посмотреть последние записи — найди в этом файле строки, начинающиеся с `## [`, и возьми последние N. Инструмент выбери сам (grep / Select-String / ripgrep — что доступно в текущей оболочке).

---
