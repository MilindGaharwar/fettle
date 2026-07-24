"""Tests for the Go post-edit check (scripts/post_edit_go.py).

Routes .go edits through semgrep (built-in rules/go-antipatterns.yml +
project rules from .fettle/rules/) and golangci-lint (only when the
anchor root has a go.mod — single files outside a module can't compile).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

sys.path.insert(0, os.path.join(PLUGIN_DIR))
from fettle.config import load_config  # noqa: E402
from fettle.dispatcher_registry import select_checks  # noqa: E402
from fettle.dispatcher_types import Decision, HookContext, HookInput  # noqa: E402
from fettle.post_edit_go import run_check  # noqa: E402

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _has_semgrep() -> bool:
    try:
        r = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5, env=_ENV)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


needs_semgrep = pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")


def _ctx(tmp_path, file_path, event="PostToolUse", tool="Edit", config_overrides=None):
    cfg = load_config(str(tmp_path))
    for dotted, value in (config_overrides or {}).items():
        node = cfg
        keys = dotted.split(".")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
    hook_input = HookInput(
        hook_event_name=event,
        tool_name=tool,
        tool_input={"file_path": str(file_path)},
        cwd=Path(tmp_path),
        session_id="test",
        raw={},
    )
    now = time.monotonic()
    return HookContext(
        input=hook_input,
        config=cfg,
        plugin_root=Path(PLUGIN_DIR),
        hook_start_monotonic=now,
        global_deadline_monotonic=now + 60,
    )


def _write_go(tmp_path, relpath, content):
    f = tmp_path / relpath
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content)
    return f


SWALLOWED_ERROR = 'package svc\n\nfunc f() {\n\tif err := do(); err != nil {\n\t}\n}\n'
DEBUG_PRINT = 'package svc\n\nimport "fmt"\n\nfunc f() {\n\tfmt.Println("here")\n}\n'
CLEAN = 'package svc\n\nfunc f() error {\n\treturn nil\n}\n'


# ── routing ──────────────────────────────────────────────────────────


def test_registry_routes_go_files(tmp_path):
    f = _write_go(tmp_path, "svc/main.go", CLEAN)
    ctx = _ctx(tmp_path, f)
    names = [spec.name for spec in select_checks(ctx)]
    assert "post_edit_go" in names


def test_non_go_file_allows(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("x = 1\n")
    result = run_check(_ctx(tmp_path, f))
    assert result.decision == Decision.ALLOW


def test_lint_gate_disabled_allows(tmp_path):
    f = _write_go(tmp_path, "svc/x.go", DEBUG_PRINT)
    ctx = _ctx(tmp_path, f, config_overrides={"gates.lint.enabled": False})
    assert run_check(ctx).decision == Decision.ALLOW


# ── semgrep findings ─────────────────────────────────────────────────


@needs_semgrep
def test_clean_go_file_allows(tmp_path):
    f = _write_go(tmp_path, "svc/x.go", CLEAN)
    assert run_check(_ctx(tmp_path, f)).decision == Decision.ALLOW


@needs_semgrep
def test_debug_print_is_advisory(tmp_path):
    f = _write_go(tmp_path, "svc/x.go", DEBUG_PRINT)
    result = run_check(_ctx(tmp_path, f))
    assert result.decision == Decision.ADVISORY
    assert "debug-print-go" in (result.message or "")


@needs_semgrep
def test_debug_print_excluded_in_cmd_dir(tmp_path):
    f = _write_go(tmp_path, "cmd/x.go", DEBUG_PRINT)
    assert run_check(_ctx(tmp_path, f)).decision == Decision.ALLOW


@needs_semgrep
def test_swallowed_error_blocks_in_enforce_mode(tmp_path):
    f = _write_go(tmp_path, "svc/x.go", SWALLOWED_ERROR)
    ctx = _ctx(tmp_path, f, config_overrides={"gates.lint.mode": "enforce"})
    result = run_check(ctx)
    assert result.decision == Decision.BLOCK
    assert "empty-error-swallow-go" in (result.message or "")


# ── project rules (.fettle/rules) — the DVA3 path ────────────────────


@needs_semgrep
def test_project_go_rule_fires(tmp_path):
    rules_dir = tmp_path / ".fettle" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "dva3.yml").write_text(
        "rules:\n"
        "  - id: no-direct-kafka-produce\n"
        "    languages: [go]\n"
        "    severity: ERROR\n"
        "    pattern: $P.Produce(...)\n"
        "    message: Produce events via the outbox, never directly.\n"
    )
    f = _write_go(
        tmp_path, "svc/handler.go",
        'package svc\n\nfunc f(p Producer) {\n\tp.Produce(msg, nil)\n}\n',
    )
    result = run_check(_ctx(tmp_path, f))
    assert result.decision == Decision.ADVISORY
    assert "no-direct-kafka-produce" in (result.message or "")
