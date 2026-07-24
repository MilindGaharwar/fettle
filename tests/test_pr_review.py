"""WP-R — PR Review Orchestration tests."""

from unittest.mock import patch, MagicMock

from fettle.pr_review import generate_pr_review, _detect_breaking_changes


def test_no_changes_reports_nothing(tmp_path):
    with patch("fettle.pr_review._git_diff_files", return_value=[]):
        result = generate_pr_review(str(tmp_path))
    assert "No changes detected" in result


def test_report_includes_all_sections(tmp_path):
    with (
        patch("fettle.pr_review._git_diff_files", return_value=["src/app.py"]),
        patch("fettle.pr_review._git_diff_stat", return_value="1 file changed, 5 insertions"),
        patch("fettle.pr_review._run_quality_scan", return_value={"findings": [], "summary": {"errors": 0, "warnings": 2, "info": 1}}),
        patch("fettle.pr_review._get_coverage", return_value="85.0% overall"),
        patch("fettle.pr_review._detect_breaking_changes", return_value=[]),
    ):
        result = generate_pr_review(str(tmp_path))

    assert "## Changes" in result
    assert "## Quality Scan" in result
    assert "Warnings: 2" in result
    assert "## Coverage" in result
    assert "85.0%" in result
    assert "## Checklist" in result


def test_breaking_changes_shown(tmp_path):
    with (
        patch("fettle.pr_review._git_diff_files", return_value=["src/__init__.py"]),
        patch("fettle.pr_review._git_diff_stat", return_value="1 file changed"),
        patch("fettle.pr_review._run_quality_scan", return_value={"findings": [], "summary": {}}),
        patch("fettle.pr_review._get_coverage", return_value="N/A"),
        patch("fettle.pr_review._detect_breaking_changes", return_value=["src/__init__.py: removed export: from .auth import login"]),
    ):
        result = generate_pr_review(str(tmp_path))

    assert "## Breaking Changes" in result
    assert "removed export" in result


def test_detect_breaking_changes_finds_removed_export(tmp_path):
    diff_output = "-from .auth import login\n-def old_function():\n+def new_function():\n"
    mock_result = MagicMock()
    mock_result.stdout = diff_output
    mock_result.returncode = 0

    with patch("fettle.pr_review.subprocess.run", return_value=mock_result):
        breaking = _detect_breaking_changes(str(tmp_path), ["__init__.py"])
    assert len(breaking) >= 1
    assert "removed export" in breaking[0]
