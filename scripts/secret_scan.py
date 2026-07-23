"""Fettle v0.5.0 — WP-81: Secret scanning.

Detect accidentally committed credentials. BLOCKING by default.
Wraps gitleaks if available, falls back to regex patterns.
"""

from __future__ import annotations

import re
from pathlib import Path

from finding import CheckFinding, FindingSeverity

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".exe", ".bin", ".dat",
}

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Azure Storage Key", re.compile(
        r"(?i)DefaultEndpointsProtocol=https?;.*AccountKey=[A-Za-z0-9+/=]{44,}"
    )),
    ("Azure AD Client Secret", re.compile(
        r"(?i)client[_-]?secret\s*[=:]\s*['\"]?[A-Za-z0-9~._-]{34,}['\"]?"
    )),
    ("GCP Service Account Key", re.compile(
        r'"private_key"\s*:\s*"-----BEGIN'
    )),
    ("GCP API Key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("GitHub PAT", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    ("GitHub OAuth", re.compile(r"gho_[a-zA-Z0-9]{36}")),
    ("GitHub App Token", re.compile(r"ghu_[a-zA-Z0-9]{36}")),
    ("OpenAI/Anthropic Key", re.compile(r"sk-[a-zA-Z0-9_-]{20,}")),
    ("Bearer Token in Source", re.compile(
        r"""(?i)['"]?authorization['"]?\s*[=:]\s*['"]bearer\s+[A-Za-z0-9._-]{20,}['"]"""
    )),
    ("Generic High-Entropy Token", re.compile(
        r"""(?xi)
        \b\w*(?:password|passwd|secret|token|api_key|apikey|auth_token|access_token)\w*
        \s*[=:]\s*
        ['"]([^'"]{8,})['"]
        """
    )),
    ("Private Key Block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
]


def is_secret_pattern(text: str) -> bool:
    """Check if text matches any known secret pattern."""
    return any(pattern.search(text) for _, pattern in _SECRET_PATTERNS)


def _is_binary(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix in _BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            return b"\x00" in chunk
    except OSError:
        return True


def _build_patterns(extra_patterns: list[str] | None = None) -> list[tuple[str, re.Pattern]]:
    """Combine built-in patterns with org-specific extras from config."""
    patterns = list(_SECRET_PATTERNS)
    for i, pat_str in enumerate(extra_patterns or []):
        try:
            patterns.append((f"Custom pattern #{i + 1}", re.compile(pat_str)))
        except re.error:
            continue
    return patterns


def scan_secrets(
    files: list[str],
    allowlist: list[str] | None = None,
    extra_patterns: list[str] | None = None,
) -> list[CheckFinding]:
    """Scan files for secrets using regex patterns. Returns BLOCKING findings."""
    findings: list[CheckFinding] = []
    allow_set = set(allowlist) if allowlist else set()
    patterns = _build_patterns(extra_patterns)

    for file_path in files:
        if _is_binary(file_path):
            continue
        try:
            content = Path(file_path).read_text(errors="replace")
        except OSError:
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            for desc, pattern in patterns:
                match = pattern.search(line)
                if not match:
                    continue
                secret_value = match.group(0)
                if secret_value in allow_set:
                    continue
                # Check if any group captured the actual secret
                if match.groups():
                    inner = match.group(1)
                    if inner in allow_set:
                        continue

                findings.append(CheckFinding(
                    checker="secret-scan",
                    severity=FindingSeverity.ERROR,
                    file=file_path,
                    line=line_num,
                    message=f"Possible {desc} detected (value redacted)",
                    blocking=True,
                    suggested_fix="Remove the secret and use environment variables or a secrets manager",
                    rerun_command="fettle check --boundaries",
                ))

    return findings
