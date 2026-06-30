#!/usr/bin/env python3
"""
MiMo Memory Integration for REEFIKI

This script provides a simple interface for MiMo Code Agent to:
1. Detect if a project is REEFIKI-connected
2. Query REEFIKI memory control plane
3. Get cross-project insights

Usage:
    python mimo_memory_integration.py detect <project_path>
    python mimo_memory_integration.py lookup <query> [--project <name>] [--layer <layer>]
    python mimo_memory_integration.py status
"""

import argparse
import os
import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def _marker_project_name(marker: Path) -> str | None:
    """Read project_name from a small REEFIKI marker file."""
    try:
        if marker.stat().st_size > 16_384:
            return None
        text = marker.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "project_name":
            project_name = value.strip()
            if project_name:
                return project_name
    return None


def detect_reefiki_connection(project_path: str) -> dict:
    """Detect if a project is connected to REEFIKI."""
    project = Path(project_path).resolve()

    # Check for .reefiki marker
    reefiki_marker = project / ".reefiki"
    if reefiki_marker.exists():
        return {
            "connected": True,
            "marker": ".reefiki",
            "project_name": _marker_project_name(reefiki_marker) or project.name,
            "project_path": str(project)
        }

    # Check for _wiki symlink/junction
    wiki_link = project / "_wiki"
    if wiki_link.exists():
        return {
            "connected": True,
            "marker": "_wiki",
            "project_name": project.name,
            "project_path": str(project)
        }

    return {
        "connected": False,
        "project_name": project.name,
        "project_path": str(project)
    }


def get_reefiki_root() -> Path:
    """Find REEFIKI root directory."""
    env_root = os.environ.get("REEFIKI_ROOT")
    if env_root:
        root = Path(env_root).expanduser().resolve()
        if _is_reefiki_root(root):
            return root

    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for root in _ancestor_candidates(start):
            if _is_reefiki_root(root):
                return root

    raise FileNotFoundError("REEFIKI root not found. Check REEFIKI installation path.")


def _ancestor_candidates(start: Path) -> list[Path]:
    resolved = start.expanduser().resolve()
    return [resolved, *resolved.parents]


def _is_reefiki_root(path: Path) -> bool:
    return path.is_dir() and (path / "AGENTS.md").is_file() and (path / "scripts" / "reefiki.py").is_file()


def memory_lookup(query: str, project: str = None, layer: str = "all", limit: int = 10) -> str:
    """Query REEFIKI memory control plane."""
    reefiki_root = get_reefiki_root()

    cmd = [
        sys.executable,
        str(reefiki_root / "scripts" / "reefiki.py"),
        "memory", "lookup",
        query,
        "--layer", layer,
        "--limit", str(limit),
        "--format", "text"
    ]

    if project:
        cmd.extend(["--project", project])

    import subprocess
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(reefiki_root))

    if result.returncode != 0:
        return f"Error: {result.stderr}"

    return result.stdout


def memory_status() -> str:
    """Get REEFIKI memory status."""
    reefiki_root = get_reefiki_root()

    import subprocess
    result = subprocess.run(
        [sys.executable, str(reefiki_root / "scripts" / "reefiki.py"), "memory", "status"],
        capture_output=True,
        text=True,
        cwd=str(reefiki_root)
    )

    if result.returncode != 0:
        return f"Error: {result.stderr}"

    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="MiMo Memory Integration for REEFIKI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect REEFIKI connection")
    detect_parser.add_argument("project_path", help="Path to project")

    # lookup command
    lookup_parser = subparsers.add_parser("lookup", help="Query memory")
    lookup_parser.add_argument("query", help="Search query")
    lookup_parser.add_argument("--project", help="Specific project")
    lookup_parser.add_argument("--layer", choices=["all", "memoir", "reefiki", "graphify"], default="all")
    lookup_parser.add_argument("--limit", type=int, default=10)

    # status command
    subparsers.add_parser("status", help="Memory status")

    args = parser.parse_args()

    if args.command == "detect":
        result = detect_reefiki_connection(args.project_path)
        print(f"Connected: {result['connected']}")
        if result["connected"]:
            print(f"Marker: {result['marker']}")
            print(f"Project: {result['project_name']}")

    elif args.command == "lookup":
        result = memory_lookup(args.query, args.project, args.layer, args.limit)
        print(result)

    elif args.command == "status":
        result = memory_status()
        print(result)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
