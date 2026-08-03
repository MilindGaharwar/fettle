"""WP-4 hardening tests — adversarial command corpus + file-path parity.

Audit H-03 (regex bypass) and H-04 (subprocess vs dispatcher path drift).
These call the pure helpers directly: fast, no subprocess.
"""

import json
import os

import pytest

from fettle.mcp_trust_gate import (
    DEFAULT_ALLOWLIST_PATH,
    _check_bash_result,
    _check_file_result,
    _file_denial_reason,
    check_file_tool,
    load_allowlist,
)

ALLOWLIST = {
    "packages": {
        "@playwright/mcp": {"version": "0.0.70", "approved_by_human": True},
        "ruff": {"version": "0.15.20", "sha256_wheel": "aa11", "approved_by_human": True},
    },
    "registries_blocked": ["registry.npmjs.org", "pypi.org"],
    "protected_paths": ["/usr/local/bin/npm"],
}


# --- Adversarial corpus: every one of these bypassed or would bypass the
# --- old boundary class / wrapper handling. All must be denied.

DENIED = [
    # newline as separator (old class had no \n for package regexes)
    "true\npip install evil==1.0",
    "echo hi\nnpm install evil@1.0.0",
    # single pipe
    "true | pip install evil==1.0",
    # backtick command substitution
    "`npm install evil@1.0.0`",
    # wrapper prefixes
    "env FOO=1 pip install evil==1.0",
    "sudo -E npm install evil@1.0.0",
    "nohup pip install evil==1.0",
    "command pip install evil==1.0",
    # xargs-fed install (spec not in argv — ambiguity backstop)
    "echo evil==1.0 | xargs pip install",
    # python -m pip and uv forms
    "python -m pip install evil==1.0",
    "python3 -m pip install evil==1.0",
    "python3.12 -m pip install evil==1.0",
    "uv pip install evil==1.0",
    "uv tool install evil==1.0",
    "uv add evil==1.0",
    "uvx evil-tool",
    # quoted inside a shell-eval construct (ambiguity backstop)
    'bash -c "pip install evil==1.0"',
    "sh -c 'npm install evil@1.0.0'",
    "eval \"pip install evil==1.0\"",
    # unpinned still denied
    "npm install evil",
    # iptables via single pipe
    "true | iptables -F",
]

ALLOWED = [
    # approved, pinned installs
    "npm install @playwright/mcp@0.0.70",
    # everyday commands with install-y words in prose or paths
    "npm ls",
    "npm run build",
    "npm run test -- --seed $(date +%s)",  # $() but no install vocabulary
    "git commit -m 'pip install docs'",  # quoted prose, no eval construct
    "ls -la && echo done",
    "cargo build --release",
]


@pytest.mark.parametrize("command", DENIED)
def test_adversarial_command_denied(command):
    assert _check_bash_result(command, ALLOWLIST) is not None, command


@pytest.mark.parametrize("command", ALLOWED)
def test_benign_command_allowed(command):
    assert _check_bash_result(command, ALLOWLIST) is None, command


# --- File-path parity (H-04): subprocess and dispatcher paths share one
# --- resolver; every spelling of a protected target is caught by both.

def _both(file_path, allowlist, configured=None):
    return (
        _file_denial_reason(file_path, allowlist, configured),
        _check_file_result(file_path, allowlist, configured),
    )


def test_parity_literal_tilde_default_path():
    for r in _both(DEFAULT_ALLOWLIST_PATH, {"protected_paths": []}):
        assert r is not None


def test_parity_expanded_default_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MCP_ALLOWLIST_PATH", raising=False)
    expanded = str(tmp_path / ".config" / "fettle" / "mcp-allowlist.json")
    for r in _both(expanded, {"protected_paths": []}):
        assert r is not None


def test_parity_env_override_path(monkeypatch, tmp_path):
    target = tmp_path / "list.json"
    monkeypatch.setenv("MCP_ALLOWLIST_PATH", str(target))
    for r in _both(str(target), {"protected_paths": []}):
        assert r is not None


def test_parity_symlink_spelling(monkeypatch, tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    target = real_dir / "list.json"
    target.write_text("{}")
    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)
    monkeypatch.setenv("MCP_ALLOWLIST_PATH", str(target))
    for r in _both(str(link_dir / "list.json"), {"protected_paths": []}):
        assert r is not None


def test_parity_protected_prefix_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    allowlist = {"protected_paths": ["~/guard"]}
    for r in _both(str(tmp_path / "guard" / "x.sh"), allowlist):
        assert r is not None
    for r in _both("~/guard/x.sh", allowlist):
        assert r is not None


def test_unprotected_path_allowed(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_ALLOWLIST_PATH", raising=False)
    for r in _both(str(tmp_path / "src" / "app.py"), {"protected_paths": ["/usr/local/bin/npm"]}):
        assert r is None


# --- WP-4c: policy-pinned allowlist path makes the env override inert.

def test_config_pinned_path_wins_over_env(monkeypatch, tmp_path):
    pinned = tmp_path / "pinned.json"
    pinned.write_text(json.dumps({"packages": {}, "registries_blocked": [], "protected_paths": []}))
    rogue = tmp_path / "rogue.json"
    rogue.write_text(json.dumps({"packages": {"evil": {"version": "1.0"}},
                                 "registries_blocked": [], "protected_paths": []}))
    monkeypatch.setenv("MCP_ALLOWLIST_PATH", str(rogue))
    allowlist, err = load_allowlist(str(pinned))
    assert err is None
    assert allowlist["packages"] == {}  # rogue env file was ignored
    # and the PINNED file is what the write guard protects
    assert _file_denial_reason(str(pinned), allowlist, str(pinned)) is not None


def test_env_override_used_when_no_pin(monkeypatch, tmp_path):
    over = tmp_path / "over.json"
    over.write_text(json.dumps({"packages": {}, "registries_blocked": [],
                                "protected_paths": ["/opt/guard"]}))
    monkeypatch.setenv("MCP_ALLOWLIST_PATH", str(over))
    allowlist, err = load_allowlist()
    assert err is None
    assert allowlist["protected_paths"] == ["/opt/guard"]


def test_check_file_tool_denies_via_shared_resolver(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("MCP_ALLOWLIST_PATH", str(tmp_path / "list.json"))
    with pytest.raises(SystemExit) as exc:
        check_file_tool(str(tmp_path / "list.json"), {"protected_paths": []})
    assert exc.value.code == 2
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
