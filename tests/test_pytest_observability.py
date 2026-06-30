from __future__ import annotations

import re
import tomllib
from pathlib import Path

from scripts.reefiki_core.test_observability import (
    build_test_observability_payload,
    print_test_observability,
)


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_MARKERS = {
    "agent_flow",
    "benchmark",
    "contract",
    "dashboard",
    "governance",
    "integration",
    "memory",
    "slow",
}

MARKED_SURFACES = {
    "tests/test_agent_flow_e2e.py": {"agent_flow", "integration", "contract"},
    "tests/test_install_smoke.py": {"integration", "slow"},
    "tests/test_reefiki_core_ops_dashboard.py": {"dashboard", "integration"},
    "tests/test_reefiki_core_retrieval_benchmark.py": {"benchmark", "memory"},
    "tests/test_reefiki_memory_contracts.py": {"memory", "contract", "slow"},
    "tests/test_reefiki_memory_governance.py": {"memory", "governance", "contract"},
}


def pyproject_markers() -> set[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    markers = config["tool"]["pytest"]["ini_options"]["markers"]
    return {marker.split(":", 1)[0] for marker in markers}


def documented_markers() -> set[str]:
    text = (ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    return set(re.findall(r"\| `([a-z_]+)` \|", text))


def test_pytest_markers_are_registered_and_documented() -> None:
    assert pyproject_markers() == EXPECTED_MARKERS
    assert documented_markers() == EXPECTED_MARKERS


def test_high_cost_surfaces_have_lane_markers() -> None:
    for relative_path, markers in MARKED_SURFACES.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "pytestmark" in text
        for marker in markers:
            assert f"pytest.mark.{marker}" in text


def write_test_observability_fixture(root: Path) -> None:
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        """[tool.pytest.ini_options]
markers = [
  "memory: memory lane",
  "slow: slow lane",
]
""",
        encoding="utf-8",
    )
    (root / "tests" / "test_memory_lane.py").write_text(
        """import pytest

pytestmark = [pytest.mark.memory, pytest.mark.slow]


def test_memory_lane():
    assert True
""",
        encoding="utf-8",
    )
    (root / "tests" / "test_unmarked.py").write_text(
        """def test_unmarked():
    assert True
""",
        encoding="utf-8",
    )


def test_test_observability_payload_reports_marker_usage_and_unmarked_files(tmp_path: Path) -> None:
    write_test_observability_fixture(tmp_path)

    payload = build_test_observability_payload(tmp_path)

    assert payload["outcome"] == "pass"
    assert payload["marker_usage"] == {"memory": 1, "slow": 1}
    assert payload["unmarked_files"] == ["tests/test_unmarked.py"]
    assert payload["summary"]["registered_marker_count"] == 2
    assert payload["coverage"]["default_gate"] is False
    commands = {command["name"]: command["command"] for command in payload["recommended_commands"]}
    assert commands["fast"] == 'python -m pytest -q -m "not slow"'
    assert commands["memory"] == "python -m pytest -q -m memory"


def test_test_observability_payload_blocks_unknown_custom_markers(tmp_path: Path) -> None:
    write_test_observability_fixture(tmp_path)
    (tmp_path / "tests" / "test_unknown.py").write_text(
        """import pytest

pytestmark = pytest.mark.not_registered


def test_unknown():
    assert True
""",
        encoding="utf-8",
    )

    payload = build_test_observability_payload(tmp_path)

    assert payload["outcome"] == "block"
    assert payload["unknown_markers"] == {"not_registered": ["tests/test_unknown.py"]}


def test_print_test_observability_json_and_text(capsys, tmp_path: Path) -> None:
    write_test_observability_fixture(tmp_path)

    assert print_test_observability(tmp_path, "json") == 0
    json_output = capsys.readouterr().out
    assert '"outcome": "pass"' in json_output
    assert '"memory": 1' in json_output

    assert print_test_observability(tmp_path, "text") == 0
    text_output = capsys.readouterr().out
    assert "outcome: pass" in text_output
    assert "memory: 1" in text_output
    assert "coverage_default_gate: false" in text_output
