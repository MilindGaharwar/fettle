"""Tests for project-local rule extension (scripts/project_rules.py).

Projects extend Fettle's built-in semgrep rules via .fettle.toml:

    [rules]
    extra_dirs = [".fettle/rules"]          # project rule files
    promise_apis = ["jQuery.ajax"]           # extra unawaited-promise APIs

extra_rule_configs() returns additional --config paths for the hooks.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))
from config import load_config  # noqa: E402
from project_rules import extra_rule_configs, generate_promise_rule  # noqa: E402

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _has_semgrep() -> bool:
    try:
        r = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5, env=_ENV)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _write_config(tmp_path, body):
    (tmp_path / ".fettle.toml").write_text(textwrap.dedent(body))


# ── discovery ────────────────────────────────────────────────────────


def test_no_project_rules_returns_empty(tmp_path):
    cfg = load_config(str(tmp_path))
    assert extra_rule_configs(cfg, str(tmp_path)) == []


def test_default_rules_dir_is_discovered(tmp_path):
    rules_dir = tmp_path / ".fettle" / "rules"
    rules_dir.mkdir(parents=True)
    rule = rules_dir / "custom.yml"
    rule.write_text("rules: []\n")
    cfg = load_config(str(tmp_path))
    assert extra_rule_configs(cfg, str(tmp_path)) == [str(rule)]


def test_configured_extra_dir_is_discovered(tmp_path):
    _write_config(tmp_path, """
        [rules]
        extra_dirs = ["lint/semgrep"]
    """)
    rules_dir = tmp_path / "lint" / "semgrep"
    rules_dir.mkdir(parents=True)
    rule = rules_dir / "go-rules.yaml"
    rule.write_text("rules: []\n")
    cfg = load_config(str(tmp_path))
    assert extra_rule_configs(cfg, str(tmp_path)) == [str(rule)]


def test_promise_apis_config_generates_rule(tmp_path):
    _write_config(tmp_path, """
        [rules]
        promise_apis = ["jQuery.ajax"]
    """)
    cfg = load_config(str(tmp_path))
    configs = extra_rule_configs(cfg, str(tmp_path))
    assert len(configs) == 1
    content = open(configs[0]).read()
    assert "jQuery.ajax(...)" in content


def test_generated_promise_rule_is_cached(tmp_path):
    cfg = {"rules": {"extra_dirs": [], "promise_apis": ["jQuery.ajax"]}}
    first = generate_promise_rule(cfg, str(tmp_path))
    mtime = os.path.getmtime(first)
    second = generate_promise_rule(cfg, str(tmp_path))
    assert first == second
    assert os.path.getmtime(second) == mtime


# ── end-to-end with semgrep ──────────────────────────────────────────


@pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")
def test_configured_promise_api_fires_end_to_end(tmp_path):
    _write_config(tmp_path, """
        [rules]
        promise_apis = ["jQuery.ajax"]
    """)
    src = tmp_path / "app.js"
    src.write_text("function f() {\n  jQuery.ajax({ url: '/x' });\n}\n")
    clean = tmp_path / "clean.js"
    clean.write_text("async function f() {\n  await jQuery.ajax({ url: '/x' });\n}\n")

    cfg = load_config(str(tmp_path))
    configs = extra_rule_configs(cfg, str(tmp_path))
    result = subprocess.run(
        ["semgrep", "scan", *[a for c in configs for a in ("--config", c)],
         "--json", "--quiet", "--project-root", ".", "app.js", "clean.js"],
        capture_output=True, text=True, timeout=60, env=_ENV, cwd=str(tmp_path),
    )
    data = json.loads(result.stdout)
    hits = {(r["path"], r["check_id"].split(".")[-1]) for r in data.get("results", [])}
    assert ("app.js", "unawaited-promise-project") in hits
    assert not any(p == "clean.js" for p, _ in hits)
