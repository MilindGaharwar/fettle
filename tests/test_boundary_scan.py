"""Boundary scanner: secrets, out-of-project paths, repo-forbidden strings.

All fixtures are synthetic (AWS's public documentation key, placeholder
paths) — the scanner is generic and names no real project.
"""

import os
import subprocess
import sys
import tempfile

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))

from boundary_scan import scan_repo, scan_text  # noqa: E402

SYNTH_AWS = "AKIAZ7Q3M5N8P2K4R6T9"   # synthetic, non-credential shape that SHOULD flag
AWS_EXAMPLE = "AKIAIOSFODNN7EXAMPLE"  # AWS docs convention — must NOT flag
FAKE_PEM = ("-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDabc123\n"
            "-----END PRIVATE KEY-----")


# --- secrets -----------------------------------------------------------------

def test_flags_cloud_access_key():
    findings = scan_text(f'aws_key = "{SYNTH_AWS}"')
    assert any(f.code == "aws-key" for f in findings)


def test_ignores_aws_example_key():
    # AWS's documented example key ends in EXAMPLE — never a real credential,
    # and it appears in docs/tests describing detectors. Must not flag.
    assert scan_text(f'k = "{AWS_EXAMPLE}"') == []


def test_flags_private_key_block():
    assert scan_text(FAKE_PEM)


def test_flags_high_entropy_assignment():
    assert scan_text('api_key = "aZ92hKd0Lm4Rp7Qx13BvN8sTfWjUy6Ec5Gd2Hn0"')


def test_ignores_env_reads_and_placeholders():
    assert scan_text('api_key = os.environ.get("SOME_API_KEY")') == []
    assert scan_text('key = "your-key-here"') == []
    assert scan_text('token = ""') == []
    assert scan_text('SESSION_TOKEN_ENV = "APP_SESSION_TOKEN"') == []  # env-var NAME


def test_entropy_threshold_spares_prose():
    # a long lowercase dictionary phrase must not read as a secret
    assert scan_text('note = "the quick brown fox jumps over the lazy dog again"') == []


# --- out-of-project absolute paths (zero config) -----------------------------

def test_flags_out_of_project_absolute_path():
    findings = scan_text('CACHE = "/Users/someone/other-project/data.db"')
    assert any("path" in f.code for f in findings)


def test_flags_home_path():
    assert scan_text('p = "/home/alice/sibling-repo/x.py"')


def test_ignores_generic_and_relative_paths():
    assert scan_text('p = "/usr/local/bin/tool"') == []   # system path, not a user home
    assert scan_text('p = "./data/local.db"') == []        # relative
    assert scan_text('p = "data/warehouse.duckdb"') == []


# --- repo-declared forbidden strings -----------------------------------------

def test_forbidden_pattern_flags_caller_supplied_string():
    findings = scan_text("import sibling_project.things", forbidden_patterns=["sibling_project"])
    assert any(f.code == "forbidden-string" for f in findings)


def test_regression_forbidden_and_no_data():
    """Regression — the scanner must not become a false-positive machine that
    gets disabled: a caller-supplied forbidden list flags matching text, an
    out-of-project absolute path is flagged with zero config, and clean text
    with no data returns none/zero (never a false hit or a crash)."""
    assert scan_text("uses acme_widget internals", forbidden_patterns=["acme_widget"])
    assert scan_text('P = "/Users/bob/elsewhere/f.py"')          # zero config
    assert scan_text("") == []                                    # no data
    assert scan_text("just ordinary code with no secrets") == []
    assert scan_text("clean", forbidden_patterns=["neverpresent"]) == []


# --- scan_repo ---------------------------------------------------------------

def test_integration_scan_repo_finds_planted_key():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        with open(os.path.join(d, "clean.py"), "w") as f:
            f.write("x = os.environ.get('KEY')\n")
        with open(os.path.join(d, "leak.py"), "w") as f:
            f.write(f'k = "{SYNTH_AWS}"\n')
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        findings = scan_repo(d, {})
        leak_findings = [f for f in findings if f.path and "leak.py" in f.path]
        assert len(leak_findings) == 1
        assert leak_findings[0].line == 1
        assert not any("clean.py" in (f.path or "") for f in findings)


def test_integration_scan_repo_honors_forbidden_config():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        with open(os.path.join(d, "a.py"), "w") as f:
            f.write("from otherpkg import thing\n")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        cfg = {"boundary": {"forbidden": ["otherpkg"]}}
        findings = scan_repo(d, cfg)
        assert any(f.code == "forbidden-string" for f in findings)
