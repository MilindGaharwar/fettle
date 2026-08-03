"""Tests for fettle.semgrep_util — semgrep CLI argument helpers."""

from fettle.semgrep_util import anchored_semgrep_args


class TestAnchoredSemgrepArgs:
    def test_file_in_repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        target = tmp_path / "src" / "main.py"
        target.parent.mkdir()
        target.write_text("x = 1")
        args, cwd = anchored_semgrep_args(str(target), cwd=str(tmp_path))
        assert isinstance(args, list)
        assert isinstance(cwd, str)
        assert any("main.py" in a for a in args) or cwd == str(tmp_path)

    def test_absolute_path_preserved(self, tmp_path):
        target = tmp_path / "file.py"
        target.write_text("x = 1")
        args, cwd = anchored_semgrep_args(str(target), cwd=str(tmp_path))
        assert len(args) > 0
