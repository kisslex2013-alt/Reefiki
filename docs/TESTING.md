# REEFIKI Testing

REEFIKI tests are split into pytest marker lanes so agents can choose a focused gate before running the full suite.

## Common Commands

| Goal | Command |
| --- | --- |
| Full local suite | `python -m pytest -q` |
| Fast inner loop | `python -m pytest -q -m "not slow"` |
| Memory control plane | `python -m pytest -q -m memory` |
| Contract compatibility | `python -m pytest -q -m contract` |
| Git/CLI/filesystem workflows | `python -m pytest -q -m integration` |
| Agent-facing command flows | `python -m pytest -q -m agent_flow` |
| Ops Dashboard tests | `python -m pytest -q -m dashboard` |
| Retrieval benchmarks | `python -m pytest -q -m benchmark` |
| Publish and wiki governance gates | `python -m pytest -q -m governance` |
| Test observability report | `python scripts\reefiki.py test-observability --format text` |
| Machine-readable test observability | `python scripts\reefiki.py test-observability --format json` |
| Package artifact smoke | `python -m build`, then install `dist/reefiki-*.whl` in a clean venv and run `reefiki init` + `doctor` |
| Slow-test visibility | `python -m pytest -q --durations=20` |

## Marker Registry

The source of truth is `pyproject.toml`. Keep this table in sync with `[tool.pytest.ini_options].markers`.

| Marker | Use For |
| --- | --- |
| `agent_flow` | User-facing slash-command and agent-flow conformance tests. |
| `benchmark` | Retrieval or performance comparison tests. |
| `contract` | Cross-module behavior contracts and compatibility guarantees. |
| `dashboard` | Ops Dashboard payload, static asset and browser-adjacent tests. |
| `governance` | Publish, staging, security and wiki governance gates. |
| `integration` | Filesystem, git, subprocess, CLI or multi-step workflow tests. |
| `memory` | Memory control plane, provider, golden, lookup, pack and promote tests. |
| `slow` | Higher-cost tests that are reasonable to skip in a tight inner loop. |

## Observability Report

`python scripts\reefiki.py test-observability --format json` is a read-only report over `pyproject.toml` and `tests/**/*.py`.

It reports registered marker lanes, marker usage counts, test files without a lane marker, unknown custom markers, built-in pytest marker usage and recommended commands. Unknown custom markers are blocking because `--strict-markers` would reject them; unmarked files are reported for triage but do not fail the command.

## Coverage

Coverage is intentionally not a default gate yet. Add `pytest-cov` only when the project wants an enforced threshold and a stable report location. Until then, use marker lanes plus `--durations=20` to keep feedback loops observable without adding a new dependency.
