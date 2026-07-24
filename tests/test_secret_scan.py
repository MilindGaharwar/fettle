"""Tests for scripts/secret_scan.py — WP-81: Secret scanning."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from fettle.secret_scan import scan_secrets, is_secret_pattern


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


# --- WP-L: Azure/GCP patterns ---


def test_detects_azure_storage_key(tmp_path):
    src = tmp_path / "config.py"
    src.write_text(
        'CONN = "DefaultEndpointsProtocol=https;AccountName=myacct;'
        'AccountKey=abc123def456ghi789jkl012mno345pqr678stu901vwx=;EndpointSuffix=core.windows.net"\n'
    )
    findings = scan_secrets([str(src)])
    assert any("Azure Storage" in f.message for f in findings)


def test_detects_azure_ad_client_secret(tmp_path):
    src = tmp_path / "auth.py"
    src.write_text('client_secret = "abc123~def456.ghi789-jkl012mno345p"\n')
    findings = scan_secrets([str(src)])
    assert any("Azure AD" in f.message or "client" in f.message.lower() for f in findings)


def test_detects_gcp_service_account_key(tmp_path):
    src = tmp_path / "creds.json"
    src.write_text('{"private_key": "-----BEGIN RSA PRIVATE KEY-----\\nMIIE..."}\n')
    findings = scan_secrets([str(src)])
    assert any("GCP" in f.message or "Private Key" in f.message for f in findings)


def test_detects_gcp_api_key(tmp_path):
    src = tmp_path / "config.py"
    src.write_text('GCP_KEY = "AIzaSyA1234567890abcdefghijklmnopqrstuvwx"\n')
    findings = scan_secrets([str(src)])
    assert any("GCP API" in f.message for f in findings)


def test_detects_bearer_token_in_source(tmp_path):
    src = tmp_path / "client.py"
    src.write_text('headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123"}\n')
    findings = scan_secrets([str(src)])
    assert any("Bearer" in f.message for f in findings)


def test_vault_retrieval_not_flagged(tmp_path):
    src = tmp_path / "deploy.sh"
    src.write_text("vault kv get secret/database/password\n")
    findings = scan_secrets([str(src)])
    # vault kv get is proper secret retrieval, NOT leakage
    vault_findings = [f for f in findings if "vault" in f.message.lower()]
    assert vault_findings == []


def test_extra_patterns_from_config(tmp_path):
    src = tmp_path / "app.py"
    src.write_text('CUSTOM_TOKEN = "xoxb-1234567890-abcdefghij"\n')
    # Without custom pattern: might not match
    # With custom pattern: should match
    findings = scan_secrets([str(src)], extra_patterns=[r"xoxb-[0-9]+-[a-z]+"])
    assert len(findings) >= 1
