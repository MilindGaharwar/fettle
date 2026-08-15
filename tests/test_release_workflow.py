"""Release workflow invariants for fail-closed publication."""

from pathlib import Path


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


def test_release_prerequisites_are_checked_before_publication():
    workflow = _workflow()

    notes_check = workflow.index("Verify authored release notes")
    publish = workflow.index("pypa/gh-action-pypi-publish")
    assert notes_check < publish


def test_release_candidate_runs_on_minimum_supported_python():
    workflow = _workflow()

    build = workflow[workflow.index("  build:"):workflow.index("  publish:")]
    assert 'python-version: "3.11"' in build


def test_ci_exposes_one_stable_required_check():
    workflow = CI_WORKFLOW.read_text()

    assert "  required:\n" in workflow
    assert "name: CI required" in workflow
    assert "needs: [lint, test, coverage]" in workflow
    assert "if: always()" in workflow
    assert "LINT_RESULT: ${{ needs.lint.result }}" in workflow
    assert "TEST_RESULT: ${{ needs.test.result }}" in workflow
    assert "COVERAGE_RESULT: ${{ needs.coverage.result }}" in workflow
    assert workflow.count('!= "success"') == 3
