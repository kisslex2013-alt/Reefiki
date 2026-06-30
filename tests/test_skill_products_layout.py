from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BASE_SKILLS = {
    "safe-task-worktree-bootstrap",
    "source-of-truth-diagnostics",
    "staged-scope-and-publish-guard",
    "reefiki-experience-monitor",
    "durable-harvest-closeout",
    "verification-before-completion",
    "browser-runtime-smoke-gate",
}

ADAPTER_DOCS = {
    "adapters/README.md",
    "adapters/PROOF_GATES.md",
    "adapters/generic-agents/AGENTS.md.fragment",
    "adapters/generic-agents/install.md",
    "adapters/codex/install.md",
    "adapters/codex/proof.md",
    "adapters/claude-code/install.md",
    "adapters/cursor/install.md",
    "adapters/hermes/install.md",
}

ADAPTER_POLICY_DOCS = ADAPTER_DOCS - {"adapters/generic-agents/AGENTS.md.fragment"}
ADAPTER_PROOF_DOCS = {"adapters/PROOF_GATES.md", "adapters/codex/proof.md"}

REQUIRED_SECTIONS = {
    "## When to use",
    "## Inputs",
    "## Workflow",
    "## Safety rules",
    "## Verification",
    "## Outputs",
    "## Adapter notes",
}

FORBIDDEN_RUNTIME_ADAPTER_FILES = {
    "adapters/codex/hooks.json",
    "adapters/claude-code/commands.md",
    "adapters/cursor/rules.mdc",
    "adapters/hermes/runtime-prompt.md",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_base_skill_layout_and_frontmatter() -> None:
    for name in BASE_SKILLS:
        path = ROOT / "skills" / "base" / name / "SKILL.md"
        assert path.exists(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{name} missing YAML frontmatter"
        assert f"name: {name}" in text
        assert re.search(r"^description: .{40,}$", text, re.MULTILINE), name
        for section in REQUIRED_SECTIONS:
            assert section in text, f"{name} missing {section}"


def test_adapter_docs_are_read_only_mvp() -> None:
    for path in ADAPTER_DOCS:
        assert (ROOT / path).exists(), f"missing {path}"

    for path in FORBIDDEN_RUNTIME_ADAPTER_FILES:
        assert not (ROOT / path).exists(), f"runtime adapter file should be a later slice: {path}"

    for path in ADAPTER_POLICY_DOCS:
        text = read(path).lower()
        assert "read-only" in text or "explicit approval" in text, path
        assert (
            "global config" in text
            or "global agent config" in text
            or "global claude code config" in text
            or "global settings" in text
            or "global cursor settings" in text
            or "hermes config" in text
            or "daemon processes" in text
        ), path


def test_markdown_links_resolve_in_skill_product_slice() -> None:
    checked_paths = [
        "skills/base/README.md",
        "docs/skill-products/AI_AGENT_REPO_SAFETY_CHECKLIST.md",
        "docs/skill-products/DEMO_REPO_PROOF.md",
        *ADAPTER_DOCS,
        *(f"skills/base/{name}/SKILL.md" for name in BASE_SKILLS),
    ]
    link_re = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)#]+)(?:#[^)]+)?\)")
    missing: list[str] = []
    for rel_path in checked_paths:
        source = ROOT / rel_path
        for match in link_re.finditer(source.read_text(encoding="utf-8")):
            target = (source.parent / match.group(1)).resolve()
            if not target.exists():
                missing.append(f"{rel_path} -> {match.group(1)}")
    assert missing == []


def test_codex_adapter_proof_covers_all_base_skills_without_runtime_files() -> None:
    proof = read("adapters/codex/proof.md")
    for skill in BASE_SKILLS:
        assert f"`{skill}`" in proof

    for path in FORBIDDEN_RUNTIME_ADAPTER_FILES:
        assert not (ROOT / path).exists(), f"runtime adapter file should be a later slice: {path}"

    for path in ADAPTER_PROOF_DOCS:
        text = read(path).lower()
        assert "proof" in text
        assert "explicit approval" in text or "separate proof-gated" in text
