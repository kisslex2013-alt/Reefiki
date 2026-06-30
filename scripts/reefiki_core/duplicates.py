from __future__ import annotations

import re


DUPLICATE_TITLE_STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "by",
    "for",
    "in",
    "of",
    "or",
    "the",
    "to",
    "vs",
    "with",
    "как",
    "для",
    "и",
    "или",
    "между",
    "по",
    "про",
    "что",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _title_tokens(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-zа-я0-9]+", value.lower(), flags=re.IGNORECASE))
    return {token for token in tokens if len(token) > 2 and token not in DUPLICATE_TITLE_STOP_WORDS}


def _titles_are_similar(left: str, right: str) -> bool:
    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens)
    ratio = overlap / len(left_tokens | right_tokens)
    return overlap >= 3 or (overlap >= 2 and ratio >= 0.67)


def _is_duplicate_source_signal(source: str) -> bool:
    normalized = _normalize_text(source)
    if not normalized:
        return False
    if normalized.startswith("current-session-"):
        return False
    if normalized.startswith(("session-", "local-session-", "repo-local-")):
        return False
    if re.fullmatch(r"[a-z0-9-]+", normalized):
        return False
    return True
