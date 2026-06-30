# Obsidian setup

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Obsidian можно использовать как удобный просмотрщик REEFIKI: граф, поиск, теги, ручное чтение wiki-страниц.

## English

Obsidian can be used as a viewer/editor shell for REEFIKI: graph view, search, tags, and manual reading of wiki pages.

Safe default:

- open the `REEFIKI/` root as the vault;
- treat markdown and git as the source of truth;
- do not use Obsidian Git to publish REEFIKI repository changes;
- avoid editing the same wiki page manually while an agent is processing or harvesting it.

The detailed setup continues below in Russian.

## 中文

Obsidian 可以作为 REEFIKI 的查看/编辑外壳：图谱、搜索、标签和手动阅读 wiki 页面。

安全默认设置：

- 把 `REEFIKI/` 根目录作为 vault 打开；
- markdown 和 git 仍然是事实来源；
- 不要用 Obsidian Git 发布 REEFIKI 仓库变更；
- 当代理正在 process 或 harvest 时，不要手动编辑同一个 wiki 页面。

下面继续保留俄语的详细设置说明。

## Базовая настройка

1. Установи Obsidian.
2. Open folder as vault: выбери корень `REEFIKI/`.
3. Включи graph view.
4. В фильтрах графа исключи служебные зоны:

```text
-path:"projects/_template/" -path:"/raw/" -path:"/inbox/" -path:"/seen/" -path:"/deep-research/" -path:"/.claude/" -path:"/plans/" -file:CLAUDE -file:_domain -file:README -file:log -file:index
```

## Рекомендуемые настройки

В Obsidian лучше держать wiki в source/live preview режиме и использовать короткие wikilinks.

Стабильные настройки можно хранить в git, но workspace-файлы открытых вкладок должны оставаться локальными:

```text
.obsidian/workspace*
.obsidian/cache
```

## Плагины

| Плагин | Статус | Почему |
|---|---|---|
| Dataview | можно | читает frontmatter, не мешает агенту |
| Tag Wrangler | можно | помогает с тегами |
| Templater | осторожно | может создавать страницы вне REEFIKI-контракта |
| Obsidian Git | не использовать | коммитит вне безопасного REEFIKI workflow |

## Как не потерять изменения

Obsidian сохраняет файлы автоматически. Если одновременно редактировать страницу руками и просить агента менять ту же страницу, возможен конфликт.

Практичное правило:

- в Obsidian читать и делать короткие заметки безопасно;
- перед ручной правкой wiki-страницы не запускай `/process`, `/harvest`, `/resolve` в том же проекте;
- если агент менял страницу, обнови Obsidian view перед продолжением ручной правки;
- не используй Obsidian Git для публикации изменений REEFIKI.

## Что не открывать как рабочую область

Для ежедневной работы открывай либо корень REEFIKI, либо конкретный кодовый проект с `_wiki/`.

Не делай отдельный Obsidian vault только из `projects/<name>/wiki/`: так легко потерять контекст `inbox/`, `seen/`, `AGENTS.md`, command specs и project domain.
