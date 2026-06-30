from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path


DEFAULT_ONBOARDING_PROJECT = "reefiki-onboarding-demo"
DEFAULT_ONBOARDING_SOURCE = "https://example.com/reefiki-onboarding"
DEFAULT_ONBOARDING_QUESTION = "What did the onboarding source establish?"
DEFAULT_ONBOARDING_QUESTION_RU = "Что подтвердил первый источник?"
DEFAULT_ONBOARDING_SESSION_NOTE = "Finished the first REEFIKI onboarding run."
DEFAULT_ONBOARDING_SESSION_NOTE_RU = "Завершён первый запуск REEFIKI."
SUPPORTED_ONBOARDING_LANGUAGES = ("ru", "en")

RIFIKI_ASCII = [
    "  (.)---(.)",
    " /  \\_/  \\",
    " \\_______/",
    "  /_/ \\_\\",
]

ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "reef": "\033[38;5;37m",
    "coral": "\033[38;5;209m",
    "muted": "\033[38;5;245m",
}


ONBOARDING_UI = {
    "ru": {
        "logo": "REEFIKI · Рифик",
        "mascot": "Рифик, краб-архивариус рифа-вики",
        "title": "Добро пожаловать в REEFIKI",
        "headline": "Я покажу безопасный первый маршрут: демо-проект, источник, вики-страницы, сохранение вывода и панель состояния.",
        "intro": "Сейчас это только просмотр: без --fixture-root команда ничего не записывает.",
        "language": "Язык: русский. Переключить на английский: reefiki onboarding --lang en",
        "tagline": "Локальная память для сессий агентов.",
        "promise": "Сначала выбери путь. Команды покажу только когда они нужны.",
        "language_prompt": "Выберите язык / Choose language",
        "choose_action": "Что хотите сделать сейчас?",
        "choice_prompt": "Ваш выбор",
        "path_prompt": "Папка для демо",
        "confirm_demo": "Создать демо сейчас?",
        "invalid_choice": "Не понял выбор. Введите номер из списка.",
        "cancelled": "Ок, ничего не записываю.",
        "next_safe_step": "Безопасный следующий шаг",
        "interactive_hint": "Пошаговый режим",
        "commands_hint": "Показать все команды",
        "language_hint": "Язык можно задать сразу",
        "default_demo_root": r"C:\Temp\reefiki-demo",
        "demo_created": "Демо создано",
        "dashboard_title": "Локальная панель состояния",
        "connect_title": "Подключить свой проект",
        "commands_title": "Команды первого запуска",
        "fallback_hint": "Запасной запуск нужен только если команда reefiki не найдена.",
        "mode": {"dry-run": "просмотр", "fixture": "демо"},
        "project": "проект",
        "source": "источник",
        "path": "Маршрут",
        "command": "команда",
        "commands": "Команды",
        "checkout_fallback": "Запасной запуск из папки проекта",
        "artifacts": "Что будет создано",
        "next": "дальше",
        "steps": {
            "create": "создать изолированный REEFIKI-проект из шаблона",
            "save": "положить один источник в копилку без анализа",
            "process": "превратить источник в сохранённую страницу вики",
            "query": "задать вопрос локальной вики с источниками",
            "harvest": "сохранить вывод сессии в проектной памяти",
            "status": "показать состояние созданного проекта",
        },
        "step_labels": {
            "create": "Создать",
            "save": "Сохранить",
            "process": "Разобрать",
            "query": "Спросить",
            "harvest": "Зафиксировать",
            "status": "Проверить",
        },
        "next_fixture": "запусти с --fixture-root <demo-folder>, чтобы создать локальный демо-проект",
        "next_status": "запусти `{status_command}`, затем `{dashboard_demo_command}`",
        "actions": [
            {
                "key": "1",
                "id": "demo",
                "title": "Посмотреть безопасное демо",
                "body": "Создаст тестовый проект в отдельной папке. Реальные данные не трогаются.",
            },
            {
                "key": "2",
                "id": "connect",
                "title": "Подключить мой проект",
                "body": "Покажет короткий путь к /connect для существующего кода.",
            },
            {
                "key": "3",
                "id": "dashboard",
                "title": "Открыть dashboard",
                "body": "Подготовит локальную read-only панель на 127.0.0.1.",
            },
            {
                "key": "4",
                "id": "commands",
                "title": "Показать команды",
                "body": "Выведет полный ручной маршрут для копирования.",
            },
        ],
    },
    "en": {
        "logo": "REEFIKI · Rifiki",
        "mascot": "Rifiki, the reef-wiki archivist crab",
        "title": "Welcome to REEFIKI",
        "headline": "Preview the safe first-run path: demo project, source, wiki pages, harvest and dashboard.",
        "intro": "Without --fixture-root this is only a preview: nothing is written.",
        "language": "Language: English. Русский: reefiki onboarding --lang ru",
        "tagline": "Local memory for agent sessions.",
        "promise": "Choose a path first. Commands appear only when needed.",
        "language_prompt": "Choose language / Выберите язык",
        "choose_action": "What do you want to do now?",
        "choice_prompt": "Your choice",
        "path_prompt": "Demo folder",
        "confirm_demo": "Create the demo now?",
        "invalid_choice": "I did not understand that choice. Enter a listed number.",
        "cancelled": "Ok, writing nothing.",
        "next_safe_step": "Safe next step",
        "interactive_hint": "Step-by-step mode",
        "commands_hint": "Show all commands",
        "language_hint": "Set language directly",
        "default_demo_root": r"C:\Temp\reefiki-demo",
        "demo_created": "Demo created",
        "dashboard_title": "Local status dashboard",
        "connect_title": "Connect your project",
        "commands_title": "First-run commands",
        "fallback_hint": "Checkout fallback is only needed if the reefiki command is missing.",
        "mode": {"dry-run": "dry-run", "fixture": "demo"},
        "project": "project",
        "source": "source",
        "path": "Path",
        "command": "command",
        "commands": "Commands",
        "checkout_fallback": "Checkout fallback",
        "artifacts": "Artifacts",
        "next": "next",
        "steps": {
            "create": "create an isolated REEFIKI project from the template",
            "save": "put one source into the inbox without analysis",
            "process": "turn the saved source into a durable wiki page",
            "query": "ask the local wiki with provenance",
            "harvest": "record a session-level takeaway as durable wiki knowledge",
            "status": "show the resulting project state",
        },
        "step_labels": {
            "create": "Create",
            "save": "Save",
            "process": "Process",
            "query": "Query",
            "harvest": "Harvest",
            "status": "Status",
        },
        "next_fixture": "rerun with --fixture-root <demo-folder> to create a deterministic demo project",
        "next_status": "run `{status_command}`, then `{dashboard_demo_command}`",
        "actions": [
            {
                "key": "1",
                "id": "demo",
                "title": "Try a safe demo",
                "body": "Creates a test project in a separate folder. Real data is untouched.",
            },
            {
                "key": "2",
                "id": "connect",
                "title": "Connect my project",
                "body": "Shows the shortest /connect path for existing code.",
            },
            {
                "key": "3",
                "id": "dashboard",
                "title": "Open dashboard",
                "body": "Prepares a local read-only board on 127.0.0.1.",
            },
            {
                "key": "4",
                "id": "commands",
                "title": "Show commands",
                "body": "Prints the full manual route for copying.",
            },
        ],
    },
}


def _ui(lang: str) -> dict[str, object]:
    if lang not in SUPPORTED_ONBOARDING_LANGUAGES:
        raise SystemExit(f"Unsupported onboarding language: {lang}")
    return ONBOARDING_UI[lang]


def _localized_default(value: str, english_default: str, russian_default: str, lang: str) -> str:
    if lang == "ru" and value == english_default:
        return russian_default
    return value


def _supports_color(stream: object) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _paint(text: str, style: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{ANSI[style]}{text}{ANSI['reset']}"


def _terminal_width() -> int:
    return min(max(shutil.get_terminal_size((88, 24)).columns, 68), 92)


def _box(title: str, lines: list[str], *, plain: bool = False, width: int | None = None) -> list[str]:
    if plain:
        return [title, *lines]
    width = width or _terminal_width()
    inner = max(width - 4, 48)
    result = [f"╭─ {title} " + "─" * max(inner - len(title) - 1, 1) + "╮"]
    for line in lines:
        if not line:
            result.append("│" + " " * (inner + 2) + "│")
            continue
        for chunk in _wrap_line(line, inner):
            result.append(f"│ {chunk.ljust(inner)} │")
    result.append("╰" + "─" * (inner + 2) + "╯")
    return result


def _wrap_line(line: str, width: int) -> list[str]:
    if len(line) <= width:
        return [line]
    words = line.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
            continue
        if len(current) + 1 + len(word) <= width:
            current += f" {word}"
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks or [line]


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def _actions_for(ui: dict[str, object]) -> list[dict[str, str]]:
    actions = ui["actions"]
    assert isinstance(actions, list)
    return actions


def _print_hero(ui: dict[str, object], *, plain: bool, color: bool) -> None:
    title = str(ui["logo"])
    lines = [
        *RIFIKI_ASCII,
        "",
        _paint(str(ui["mascot"]), "coral", color),
        str(ui["tagline"]),
        str(ui["promise"]),
    ]
    _print_lines(_box(title, lines, plain=plain))


def _print_action_menu(ui: dict[str, object], *, plain: bool) -> None:
    lines: list[str] = []
    for action in _actions_for(ui):
        lines.append(f"{action['key']}. {action['title']}")
        lines.append(f"   {action['body']}")
    _print_lines(_box(str(ui["choose_action"]), lines, plain=plain))


def _print_language_gate(*, plain: bool) -> None:
    title = "REEFIKI"
    _print_lines(
        _box(
            title,
            ["Выберите язык / Choose language"],
            plain=plain,
        )
    )


def _prompt(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default or ""
    return value or (default or "")


def _confirm(prompt: str, default_yes: bool = True) -> bool:
    suffix = " [Y/n]" if default_yes else " [y/N]"
    try:
        value = input(f"{prompt}{suffix}: ").strip().lower()
    except EOFError:
        return False
    if not value:
        return default_yes
    return value in {"y", "yes", "д", "да"}


def _prompt_language() -> str:
    print("1. Русский")
    print("2. English")
    try:
        value = input("> ").strip().lower()
    except EOFError:
        return "ru"
    return "en" if value in {"2", "en", "english"} else "ru"


def _project_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _onboarding_steps(project_name: str, source: str, question: str, session_note: str, lang: str) -> list[dict[str, object]]:
    steps = _ui(lang)["steps"]
    assert isinstance(steps, dict)
    return [
        {
            "step": "create",
            "intent": steps["create"],
            "equivalent": f"/new {project_name}",
            "writes": [
                f"projects/{project_name}/AGENTS.md",
                f"projects/{project_name}/_domain.md",
                f"projects/{project_name}/wiki/index.md",
                f"projects/{project_name}/wiki/log.md",
            ],
        },
        {
            "step": "save",
            "intent": steps["save"],
            "equivalent": f"reefiki --project projects/{project_name} save {source}",
            "writes": [f"projects/{project_name}/inbox/onboarding-source.md"],
        },
        {
            "step": "process",
            "intent": steps["process"],
            "equivalent": "/process",
            "writes": [
                f"projects/{project_name}/raw/onboarding-source.md",
                f"projects/{project_name}/wiki/concepts/onboarding-first-source.md",
                f"projects/{project_name}/wiki/index.md",
                f"projects/{project_name}/wiki/log.md",
            ],
        },
        {
            "step": "query",
            "intent": steps["query"],
            "equivalent": f"reefiki --project projects/{project_name} search \"{question}\" --format json",
            "writes": [],
        },
        {
            "step": "harvest",
            "intent": steps["harvest"],
            "equivalent": f"/harvest {session_note}",
            "writes": [
                f"projects/{project_name}/wiki/synthesis/onboarding-session-summary.md",
                f"projects/{project_name}/wiki/index.md",
                f"projects/{project_name}/wiki/log.md",
            ],
        },
        {
            "step": "status",
            "intent": steps["status"],
            "equivalent": f"reefiki --project projects/{project_name} status",
            "writes": [],
        },
    ]


def _first_run_commands(project_name: str, fixture_root: Path | None) -> list[str]:
    demo_root = str(fixture_root) if fixture_root else "<demo-folder>"
    return [
        "reefiki tour",
        "reefiki onboarding",
        f"reefiki onboarding --fixture-root {demo_root}",
        f"reefiki --project {demo_root}/projects/{project_name} status",
        "reefiki ops-dashboard demo --fixture-root <dashboard-demo-folder>",
        "reefiki ops-dashboard serve --workspace-root <dashboard-demo-folder> --port 7310",
    ]


def _checkout_fallback_commands(project_name: str, fixture_root: Path | None) -> list[str]:
    demo_root = str(fixture_root) if fixture_root else "<demo-folder>"
    return [
        "python scripts/reefiki.py tour",
        "python scripts/reefiki.py onboarding",
        f"python scripts/reefiki.py onboarding --fixture-root {demo_root}",
        f"python scripts/reefiki.py --project {demo_root}/projects/{project_name} status",
        "python scripts/reefiki.py ops-dashboard demo --fixture-root <dashboard-demo-folder>",
        "python scripts/reefiki.py ops-dashboard serve --workspace-root <dashboard-demo-folder> --port 7310",
    ]


def _write_onboarding_fixture(
    fixture_root: Path,
    project_name: str,
    source: str,
    question: str,
    session_note: str,
) -> list[str]:
    project = fixture_root / "projects" / project_name
    for dirname in [
        "inbox",
        "raw",
        "seen",
        "wiki/concepts",
        "wiki/synthesis",
    ]:
        (project / dirname).mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    artifacts: list[Path] = []

    files = {
        project / "AGENTS.md": "Onboarding demo project. Use project-level REEFIKI rules.\n",
        project / "_domain.md": (
            "# Domain\n\n"
            "A deterministic onboarding demo project used to learn the REEFIKI first-run flow.\n"
        ),
        project / "raw" / "onboarding-source.md": (
            f"# Onboarding Source\n\nSource: {source}\n\n"
            "The first source explains that REEFIKI keeps sources, distilled wiki pages and session harvests separate.\n"
        ),
        project / "wiki" / "concepts" / "onboarding-first-source.md": (
            "---\n"
            "id: onboarding-first-source\n"
            "type: concept\n"
            'title: "Onboarding first source"\n'
            "tags: [onboarding, first-run]\n"
            "useful_when:\n"
            '  - "checking that the first REEFIKI source was processed into durable wiki knowledge"\n'
            f"date_added: {today}\n"
            "use_count: 0\n"
            "last_used: null\n"
            "---\n\n"
            "# Onboarding first source\n\n"
            "The first source demonstrates the capture -> process -> query flow without relying on external services.\n"
        ),
        project / "wiki" / "synthesis" / "onboarding-session-summary.md": (
            "---\n"
            "id: onboarding-session-summary\n"
            "type: synthesis\n"
            'title: "Onboarding session summary"\n'
            "tags: [onboarding, harvest]\n"
            "useful_when:\n"
            '  - "remembering what a successful first REEFIKI run should leave behind"\n'
            f"date_added: {today}\n"
            "use_count: 0\n"
            "last_used: null\n"
            "---\n\n"
            "# Onboarding session summary\n\n"
            f"{session_note}\n\n"
            "A successful first run leaves an inbox source, a raw source copy, a distilled wiki page, a harvest page and a status check.\n"
        ),
        project / "wiki" / "index.md": (
            "# Index\n\n"
            f"Last updated: {today}\n"
            "Total pages: 2\n\n"
            "## Sources\n"
            "## Entities\n"
            "## Concepts\n\n"
            "### onboarding-first-source\n"
            "- type: concept\n"
            "- tags: [onboarding, first-run]\n"
            '- useful_when: ["checking that the first REEFIKI source was processed into durable wiki knowledge"]\n'
            "- file: wiki/concepts/onboarding-first-source.md\n"
            f"- date_added: {today}\n"
            "- use_count: 0\n\n"
            "## Synthesis\n\n"
            "### onboarding-session-summary\n"
            "- type: synthesis\n"
            "- tags: [onboarding, harvest]\n"
            '- useful_when: ["remembering what a successful first REEFIKI run should leave behind"]\n'
            "- file: wiki/synthesis/onboarding-session-summary.md\n"
            f"- date_added: {today}\n"
            "- use_count: 0\n\n"
            "## Decisions\n"
            "## Skills\n"
        ),
        project / "wiki" / "log.md": (
            f"# Log\n\n"
            f"- {today}: onboarding fixture created project `{project_name}`.\n"
            f"- {today}: /save | {source}\n"
            f"- {today}: /process | accepted onboarding-source -> wiki/concepts/onboarding-first-source.md\n"
            f"- {today}: /query | {question}\n"
            f"- {today}: /harvest | {session_note}\n"
            f"- {today}: /status | onboarding fixture complete\n"
        ),
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        artifacts.append(path)
    return [_project_rel(path, fixture_root) for path in sorted(artifacts)]


def onboarding_wizard_payload(
    root: Path,
    project_name: str = DEFAULT_ONBOARDING_PROJECT,
    source: str = DEFAULT_ONBOARDING_SOURCE,
    question: str = DEFAULT_ONBOARDING_QUESTION,
    session_note: str = DEFAULT_ONBOARDING_SESSION_NOTE,
    fixture_root: Path | None = None,
    lang: str = "ru",
) -> dict[str, object]:
    ui = _ui(lang)
    effective_question = _localized_default(
        question,
        DEFAULT_ONBOARDING_QUESTION,
        DEFAULT_ONBOARDING_QUESTION_RU,
        lang,
    )
    effective_session_note = _localized_default(
        session_note,
        DEFAULT_ONBOARDING_SESSION_NOTE,
        DEFAULT_ONBOARDING_SESSION_NOTE_RU,
        lang,
    )
    target_root = fixture_root or root
    mode = "fixture" if fixture_root else "dry-run"
    artifacts = (
        _write_onboarding_fixture(
            target_root,
            project_name,
            source,
            effective_question,
            effective_session_note,
        )
        if fixture_root
        else []
    )
    status_root = target_root if fixture_root else Path("<demo-folder>")
    status_command = f"reefiki --project {status_root}/projects/{project_name} status"
    dashboard_demo_command = "reefiki ops-dashboard demo --fixture-root <dashboard-demo-folder>"
    dashboard_serve_command = "reefiki ops-dashboard serve --workspace-root <dashboard-demo-folder> --port 7310"
    return {
        "mode": mode,
        "language": lang,
        "brand": {
            "name": "REEFIKI",
            "mascot": "Рифик" if lang == "ru" else "Rifiki",
            "mascot_role": ui["mascot"],
        },
        "project": project_name,
        "root": str(target_root),
        "headline": ui["headline"],
        "intro": ui["intro"],
        "source": source,
        "question": effective_question,
        "session_note": effective_session_note,
        "steps": _onboarding_steps(
            project_name,
            source,
            effective_question,
            effective_session_note,
            lang,
        ),
        "first_run_commands": _first_run_commands(project_name, fixture_root),
        "checkout_fallback_commands": _checkout_fallback_commands(project_name, fixture_root),
        "status_command": status_command,
        "dashboard_demo_command": dashboard_demo_command,
        "dashboard_serve_command": dashboard_serve_command,
        "artifacts": artifacts,
        "transient_artifacts": (
            [f"projects/{project_name}/inbox/onboarding-source.md"] if fixture_root else []
        ),
        "next_action": (
            str(ui["next_status"]).format(
                status_command=status_command,
                dashboard_demo_command=dashboard_demo_command,
            )
            if fixture_root
            else ui["next_fixture"]
        ),
}


def _print_command_list(
    payload: dict[str, object],
    ui: dict[str, object],
    *,
    include_fallback: bool,
    show_fallback_hint: bool = True,
) -> None:
    print("")
    print(f"{ui['commands']}:")
    for command in payload["first_run_commands"]:
        print(f"  {command}")
    if include_fallback:
        print("")
        print(f"{ui['checkout_fallback']}:")
        for command in payload["checkout_fallback_commands"]:
            print(f"  {command}")
        if show_fallback_hint:
            print(str(ui["fallback_hint"]))


def _print_compact_summary(
    payload: dict[str, object],
    ui: dict[str, object],
    *,
    plain: bool,
    color: bool,
    show_commands: bool,
) -> None:
    _print_hero(ui, plain=plain, color=color)
    print("")
    print(_paint(str(ui["title"]), "bold", color))
    print(str(payload["headline"]))
    print(str(payload["intro"]))
    print("")
    print(f"{ui['next_safe_step']}:")
    print(f"  reefiki onboarding --fixture-root {ui['default_demo_root']}")
    print("")
    print(f"{ui['interactive_hint']}: reefiki onboarding --interactive")
    print(f"{ui['language_hint']}: reefiki onboarding --lang en")
    print(f"{ui['commands_hint']}: reefiki onboarding --show-commands")
    if show_commands:
        _print_command_list(payload, ui, include_fallback=True)


def _print_fixture_summary(
    payload: dict[str, object],
    ui: dict[str, object],
    *,
    plain: bool,
    color: bool,
    show_hero: bool = True,
) -> None:
    if show_hero:
        _print_hero(ui, plain=plain, color=color)
        print("")
    print(_paint(str(ui["demo_created"]), "bold", color))
    print(f"{ui['project']}: {payload['project']}")
    print(f"root: {payload['root']}")
    print("")
    print(f"{ui['artifacts']}:")
    for artifact in payload["artifacts"]:
        print(f"  {artifact}")
    print("")
    print(f"{ui['next']}: {payload['next_action']}")


def _print_connect_help(ui: dict[str, object], *, lang: str, plain: bool) -> None:
    _print_lines(
        _box(
            str(ui["connect_title"]),
            [
                "Открой REEFIKI в корне репозитория и скажи агенту:",
                "Подключи проект D:\\Projects\\MyApp к вики",
                "",
                "CLI-safe форма:",
                "python scripts\\reefiki.py --help",
            ]
            if lang == "ru"
            else [
                "Open REEFIKI at the repository root and tell the agent:",
                "Connect D:\\Projects\\MyApp to the wiki",
                "",
                "CLI-safe form:",
                "python scripts\\reefiki.py --help",
            ],
            plain=plain,
        )
    )


def _print_dashboard_help(payload: dict[str, object], ui: dict[str, object], *, plain: bool) -> None:
    _print_lines(
        _box(
            str(ui["dashboard_title"]),
            [
                str(payload["dashboard_demo_command"]),
                str(payload["dashboard_serve_command"]),
                "http://127.0.0.1:7310/",
            ],
            plain=plain,
        )
    )


def _print_manual_commands(payload: dict[str, object], ui: dict[str, object], *, plain: bool) -> None:
    _print_lines(
        _box(
            str(ui["commands_title"]),
            [str(ui["fallback_hint"])],
            plain=plain,
        )
    )
    _print_command_list(payload, ui, include_fallback=True, show_fallback_hint=False)


def _run_interactive_onboarding(
    root: Path,
    project_name: str,
    source: str,
    question: str,
    session_note: str,
    lang: str | None,
    yes: bool,
    plain: bool,
) -> int:
    color = _supports_color(sys.stdout) and not plain
    if lang is None:
        _print_language_gate(plain=plain)
        lang = _prompt_language()
    ui = _ui(lang)
    _print_hero(ui, plain=plain, color=color)
    print("")
    _print_action_menu(ui, plain=plain)
    print("")
    choice = _prompt(str(ui["choice_prompt"]), "1")
    actions = {action["key"]: action["id"] for action in _actions_for(ui)}
    action_id = actions.get(choice)
    if action_id is None:
        print(str(ui["invalid_choice"]))
        return 2

    payload = onboarding_wizard_payload(
        root,
        project_name=project_name,
        source=source,
        question=question,
        session_note=session_note,
        lang=lang,
    )
    if action_id == "commands":
        _print_manual_commands(payload, ui, plain=plain)
        return 0
    if action_id == "connect":
        _print_connect_help(ui, lang=lang, plain=plain)
        return 0
    if action_id == "dashboard":
        _print_dashboard_help(payload, ui, plain=plain)
        return 0

    demo_root = Path(_prompt(str(ui["path_prompt"]), str(ui["default_demo_root"])))
    if not (yes or _confirm(str(ui["confirm_demo"]), default_yes=True)):
        print(str(ui["cancelled"]))
        return 0
    demo_payload = onboarding_wizard_payload(
        root,
        project_name=project_name,
        source=source,
        question=question,
        session_note=session_note,
        fixture_root=demo_root,
        lang=lang,
    )
    _print_fixture_summary(demo_payload, ui, plain=plain, color=color, show_hero=False)
    return 0


def _should_interact(interactive: bool | None, *, plain: bool, fixture_root: str | None, fmt: str) -> bool:
    if fmt == "json" or plain or fixture_root:
        return False
    if interactive is not None:
        return interactive
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def print_onboarding_wizard(
    root: Path,
    project_name: str,
    source: str,
    question: str,
    session_note: str,
    fixture_root: str | None,
    fmt: str,
    lang: str | None,
    interactive: bool | None = None,
    show_commands: bool = False,
    plain: bool = False,
    yes: bool = False,
) -> int:
    if _should_interact(interactive, plain=plain, fixture_root=fixture_root, fmt=fmt):
        return _run_interactive_onboarding(
            root,
            project_name,
            source,
            question,
            session_note,
            lang,
            yes,
            plain,
        )
    effective_lang = lang or "ru"
    ui = _ui(effective_lang)
    payload = onboarding_wizard_payload(
        root,
        project_name=project_name,
        source=source,
        question=question,
        session_note=session_note,
        fixture_root=Path(fixture_root) if fixture_root else None,
        lang=effective_lang,
    )
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif fixture_root:
        _print_fixture_summary(payload, ui, plain=plain, color=_supports_color(sys.stdout) and not plain)
    else:
        _print_compact_summary(
            payload,
            ui,
            plain=plain,
            color=_supports_color(sys.stdout) and not plain,
            show_commands=show_commands,
        )
    return 0
