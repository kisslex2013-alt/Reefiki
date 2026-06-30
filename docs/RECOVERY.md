# RECOVERY

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Runbook для восстановления REEFIKI после типовых проблем.

## English

Recovery runbook for common REEFIKI problems.

First rule: if there is any risk of data loss, stop and inspect before changing anything. Do not run `git reset --hard`, do not delete worktrees, do not publish a public snapshot, and ask the agent to show `git status`, recent commits, and changed files.

Common cases covered below in Russian: corrupt local SQLite index, deleted wiki page, broken frontmatter, lost local repository, accidental private publication, and backup strategy.

## 中文

REEFIKI 常见问题恢复 runbook。

第一条规则：如果有数据丢失风险，先停止并检查，不要直接修改。不要运行 `git reset --hard`，不要删除 worktree，不要发布 public snapshot，并让代理先显示 `git status`、最近 commit 和已修改文件。

下面俄语 canonical 部分覆盖：本地 SQLite index 损坏、wiki 页面误删、frontmatter 损坏、本地仓库丢失、意外发布私有材料、备份策略。

## Сначала остановись

Если есть риск потери данных:

1. Не запускай `git reset --hard`.
2. Не удаляй worktree и временные файлы.
3. Не публикуй public snapshot.
4. Попроси агента показать `git status`, последние коммиты и список изменённых файлов.

## Повреждён локальный SQLite index

Симптомы: `search` падает, `doctor` говорит про corrupt/missing index, результаты поиска явно устарели.

Восстановление:

```text
переиндексируй проект
```

Агент пересоберёт `.reefiki/index.sqlite` из markdown. Markdown остаётся источником истины, поэтому потеря SQLite index не равна потере знаний.

## Случайно удалена wiki-страница

Симптом: файл пропал из `projects/<name>/wiki/...`, но раньше был в git.

Восстановление:

1. Найти последний коммит, где файл существовал.
2. Восстановить только этот файл.
3. Проверить frontmatter.
4. Обновить `wiki/index.md`, если нужно.
5. Добавить запись в `wiki/log.md`.

Не восстанавливать весь репозиторий широким откатом, если потерян один файл.

## Сломан frontmatter

Симптомы: validator ругается на YAML/frontmatter, `/process` или `/query` не видит страницу.

Восстановление:

1. Сравнить страницу с `projects/<name>/wiki/_schema.md`.
2. Починить обязательные поля.
3. Проверить, что `useful_when` остаётся конкретным сценарием применения.
4. Запустить validation только на затронутых файлах.

## Потерян локальный репозиторий

Если private remote актуален:

1. Склонировать private `origin`.
2. Открыть REEFIKI в агенте.
3. Пересобрать индексы нужных проектов.
4. Проверить `health`.

Если были незапушенные локальные изменения, восстановить их можно только из локального бэкапа, другого worktree или editor history.

## Случайно опубликован приватный материал

Это high-risk incident.

1. Остановить дальнейшие publish/push.
2. Определить, какой remote и commit затронуты.
3. Если утёк секрет, немедленно ротировать секрет.
4. Удалить материал из текущей истории через approved history-rewrite flow.
5. Проверить public snapshot content scan.
6. Зафиксировать incident в private wiki/log.

Важно: удаление из git history не гарантирует, что материал исчез из уже скачанных копий интернета.

## Бэкап-стратегия

Минимальный уровень:

- private `origin` должен получать регулярные push;
- public snapshot не считается backup;
- локальные worktree не считаются backup, пока commit не reachable from private remote.

Рекомендуемый уровень:

- private remote;
- локальная копия на другом диске;
- offsite backup или второй private remote;
- периодический `health check` после восстановления.

## Перед cleanup

Перед удалением временного worktree, cleanup ветки или publish cleanup проверь:

- worktree clean;
- нужный commit reachable from `origin/main` или task branch pushed;
- нет незакоммиченных wiki/log/index изменений;
- public snapshot не содержит private project paths.
