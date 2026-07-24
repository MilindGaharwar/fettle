"""Tests for scripts/test_runner_opts.py — WP-88+89: Last-failed + parallel execution."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.test_runner_opts import (
    build_pytest_args,
    record_failures,
    get_last_failures,
    has_xdist,
)


def test_last_failed_rerun_first(tmp_path):
    history = tmp_path / "failures.json"
    record_failures(str(history), ["tests/test_a.py::test_x", "tests/test_b.py::test_y"])
    failures = get_last_failures(str(history))
    assert "tests/test_a.py::test_x" in failures


def test_failures_first_in_full_mode(tmp_path):
    history = tmp_path / "failures.json"
    record_failures(str(history), ["tests/test_a.py::test_x"])
    args = build_pytest_args(
        mode="full",
        failure_history=str(history),
    )
    assert "--ff" in args


def test_no_previous_failures_runs_normally(tmp_path):
    history = tmp_path / "failures.json"
    args = build_pytest_args(
        mode="full",
        failure_history=str(history),
    )
    assert "--lf" not in args
    assert "--ff" not in args


def test_failure_history_persisted(tmp_path):
    history = tmp_path / "failures.json"
    record_failures(str(history), ["tests/test_a.py::test_fail"])
    assert history.exists()
    data = json.loads(history.read_text())
    assert "tests/test_a.py::test_fail" in data


def test_cleared_on_full_pass(tmp_path):
    history = tmp_path / "failures.json"
    record_failures(str(history), ["tests/test_a.py::test_fail"])
    record_failures(str(history), [])
    failures = get_last_failures(str(history))
    assert failures == []


def test_xdist_detection():
    result = has_xdist()
    assert isinstance(result, bool)


def test_parallel_args_when_xdist_available(tmp_path):
    args = build_pytest_args(
        mode="full",
        parallel=True,
    )
    if has_xdist():
        assert "-n" in args
    else:
        assert "-n" not in args
