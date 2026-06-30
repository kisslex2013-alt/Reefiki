import subprocess
from pathlib import Path

import pytest

from scripts.reefiki_core import memoir_io


def test_memoir_base_command_uses_store_and_json_mode() -> None:
    assert memoir_io._memoir_base_command(Path("store")) == [
        "uvx",
        "--from",
        "memoir-ai",
        "memoir",
        "--json",
        "--store",
        "store",
    ]


def test_parse_memoir_json_output_ignores_resolver_logs_and_wraps_arrays() -> None:
    assert memoir_io._parse_memoir_json_output("noise\n{\"ok\": true}") == {"ok": True}
    assert memoir_io._parse_memoir_json_output("[1, 2]") == {"payload": [1, 2]}
    assert memoir_io._parse_memoir_json_output("") == {}
    with pytest.raises(SystemExit):
        memoir_io._parse_memoir_json_output("not json")


def test_run_memoir_sets_utf8_env_and_parses_stdout(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(memoir_io.subprocess, "run", fake_run)

    assert memoir_io.run_memoir(Path("store"), ["status"], timeout_seconds=7) == {"ok": True}
    kwargs = calls[0]["kwargs"]
    assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
    assert kwargs["timeout"] == 7


def test_run_memoir_raises_stderr_on_failure(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="ignored", stderr="failed")

    monkeypatch.setattr(memoir_io.subprocess, "run", fake_run)

    with pytest.raises(SystemExit, match="failed"):
        memoir_io.run_memoir(Path("store"), ["status"], timeout_seconds=7)
