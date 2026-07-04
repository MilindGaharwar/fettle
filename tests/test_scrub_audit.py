"""Self-test for scripts/scrub_audit.sh — the guard against private strings.

A guard with no test can be silently disarmed: a quoting bug in its pattern
would make every scan pass forever. These tests plant a private string in a
scratch tree and assert the audit actually fires.

The forbidden strings are assembled from fragments so this test file itself
never contains one (the audit scans this repo, including this file).
"""

import os
import shutil
import subprocess
import tempfile

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRUB = os.path.join(PLUGIN_DIR, "scripts", "scrub_audit.sh")

# "cru" + "cible": the private plugin this repo was scrubbed from.
PRIVATE_STRING = "cru" + "cible"


def run_scrub_in(tree: dict[str, str]):
    """Copy scrub_audit.sh into a scratch dir with `tree` files; run it there."""
    tmpdir = tempfile.mkdtemp()
    try:
        script = os.path.join(tmpdir, "scrub_audit.sh")
        shutil.copy(SCRUB, script)
        for rel, content in tree.items():
            path = os.path.join(tmpdir, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(content)
        proc = subprocess.run(
            ["bash", script],
            capture_output=True, text=True, timeout=30, cwd=tmpdir,
        )
        return proc.stdout, proc.stderr, proc.returncode
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_clean_tree_passes():
    stdout, stderr, rc = run_scrub_in({"src/app.py": "print('hello')\n"})
    assert rc == 0
    assert "scrub audit clean" in stdout


def test_planted_private_string_fails():
    stdout, stderr, rc = run_scrub_in(
        {"src/app.py": f"# imported from {PRIVATE_STRING}\n"}
    )
    assert rc == 1
    assert "SCRUB AUDIT FAILED" in stderr
    assert "app.py" in stderr  # names the offending file


def test_detection_is_case_insensitive():
    stdout, stderr, rc = run_scrub_in(
        {"README.md": f"Based on {PRIVATE_STRING.upper()}.\n"}
    )
    assert rc == 1


def test_git_dir_is_excluded():
    """History may legitimately contain old strings; only the tree is policed."""
    stdout, stderr, rc = run_scrub_in(
        {".git/COMMIT_EDITMSG": f"port from {PRIVATE_STRING}\n"}
    )
    assert rc == 0
    assert "scrub audit clean" in stdout
