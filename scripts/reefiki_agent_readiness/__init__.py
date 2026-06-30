from __future__ import annotations

import fnmatch
import json
import os
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "agent-readiness.v1"
GIT_TIMEOUT_SECONDS = int(os.environ.get("REEFIKI_SUBPROCESS_TIMEOUT", "120"))

IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    "vendor",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".next",
    ".vercel",
    ".cache",
}
SECRET_NAME_PATTERNS = {
    ".env",
    ".env.*",
    "secrets.*",
    "credentials.*",
    "id_rsa",
    "id_rsa.pub",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    ".npmrc",
    ".netrc",
}
SECRET_PARTS = {".aws", ".ssh"}
SUSPICIOUS_SECRET_TOKENS = {"secret", "password", "token"}

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
}
PACKAGE_MANIFESTS = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod"}
PACKAGE_SCOPE_DIRS = {"apps", "packages", "services"}


def _run_git(path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT_SECONDS,
    )


def _git_output(path: Path, args: list[str]) -> str | None:
    completed = _run_git(path, args)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError as exc:
        raise SystemExit(f"Cannot resolve repo path: {path}: {exc}") from exc


def _is_secret_like(rel_path: str) -> bool:
    parts = [part.lower() for part in rel_path.replace("\\", "/").split("/")]
    name = parts[-1] if parts else ""
    if any(part in SECRET_PARTS for part in parts):
        return True
    if any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_NAME_PATTERNS):
        return True
    if Path(name).suffix.lower() in LANGUAGE_EXTENSIONS:
        return False
    stem = Path(name).stem.lower()
    return any(token in stem for token in SUSPICIOUS_SECRET_TOKENS)


def _scan_paths(root: Path) -> dict[str, Any]:
    files: list[str] = []
    dirs: set[str] = set()
    secret_like_paths: list[str] = []
    skipped_dirs: Counter[str] = Counter()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            full = current / dirname
            if dirname in IGNORED_DIR_NAMES or full.is_symlink():
                skipped_dirs[dirname] += 1
                continue
            rel_dir = full.relative_to(root).as_posix()
            dirs.add(rel_dir)
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            full = current / filename
            if full.is_symlink():
                continue
            rel = full.relative_to(root).as_posix()
            if _is_secret_like(rel):
                secret_like_paths.append(rel)
                continue
            files.append(rel)

    return {
        "files": sorted(files),
        "dirs": sorted(dirs),
        "secret_like_paths": sorted(secret_like_paths),
        "skipped_dirs": dict(sorted(skipped_dirs.items())),
    }


def _git_inventory(path: Path) -> dict[str, Any]:
    root_output = _git_output(path, ["rev-parse", "--show-toplevel"])
    if not root_output:
        return {
            "is_git": False,
            "root": str(path),
            "branch": None,
            "dirty": False,
            "staged_paths": [],
            "dirty_paths": [],
            "untracked_paths": [],
            "remotes": [],
            "worktree_count": 0,
        }

    root = Path(root_output).resolve()
    status_completed = _run_git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    status_output = status_completed.stdout if status_completed.returncode == 0 else ""
    staged_paths: list[str] = []
    dirty_paths: list[str] = []
    untracked_paths: list[str] = []
    entries = status_output.split("\0") if status_output else []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        status = entry[:2]
        path_part = entry[3:].replace("\\", "/") if len(entry) > 3 else ""
        if path_part:
            if status == "??":
                untracked_paths.append(path_part)
            else:
                dirty_paths.append(path_part)
                if status[0] != " ":
                    staged_paths.append(path_part)
        if "R" in status or "C" in status:
            i += 1

    remotes_output = _git_output(root, ["remote", "-v"]) or ""
    remotes: list[dict[str, str]] = []
    seen_remotes: set[tuple[str, str]] = set()
    for line in remotes_output.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        key = (parts[0], parts[1])
        if key in seen_remotes:
            continue
        seen_remotes.add(key)
        remotes.append({"name": parts[0], "url": parts[1]})

    worktree_output = _git_output(root, ["worktree", "list", "--porcelain"]) or ""
    worktree_count = sum(1 for line in worktree_output.splitlines() if line.startswith("worktree "))

    return {
        "is_git": True,
        "root": str(root),
        "branch": _git_output(root, ["branch", "--show-current"]) or None,
        "dirty": bool(staged_paths or dirty_paths or untracked_paths),
        "staged_paths": sorted(set(staged_paths)),
        "dirty_paths": sorted(set(dirty_paths)),
        "untracked_paths": sorted(set(untracked_paths)),
        "remotes": remotes,
        "worktree_count": worktree_count,
    }


def _detect_repo_types(files: set[str], dirs: set[str], extension_counts: Counter[str]) -> list[str]:
    repo_types: set[str] = set()
    if "package.json" in files:
        repo_types.add("node")
    if "package.json" in files and (
        "next.config.js" in files
        or "next.config.mjs" in files
        or "next.config.ts" in files
        or "src/app" in dirs
        or "app" in dirs
    ):
        repo_types.add("frontend")
    if "pyproject.toml" in files or "pytest.ini" in files or extension_counts["python"] > 0:
        repo_types.add("python")
    if "Cargo.toml" in files or extension_counts["rust"] > 0:
        repo_types.add("rust")
    if "go.mod" in files or extension_counts["go"] > 0:
        repo_types.add("go")
    if "pnpm-workspace.yaml" in files or "turbo.json" in files or "packages" in dirs or "apps" in dirs:
        repo_types.add("monorepo")
    if any(path.startswith("docs/") for path in files) or "README.md" in files:
        repo_types.add("docs")
    if "Dockerfile" in files or "vercel.json" in files or "wrangler.toml" in files:
        repo_types.add("deployable")
    return sorted(repo_types) or ["unknown"]


def _strip_scope(path: str, scope: str) -> str | None:
    if path == scope:
        return ""
    prefix = f"{scope}/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    return None


def _detect_package_scopes(files: set[str], dirs: set[str]) -> list[dict[str, Any]]:
    candidate_roots: set[str] = set()
    for path in files:
        parts = path.split("/")
        if parts[-1] in PACKAGE_MANIFESTS and len(parts) > 1:
            candidate_roots.add("/".join(parts[:-1]))
    for path in files:
        parts = path.split("/")
        if len(parts) >= 3 and parts[0] in PACKAGE_SCOPE_DIRS:
            candidate_roots.add("/".join(parts[:2]))

    scopes: list[dict[str, Any]] = []
    for root in sorted(candidate_roots):
        scoped_files = {stripped for path in files if (stripped := _strip_scope(path, root))}
        scoped_dirs = {stripped for path in dirs if (stripped := _strip_scope(path, root))}
        if not scoped_files and not scoped_dirs:
            continue
        extension_counts = Counter(LANGUAGE_EXTENSIONS.get(Path(path).suffix.lower(), "other") for path in scoped_files)
        extension_counts.pop("other", None)
        markers = sorted(path for path in scoped_files if path in PACKAGE_MANIFESTS or path in {"Dockerfile", "vercel.json", "wrangler.toml", "fly.toml"})
        if not markers and not extension_counts:
            continue
        scopes.append(
            {
                "path": root,
                "repo_types": _detect_repo_types(scoped_files, scoped_dirs, extension_counts),
                "markers": markers,
            }
        )
    return scopes


def _detect_test_markers(files: set[str], dirs: set[str]) -> list[str]:
    markers: set[str] = set()
    direct_files = {
        "pytest.ini",
        "tox.ini",
        "vitest.config.ts",
        "vitest.config.js",
        "vitest.config.mjs",
        "jest.config.js",
        "jest.config.ts",
        "playwright.config.ts",
        "playwright.config.js",
        "go.test.sh",
    }
    for path in files:
        name = Path(path).name
        parts = path.split("/")
        if path in direct_files:
            markers.add(path)
        if path.startswith(".github/workflows/"):
            markers.add(".github/workflows")
        if "tests" in parts[:-1]:
            markers.add(path)
        if name.endswith((".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx", "_test.py", "_test.go")):
            markers.add(path)
    if "tests" in dirs:
        markers.add("tests")
    if "test" in dirs:
        markers.add("test")
    if any(path.startswith("tests/") for path in files):
        markers.add("tests")
    if any(path.startswith("test/") for path in files):
        markers.add("test")
    return sorted(markers)


def _detect_agent_surfaces(files: set[str], dirs: set[str]) -> list[str]:
    surfaces: list[str] = []
    checks = [
        ("AGENTS.md", "AGENTS.md" in files),
        ("CLAUDE.md", "CLAUDE.md" in files),
        (".claude/commands", any(path.startswith(".claude/commands/") for path in files) or ".claude/commands" in dirs),
        (".codex/hooks.json", ".codex/hooks.json" in files),
        (".codex/instructions.md", ".codex/instructions.md" in files),
        (".cursor/rules", any(path.startswith(".cursor/rules/") for path in files) or ".cursor/rules" in dirs),
        (".cursorrules", ".cursorrules" in files),
        (".windsurf", any(path.startswith(".windsurf/") for path in files) or ".windsurf" in dirs),
        (".clinerules", ".clinerules" in files),
        ("skills", any(path.startswith("skills/") for path in files) or "skills" in dirs),
    ]
    for name, present in checks:
        if present:
            surfaces.append(name)
    return surfaces


def _recommendation(
    item_id: str,
    label_key: str,
    label_value: str,
    severity: str,
    confidence: str,
    reason: str,
    evidence: list[str],
    item_type: str | None = None,
) -> dict[str, Any]:
    item = {
        "id": item_id,
        label_key: label_value,
        "severity": severity,
        "confidence": confidence,
        "review_state": "ready" if confidence == "high" else "review_needed",
        "reason": reason,
        "evidence": evidence,
    }
    if item_type:
        item["type"] = item_type
    return item


def _risk(
    item_id: str,
    title: str,
    severity: str,
    confidence: str,
    evidence: list[str],
    recommended_blocks: list[str],
    do_not_auto_apply: bool = True,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "severity": severity,
        "confidence": confidence,
        "evidence": evidence,
        "recommended_blocks": recommended_blocks,
        "do_not_auto_apply": do_not_auto_apply,
    }


def _append_unique(bucket: list[dict[str, Any]], item: dict[str, Any]) -> None:
    if not any(existing["id"] == item["id"] for existing in bucket):
        bucket.append(item)


def _risk_level(risks: list[dict[str, Any]]) -> str:
    severities = {str(risk.get("severity")) for risk in risks}
    if "P0" in severities:
        return "P0"
    if "P1" in severities:
        return "P1"
    if "P2" in severities:
        return "P2"
    return "pass"


def agent_readiness_payload(repo_path: Path) -> dict[str, Any]:
    target = _safe_resolve(repo_path)
    if not target.exists() or not target.is_dir():
        raise SystemExit(f"Repo path not found or not a directory: {target}")

    git = _git_inventory(target)
    root = Path(str(git["root"])).resolve()
    scan = _scan_paths(root)
    files = set(scan["files"])
    dirs = set(scan["dirs"])
    extension_counts = Counter(LANGUAGE_EXTENSIONS.get(Path(path).suffix.lower(), "other") for path in files)
    extension_counts.pop("other", None)
    repo_types = _detect_repo_types(files, dirs, extension_counts)
    package_scopes = _detect_package_scopes(files, dirs)
    test_markers = _detect_test_markers(files, dirs)
    agent_surfaces = _detect_agent_surfaces(files, dirs)
    has_tests = bool(test_markers)
    frontend_evidence = []
    if "frontend" in repo_types:
        frontend_evidence.append("frontend markers detected")
    frontend_evidence.extend(f"package:{scope['path']}" for scope in package_scopes if "frontend" in scope["repo_types"])
    has_frontend = bool(frontend_evidence)
    has_public_remote = any(remote["name"] == "public" for remote in git["remotes"])
    has_deploy = any(path in files for path in ["Dockerfile", "vercel.json", "wrangler.toml", "fly.toml"])
    has_migrations = "migrations" in dirs or any("migrations/" in path for path in files) or "schema.prisma" in files
    has_security_surface = any(part in dirs for part in ["auth", "security", "payments", "payment"]) or any(
        path.startswith(("auth/", "security/", "payments/", "payment/")) for path in files
    )
    has_reefiki_surface = ".reefiki" in dirs or "_wiki" in dirs or any(path.startswith("projects/") and "/wiki/" in path for path in files)
    existing_hooks = ".codex/hooks.json" in files

    risks: list[dict[str, Any]] = []
    recommendations: dict[str, list[dict[str, Any]]] = {
        "skills": [],
        "rules": [],
        "adapters": [],
        "hooks": [],
    }
    custom_skill_drafts: list[dict[str, Any]] = []

    if git["dirty"]:
        evidence = [f"dirty_paths={len(git['dirty_paths'])}", f"untracked_paths={len(git['untracked_paths'])}"]
        risks.append(_risk("dirty_worktree", "Target repo has dirty or untracked files.", "P0", "high", evidence, ["skills", "rules", "hooks"]))
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.safe-task-worktree-bootstrap", "skill", "safe-task-worktree-bootstrap", "P0", "high", "Dirty repo increases unrelated file capture risk.", evidence, "use_existing_skill"),
        )
        _append_unique(
            recommendations["rules"],
            _recommendation("rule.one-task-one-worktree", "rule", "one task = one isolated worktree before edits", "P0", "high", "Dirty shared checkouts need an isolation rule.", evidence),
        )
        _append_unique(
            recommendations["hooks"],
            _recommendation("hook.broad-staging-guard", "hook", "block broad staging and require scoped staged-path checks", "P0", "medium", "Dirty repos benefit from deterministic staging enforcement.", evidence),
        )

    if git["staged_paths"]:
        evidence = [f"staged_paths={len(git['staged_paths'])}"]
        risks.append(_risk("staged_paths_present", "Target repo already has staged paths.", "P0", "high", evidence, ["hooks", "rules"]))

    if "AGENTS.md" not in files:
        evidence = ["missing AGENTS.md"]
        risks.append(_risk("missing_agent_contract", "Repo has no AGENTS.md contract.", "P1", "high", evidence, ["skills", "rules", "adapters"]))
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.source-of-truth-diagnostics", "skill", "source-of-truth-diagnostics", "P1", "high", "Agent needs a source-of-truth discovery workflow before changing the repo.", evidence, "use_existing_skill"),
        )
        _append_unique(
            recommendations["rules"],
            _recommendation("rule.add-agent-contract", "rule", "add AGENTS.md with repo scope, test commands, forbidden paths and publish rules", "P1", "high", "No persistent agent instruction surface was found.", evidence),
        )
        _append_unique(
            recommendations["adapters"],
            _recommendation("adapter.generic-agents", "adapter", "generic-agents", "P1", "high", "Generic AGENTS.md-compatible agents need a visible repo contract.", evidence, "adapter_only"),
        )

    if has_public_remote:
        evidence = ["remote named public detected"]
        risks.append(_risk("public_remote_present", "Repo has a public remote surface.", "P0", "high", evidence, ["skills", "rules", "hooks"]))
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.staged-scope-and-publish-guard", "skill", "staged-scope-and-publish-guard", "P0", "high", "Public/private remotes require scoped publish preflight.", evidence, "use_existing_skill"),
        )
        _append_unique(
            recommendations["rules"],
            _recommendation("rule.publish-through-approved-flow", "rule", "publish only through approved preflight flow", "P0", "high", "Public remote makes manual push a leak risk.", evidence),
        )
        _append_unique(
            recommendations["hooks"],
            _recommendation("hook.publish-preflight", "hook", "block manual push and run publish/secret preflight", "P0", "high", "Publication should fail before private paths can reach public remote.", evidence),
        )

    if has_frontend:
        evidence = frontend_evidence
        risks.append(_risk("frontend_runtime_smoke_missing", "Frontend changes need browser-visible verification.", "P1", "medium", evidence, ["skills", "rules"]))
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.browser-runtime-smoke-gate", "skill", "browser-runtime-smoke-gate", "P1", "medium", "Frontend repos need runtime smoke evidence for page/component changes.", evidence, "use_optional_skill"),
        )
        _append_unique(
            recommendations["rules"],
            _recommendation("rule.browser-smoke-for-ui", "rule", "browser-visible changes require a local runtime smoke check", "P1", "medium", "Static code checks do not prove browser behavior.", evidence),
        )

    if has_security_surface:
        evidence = ["auth/security/payment path markers detected"]
        risks.append(_risk("security_sensitive_surface", "Repo has auth/security/payment surface.", "P1", "medium", evidence, ["skills", "rules", "hooks"]))
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.security-best-practices", "skill", "security-best-practices", "P1", "medium", "Sensitive surfaces need explicit security review before completion.", evidence, "use_optional_skill"),
        )
        _append_unique(
            recommendations["hooks"],
            _recommendation("hook.secret-scan", "hook", "run secret scan before commit/publish", "P1", "medium", "Sensitive repos benefit from deterministic secret checks.", evidence),
        )
        custom_skill_drafts.append(
            {
                "type": "create_custom_skill_draft",
                "name": "repo-security-review",
                "write_allowed": False,
                "reason": "security-sensitive paths detected; draft only after human review",
                "evidence": evidence,
                "severity": "P1",
                "confidence": "medium",
            }
        )

    if has_migrations:
        evidence = ["database migration markers detected"]
        risks.append(_risk("database_migration_surface", "Repo has database migration surface.", "P1", "medium", evidence, ["skills", "rules", "hooks"]))
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.legacy-migration-audit", "skill", "legacy-migration-audit", "P1", "medium", "Migration changes need backup, rollback and data-loss review.", evidence, "use_optional_skill"),
        )
        _append_unique(
            recommendations["rules"],
            _recommendation("rule.migration-proof", "rule", "migration changes require rollback/data-loss evidence", "P1", "medium", "Schema/data changes can be destructive even when tests pass.", evidence),
        )

    if has_deploy:
        evidence = ["deploy config detected"]
        risks.append(_risk("deploy_surface", "Repo has deployment surface.", "P1", "medium", evidence, ["skills", "rules"]))
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.release-readiness-gates", "skill", "release-readiness-gates", "P1", "medium", "Deployable repos need release readiness gates.", evidence, "use_optional_skill"),
        )
        custom_skill_drafts.append(
            {
                "type": "create_custom_skill_draft",
                "name": "repo-release-guard",
                "write_allowed": False,
                "reason": "deploy config detected without repo-specific release guard",
                "evidence": evidence,
                "severity": "P1",
                "confidence": "medium",
            }
        )

    if has_reefiki_surface:
        evidence = ["REEFIKI wiki/bridge markers detected"]
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.reefiki-experience-monitor", "skill", "reefiki-experience-monitor", "P2", "medium", "Repo has REEFIKI knowledge surfaces that should be checked before non-trivial work.", evidence, "use_optional_skill"),
        )
        _append_unique(
            recommendations["skills"],
            _recommendation("skill.durable-harvest-closeout", "skill", "durable-harvest-closeout", "P2", "medium", "Valuable decisions/fixes should be harvested into durable knowledge.", evidence, "use_optional_skill"),
        )

    if not has_tests:
        evidence = ["no obvious test/CI marker detected"]
        risks.append(_risk("missing_test_gate", "Repo has no obvious test or CI gate.", "P1", "medium", evidence, ["rules"]))
        _append_unique(
            recommendations["rules"],
            _recommendation("rule.define-completion-tests", "rule", "define the command that proves completion before agent work starts", "P1", "medium", "Agents need a concrete verification gate.", evidence),
        )

    if existing_hooks:
        evidence = [".codex/hooks.json exists"]
        _append_unique(
            recommendations["hooks"],
            _recommendation("hook.review-existing-hooks", "hook", "review existing hooks and merge changes, do not overwrite", "P2", "high", "Existing deterministic enforcement should be preserved.", evidence),
        )

    if "monorepo" in repo_types and len(package_scopes) >= 2:
        evidence = [f"{scope['path']}:{','.join(scope['repo_types'])}" for scope in package_scopes[:10]]
        risks.append(
            _risk(
                "monorepo_package_scope_ambiguity",
                "Monorepo has multiple package scopes that may need package-specific agent guidance.",
                "P1",
                "medium",
                evidence,
                ["rules", "adapters"],
            )
        )
        _append_unique(
            recommendations["rules"],
            _recommendation(
                "rule.scope-agent-work-by-package",
                "rule",
                "agent tasks must declare target package/app scope before edits in a monorepo",
                "P1",
                "medium",
                "Package-level repo shapes can need different test, build, deploy and adapter guidance.",
                evidence,
            ),
        )
        _append_unique(
            recommendations["adapters"],
            _recommendation(
                "adapter.scoped-monorepo-adapters",
                "adapter",
                "scoped-monorepo-adapters",
                "P2",
                "medium",
                "Thin runtime adapters should point agents to the root contract plus the relevant package scope.",
                evidence,
                "adapter_only",
            ),
        )

    if "AGENTS.md" in files and "CLAUDE.md" not in files:
        evidence = ["AGENTS.md exists", "CLAUDE.md missing"]
        _append_unique(
            recommendations["adapters"],
            _recommendation("adapter.claude-code", "adapter", "claude-code", "P2", "medium", "Claude Code users may need a thin pointer to the canonical AGENTS.md contract.", evidence, "adapter_only"),
        )

    if "AGENTS.md" in files and ".cursor/rules" not in dirs and ".cursorrules" not in files:
        evidence = ["AGENTS.md exists", "Cursor rules missing"]
        _append_unique(
            recommendations["adapters"],
            _recommendation("adapter.cursor", "adapter", "cursor", "P2", "medium", "Cursor users may need a thin adapter that points to canonical repo rules.", evidence, "adapter_only"),
        )

    if len(agent_surfaces) >= 3:
        evidence = agent_surfaces
        risks.append(
            _risk(
                "multiple_agent_surfaces",
                "Repo has multiple agent instruction surfaces that may drift.",
                "P2",
                "low",
                evidence,
                ["rules", "adapters"],
            )
        )
        _append_unique(
            recommendations["rules"],
            _recommendation(
                "rule.consolidate-agent-contracts",
                "rule",
                "document the canonical agent contract and keep runtime adapters as thin pointers",
                "P2",
                "low",
                "Multiple agent surfaces are useful, but can drift without an explicit source-of-truth rule.",
                evidence,
            ),
        )

    signals = [
        {"id": "git", "value": git["is_git"], "evidence": [f"root={git['root']}"]},
        {"id": "dirty", "value": git["dirty"], "evidence": [f"dirty_paths={len(git['dirty_paths'])}", f"untracked_paths={len(git['untracked_paths'])}"]},
        {"id": "remotes", "value": [remote["name"] for remote in git["remotes"]], "evidence": [remote["name"] for remote in git["remotes"]]},
        {"id": "repo_types", "value": repo_types, "evidence": repo_types},
        {"id": "package_scopes", "value": package_scopes, "evidence": [scope["path"] for scope in package_scopes[:10]]},
        {"id": "test_markers", "value": test_markers, "evidence": test_markers[:10]},
        {"id": "agent_surfaces", "value": agent_surfaces, "evidence": agent_surfaces},
        {"id": "secret_like_paths_skipped", "value": len(scan["secret_like_paths"]), "evidence": scan["secret_like_paths"][:10]},
        {"id": "skipped_dirs", "value": scan["skipped_dirs"], "evidence": list(scan["skipped_dirs"].keys())},
    ]
    recommendation_count = sum(len(items) for items in recommendations.values())

    return {
        "schema_version": SCHEMA_VERSION,
        "repo": {
            "path": str(target),
            "root": str(root),
            "is_git": git["is_git"],
            "branch": git["branch"],
        },
        "summary": {
            "risk_level": _risk_level(risks),
            "repo_types": repo_types,
            "package_count": len(package_scopes),
            "agent_surfaces": agent_surfaces,
            "recommendation_count": recommendation_count,
            "risk_count": len(risks),
        },
        "signals": signals,
        "risks": risks,
        "recommendations": recommendations,
        "custom_skill_drafts": custom_skill_drafts,
        "install_plan": [
            {
                "id": "report_only_mvp",
                "action": "review recommendations manually; no install/apply command is generated in MVP",
                "write_allowed": False,
                "reason": "Agent Readiness MVP is read-only.",
            }
        ],
        "blocked_actions": [
            {"id": "auto_install", "reason": "MVP must not install skills, adapters or hooks.", "severity": "P0", "confidence": "high"},
            {"id": "mutate_target_repo", "reason": "MVP must not modify the analyzed repo.", "severity": "P0", "confidence": "high"},
            {"id": "run_package_scripts", "reason": "MVP inventory is file/git-signal based and never runs package scripts.", "severity": "P0", "confidence": "high"},
            {"id": "read_secret_contents", "reason": "Secret-like files are detected by path and skipped.", "severity": "P0", "confidence": "high"},
        ],
    }


def _format_items(items: list[dict[str, Any]], label_key: str) -> list[str]:
    if not items:
        return ["- none"]
    lines: list[str] = []
    for item in items:
        label = item.get(label_key) or item.get("id")
        evidence = ", ".join(str(value) for value in item.get("evidence", [])) or "-"
        lines.append(
            f"- `{label}` [{item['severity']}/{item['confidence']}]: {item['reason']} Evidence: {evidence}"
        )
    return lines


def agent_readiness_markdown(payload: dict[str, Any]) -> str:
    repo = payload["repo"]
    summary = payload["summary"]
    recommendations = payload["recommendations"]
    lines = [
        "# Agent Readiness Report",
        "",
        f"Repo: `{repo['root']}`",
        f"Risk level: `{summary['risk_level']}`",
        f"Recommendations: {summary['recommendation_count']}",
        "",
        "## Verdict",
        "",
        f"- Risk level: `{summary['risk_level']}`",
        f"- Read-only MVP: no install/apply action was generated.",
        "",
        "## Detected Repo Shape",
        "",
        f"- Git repo: {repo['is_git']}",
        f"- Branch: {repo.get('branch') or '-'}",
        f"- Repo types: {', '.join(summary['repo_types'])}",
        f"- Package scopes: {summary.get('package_count', 0)}",
        f"- Agent surfaces: {', '.join(summary['agent_surfaces']) if summary['agent_surfaces'] else 'none'}",
        "",
        "## Risks",
        "",
    ]
    if payload["risks"]:
        for risk in payload["risks"]:
            evidence = ", ".join(str(value) for value in risk.get("evidence", [])) or "-"
            lines.append(f"- `{risk['id']}` [{risk['severity']}/{risk['confidence']}]: {risk['title']} Evidence: {evidence}")
    else:
        lines.append("- none")
    package_signal = next((signal for signal in payload["signals"] if signal["id"] == "package_scopes"), None)
    if package_signal and package_signal["value"]:
        lines.extend(["", "## Package Scopes", ""])
        for scope in package_signal["value"]:
            markers = ", ".join(scope.get("markers", [])) or "-"
            repo_types = ", ".join(scope.get("repo_types", [])) or "unknown"
            lines.append(f"- `{scope['path']}`: {repo_types}. Markers: {markers}")
    lines.extend(["", "## Recommended Skills", ""])
    lines.extend(_format_items(recommendations["skills"], "skill"))
    lines.extend(["", "## Recommended Rules", ""])
    lines.extend(_format_items(recommendations["rules"], "rule"))
    lines.extend(["", "## Recommended Adapters", ""])
    lines.extend(_format_items(recommendations["adapters"], "adapter"))
    lines.extend(["", "## Recommended Hooks", ""])
    lines.extend(_format_items(recommendations["hooks"], "hook"))
    lines.extend(["", "## Custom Skill Drafts", ""])
    if payload["custom_skill_drafts"]:
        for draft in payload["custom_skill_drafts"]:
            evidence = ", ".join(str(value) for value in draft.get("evidence", [])) or "-"
            lines.append(f"- `{draft['name']}` [{draft['severity']}/{draft['confidence']}]: {draft['reason']} Evidence: {evidence}")
    else:
        lines.append("- none")
    lines.extend(["", "## Install Plan", ""])
    for step in payload["install_plan"]:
        lines.append(f"- `{step['id']}`: {step['action']}")
    lines.extend(["", "## Do Not Auto-Apply", ""])
    for blocked in payload["blocked_actions"]:
        lines.append(f"- `{blocked['id']}` [{blocked['severity']}/{blocked['confidence']}]: {blocked['reason']}")
    return "\n".join(lines) + "\n"


def write_agent_readiness_report(report_root: Path, payload: dict[str, Any]) -> Path:
    reports = report_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    base = reports / f"agent-readiness-{date.today().isoformat()}.md"
    path = base
    counter = 2
    while path.exists():
        path = reports / f"agent-readiness-{date.today().isoformat()}-{counter}.md"
        counter += 1
    path.write_text(agent_readiness_markdown(payload), encoding="utf-8", newline="\n")
    return path


def print_agent_readiness(repo_path: str, fmt: str, write_report: bool, report_root: Path | None) -> int:
    payload = agent_readiness_payload(Path(repo_path))
    if write_report:
        if report_root is None:
            raise SystemExit("--write-report requires a REEFIKI root via cwd or --project")
        report_path = write_agent_readiness_report(report_root, payload)
        payload["report_path"] = str(report_path.resolve())
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(agent_readiness_markdown(payload), end="")
        if write_report:
            print(f"Report written: {payload['report_path']}")
    return 0
