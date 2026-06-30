from __future__ import annotations

import re
from pathlib import Path


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9а-яё]+", "-", value, flags=re.IGNORECASE)
    return re.sub(r"-+", "-", value).strip("-") or "plan"


def numbered_path(base: Path, counter: int) -> Path:
    if counter == 1:
        return base
    return base.with_name(f"{base.stem}-{counter}{base.suffix}")


def write_new_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return path


def write_new_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)
    return path


def write_unique_text(base: Path, content: str) -> Path:
    counter = 1
    while True:
        try:
            return write_new_text(numbered_path(base, counter), content)
        except FileExistsError:
            counter += 1


def write_unique_bytes(base: Path, content: bytes) -> Path:
    counter = 1
    while True:
        try:
            return write_new_bytes(numbered_path(base, counter), content)
        except FileExistsError:
            counter += 1
