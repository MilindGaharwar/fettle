"""WP-R — PR Review Orchestration tests."""

import subprocess
from unittest.mock import patch, MagicMock

from fettle.changeset import ChangedFile, ChangeStatus
from fettle.pr_review import generate_pr_review, _detect_breaking_changes


def test_no_changes_reports_nothing(tmp_path):
    with patch("fettle.pr_review._working_changes", return_value=[]):
        result = generate_pr_review(str(tmp_path))
    assert "No working-tree changes detected" in result


def test_report_includes_all_sections(tmp_path):
    with (
        patch("fettle.pr_review._working_changes", return_value=[
            ChangedFile("src/app.py", ChangeStatus.MODIFIED),
        ]),
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
        patch("fettle.pr_review._working_changes", return_value=[
            ChangedFile("src/__init__.py", ChangeStatus.MODIFIED),
        ]),
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


def test_report_uses_current_working_tree_instead_of_previous_commit(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@fettle.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    previous = tmp_path / "previous.py"
    previous.write_text("old = True\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "previous"], cwd=tmp_path, check=True)
    previous.write_text("old = False\n")
    subprocess.run(["git", "commit", "-qam", "latest"], cwd=tmp_path, check=True)

    unstaged = tmp_path / "tracked.py"
    unstaged.write_text("before = True\n")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "track file"], cwd=tmp_path, check=True)

    staged = tmp_path / "staged.py"
    staged.write_text("staged = True\n")
    subprocess.run(["git", "add", "staged.py"], cwd=tmp_path, check=True)
    unstaged.write_text("after = True\n")
    (tmp_path / "untracked.py").write_text("new = True\n")

    with (
        patch("fettle.pr_review._run_quality_scan", return_value={"findings": [], "summary": {}}),
        patch("fettle.pr_review._get_coverage", return_value="N/A"),
    ):
        result = generate_pr_review(str(tmp_path))

    assert "staged.py" in result
    assert "tracked.py" in result
    assert "untracked.py" in result
    assert "previous.py" not in result
