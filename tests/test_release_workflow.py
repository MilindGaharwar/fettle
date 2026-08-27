"""Release workflow invariants for fail-closed publication."""

from pathlib import Path
import zipfile


WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"


def _workflow() -> str:
    return WORKFLOW.read_text()


def test_release_preflight_blocks_build_and_publish():
    workflow = _workflow()

    assert "preflight:" in workflow
    assert "Verify exact commit CI succeeded" in workflow
    assert "head_sha=$TARGET_SHA" in workflow
    assert "conclusion" in workflow
    assert "build:\n    needs: preflight" in workflow
    assert "publish:\n    needs: build" in workflow
    assert "public-canary:\n    needs: publish" in workflow
    assert "release:\n    needs: public-canary" in workflow


def test_release_prerequisites_are_checked_before_publication():
    workflow = _workflow()

    notes_check = workflow.index("Verify authored release notes")
    publish = workflow.index("pypa/gh-action-pypi-publish")
    assert notes_check < publish


def test_release_candidate_runs_on_minimum_supported_python():
    workflow = _workflow()

    build = workflow[workflow.index("  build:"):workflow.index("  publish:")]
    assert 'python-version: "3.11"' in build


def test_release_tests_exact_wheel_through_pipx_and_retains_digest():
    workflow = _workflow()
    build = workflow[workflow.index("  build:"):workflow.index("  publish:")]

    assert "pipx==1.7.1" in build
    assert "pipx install \"$WHEEL\"" in build
    assert "/tmp/candidate-bin/fettle demo" in build
    assert "sha256sum \"$WHEEL\"" in build
    assert "name: artifact-contract" in build
    assert "fettle.installed_artifact_canary" in build
    assert "cd /tmp" in build
    assert '--output "$GITHUB_WORKSPACE/artifact-contract/candidate.json"' in build
    assert "relative_to(Path('/tmp/candidate-pipx/venvs/finefettle').resolve())" in build


def test_built_wheel_contains_installed_hook_and_demo_assets(tmp_path):
    wheels = list((Path(__file__).parent.parent / "dist").glob("finefettle-*.whl"))
    if not wheels:
        return
    with zipfile.ZipFile(max(wheels, key=lambda path: path.stat().st_mtime_ns)) as archive:
        names = set(archive.namelist())
    assert "fettle/_bridge/subagent_inject.js" in names
    assert "fettle/_demo_fixture/calculator.py.txt" in names
    assert "fettle/_demo_fixture/test_calculator.py.txt" in names


def test_sdist_smoke_runs_demo():
    build = _workflow()[_workflow().index("  build:"):_workflow().index("  publish:")]
    assert "/tmp/sdist-smoke/bin/fettle demo" in build


def test_release_smokes_dependency_free_base_and_all_capabilities():
    workflow = _workflow()
    build = workflow[workflow.index("  build:"):workflow.index("  publish:")]

    assert "/tmp/smoke/bin/pip install --quiet --no-deps dist/*.whl" in build
    assert "/tmp/smoke/bin/fettle demo" in build
    assert '"${WHEEL}[all]"' in build
    assert "import fettle.evals_runner, playwright, pytest, yaml" in build
    assert "bindir = Path('/tmp/all-smoke/bin')" in build
    assert "('deptry', 'mutmut', 'pre-commit', 'pyright', 'ruff', 'semgrep')" in build


def test_public_canary_verifies_digest_and_installed_behavior():
    workflow = _workflow()
    canary = workflow[workflow.index("  public-canary:"):workflow.index("  release:")]

    assert "pip download" in canary
    assert "sha256sum -c" in canary
    assert "pipx install \"$PUBLIC_WHEEL\"" in canary
    assert "fettle.installed_artifact_canary" in canary
    assert "cd /tmp" in canary
    assert '--output "$GITHUB_WORKSPACE/artifact-contract/public.json"' in canary
    assert "fettle.installed_artifact_contract" in canary
    assert '"$GITHUB_WORKSPACE/artifact-contract/candidate.json" "$GITHUB_WORKSPACE/artifact-contract/public.json"' in canary
    assert "name: public-artifact-contract" in canary
    assert "relative_to(Path('/tmp/public-pipx/venvs/finefettle').resolve())" in canary
    assert "actions/checkout" not in canary


def test_ci_exposes_one_stable_required_check():
    workflow = CI_WORKFLOW.read_text()

    assert "  required:\n" in workflow
    assert "name: CI required" in workflow
    assert "needs: [lint, test, coverage, windows-bridge, linux-wheel]" in workflow
    assert "if: always()" in workflow
    assert "LINT_RESULT: ${{ needs.lint.result }}" in workflow
    assert "TEST_RESULT: ${{ needs.test.result }}" in workflow
    assert "COVERAGE_RESULT: ${{ needs.coverage.result }}" in workflow
    assert "WINDOWS_BRIDGE_RESULT: ${{ needs.windows-bridge.result }}" in workflow
    assert "LINUX_WHEEL_RESULT: ${{ needs.linux-wheel.result }}" in workflow
    assert workflow.count('!= "success"') == 5


def test_ci_runs_blocking_windows_bridge_publication_uat():
    workflow = CI_WORKFLOW.read_text()
    windows = workflow[workflow.index("  windows-bridge:"):workflow.index("  required:")]

    assert "runs-on: windows-latest" in windows
    assert '"fettle python"' in windows
    assert "$env:LOCALAPPDATA" in windows
    assert "fettle init --dry-run --json" in windows
    assert "fettle init --json" in windows
    assert "fettle doctor --json" in windows
    assert 'from fettle.bridge import bridge_dir; print(bridge_dir())' in windows
    assert 'Write-Host ($doctor | ConvertTo-Json -Depth 6)' in windows
    assert 'Add-Content (Join-Path $bridgeVersion "opencode\\fettle.ts")' in windows
    assert "fettle demo" in windows


def test_ci_runs_blocking_linux_pipx_container_uat():
    workflow = CI_WORKFLOW.read_text()
    linux = workflow[workflow.index("  linux-wheel:"):workflow.index("  required:")]

    assert "container: python:3.12-slim" in linux
    assert "pipx install dist/*.whl" in linux
    assert "/tmp/bin/fettle demo || exit 1" in linux
    assert "/tmp/bin/fettle init --json" in linux
    assert "steps['opencode']['status'] == 'created'" in linux
    assert "validate_bridge().ok" in linux
