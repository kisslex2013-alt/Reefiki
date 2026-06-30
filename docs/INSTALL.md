# REEFIKI Install

Languages: [Русский](#русский) · [English](#english) · [中文](#中文)

## Русский

Это публичная страница установки REEFIKI CLI. Поддерживаемый путь для пользователя:

```powershell
pipx install git+https://github.com/kisslex2013-alt/reefiki.git
pipx ensurepath
reefiki --help
reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run status
```

Требования: Git, Python 3.11+, `pipx` для изолированной установки или virtualenv для разработки из checkout.

`reefiki init` создаёт новый локальный workspace и первый wiki-проект. Команда не перезаписывает существующий проект и не создаёт `_wiki` bridge без явного `--code-project ... --apply-bridge`.

Проверка PATH после установки:

```powershell
Get-Command reefiki
where.exe reefiki
reefiki --help
```

Если `reefiki` не найден сразу после `pipx ensurepath`, закрой текущий терминал и открой новый. Если команда всё ещё не находится, используй запасной запуск из папки репозитория ниже и проверь, что папка `pipx` scripts добавлена в пользовательский PATH.

Для безопасной первой проверки используй:

```powershell
reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run status
reefiki ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
reefiki ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

POSIX:

```bash
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run status
reefiki ops-dashboard demo --fixture-root /tmp/reefiki-dashboard-demo
reefiki ops-dashboard serve --workspace-root /tmp/reefiki-dashboard-demo --port 7310
```

`init` пишет только в указанный `--workspace`. Dashboard demo пишет только в указанную demo-папку.

Если `reefiki` не найден в текущем shell, это обычно локальный PATH/install drift. Из папки репозитория используй запасной запуск:

```powershell
python scripts\reefiki.py --help
python scripts\reefiki.py init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
python scripts\reefiki.py --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
python scripts\reefiki.py --project C:\Temp\reefiki-workspace\projects\first-run status
python scripts\reefiki.py ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
python scripts\reefiki.py ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

## English

This page is the public install landing for the current REEFIKI CLI. It documents the supported local install paths without adding an installer, marketplace package, auto-update mechanism or curl-to-shell script.

The first real command is `reefiki init --workspace <path> --project-name <name>`. It creates a local workspace from built-in templates, then you verify it with `doctor` and `status`. The onboarding wizard remains available after that with `reefiki onboarding --lang en`.

## 中文

这是 REEFIKI CLI 的公开安装入口。推荐用户安装方式：

```powershell
pipx install git+https://github.com/kisslex2013-alt/reefiki.git
pipx ensurepath
reefiki --help
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
```

要求：Git、Python 3.11+，以及用于隔离安装的 `pipx`，或用于 checkout 开发的 virtualenv。

安全的首次检查：

```powershell
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
```

`init` 只会写入你指定的 `--workspace`。

## Requirements

- Git.
- Python 3.11 or newer.
- `pipx` for isolated user installs, or a Python virtual environment for checkout/developer installs.

REEFIKI core CLI has no runtime package dependencies beyond the Python standard library. Development and test workflows use optional tools such as `pytest` and `pre-commit`.

## User Install With pipx

Install from the git repository:

```powershell
pipx install git+https://github.com/kisslex2013-alt/reefiki.git
pipx ensurepath
reefiki --help
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run status
```

PATH check:

```powershell
Get-Command reefiki
where.exe reefiki
reefiki --help
```

If `reefiki` is still missing after `pipx ensurepath`, open a new shell and repeat the PATH check. If it is still missing, use the checkout fallback below and inspect the pipx scripts directory in your user PATH.

If the package is already installed:

```powershell
pipx upgrade reefiki
```

Uninstall:

```powershell
pipx uninstall reefiki
```

## Checkout Install

Use this path when you already cloned the repository or want to develop REEFIKI itself:

```powershell
git clone https://github.com/kisslex2013-alt/reefiki.git
cd reefiki
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\reefiki --help
.\.venv\Scripts\reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
.\.venv\Scripts\reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
```

The compatibility entrypoint remains available:

```powershell
python scripts\reefiki.py --help
python scripts\reefiki.py init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
```

## First Safe Commands

Start by creating a local workspace and checking it:

```powershell
reefiki --help
reefiki init --workspace C:\Temp\reefiki-workspace --project-name first-run --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run doctor --format json
reefiki --project C:\Temp\reefiki-workspace\projects\first-run status
reefiki ops-dashboard demo --fixture-root C:\Temp\reefiki-dashboard-demo
reefiki ops-dashboard serve --workspace-root C:\Temp\reefiki-dashboard-demo --port 7310
```

POSIX:

```bash
reefiki init --workspace /tmp/reefiki-workspace --project-name first-run --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run doctor --format json
reefiki --project /tmp/reefiki-workspace/projects/first-run status
```

The init command writes only under the `--workspace` folder you provide. The default onboarding wizard remains available after that with `reefiki onboarding`; use `reefiki onboarding --lang en` for English output.

## Development Install

For tests and local development from a checkout:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

Focused test lanes are documented in [TESTING.md](TESTING.md).

Publishing the REEFIKI repository itself is not part of installation. Ordinary users do not need publication commands to run the CLI, create a demo, or connect their own projects.

## Current Boundaries

This install path does not provide:

- a hosted cloud account;
- a managed sync backend;
- an MCP server;
- vector or hybrid search runtime;
- marketplace submission or paid-gating;
- a curl-to-shell installer.

Those items stay behind separate product decisions and proof gates.

## Install Smoke

Minimal local smoke from a clean temporary virtual environment:

```powershell
$tmp = Join-Path $env:TEMP "reefiki-install-smoke"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
python -m venv $tmp
& "$tmp\Scripts\python.exe" -m pip install .
$env:PATH = "$tmp\Scripts;$env:PATH"
Get-Command reefiki
where.exe reefiki
reefiki --help
reefiki init --workspace "$tmp\reefiki-workspace" --project-name first-run --format json
reefiki --project "$tmp\reefiki-workspace\projects\first-run" doctor --format json
reefiki --project "$tmp\reefiki-workspace\projects\first-run" status
reefiki ops-dashboard demo --fixture-root "$tmp\dashboard-demo" --format json
```

Expected result:

- `Get-Command reefiki` and `where.exe reefiki` resolve the installed console script;
- `reefiki --help` prints the CLI command list through PATH, not a direct executable path;
- `reefiki init --workspace ...` creates a minimal local workspace and JSON payload;
- `reefiki --project ... doctor --format json` passes on the initialized project;
- `reefiki ops-dashboard demo --format json` creates only synthetic demo repos under the supplied fixture root;
- no files are written outside the temporary virtual environment unless you explicitly pass `--workspace` or a demo fixture path.

## Package Artifact Smoke

Use this before publishing a release artifact. It proves the wheel, not just the checkout, can install and run the first workspace flow:

```powershell
python -m pip install --upgrade build
python -m build
$tmp = Join-Path $env:TEMP ("reefiki-wheel-smoke-" + [System.Guid]::NewGuid().ToString("N"))
python -m venv $tmp
& "$tmp\Scripts\python.exe" -m pip install (Get-ChildItem dist\reefiki-*.whl | Select-Object -First 1).FullName
$env:PATH = "$tmp\Scripts;$env:PATH"
reefiki --help
reefiki init --workspace "$tmp\reefiki-workspace" --project-name first-run --format json
reefiki --project "$tmp\reefiki-workspace\projects\first-run" doctor --format json
```

This is still a source-built package smoke. It does not publish to PyPI, create a single-file executable, sign an installer, or mutate global REEFIKI configuration.
