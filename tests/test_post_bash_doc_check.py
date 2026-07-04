"""Tests for post_bash_doc_check.py — documentation-before-push enforcement hook."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "post_bash_doc_check.py")


def run_hook(command: str, tracking_entries: list[dict] | None = None, mode: str = "soft",
             enabled: bool = True):
    """Run post_bash_doc_check.py with a crafted tracking file and return (stdout, stderr, rc)."""
    tmpdir = tempfile.mkdtemp()
    try:
        tracking_path = os.path.join(tmpdir, "fettle-edits.jsonl")
        if tracking_entries is not None:
            with open(tracking_path, "w") as fh:
                for entry in tracking_entries:
                    fh.write(json.dumps(entry) + "\n")

        if enabled:
            with open(os.path.join(tmpdir, ".fettle.toml"), "w") as fh:
                fh.write(f'[gates.docs]\nenabled = true\nmode = "{mode}"\n')

        stdin_data = {"tool_input": {"command": command}, "cwd": tmpdir}
        env = {
            **os.environ,
            "FETTLE_EDIT_TRACKING": tracking_path,
        }
        env.pop("FETTLE_GATE_MODE", None)

        proc = subprocess.run(
            [sys.executable, SCRIPT],
            input=json.dumps(stdin_data),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        return proc.stdout, proc.stderr, proc.returncode
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def make_entry(path: str, ts: float | None = None) -> dict:
    return {"file": path, "ts": ts or time.time(), "tested": False, "tool": "Edit"}


# ─── 1. Non-push command is ignored ─────────────────────────────────────────
def test_non_push_command_ignored():
    stdout, stderr, rc = run_hook("ls -la", tracking_entries=[make_entry("/app/foo.py")])
    assert rc == 0
    assert stdout == ""


# ─── 2. Push with no tracking file exits 0 ──────────────────────────────────
def test_push_no_tracking_file():
    """No tracking file means nothing to enforce."""
    tmpdir = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmpdir, ".fettle.toml"), "w") as fh:
            fh.write('[gates.docs]\nenabled = true\nmode = "soft"\n')
        stdin_data = {"tool_input": {"command": "git push origin main"}, "cwd": tmpdir}
        env = {**os.environ, "FETTLE_EDIT_TRACKING": os.path.join(tmpdir, "nonexistent.jsonl")}
        env.pop("FETTLE_GATE_MODE", None)
        proc = subprocess.run(
            [sys.executable, SCRIPT],
            input=json.dumps(stdin_data),
            capture_output=True, text=True, timeout=10, env=env,
        )
        assert proc.returncode == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── 2b. Gate is off by default — push never blocked without opt-in ─────────
def test_gate_off_by_default():
    """Opinionated process gates default OFF: no .fettle.toml, no blocking."""
    entries = [make_entry("/project/scripts/post_edit.py")]
    stdout, stderr, rc = run_hook("git push origin main", entries, enabled=False)
    assert rc == 0
    assert stdout == ""


# ─── 3. Push with empty tracking file exits 0 ───────────────────────────────
def test_push_empty_tracking_file():
    stdout, stderr, rc = run_hook("git push origin main", tracking_entries=[])
    assert rc == 0
    assert stdout == ""


# ─── 4. Push with only doc edits exits 0 ────────────────────────────────────
def test_push_only_doc_edits_allowed():
    entries = [make_entry("/project/README.md")]
    stdout, stderr, rc = run_hook("git push", entries)
    assert rc == 0
    assert stdout == ""


# ─── 5. Push blocked when only impl edits, no doc update ────────────────────
def test_push_blocked_with_only_impl_edits():
    """Regression for 2026-05-01: Fettle hardening pushed without README update."""
    entries = [make_entry("/project/scripts/post_edit.py")]
    stdout, stderr, rc = run_hook("git push origin main", entries)
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed["decision"] == "block"
    assert "CRITICAL SYSTEM DIRECTIVE" in parsed["reason"]
    assert "post_edit.py" in parsed["reason"]


# ─── 6. Push allowed when doc edited after impl edit ────────────────────────
def test_push_allowed_when_doc_follows_impl():
    base_ts = time.time() - 100
    entries = [
        make_entry("/project/scripts/post_edit.py", ts=base_ts),
        make_entry("/project/README.md", ts=base_ts + 10),
    ]
    stdout, stderr, rc = run_hook("git push origin main", entries)
    assert rc == 0


# ─── 7. Push blocked when doc edit is older than impl edit ──────────────────
def test_push_blocked_when_doc_is_older_than_impl():
    base_ts = time.time() - 100
    entries = [
        make_entry("/project/README.md", ts=base_ts),
        make_entry("/project/scripts/post_edit.py", ts=base_ts + 10),
    ]
    stdout, stderr, rc = run_hook("git push origin main", entries)
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert parsed["decision"] == "block"


# ─── 8. Advisory mode never blocks ──────────────────────────────────────────
def test_advisory_mode_never_blocks():
    entries = [make_entry("/project/scripts/post_edit.py")]
    stdout, stderr, rc = run_hook("git push origin main", entries, mode="advisory")
    assert rc == 0
    parsed = json.loads(stdout.strip())
    assert parsed["decision"] == "continue"
    assert "[ADVISORY]" in parsed["reason"]


# ─── 9. Test files in /tests/ not counted as impl ───────────────────────────
def test_test_files_not_counted_as_impl():
    entries = [make_entry("/project/tests/test_foo.py")]
    stdout, stderr, rc = run_hook("git push", entries)
    assert rc == 0
    assert stdout == ""


# ─── 10. Multiple impl files listed in block message ────────────────────────
def test_multiple_impl_files_listed():
    entries = [
        make_entry("/project/scripts/hook_a.py"),
        make_entry("/project/scripts/hook_b.py"),
    ]
    stdout, stderr, rc = run_hook("git push origin main", entries)
    assert rc == 2
    parsed = json.loads(stdout.strip())
    assert "hook_a.py" in parsed["reason"]
    assert "hook_b.py" in parsed["reason"]


# ─── 11. git push --force also triggers the hook ────────────────────────────
def test_git_push_force_triggers():
    entries = [make_entry("/project/main.py")]
    stdout, stderr, rc = run_hook("git push --force origin main", entries)
    assert rc == 2


# ─── 12. Malformed stdin exits 0 ────────────────────────────────────────────
def test_malformed_stdin_exits_0():
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input="NOT VALID JSON",
        capture_output=True, text=True, timeout=10, env=os.environ,
    )
    assert proc.returncode == 0


# ─── 13. Rust impl files are counted ────────────────────────────────────────
def test_rust_impl_files_counted():
    entries = [make_entry("/project/src/main.rs")]
    stdout, stderr, rc = run_hook("git push", entries)
    assert rc == 2


# ─── 14. hookSpecificOutput contains impl file count ────────────────────────
def test_hook_specific_output_contains_metadata():
    entries = [make_entry("/project/scripts/post_edit.py")]
    stdout, stderr, rc = run_hook("git push origin main", entries)
    assert rc == 2
    parsed = json.loads(stdout.strip())
    ctx = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "impl_files_edited=1" in ctx
    assert "doc_files_updated=0" in ctx
