from __future__ import annotations

import re
from pathlib import Path


def project_code_path(project: Path) -> Path | None:
    domain = project / "_domain.md"
    if not domain.exists():
        return None
    text = domain.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Путь:\s*`([^`]+)`", text, re.MULTILINE)
    if not match:
        match = re.search(r"^- Путь:\s*`([^`]+)`", text, re.MULTILINE)
    if not match:
        if project.name.lower() == "reefiki" and project.parent.name == "projects":
            repo_root = project.parent.parent
            if (repo_root / "AGENTS.md").exists():
                return repo_root
        return None
    return Path(match.group(1))


def graphify_report_path(project: Path) -> Path | None:
    code_path = project_code_path(project)
    if not code_path:
        return None
    report = code_path / "graphify-out" / "GRAPH_REPORT.md"
    return report if report.exists() else None


def graphify_graph_path(project: Path) -> Path | None:
    code_path = project_code_path(project)
    if not code_path:
        return None
    graph = code_path / "graphify-out" / "graph.json"
    return graph if graph.exists() else None
