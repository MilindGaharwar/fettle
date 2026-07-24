"""WP-X1 — Technical Debt Dashboard tests."""

from debt_report import _scan_markers, _compute_rating, generate_debt_report, format_debt_report


def test_scan_counts_todos(tmp_path):
    (tmp_path / "app.py").write_text("# TODO: fix this\nx = 1  # FIXME later\n")
    result = _scan_markers(str(tmp_path))
    assert result["todo_count"] == 2


def test_scan_counts_suppressions(tmp_path):
    (tmp_path / "app.py").write_text("x = 1  # noqa: E501\ny = 2  # noqa\n")
    result = _scan_markers(str(tmp_path))
    assert result["suppression_count"] == 2


def test_scan_ignores_binary(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG TODO FIXME")
    result = _scan_markers(str(tmp_path))
    assert result["todo_count"] == 0


def test_scan_ignores_venv(tmp_path):
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "pkg.py").write_text("# TODO: internal\n")
    (tmp_path / "app.py").write_text("# clean\n")
    result = _scan_markers(str(tmp_path))
    assert result["todo_count"] == 0


def test_rating_a_for_clean():
    assert _compute_rating(0, 0, 100) == "A"


def test_rating_b_for_moderate():
    assert _compute_rating(3, 2, 100) == "B"


def test_rating_e_for_heavy():
    assert _compute_rating(15, 10, 100) == "E"


def test_rating_a_for_empty():
    assert _compute_rating(0, 0, 0) == "A"


def test_full_report(tmp_path):
    (tmp_path / "app.py").write_text("# TODO: something\nx = 1  # noqa\n")
    report = generate_debt_report(str(tmp_path))
    assert report["todo_count"] == 1
    assert report["suppression_count"] == 1
    assert report["rating"] in ("A", "B", "C", "D", "E")
    assert report["complexity_trend"] == "unknown"


def test_format_report():
    report = {
        "todo_count": 3,
        "suppression_count": 2,
        "files_scanned": 50,
        "complexity_trend": "stable",
        "lean_markers": [],
        "rating": "B",
    }
    output = format_debt_report(report)
    assert "Rating" in output
    assert "**B**" in output
    assert "TODO" in output
    assert "stable" in output
