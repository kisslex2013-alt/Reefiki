import json
from pathlib import Path

from scripts.reefiki_core.adapter_smoke import adapter_smoke_payload, print_adapter_smoke


def write_fixture_project(root: Path) -> Path:
    project = root / "projects" / "reefiki"
    (project / "wiki" / "concepts").mkdir(parents=True)
    for dirname in ["inbox", "raw", "seen"]:
        (project / dirname).mkdir(parents=True, exist_ok=True)
    (project / "wiki" / "log.md").write_text("", encoding="utf-8")
    (project / "_domain.md").write_text("adapter smoke fixture\n", encoding="utf-8")
    (project / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    (project / "wiki" / "concepts" / "local-adapter-smoke.md").write_text(
        """---
id: local-adapter-smoke
type: concept
title: "Local Adapter Smoke"
tags: [adapter, smoke]
useful_when:
  - "checking local adapter smoke"
date_added: 2026-06-14
use_count: 0
last_used: null
---

# Local Adapter Smoke

The local adapter smoke checks query, status and read-only project lookup without a daemon.
""",
        encoding="utf-8",
    )
    (project / "wiki" / "index.md").write_text(
        """# Index

Last updated: 2026-06-14
Total pages: 1

## Sources
## Entities
## Concepts

### local-adapter-smoke
- type: concept
- tags: [adapter, smoke]
- useful_when: ["checking local adapter smoke"]
- file: wiki/concepts/local-adapter-smoke.md
- date_added: 2026-06-14
- use_count: 0

## Synthesis
## Decisions
## Skills
""",
        encoding="utf-8",
    )
    return project


def test_adapter_smoke_covers_read_only_surfaces_and_write_guard(tmp_path: Path) -> None:
    project = write_fixture_project(tmp_path)

    payload = adapter_smoke_payload(tmp_path, "reefiki", "local adapter smoke", 3)

    assert payload["outcome"] == "pass"
    assert payload["transport"] == "local-cli-json"
    assert payload["daemon_started"] is False
    assert payload["network_listener"] is False
    assert payload["mcp_config_written"] is False
    assert payload["checks"]["status"]["outcome"] == "pass"
    assert payload["checks"]["status"]["read_only"] is True
    assert payload["checks"]["query"]["count"] == 1
    assert payload["checks"]["query"]["read_only"] is True
    assert payload["checks"]["project_lookup"]["count"] == 1
    assert payload["checks"]["project_lookup"]["read_only"] is True
    assert payload["checks"]["write_guard"]["outcome"] == "block"
    assert list((project / "inbox").glob("*.md")) == []


def test_print_adapter_smoke_json(capsys, tmp_path: Path) -> None:
    write_fixture_project(tmp_path)

    assert print_adapter_smoke(tmp_path, "reefiki", "local adapter smoke", 3, "json") == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["outcome"] == "pass"
    assert payload["checks"]["query"]["results"][0]["id"] == "local-adapter-smoke"
