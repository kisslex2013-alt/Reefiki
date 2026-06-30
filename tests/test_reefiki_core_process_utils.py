import subprocess
from pathlib import Path

import pytest

from scripts.reefiki_core.process_utils import git_repo_root


def test_git_repo_root_returns_current_repo_root() -> None:
    expected = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()

    assert git_repo_root(Path(__file__).parent).as_posix().lower() == expected.replace("\\", "/").lower()


def test_git_repo_root_reports_git_failure(tmp_path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        git_repo_root(tmp_path)

    assert str(exc_info.value)
