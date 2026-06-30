from pathlib import Path

from scripts.reefiki_core.memoir_io import memoir_store_path


def test_memoir_store_env_override_wins() -> None:
    store = memoir_store_path(
        environ={"REEFIKI_MEMOIR_STORE": "D:/stores/custom"},
        platform_name="win32",
        home=Path("C:/Users/Ada"),
    )

    assert store == Path("D:/stores/custom")


def test_memoir_store_specific_env_wins_over_standard_env() -> None:
    store = memoir_store_path(
        environ={
            "REEFIKI_MEMOIR_STORE": "D:/stores/specific",
            "MEMOIR_STORE": "D:/stores/standard",
        },
        platform_name="win32",
        home=Path("C:/Users/Ada"),
    )

    assert store == Path("D:/stores/specific")


def test_existing_codex_memoir_store_wins_over_platform_default(tmp_path) -> None:
    codex_store = tmp_path / ".codex" / "memoir-stores" / "reefiki"
    codex_store.mkdir(parents=True)

    store = memoir_store_path(
        environ={"LOCALAPPDATA": str(tmp_path / "AppData" / "Local")},
        platform_name="win32",
        home=tmp_path,
    )

    assert store == codex_store


def test_default_memoir_store_uses_xdg_data_home_off_windows() -> None:
    store = memoir_store_path(
        environ={"XDG_DATA_HOME": "/home/ada/.local/share"},
        platform_name="linux",
        home=Path("/home/ada"),
    )

    assert store == Path("/home/ada/.local/share/memoir/reefiki")
