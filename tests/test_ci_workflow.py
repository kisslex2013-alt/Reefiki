from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_runs_core_verification_gates():
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "timeout-minutes: 10" in text
    assert "contents: read" in text
    assert "runs-on: ${{ matrix.os }}" in text
    assert "fail-fast: false" in text
    assert "ubuntu-latest" in text
    assert "windows-latest" in text
    assert "macos-latest" in text
    assert "shell: pwsh" in text
    assert "python scripts/validate_frontmatter.py" in text
    assert '"projects/_template/wiki" "projects/reefiki-demo/wiki"' in text
    assert "projects/reefiki/wiki/*.md" not in text
    assert "projects/metrica/wiki/*.md" not in text
    assert "'projects/*/wiki/*.md'" not in text
    assert "xargs" not in text
    assert "python -m pytest" in text
    assert "python -m build" in text
    assert "reefiki-*.whl" in text
    assert "reefiki init --workspace" in text
    assert "reefiki --project $project doctor --format json" in text
    assert "python scripts/reefiki.py memory golden --project reefiki-demo --format json" in text
    assert "actions/checkout@v4" not in text
    assert "actions/setup-python@v5" not in text
    assert re.search(r"uses: actions/checkout@[0-9a-f]{40}", text)
    assert re.search(r"uses: actions/setup-python@[0-9a-f]{40}", text)


def _job_block(text: str, job_name: str, next_job_name: str | None = None) -> str:
    start = text.index(f"  {job_name}:")
    if next_job_name is None:
        return text[start:]
    end = text.index(f"  {next_job_name}:", start)
    return text[start:end]


def test_publish_python_workflow_is_manual_tokenless_and_oidc_scoped():
    workflow = ROOT / ".github" / "workflows" / "publish-python.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "push:" not in text
    assert "permissions:\n  contents: read" in text
    assert "description: \"Package index target\"" in text
    assert "default: build-only" in text
    assert "build-only" in text
    assert "testpypi" in text
    assert "pypi" in text
    assert "PyPI publishing requires running this workflow from a refs/tags/v* tag." in text
    assert "github.event.inputs.target == 'pypi' && !startsWith(github.ref, 'refs/tags/v')" in text
    assert "github.event.inputs.target == 'pypi' && startsWith(github.ref, 'refs/tags/v')" in text
    assert "repository-url: https://test.pypi.org/legacy/" in text
    assert "environment: testpypi" in text
    assert "environment: pypi" in text
    assert "TWINE_PASSWORD" not in text
    assert "PYPI_TOKEN" not in text
    assert "TEST_PYPI_TOKEN" not in text
    assert "secrets." not in text

    build_block = _job_block(text, "build-and-test", "publish-testpypi")
    assert "id-token" not in build_block
    assert "python -m pytest -q" in build_block
    assert "python -m twine check --strict dist/*" in build_block
    assert "github.event.inputs.target == 'build-only'" not in build_block

    testpypi_block = _job_block(text, "publish-testpypi", "publish-pypi")
    pypi_block = _job_block(text, "publish-pypi")
    assert "id-token: write" in testpypi_block
    assert "id-token: write" in pypi_block
    assert "skip-existing: true" in testpypi_block
    assert "repository-url:" not in pypi_block

    assert re.search(r"uses: actions/checkout@[0-9a-f]{40}", text)
    assert re.search(r"uses: actions/setup-python@[0-9a-f]{40}", text)
    assert re.search(r"uses: actions/upload-artifact@[0-9a-f]{40}", text)
    assert re.search(r"uses: actions/download-artifact@[0-9a-f]{40}", text)
    assert text.count("uses: pypa/gh-action-pypi-publish@v1.14.0") == 2
    assert "SHA-named image" in text
