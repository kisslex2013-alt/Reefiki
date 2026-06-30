from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_FAILURE_MODE_SKILLS = {
    "dirty shared checkout": "safe-task-worktree-bootstrap",
    "broad staging or unsafe publish": "staged-scope-and-publish-guard",
    "stale source-of-truth answer": "source-of-truth-diagnostics",
}

FORBIDDEN_RUNTIME_ADAPTER_FILES = {
    "adapters/codex/hooks.json",
    "adapters/claude-code/commands.md",
    "adapters/cursor/rules.mdc",
    "adapters/hermes/runtime-prompt.md",
}

FORBIDDEN_CONFIG_PATTERNS = {
    ".codex/hooks.json",
    ".cursor/rules.mdc",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_safety_checklist_maps_failure_modes_to_base_skills() -> None:
    checklist = read("docs/skill-products/AI_AGENT_REPO_SAFETY_CHECKLIST.md").lower()
    for failure_mode, skill in EXPECTED_FAILURE_MODE_SKILLS.items():
        assert failure_mode in checklist
        assert f"`{skill}`" in checklist
        assert (ROOT / "skills" / "base" / skill / "SKILL.md").exists()


def test_demo_proof_preserves_no_live_wiring_boundary() -> None:
    proof = read("docs/skill-products/DEMO_REPO_PROOF.md")
    for path in FORBIDDEN_RUNTIME_ADAPTER_FILES | FORBIDDEN_CONFIG_PATTERNS:
        assert path in proof
    for path in FORBIDDEN_RUNTIME_ADAPTER_FILES:
        assert not (ROOT / path).exists(), f"live wiring must be a later slice: {path}"


def test_demo_proof_has_validation_commands() -> None:
    proof = read("docs/skill-products/DEMO_REPO_PROOF.md")
    assert "python -m pytest tests\\test_skill_products_layout.py tests\\test_skill_products_demo.py" in proof
    assert "secret-scan" in proof
