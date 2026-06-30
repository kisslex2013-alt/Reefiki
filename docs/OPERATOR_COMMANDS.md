# REEFIKI Operator Commands

Languages: [Русский](#русский)

## Русский

Это справочник для maintainer/operator workflows: staged scope, secret scan, publish, cleanup, worktree inventory и evidence matrix. Для обычного первого запуска и ежедневной wiki-работы смотри [COMMANDS.md](../COMMANDS.md#русский).

## Operator / maintainer-команды

Следующие команды нужны редко. Они полезны агентам и maintainer'ам, когда нужно безопасно сделать commit/publish, проверить staged scope, собрать evidence или убрать task worktree после merge. Для обычного first-run, demo и ежедневной wiki-работы они не нужны.

### `reefiki.py guard-staged` / staged-path guard перед commit

**Что делает.** Проверяет staged-файлы по operation profile: `harvest` (по умолчанию), `process`, `docs` или `code`.
**Когда нужна.** Перед commit/push после `/harvest`, `/process`, docs/code slice или cross-project durable write, особенно когда в REEFIKI repo есть чужие dirty-файлы.
**Как сказать по-человечески.** «Проверь, что в коммит попадёт только wiki demo-проекта reefiki-demo».
**Что произойдёт.** Агент сравнит staged paths с выбранным profile. `harvest` разрешает только `projects/<name>/wiki/**`; `process` дополнительно разрешает `inbox/`, `seen/`, `wiki/index.md`, append-only `wiki/log.md`, created wiki pages и raw create-only paths; `docs`/`code` не разрешают `projects/*/raw/**`. Non-append edits к `wiki/log.md` и raw modify/delete блокируются. Dirty, но не staged файлы не блокируют commit, но должны быть перечислены в финале как excluded.

Пример:

```bash
python scripts/reefiki.py guard-staged --target-project reefiki --mode process --format json
```

### `reefiki.py secret-scan` / content secret scan

**Что делает.** Проверяет явно перечисленные файлы на secret-like content. Для ручной полной проверки repo есть explicit full-tree mode `--all`: он обходит рабочее дерево, сканирует текстовые кандидаты и возвращает `skipped_paths` для forbidden/binary/large files.

**Когда нужна.** Перед publish, перед cleanup source reports, после добавления agent outputs или когда нужно доказать не только staged-path hook, но и отдельный full-tree pass.

**Важно.** Без paths и без `--all` команда fail-closed с `reason: no_paths`; это защищает от ложного pass на пустом вводе. `--all` не заменяет publish gate и не читает `.git`, `node_modules`, build/cache dirs, archives/binaries или большие файлы.

```bash
python scripts/reefiki.py secret-scan --format json README.md TASKS.md
python scripts/reefiki.py secret-scan --all --format json
```

### `reefiki.py policy-evidence` / explanatory evidence matrix

**Что делает.** Собирает компактные evidence rows из JSON-выводов `guard-staged`, `publish-task --dry-run`, `cleanup-worktree --dry-run`, `secret-scan` и `worktree-status`.
**Когда нужна.** Когда надо показать, почему publish/guard/cleanup разрешён или заблокирован: staged paths, target project, public snapshot intent, private exclusions, secret scan, raw/log guards and cleanup reachability.
**Как сказать по-человечески.** «Покажи policy evidence по этим guard/publish/cleanup артефактам».
**Что произойдёт.** Команда прочитает только переданные JSON-файлы, вернёт rows с `tool`, `check_id`, `outcome`, summary и `evidence_pointer`. Matrix explanatory-only: она не обходит guard, не выдаёт approval и не заменяет исходные gates.

```bash
python scripts/reefiki.py policy-evidence --input guard.json --input publish-dry-run.json --format json
```

### `reefiki.py harvest-commit` / isolated cross-project harvest commit

**Что делает.** Создаёт commit только из явно перечисленных `projects/<name>/wiki/**` файлов выбранного проекта через временный git index.
**Когда нужна.** Когда `/harvest` выполняется из другого проекта или когда в REEFIKI repo есть параллельные dirty/staged изменения от других агентов.
**Как сказать по-человечески.** «Закоммить только harvest demo-проекта, не трогая другой dirty state».
**Что произойдёт.** Агент передаст target project, список touched wiki-файлов и commit message. Команда заблокирует path вне `projects/<name>/wiki/**`, проваленную wiki-валидацию или target-файл, который уже был staged до запуска. Чужие dirty/staged paths вне target остаются на месте, не попадают в commit и возвращаются в отчёте как excluded/preexisting.

Пример для агента:

```bash
python scripts/reefiki.py harvest-commit --target-project reefiki-demo \
  --path projects/reefiki-demo/wiki/skills/public-release-verification.md \
  --path projects/reefiki-demo/wiki/log.md \
  --message "Harvest demo release verification note"
```

### `reefiki.py publish-task` / safe dual-remote publication

**Что делает.** Автоматически классифицирует task branch/worktree перед публикацией: `private-only`, `public-safe`, `mixed` или `block`.
**Когда нужна.** При любой просьбе «push», «пуш», «отправь на git», «merge», «PR», особенно когда работа сделана в отдельном `git worktree`/`codex/*` branch.
**Как сказать по-человечески.** «Опубликуй безопасно с учётом private/public repo».
**Что произойдёт.** Dry-run проверит clean worktree, diff относительно base, fail-closed private project inventory, content scan изменённых файлов, приватные project paths и нужные действия; если нужен public snapshot, dry-run также построит filtered snapshot и просканирует итоговые staged public files без push. Apply push-ит task branch/private main, а при public-safe/mixed делает filtered public snapshot и перед public push повторяет scan итоговых staged public files. Dirty worktree и non-fast-forward base блокируются.

Стартовый dry-run:

```bash
python scripts/reefiki.py publish-task --dry-run --cleanup --format json
```

Применение после pass:

```bash
python scripts/reefiki.py publish-task --apply --cleanup --format json
```

Если private push уже прошёл, а public snapshot упал по сети:

```bash
python scripts/reefiki.py publish-task --apply --public-snapshot --format json
```

Текущие ограничения:

- `scripts/public-snapshot.private-projects.txt` должен оставаться полным и актуальным; Python path блокирует missing/empty/incomplete inventory, но сам список всё равно является critical safety surface.
- Content scan rule-based: он блокирует известные secret-like patterns, но не заменяет human review для спорного public text.
- `push-public.ps1` остаётся manual fallback для PowerShell/Windows-сценариев.

### `reefiki.py cleanup-worktree` / safe task worktree cleanup

**Что делает.** Проверяет, можно ли удалить отдельный task worktree после publish/merge.
**Когда нужна.** Когда после публикации остался каталог вроде `REEFIKI__harvest_isolated` на ветке `codex/*`.
**Что произойдёт.** Dry-run блокирует dirty worktree, missing base и commit, который ещё не reachable from base. Apply удаляет worktree и удаляет local branch только после safety checks; branch cleanup проверяется fail-closed. Если intent уже перенесён или заменён без ancestry-merge, нужен явный semantic evidence:
`--semantic-superseded "<что именно заменило этот branch>"`. Короткая/пустая evidence строка блокируется.

```bash
python scripts/reefiki.py cleanup-worktree --worktree /path/to/REEFIKI-task --dry-run --format json
```

### `reefiki.py worktree-status` / parallel worktree lifecycle status

**Что делает.** Read-only показывает состояние всех git worktrees: path, branch, head, dirty paths, dirty groups by scope, ahead/behind vs base, ancestry и рекомендацию `keep`/`delete`/`review`/`block`.
**Когда нужна.** Перед closeout, publish, cleanup или разбором старых task worktrees.
**Что произойдёт.** Команда ничего не удаляет, не stage-ит и не меняет git state. С `--scope <path>` отдельно показывает `excluded_dirty_paths`, `scope_conflicts` и рекомендацию для dirty shared checkout. С `--ledger <path>` добавляет owner/milestone/lease status из LeadOps ledger. Правила lifecycle описаны в `docs/WORKTREE_LIFECYCLE.md`.

```bash
python scripts/reefiki.py worktree-status --format json
python scripts/reefiki.py worktree-status --scope projects/reefiki-demo --format json
python scripts/reefiki.py worktree-status --ledger plans/leadops/worktree-ledger.json --format json
```

### `reefiki.py orchestration-check` / LeadOps control-plane preflight

**Что делает.** Read-only объединяет live worktree inventory, LeadOps ledger, coordination-file owner checks, remote `codex/*` branch cleanup candidates, optional global Codex rule scan and local CI visibility.
**Когда нужна.** Перед publish/cleanup длинного batch, при параллельных worktrees, при проверке разрозненности или перед передачей работы другому агенту.
**Что произойдёт.** Команда не создаёт и не удаляет worktree, не stage-ит, не commit-ит и не push-ит. `block` означает: текущий task worktree грязный, нет owner/milestone/lease discipline, есть конфликт coordination files или global rule scan нашёл опасный паттерн. GitHub branch protection возвращается как manual check, потому локальный git не доказывает настройки GitHub.

```bash
python scripts/reefiki.py orchestration-check --ledger plans/leadops/worktree-ledger.json --format json
python scripts/reefiki.py orchestration-check --ledger plans/leadops/worktree-ledger.json --include-global-config --format json
```

### `reefiki.py confidence-pass` / repeatable full-confidence recipe

**Что делает.** Собирает официальный confidence-pass report из уже существующих gates: `git status`, `orchestration-check`, project `doctor`, `review-queues --summary`, `memory golden` и `publish-task --dry-run --cleanup`. С `--include-pytest` дополнительно запускает `python -m pytest`.
**Когда нужна.** Перед publish/cleanup значимого REEFIKI task, после широкого code/docs batch или когда TeamLead хочет не вспоминать порядок ручных проверок.
**Что произойдёт.** Команда не stage-ит, не commit-ит, не push-ит, не cleanup-ит текущий task worktree и не запускает delegated agents. Встроенный `publish-task --dry-run` может создать и удалить временный public snapshot worktree. Если `--include-pytest` не указан, итог будет `review`, потому полный локальный test gate пропущен. Read-only verifier остаётся отдельным TeamLead/subagent шагом и отражается в `manual_steps`.

```bash
python scripts/reefiki.py confidence-pass --project-name reefiki-demo --format json
python scripts/reefiki.py confidence-pass --project-name reefiki-demo --include-pytest --format json
python scripts/reefiki.py confidence-pass --project-name reefiki-demo --include-pytest --pytest-arg tests/test_reefiki_core_publish_task.py --format json
```
