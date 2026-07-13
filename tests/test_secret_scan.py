"""Tests for scripts/secret_scan.py — WP-81: Secret scanning."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from secret_scan import scan_secrets, is_secret_pattern


def test_detects_aws_key_pattern(tmp_path):
    src = tmp_path / "config.py"
    src.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
    findings = scan_secrets([str(src)])
    assert len(findings) >= 1
    assert findings[0].blocking is True


def test_detects_generic_api_key(tmp_path):
    src = tmp_path / "settings.py"
    src.write_text('API_KEY = "sk-proj-abc123def456ghi789jkl012mno345"\n')
    findings = scan_secrets([str(src)])
    assert len(findings) >= 1


def test_detects_password_in_config(tmp_path):
    src = tmp_path / "db.py"
    src.write_text('DB_PASSWORD = "super_secret_p@ssw0rd_123"\n')
    findings = scan_secrets([str(src)])
    assert len(findings) >= 1


def test_ignores_allowlisted_pattern(tmp_path):
    src = tmp_path / "test.py"
    src.write_text('FAKE_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
    findings = scan_secrets([str(src)], allowlist=["AKIAIOSFODNN7EXAMPLE"])
    assert findings == []


def test_only_scans_changed_files_in_fast_mode(tmp_path):
    src1 = tmp_path / "clean.py"
    src1.write_text("x = 1\n")
    src2 = tmp_path / "dirty.py"
    src2.write_text('SECRET = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"\n')
    # Only scan src1
    findings = scan_secrets([str(src1)])
    assert findings == []


def test_raw_secret_never_printed(tmp_path):
    src = tmp_path / "leak.py"
    src.write_text('TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"\n')
    findings = scan_secrets([str(src)])
    for f in findings:
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in f.message


def test_blocks_by_default(tmp_path):
    src = tmp_path / "leak.py"
    src.write_text('AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"\n')
    findings = scan_secrets([str(src)])
    assert all(f.blocking for f in findings)


def test_binary_files_skipped(tmp_path):
    src = tmp_path / "image.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\nAKIAIOSFODNN7EXAMPLE")
    findings = scan_secrets([str(src)])
    assert findings == []


def test_is_secret_pattern():
    assert is_secret_pattern("AKIAIOSFODNN7EXAMPLE")
    assert is_secret_pattern("ghp_1234567890abcdefghijklmnopqrstuvwxyz")
    assert is_secret_pattern("sk-proj-abc123def456ghi789")
    assert not is_secret_pattern("hello world")
    assert not is_secret_pattern("normal_variable_name")
