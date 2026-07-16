"""Contract tests for semgrep rule configs and scan anchoring.

1. Every rule file under rules/ must pass `semgrep --validate` — an
   invalid config silently disables ALL rules in that file (this is
   exactly how the TS checks went dead before v0.4.1).
2. The anchored invocation helper must resolve paths.include/exclude
   correctly for files inside and outside git repos (semgrep >= 1.136
   anchors path filters to the git project root).
"""

import glob
import json
import os
import subprocess
import sys

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RULES_DIR = os.path.join(PLUGIN_DIR, "rules")

sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))
from semgrep_util import anchored_semgrep_args, validate_rule_pack  # noqa: E402

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _has_semgrep() -> bool:
    try:
        r = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5, env=_ENV)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")

RULE_FILES = sorted(glob.glob(os.path.join(RULES_DIR, "**", "*.yml"), recursive=True))


# ── 1. Config validity ────────────────────────────────────────────────


def test_rule_files_discovered():
    assert RULE_FILES, "no rule files found under rules/"


@pytest.mark.parametrize("rule_file", RULE_FILES, ids=lambda p: os.path.relpath(p, RULES_DIR))
def test_rule_file_is_valid(rule_file):
    # Offline-safe validation: semgrep >= 1.168 --validate fetches a registry
    # pack and hard-fails behind TLS-intercepting proxies.
    valid, err = validate_rule_pack(rule_file)
    assert valid, (
        f"{os.path.relpath(rule_file, PLUGIN_DIR)} is invalid — "
        f"ALL its rules are silently disabled:\n{err}"
    )


# ── 2. Anchored invocation helper ─────────────────────────────────────


def _scan(file_path, rules_file, cwd=None):
    args, run_cwd = anchored_semgrep_args(file_path, cwd=cwd)
    result = subprocess.run(
        ["semgrep", "scan", "--config", rules_file, "--json", "--quiet", *args],
        capture_output=True, text=True, timeout=60, env=_ENV, cwd=run_cwd,
    )
    data = json.loads(result.stdout)
    return [r["check_id"].split(".")[-1] for r in data.get("results", [])]


def test_anchor_non_git_dir_uses_file_dir_as_root(tmp_path):
    args, run_cwd = anchored_semgrep_args(str(tmp_path / "sub" / "x.py"))
    assert run_cwd == str(tmp_path / "sub")
    assert args == ["--project-root", ".", "x.py"]


def test_anchor_non_git_dir_falls_back_to_session_cwd(tmp_path):
    sub = tmp_path / "scripts"
    sub.mkdir()
    args, run_cwd = anchored_semgrep_args(str(sub / "x.py"), cwd=str(tmp_path))
    assert run_cwd == str(tmp_path)
    assert args == ["--project-root", ".", os.path.join("scripts", "x.py")]


def test_anchor_git_repo_uses_git_root(tmp_path):
    (tmp_path / ".git").mkdir()
    sub = tmp_path / "pipeline"
    sub.mkdir()
    args, run_cwd = anchored_semgrep_args(str(sub / "x.py"))
    assert run_cwd == str(tmp_path)
    assert args == ["--project-root", ".", os.path.join("pipeline", "x.py")]


def test_exclude_filter_applies_outside_git_repo(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    f = scripts_dir / "build.js"
    f.write_text("console.log('Building...');\n")
    rules = _scan(str(f), os.path.join(RULES_DIR, "ts-antipatterns.yml"), cwd=str(tmp_path))
    assert "debug-console-log" not in rules


def test_include_filter_applies_inside_git_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    f = pipeline / "job.py"
    f.write_text("from datetime import datetime\nnow = datetime.now()\n")
    rules = _scan(str(f), os.path.join(RULES_DIR, "llm-antipatterns.yml"))
    assert "datetime-now-pipeline" in rules
