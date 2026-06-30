from scripts.reefiki_core.secret_scan import (
    full_tree_secret_scan_payload,
    print_secret_scan,
    secret_content_scan_payload,
)


def test_secret_content_scan_payload_passes_safe_files_and_skips_missing(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("safe public content", encoding="utf-8")

    payload = secret_content_scan_payload(repo, ["README.md", "missing.md"], "publish-task")

    assert payload == {
        "operation": "publish-task",
        "outcome": "pass",
        "reason": None,
        "checked_paths": ["README.md"],
        "blocking_paths": [],
    }


def test_secret_content_scan_payload_blocks_sensitive_content(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = "api" + "_key"
    (repo / "notes.md").write_text(f"{marker} = 'value'\n", encoding="utf-8")

    payload = secret_content_scan_payload(repo, ["notes.md"], "publish-task")

    assert payload["outcome"] == "block"
    assert payload["reason"] == "secret_like_content"
    assert payload["checked_paths"] == ["notes.md"]
    assert payload["blocking_paths"] == ["notes.md"]


def test_secret_content_scan_payload_allows_github_actions_oidc_permission(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    workflow = repo / ".github" / "workflows" / "publish-python.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("permissions:\n  contents: read\n  id-token: write\n", encoding="utf-8")

    payload = secret_content_scan_payload(repo, [".github/workflows/publish-python.yml"], "publish-task")

    assert payload["outcome"] == "pass"
    assert payload["blocking_paths"] == []


def test_secret_content_scan_payload_blocks_common_secret_canaries(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    credential_assignment = "cred" + "ential = "
    token_assignment = "to" + "ken = "
    bearer_prefix = "Bear" + "er "
    pem_header = "-----BEGIN " + "OPENSSH PRIVATE KEY" + "-----"
    aws_prefix = "AK" + "IA"
    github_prefix = "gh" + "p_"
    github_pat_prefix = "github" + "_pat_"
    google_prefix = "AI" + "za"
    slack_prefix = "xo" + "xb-"
    jwt_prefix = "ey" + "J"
    canaries = {
        "aws.md": credential_assignment + aws_prefix + "ABCDEFGHIJKLMNOP\n",
        "pem.md": pem_header + "\nplaceholder\n",
        "github.md": token_assignment + github_prefix + "abcdefghijklmnopqrstuvwxyz1234567890\n",
        "github-pat.md": github_pat_prefix + "abcdefghijklmnopqrstuvwxyz1234567890\n",
        "google.md": "api = " + google_prefix + "abcdefghijklmnopqrstuvwxyz12345\n",
        "slack.md": "slack = " + slack_prefix + "123456789012-abcdefghij\n",
        "bearer.md": "Authorization: " + bearer_prefix + "abcdefghijklmnopqrstuvwxyz012345\n",
        "jwt.md": "jwt = " + jwt_prefix + "abcdefghijk.abcdefghijklmnop.abcdefghijklmnop\n",
    }
    for path, content in canaries.items():
        (repo / path).write_text(content, encoding="utf-8")

    payload = secret_content_scan_payload(repo, list(canaries), "publish-task")

    assert payload["outcome"] == "block"
    assert payload["reason"] == "secret_like_content"
    assert payload["blocking_paths"] == sorted(canaries) or set(payload["blocking_paths"]) == set(canaries)


def test_secret_content_scan_payload_blocks_secret_like_paths(tmp_path) -> None:
    repo = tmp_path / "repo"
    secret_paths = [
        ".env",
        "data.env",
        "deploy.pem",
        "id_rsa",
        ".aws/credentials",
        ".ssh/config",
        "secrets.json",
    ]
    for path in secret_paths:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")

    payload = secret_content_scan_payload(repo, secret_paths, "publish-task")

    assert payload["outcome"] == "block"
    assert payload["reason"] == "secret_like_path"
    assert set(payload["blocking_paths"]) == set(secret_paths)


def test_secret_content_scan_payload_allows_public_token_economy_filename(tmp_path) -> None:
    repo = tmp_path / "repo"
    asset = repo / "assets" / "reefiki-token-economy.png"
    asset.parent.mkdir(parents=True)
    asset.write_text("public visual asset placeholder\n", encoding="utf-8")

    payload = secret_content_scan_payload(repo, ["assets/reefiki-token-economy.png"], "public-snapshot")

    assert payload["outcome"] == "pass"
    assert payload["blocking_paths"] == []


def test_print_secret_scan_text_reports_checked_paths(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("safe public content", encoding="utf-8")

    assert print_secret_scan(repo, ["README.md"], "text") == 0

    output = capsys.readouterr().out
    assert "outcome: pass" in output
    assert "- README.md" in output


def test_print_secret_scan_json_returns_nonzero_for_block(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = "api" + "_key"
    (repo / "notes.md").write_text(f"{marker} = 'value'\n", encoding="utf-8")

    assert print_secret_scan(repo, ["notes.md"], "json") == 1

    output = capsys.readouterr().out
    assert '"outcome": "block"' in output
    assert '"blocking_paths": [' in output


def test_print_secret_scan_requires_paths_without_all(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    assert print_secret_scan(repo, [], "json") == 1

    output = capsys.readouterr().out
    assert '"reason": "no_paths"' in output


def test_full_tree_secret_scan_blocks_untracked_secret_and_skips_forbidden_dirs(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("safe public content", encoding="utf-8")
    marker = "api" + "_key"
    (repo / "notes.md").write_text(f"{marker} = 'value'\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "ignored.md").write_text(f"{marker} = 'ignored'\n", encoding="utf-8")
    (repo / "archive.zip").write_bytes(b"PK\x03\x04")

    payload = full_tree_secret_scan_payload(repo)

    assert payload["scan_scope"] == "full-tree"
    assert payload["outcome"] == "block"
    assert "README.md" in payload["checked_paths"]
    assert "notes.md" in payload["checked_paths"]
    assert "notes.md" in payload["blocking_paths"]
    assert "node_modules/ignored.md" not in payload["checked_paths"]
    assert {"path": "node_modules/ignored.md", "reason": "forbidden_dir"} in payload["skipped_paths"]
    assert {"path": "archive.zip", "reason": "binary_or_archive"} in payload["skipped_paths"]


def test_full_tree_secret_scan_skips_symlinked_files(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    marker = "api" + "_key"
    outside.write_text(f"{marker} = 'outside'\n", encoding="utf-8")
    link = repo / "outside-link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        return

    payload = full_tree_secret_scan_payload(repo)

    assert "outside-link.txt" not in payload["checked_paths"]
    assert {"path": "outside-link.txt", "reason": "symlink"} in payload["skipped_paths"]


def test_print_secret_scan_all_rejects_mixed_explicit_paths(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("safe public content", encoding="utf-8")

    assert print_secret_scan(repo, ["README.md"], "json", scan_all=True) == 1

    output = capsys.readouterr().out
    assert '"reason": "all_with_paths"' in output
