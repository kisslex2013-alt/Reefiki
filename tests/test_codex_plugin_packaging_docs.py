from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_skill_product_docs_keep_install_as_future_scope():
    text = "\n\n".join(
        [
            (ROOT / "docs" / "skill-products" / "SKILL_PRODUCTS.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "skill-products" / "AGENT_ADAPTERS.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "skill-products" / "DEMO_REPO_PROOF.md").read_text(encoding="utf-8"),
        ]
    )

    assert "agent-safe-repo-pack" in text
    assert "staged-scope-and-publish-guard" in text
    assert "source-of-truth-diagnostics" in text
    assert "safe-task-worktree-bootstrap" in text
    assert "public snapshot exclusions" in text
    assert "private/public publish boundary" in text
    assert "does not create a demo repository" in text
    assert "does not mean live hooks or global config may be installed" in text


def test_public_skill_product_docs_preserve_no_global_config_boundary():
    text = (ROOT / "docs" / "skill-products" / "DEMO_REPO_PROOF.md").read_text(encoding="utf-8")

    assert "The demo must not change global Codex, Claude Code, Cursor or Hermes config." in text
    assert ".codex/hooks.json" in text
    assert ".claude/**" in text
