from scripts.reefiki_core.memory_preflight import (
    memory_global_strict_preflight,
    memory_preflight,
)


def test_memory_preflight_passes_selected_project_scope() -> None:
    payload = memory_preflight(
        project="reefiki",
        visibility="private",
        operation="lookup",
        content="normal query",
        paths=["projects/reefiki"],
    )

    assert payload["outcome"] == "pass"
    assert payload["blocking_reasons"] == []


def test_memory_preflight_blocks_other_project_scope() -> None:
    payload = memory_preflight(
        project="reefiki",
        visibility="private",
        operation="lookup",
        content="normal query",
        paths=["projects/metrica"],
    )

    assert payload["outcome"] == "block"
    assert "forbidden_scope:projects/metrica" in payload["blocking_reasons"]


def test_memory_preflight_blocks_public_secret_content() -> None:
    content = "api_" + "key=secret"
    payload = memory_preflight(
        project="reefiki",
        visibility="public",
        operation="export",
        content=content,
        paths=["projects/reefiki"],
    )

    assert payload["outcome"] == "block"
    assert "secret_like_content" in payload["blocking_reasons"]


def test_memory_preflight_blocks_secret_like_paths() -> None:
    payload = memory_preflight(
        project="reefiki",
        visibility="public",
        operation="export",
        content="placeholder",
        paths=["projects/reefiki/.env"],
    )

    assert payload["outcome"] == "block"
    assert "secret_like_path" in payload["blocking_reasons"]


def test_memory_preflight_allows_safe_docs_with_secret_terms_in_filename() -> None:
    payload = memory_preflight(
        project="reefiki",
        visibility="public",
        operation="export",
        content="token economy notes without credentials",
        paths=["projects/reefiki/wiki/concepts/token-economy.md"],
    )

    assert payload["outcome"] == "pass"
    assert "secret_like_path" not in payload["blocking_reasons"]


def test_memory_global_strict_preflight_blocks_metrica_even_for_metrica_project() -> None:
    payload = memory_global_strict_preflight(
        project="metrica",
        visibility="private",
        operation="lookup",
        content="normal query",
        paths=["projects/metrica"],
    )

    assert payload["outcome"] == "block"
    assert "forbidden_scope:projects/metrica" in payload["blocking_reasons"]


def test_memory_global_strict_preflight_blocks_metrica_case_insensitively() -> None:
    payload = memory_global_strict_preflight(
        project="Metrica",
        visibility="private",
        operation="lookup",
        content="normal query",
        paths=["projects/Metrica/wiki/index.md"],
    )

    assert payload["outcome"] == "block"
    assert payload["checked_paths"] == ["projects/Metrica/wiki/index.md"]
    assert "forbidden_scope:projects/metrica" in payload["blocking_reasons"]
