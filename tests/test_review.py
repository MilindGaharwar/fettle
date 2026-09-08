"""Tests for the provider-agnostic review command."""

from unittest.mock import patch

from fettle.review import main, review_file


def test_review_file_rejects_missing_and_short_files(tmp_path):
    assert review_file(str(tmp_path / "missing.py"), {})["message"] == "File not found"
    short = tmp_path / "short.py"
    short.write_text("pass\n")

    assert review_file(str(short), {})["status"] == "skipped"


def test_review_file_preserves_success_and_provider_failure(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("def answer():\n    return 42\n")
    with patch("fettle.review._call_review_llm", return_value="No issues found."):
        reviewed = review_file(str(source), {})
    with patch("fettle.review._call_review_llm", return_value=None):
        failed = review_file(str(source), {})

    assert reviewed == {
        "file": str(source),
        "status": "reviewed",
        "findings": "No issues found.",
    }
    assert failed["status"] == "error"
    assert failed["message"] == "LLM unavailable"


def test_main_returns_tool_error_when_review_is_incomplete(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.py"
    source.write_text("def answer():\n    return 42\n")
    monkeypatch.setattr("sys.argv", ["fettle.review", "--file", str(source)])

    with patch("fettle.review._call_review_llm", return_value=None):
        result = main()

    assert result == 2
    assert "error: LLM unavailable" in capsys.readouterr().out


def test_main_returns_tool_error_for_missing_file(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "missing.py"
    monkeypatch.setattr("sys.argv", ["fettle.review", "--file", str(missing)])

    result = main()

    assert result == 2
    assert "error: File not found" in capsys.readouterr().out


def test_main_returns_success_for_completed_review(tmp_path, monkeypatch, capsys):
    source = tmp_path / "app.py"
    source.write_text("def answer():\n    return 42\n")
    monkeypatch.setattr("sys.argv", ["fettle.review", "--file", str(source)])

    with patch("fettle.review._call_review_llm", return_value="No issues found."):
        result = main()

    assert result == 0
    assert "No issues found." in capsys.readouterr().out
