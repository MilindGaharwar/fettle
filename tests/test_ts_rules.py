"""Contract tests for ts-antipatterns.yml precision.

The v0.4.0 rules were resurrected in v0.4.1 after the config was found
invalid — and immediately measured at ~9,000 findings on a 23-file UI5
app. These tests pin the precision fixes:

- unawaited-promise only fires on known promise-returning APIs
  (fetch/axios), not on arbitrary function calls.
- regex-llm-output-ts is path-scoped to LLM-adjacent code
  (agents/, pipeline/, llm/) like its Python counterpart.
"""

import json
import os
import subprocess
import sys

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RULES_FILE = os.path.join(PLUGIN_DIR, "rules", "ts-antipatterns.yml")

sys.path.insert(0, os.path.join(PLUGIN_DIR))

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _has_semgrep() -> bool:
    try:
        r = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5, env=_ENV)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")


def _scan(tmp_path, relpath, content):
    fpath = tmp_path / relpath
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content)
    result = subprocess.run(
        ["semgrep", "scan", "--config", RULES_FILE, "--json", "--quiet",
         "--project-root", ".", relpath],
        capture_output=True, text=True, timeout=60, env=_ENV, cwd=str(tmp_path),
    )
    data = json.loads(result.stdout)
    return [r["check_id"].split(".")[-1] for r in data.get("results", [])]


# ── unawaited-promise ────────────────────────────────────────────────


def test_unawaited_fetch_statement_fires(tmp_path):
    rules = _scan(tmp_path, "app.ts", "function f(url) {\n  fetch(url, { signal: AbortSignal.timeout(1) });\n}\n")
    assert "unawaited-promise" in rules


def test_unawaited_axios_call_fires(tmp_path):
    rules = _scan(tmp_path, "app.ts", "function f(url) {\n  axios.post(url, {});\n}\n")
    assert "unawaited-promise" in rules


def test_awaited_fetch_is_clean(tmp_path):
    rules = _scan(tmp_path, "app.ts", "async function f(url) {\n  await fetch(url, { signal: AbortSignal.timeout(1) });\n}\n")
    assert "unawaited-promise" not in rules


def test_assigned_fetch_is_clean(tmp_path):
    rules = _scan(tmp_path, "app.ts", "async function f(url) {\n  const r = fetch(url, { signal: AbortSignal.timeout(1) });\n  return r;\n}\n")
    assert "unawaited-promise" not in rules


def test_returned_fetch_is_clean(tmp_path):
    rules = _scan(tmp_path, "app.ts", "function f(url) {\n  return fetch(url, { signal: AbortSignal.timeout(1) });\n}\n")
    assert "unawaited-promise" not in rules


def test_then_chained_fetch_is_clean(tmp_path):
    rules = _scan(tmp_path, "app.ts", "function f(url) {\n  fetch(url, { signal: AbortSignal.timeout(1) }).then(r => r.json());\n}\n")
    assert "unawaited-promise" not in rules


def test_ordinary_function_call_is_clean(tmp_path):
    rules = _scan(tmp_path, "app.ts", "function f() {\n  console.error('x');\n  doWork();\n  this.getView().setModel(m);\n}\n")
    assert "unawaited-promise" not in rules


# ── regex-llm-output-ts scoping ──────────────────────────────────────

_MATCH_CODE = "function f(s: string) {\n  return s.match(/x/);\n}\n"


def test_regex_llm_output_fires_in_agents_dir(tmp_path):
    rules = _scan(tmp_path, os.path.join("agents", "parse.ts"), _MATCH_CODE)
    assert "regex-llm-output-ts" in rules


def test_regex_llm_output_silent_outside_llm_paths(tmp_path):
    rules = _scan(tmp_path, os.path.join("webapp", "controller.ts"), _MATCH_CODE)
    assert "regex-llm-output-ts" not in rules
