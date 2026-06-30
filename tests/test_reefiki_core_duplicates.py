from scripts.reefiki_core.duplicates import (
    _is_duplicate_source_signal,
    _normalize_text,
    _title_tokens,
    _titles_are_similar,
)


def test_normalize_text_collapses_whitespace_and_case() -> None:
    assert _normalize_text("  Mixed\n\tCase  ") == "mixed case"


def test_title_tokens_drop_short_and_stop_words_for_latin_and_russian() -> None:
    assert _title_tokens("The agent plan for delivery") == {"agent", "plan", "delivery"}
    assert _title_tokens("План для агента и проекта") == {"план", "агента", "проекта"}


def test_titles_are_similar_by_token_overlap() -> None:
    assert _titles_are_similar("Agent delivery review queue", "Review queue for agent delivery")
    assert not _titles_are_similar("Agent delivery", "Memory routing")


def test_duplicate_source_signal_filters_session_like_ids() -> None:
    assert not _is_duplicate_source_signal("")
    assert not _is_duplicate_source_signal("session-2026-06-11")
    assert not _is_duplicate_source_signal("repo-local-note")
    assert not _is_duplicate_source_signal("simple-slug")
    assert _is_duplicate_source_signal("https://example.com/source")
