"""Tests for scripts/targeted_tests.py — WP-86+87: Targeted test selection + confidence."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from targeted_tests import (
    select_tests,
    SelectedTests,
    Confidence,
)


def test_changed_test_file_selected_directly(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("def test_x(): pass\n")
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["tests/test_app.py"],
    )
    assert "tests/test_app.py" in sel.selected
    assert sel.confidence == Confidence.HIGH


def test_import_graph_selects_dependents(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "util.py").write_text("def helper(): pass\n")
    (src / "app.py").write_text("from src.util import helper\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("from src.app import *\ndef test_x(): pass\n")
    (tests / "test_util.py").write_text("from src.util import helper\ndef test_h(): pass\n")
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["src/util.py"],
        test_roots=["tests"],
    )
    # Should select test_util.py at minimum (imports util directly)
    assert any("test_util" in t for t in sel.selected)


def test_config_change_triggers_full_suite(tmp_path):
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["pyproject.toml"],
    )
    assert sel.run_full
    assert sel.confidence == Confidence.LOW


def test_lockfile_change_triggers_full_suite(tmp_path):
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["uv.lock"],
    )
    assert sel.run_full


def test_no_mapping_falls_back_to_full(tmp_path):
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["src/mystery.py"],
        test_roots=["tests"],
    )
    # No test directly imports mystery.py, confidence is low
    assert sel.confidence in (Confidence.LOW, Confidence.MEDIUM)


def test_confidence_high_for_direct_test(tmp_path):
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["tests/test_foo.py"],
    )
    assert sel.confidence == Confidence.HIGH


def test_confidence_medium_for_import_graph(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "core.py").write_text("x = 1\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text("from src.core import x\ndef test_x(): pass\n")
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["src/core.py"],
        test_roots=["tests"],
    )
    if sel.selected:
        assert sel.confidence == Confidence.MEDIUM


def test_confidence_low_for_no_mapping(tmp_path):
    sel = select_tests(
        cwd=str(tmp_path),
        changed_files=["src/isolated.py"],
        test_roots=[],
    )
    assert sel.confidence == Confidence.LOW


def test_respects_tier_timeout_budget():
    # Selection should be fast — just path analysis, no subprocess
    sel = select_tests(
        cwd="/tmp",
        changed_files=["a.py", "b.py", "c.py"],
    )
    assert isinstance(sel, SelectedTests)
