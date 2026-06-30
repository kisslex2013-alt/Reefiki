from __future__ import annotations

from datetime import date
from pathlib import Path

from .file_utils import write_unique_bytes, write_unique_text
from .privacy import classify_path, dedup_check, inbox_items, is_url
from .project_paths import relative
from .repo_paths import resolve_contained_path
from .save_paths import inbox_base_path


def append_save_log(project: Path, source: str) -> None:
    log = project / "wiki" / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"\n## [{date.today().isoformat()}] /save | {source}\n")


def save_source(project: Path, source: str) -> int:
    ok, reason = classify_path(source, project)
    if not ok:
        print(f"Refused: {reason}")
        return 2
    duplicate_code = dedup_check(project, source)
    if duplicate_code != 0:
        return duplicate_code
    if is_url(source):
        destination = write_unique_text(inbox_base_path(project, source), f"{source}\n")
    else:
        path, reason = resolve_contained_path(project, source)
        if path is None:
            print(f"Refused: {reason}")
            return 2
        destination = write_unique_bytes(inbox_base_path(project, source), path.read_bytes())
    append_save_log(project, source)
    inbox_count = len(inbox_items(project))
    print(f"Saved: {relative(project, destination)}")
    print(f"Inbox entries: {inbox_count}")
    return 0
