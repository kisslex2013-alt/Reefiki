from __future__ import annotations

import re

from .file_utils import slugify


def split_inline_list(value: str) -> list[str]:
    parts: list[str] = []
    buf = ""
    in_quote = False
    quote = ""
    for char in value:
        if char in {"'", '"'}:
            if not in_quote:
                in_quote = True
                quote = char
            elif quote == char:
                in_quote = False
        if char == "," and not in_quote:
            parts.append(buf)
            buf = ""
            continue
        buf += char
    if buf:
        parts.append(buf)
    return parts


def parse_value(value: str) -> object:
    if value in {"", "null", "Null", "NULL"}:
        return None if value else []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_value(part.strip()) for part in split_inline_list(inner)]
    if value.isdigit():
        return int(value)
    return value.strip("\"'")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 4 :]
    data: dict[str, object] = {}
    current_key = ""
    for line in raw.splitlines():
        key_match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if key_match:
            current_key = key_match.group(1)
            value = key_match.group(2).strip()
            data[current_key] = parse_value(value)
            continue
        item_match = re.match(r"^\s*-\s*(.*)$", line)
        if item_match and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(parse_value(item_match.group(1).strip()))
    return data, body


def as_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def extract_wiki_links(body: str) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []
    for lineno, line in enumerate(body.splitlines(), 1):
        for match in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", line):
            target = slugify(match.group(1).strip())
            if not target:
                continue
            links.append({"target_id": target, "kind": "wikilink", "line": lineno})
    return links


def extract_heading_chunks(body: str) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []
    current_path = "Page"
    start_line = 1

    def flush() -> None:
        content = "\n".join(current_lines).strip()
        if content:
            chunks.append(
                {
                    "heading_path": current_path,
                    "content": content,
                    "start_line": start_line,
                }
            )

    for lineno, line in enumerate(body.splitlines(), 1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = [(lvl, text) for lvl, text in heading_stack if lvl < level]
            heading_stack.append((level, title))
            current_path = " > ".join(text for _lvl, text in heading_stack)
            current_lines = []
            start_line = lineno + 1
            continue
        current_lines.append(line)
    flush()
    return chunks
