"""Tests for Fettle Semgrep rules — llm-antipatterns.yml.

Each of the 7 rules has one positive test (fixture triggers it) and
one negative test (clean code does NOT trigger it).
"""
import subprocess
import json
import tempfile
import shutil
import os
import textwrap

PLUGIN_DIR = os.path.expanduser(
    "~/.claude/plugins/fettle"
)
RULES_FILE = os.path.join(PLUGIN_DIR, "rules", "llm-antipatterns.yml")
FIXTURES_DIR = os.path.join(PLUGIN_DIR, "tests", "fixtures", "violations")

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def run_semgrep(target_file, cwd=None, extra_args=None):
    """Run semgrep and return list of rule IDs that matched."""
    cmd = ["semgrep", "scan", "--config", RULES_FILE, "--json"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(target_file)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        env=_ENV,
        cwd=cwd,
    )
    try:
        data = json.loads(result.stdout)
        return [r["check_id"].split(".")[-1] for r in data.get("results", [])]
    except (json.JSONDecodeError, KeyError):
        return []


def _write_tmp(content, filename="clean.py", subdir=None):
    """Write content to a temp file, optionally under subdir, return (tmpdir, relpath)."""
    tmpdir = tempfile.mkdtemp()
    if subdir:
        target_dir = os.path.join(tmpdir, subdir)
        os.makedirs(target_dir, exist_ok=True)
    else:
        target_dir = tmpdir
    fpath = os.path.join(target_dir, filename)
    with open(fpath, "w") as f:
        f.write(textwrap.dedent(content))
    relpath = os.path.relpath(fpath, tmpdir)
    return tmpdir, relpath


# ── Rule 1: regex-llm-output ──────────────────────────────────────────


def test_regex_llm_output_positive():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline_dir = os.path.join(tmpdir, "pipeline")
        os.makedirs(pipeline_dir)
        shutil.copy(
            os.path.join(FIXTURES_DIR, "regex_llm_output.py"),
            os.path.join(pipeline_dir, "test.py"),
        )
        rules = run_semgrep("pipeline/test.py", cwd=tmpdir)
        assert "regex-llm-output" in rules


def test_regex_llm_output_negative():
    tmpdir, relpath = _write_tmp(
        """\
        import re
        m = re.search(r"hello", text)
        """,
        subdir="pipeline",
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "regex-llm-output" not in rules
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 2: bare-except-swallow ───────────────────────────────────────


def test_bare_except_swallow_positive():
    rules = run_semgrep(os.path.join(FIXTURES_DIR, "except_pass.py"))
    assert "bare-except-swallow" in rules


def test_bare_except_swallow_negative():
    tmpdir, relpath = _write_tmp(
        """\
        try:
            x = 1 / 0
        except ZeroDivisionError:
            pass
        """
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "bare-except-swallow" not in rules
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 3: broad-except-no-reraise ──────────────────────────────────


def test_broad_except_no_reraise_positive():
    rules = run_semgrep(os.path.join(FIXTURES_DIR, "broad_except.py"))
    assert "broad-except-no-reraise" in rules


def test_broad_except_no_reraise_negative():
    tmpdir, relpath = _write_tmp(
        """\
        import logging
        try:
            x = 1 / 0
        except Exception as e:
            logging.error("err %s", e)
        """
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "broad-except-no-reraise" not in rules
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 4: missing-httpx-timeout ────────────────────────────────────


def test_missing_httpx_timeout_positive():
    rules = run_semgrep(os.path.join(FIXTURES_DIR, "missing_timeout.py"))
    assert "missing-httpx-timeout" in rules


def test_missing_httpx_timeout_negative():
    tmpdir, relpath = _write_tmp(
        """\
        import httpx
        client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        """
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "missing-httpx-timeout" not in rules
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 5: sql-fstring ──────────────────────────────────────────────


def test_sql_fstring_positive():
    rules = run_semgrep(os.path.join(FIXTURES_DIR, "sql_fstring_semgrep.py"))
    assert "sql-fstring" in rules


def test_sql_fstring_negative():
    tmpdir, relpath = _write_tmp(
        """\
        query = "SELECT * FROM users WHERE id = ?"
        cursor.execute(query, (user_id,))
        """
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "sql-fstring" not in rules
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 6: datetime-now-pipeline ────────────────────────────────────


def test_datetime_now_pipeline_positive():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline_dir = os.path.join(tmpdir, "pipeline")
        os.makedirs(pipeline_dir)
        shutil.copy(
            os.path.join(FIXTURES_DIR, "datetime_now_pipeline.py"),
            os.path.join(pipeline_dir, "test.py"),
        )
        rules = run_semgrep("pipeline/test.py", cwd=tmpdir)
        assert "datetime-now-pipeline" in rules


def test_datetime_now_pipeline_negative():
    tmpdir, relpath = _write_tmp(
        """\
        from datetime import datetime
        def get_time(clock=None):
            return clock() if clock else None
        """,
        subdir="pipeline",
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "datetime-now-pipeline" not in rules
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 7: non-atomic-write-output ──────────────────────────────────


def test_non_atomic_write_output_positive():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = os.path.join(tmpdir, "output")
        os.makedirs(output_dir)
        shutil.copy(
            os.path.join(FIXTURES_DIR, "non_atomic_write.py"),
            os.path.join(output_dir, "test.py"),
        )
        rules = run_semgrep("output/test.py", cwd=tmpdir)
        assert "non-atomic-write-output" in rules


def test_non_atomic_write_output_negative():
    tmpdir, relpath = _write_tmp(
        """\
        import tempfile, os
        from pathlib import Path
        path = Path("/tmp/output.txt")
        fd, tmp = tempfile.mkstemp(dir=path.parent)
        os.write(fd, b"data")
        os.close(fd)
        os.replace(tmp, str(path))
        """,
        subdir="output",
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "non-atomic-write-output" not in rules
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 8: health-score-inversion ───────────────────────────────────


def test_health_score_inversion_positive():
    """health_inversion.py fixture triggers health-score-inversion."""
    rules = run_semgrep(os.path.join(FIXTURES_DIR, "health_inversion.py"))
    assert "health-score-inversion" in rules, (
        f"Expected health-score-inversion, got: {rules}"
    )


def test_health_score_inversion_negative():
    """A function that returns 0.0 on no-data does NOT trigger the rule."""
    tmpdir, relpath = _write_tmp(
        """\
        def responsiveness(p95: float) -> float:
            if p95 <= 0.0:
                return 0.0
            return max(0.0, 1.0 - p95 / 10.0)
        """
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "health-score-inversion" not in rules, (
            f"False positive on correct degraded-on-no-data pattern: {rules}"
        )
    finally:
        shutil.rmtree(tmpdir)


def test_health_score_inversion_ternary():
    """Ternary form `return 1.0 if x <= 0 else x` also triggers the rule."""
    tmpdir, relpath = _write_tmp(
        """\
        def score(x: float) -> float:
            return 1.0 if x <= 0.0 else x
        """
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir)
        assert "health-score-inversion" in rules, (
            f"Ternary inversion not caught: {rules}"
        )
    finally:
        shutil.rmtree(tmpdir)


# ── Rule 9: orphaned-queue-flag ───────────────────────────────────────


def test_orphaned_queue_flag_positive():
    """orphaned_queue.py fixture triggers orphaned-queue-flag."""
    rules = run_semgrep(
        os.path.join(FIXTURES_DIR, "orphaned_queue.py"),
        extra_args=["--no-git-ignore"],
    )
    assert "orphaned-queue-flag" in rules, (
        f"Expected orphaned-queue-flag, got: {rules}"
    )


def test_orphaned_queue_flag_negative():
    """File with fettle:queue-consumer-verified annotation does NOT trigger."""
    tmpdir, relpath = _write_tmp(
        """\
        import sqlite3

        def append_episode(db_path, text):
            conn = sqlite3.connect(db_path)
            processed = 0  # fettle:queue-consumer-verified consumer=consumer.py
            conn.execute(
                "INSERT INTO episodes (text, processed) VALUES (?,?)",
                (text, processed),
            )
            conn.commit()
        """
    )
    try:
        rules = run_semgrep(relpath, cwd=tmpdir, extra_args=["--no-git-ignore"])
        assert "orphaned-queue-flag" not in rules, (
            f"Annotated queue incorrectly flagged: {rules}"
        )
    finally:
        shutil.rmtree(tmpdir)
