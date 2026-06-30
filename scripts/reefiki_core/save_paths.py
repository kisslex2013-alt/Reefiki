from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from .file_utils import numbered_path, slugify
from .privacy import is_url


def source_slug(source: str) -> str:
    if is_url(source):
        parsed = urlparse(source)
        value = f"{parsed.netloc}{parsed.path}"
        return slugify(value)
    return slugify(Path(source).stem)


def inbox_base_path(project: Path, source: str) -> Path:
    inbox = project / "inbox"
    inbox.mkdir(exist_ok=True)
    suffix = ".md" if is_url(source) else Path(source).suffix
    stem = source_slug(source)
    return inbox / f"{stem}{suffix}"


def unique_inbox_path(project: Path, source: str) -> Path:
    path = inbox_base_path(project, source)
    counter = 2
    while path.exists():
        path = numbered_path(inbox_base_path(project, source), counter)
        counter += 1
    return path
