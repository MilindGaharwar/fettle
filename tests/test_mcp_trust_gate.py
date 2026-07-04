"""Tests for trust gate — PreToolUse hook blocking unauthorized package installations."""

import json
import os
import subprocess
import sys

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "mcp_trust_gate.py")

LEDGER = {
    "version": 1,
    "packages": {
        "@playwright/mcp": {
            "version": "0.0.70",
            "sha256_tarball": "abc123",
            "audited_date": "2026-04-22",
            "audited_by": "council-4-model",
            "audit_report": ".fettle/audits/playwright-mcp-0.0.70.md",
            "approved_by_human": True,
        }
    },
    "registries_blocked": [
        "registry.npmjs.org",
        "pypi.org",
        "files.pythonhosted.org",
        "crates.io",
        "static.crates.io",
    ],
    "protected_paths": [
        "~/.config/fettle/mcp-allowlist.json",
        "/usr/local/sbin/pkg-guard.sh",
        "/usr/local/bin/npm",
        "/usr/local/bin/npx",
    ],
}


@pytest.fixture(autouse=True)
def ledger_file(tmp_path):
    path = tmp_path / "allowlist.json"
    path.write_text(json.dumps(LEDGER))
    os.environ["MCP_ALLOWLIST_PATH"] = str(path)
    yield path
    os.environ.pop("MCP_ALLOWLIST_PATH", None)


def run_gate(stdin_data: dict):
    env = {
        **os.environ,
        "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""),
    }
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return proc.stdout, proc.stderr, proc.returncode


# --- Package install commands blocked ---

def test_npm_install_no_version_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "npm install some-package"}}
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_npm_install_not_in_ledger_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "npm install evil-pkg@1.0.0"}}
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_npm_install_approved_allowed():
    _, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "npm install @playwright/mcp@0.0.70"}}
    )
    assert rc == 0


def test_npx_unapproved_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "npx @evil/mcp@latest"}}
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pip_install_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "pip install some-server"}}
    )
    assert rc == 2


def test_curl_registry_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "curl https://registry.npmjs.org/@evil/pkg"}}
    )
    assert rc == 2


def test_wget_registry_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "wget https://pypi.org/packages/evil-pkg.tar.gz"}}
    )
    assert rc == 2


# --- sudo escalation blocked ---

def test_sudo_npm_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "sudo npm install evil-pkg@1.0.0"}}
    )
    assert rc == 2


def test_sudo_iptables_delete_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "sudo iptables -D OUTPUT 1"}}
    )
    assert rc == 2


def test_sudo_iptables_flush_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "sudo iptables -F"}}
    )
    assert rc == 2


# --- Non-install commands pass through ---

def test_npm_ls_allowed():
    _, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "npm ls"}}
    )
    assert rc == 0


def test_non_package_manager_allowed():
    _, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "ls -la /tmp/fettle"}}
    )
    assert rc == 0


def test_git_clone_non_registry_allowed():
    _, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "git clone https://github.com/user/some-repo.git"}}
    )
    assert rc == 0


# --- Edge cases ---

def test_malformed_stdin_allows():
    env = {
        **os.environ,
        "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", ""),
    }
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input="NOT JSON",
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert proc.returncode == 0


# --- File tool protection (Write/Edit to protected paths) ---

def test_write_to_ledger_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Write", "tool_input": {"file_path": "~/.config/fettle/mcp-allowlist.json", "content": "{}"}}
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_edit_to_wrapper_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Edit", "tool_input": {"file_path": "/usr/local/sbin/pkg-guard.sh", "old_string": "x", "new_string": "y"}}
    )
    assert rc == 2


def test_bash_redirect_to_ledger_blocked():
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": "cat > ~/.config/fettle/mcp-allowlist.json << 'EOF'\n{}\nEOF"}}
    )
    assert rc == 2


def test_iptables_delete_multiline_blocked():
    cmd = 'echo "Testing..."' + chr(10) + 'sudo ipt' + 'ables -D OUTPUT 1'
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}}
    )
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_iptables_flush_after_semicolon_blocked():
    cmd = 'echo test; sudo ipt' + 'ables -F'
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}}
    )
    assert rc == 2


def test_iptables_no_sudo_blocked():
    cmd = 'ipt' + 'ables -D OUTPUT 1'
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": cmd}}
    )
    assert rc == 2


def test_cp_to_protected_path_blocked():
    path = "/usr/local" + "/bin/npm"
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": f"sudo cp /tmp/evil.sh {path}"}}
    )
    assert rc == 2


def test_mv_to_protected_path_blocked():
    path = "/usr/local" + "/bin/npx"
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": f"sudo mv /tmp/evil.sh {path}"}}
    )
    assert rc == 2


def test_install_to_protected_path_blocked():
    path = "/etc/mcp-" + "allowlist.json"
    stdout, _, rc = run_gate(
        {"tool_name": "Bash", "tool_input": {"command": f"sudo install -m 755 /tmp/evil.sh {path}"}}
    )
    assert rc == 2
