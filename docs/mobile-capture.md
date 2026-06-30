# Mobile capture

Mobile capture нужен только для дешёвого сохранения в копилку. Разбор и превращение в durable wiki-страницы делает агент позже.

## Минимальный безопасный контракт

Любой mobile flow должен выполнять четыре условия:

1. Принимать сообщения только от разрешённого пользователя.
2. Писать только в `projects/<name>/inbox/`.
3. Не принимать секреты, бинарники и большие файлы.
4. Не коммитить напрямую private/public snapshot в обход REEFIKI publish rules.

Если flow не может выполнить эти условия, использовать его нельзя.

## Telegram flow

Допустимый путь:

```text
Telegram bot -> webhook/automation -> GitHub Actions или локальный bridge -> inbox/
```

Обязательные настройки:

- хранить bot token только в secret storage;
- проверять Telegram `user_id` по allowlist;
- отклонять сообщения от неизвестных пользователей;
- ограничивать размер входящего текста;
- сохранять URL/text как inbox item без анализа;
- сообщать пользователю, если сохранение не прошло.

Нельзя:

- hardcode токена в YAML, markdown или коде;
- принимать сообщения от любого Telegram user;
- писать сразу в `wiki/`;
- запускать public publish из mobile webhook.

## iOS Shortcut / Android Tasker

Более простой вариант без Telegram:

```text
Share sheet -> Shortcut/Tasker -> GitHub API или локальный endpoint -> inbox/
```

Этот путь всё равно требует token/secret storage и allowlist. Если токен хранится на телефоне, он должен иметь минимальные права и не должен давать доступ к public publish.

## Что делать после capture

Когда в копилке появились элементы, попроси агента:

```text
разбери копилку проекта
```

Агент сам решит, что сохранить в `wiki/`, а что отложить в `seen/`.

## Проверка flow

Перед регулярным использованием проверь:

- неизвестный Telegram user получает отказ;
- ссылка сохраняется в `inbox/`, а не в `wiki/`;
- `.env`, token-like текст и большие вложения отклоняются;
- ошибка webhook не теряется молча;
- после сохранения `health check` показывает pending inbox item.
