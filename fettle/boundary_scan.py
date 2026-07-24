"""Boundary scanner — keep a package generic and standalone.

Three detectors over one text pass:
  1. Secrets — cloud access-key IDs, private-key blocks, high-entropy
     api_key/token/secret assignments.
  2. Out-of-project absolute paths — a user-home or absolute path literal
     that escapes the project (the local-path / username leak class).
  3. Repo-declared forbidden strings — a project lists, in .fettle.toml
     `[boundary].forbidden`, the sibling projects/strings it must not
     reference. Fettle itself ships no such list; the mechanism is generic.

`scan_text` is pure and takes the forbidden list explicitly, so it is
trivially testable. `scan_repo` walks git-tracked files, honours
.fettle-ignore, and reads the forbidden list from config.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.result import Finding, Severity  # noqa: E402

TOOL = "boundary"

# --- secret patterns ---------------------------------------------------------
_AWS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_EXAMPLE_KEY = re.compile(r"(?:AKIA|ASIA)[0-9A-Z]*EXAMPLE")  # AWS docs convention — not a credential
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
_KEY_MATERIAL = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")  # a real key's base64 body
_SK_TOKEN = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
# assignment of a quoted value to a secret-ish name
_SECRET_ASSIGN = re.compile(
    r"""(?ix)
    \b(?:api[_-]?key|secret|token|password|passwd|bearer)\b
    \s*[:=]\s*
    ["']([^"']{12,})["']
    """
)
# obvious non-secret RHS values
_PLACEHOLDER = re.compile(
    r"(?i)^(?:your[-_ ]|<|\$\{|example|changeme|placeholder|xxx+|todo|none|null|test[-_]?)"
)
_ENV_READ = re.compile(r"os\.environ|getenv|os\.getenv|process\.env")

# --- out-of-project absolute path --------------------------------------------
_USER_HOME_PATH = re.compile(r"""["'](/(?:Users|home)/[^"'/]+/[^"']*)["']""")

ENTROPY_MIN = 3.2  # bits/char — random keys clear this; prose/words don't


def _shannon(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.match(value.strip())) or value.strip() == ""


def scan_text(text: str, forbidden_patterns: list[str] | None = None) -> list[Finding]:
    """Scan one blob of text. Pure. Returns findings (possibly empty)."""
    findings: list[Finding] = []
    forbidden = forbidden_patterns or []

    lines = text.splitlines() or [""]
    for i, line in enumerate(lines):
        lineno = i + 1
        # a line that only reads from the environment is safe
        env_read = bool(_ENV_READ.search(line))

        if _AWS_KEY.search(line) and not _EXAMPLE_KEY.search(line):
            findings.append(_f(Severity.ERROR, lineno, "aws-key",
                              "Hardcoded cloud access-key ID"))
        if _PRIVATE_KEY.search(line) and _has_key_material(lines, i):
            findings.append(_f(Severity.ERROR, lineno, "private-key",
                              "Hardcoded private key block"))
        if _SK_TOKEN.search(line):
            findings.append(_f(Severity.ERROR, lineno, "secret",
                              "Hardcoded token literal"))

        m = _SECRET_ASSIGN.search(line)
        if m and not env_read:
            value = m.group(1)
            if not _is_placeholder(value) and _shannon(value) >= ENTROPY_MIN:
                findings.append(_f(Severity.ERROR, lineno, "secret",
                                  "Hardcoded secret assignment"))

        for pm in _USER_HOME_PATH.finditer(line):
            findings.append(_f(Severity.ERROR, lineno, "out-of-project-path",
                              f"Absolute path escaping the project: {pm.group(1)}"))

        low = line.lower()
        for pat in forbidden:
            if pat.lower() in low:
                findings.append(_f(Severity.ERROR, lineno, "forbidden-string",
                                  f"Repo-forbidden reference to another package: {pat!r}"))
    return findings


def _has_key_material(lines: list[str], header_idx: int) -> bool:
    """True if a real base64 key body appears on/after the BEGIN line —
    distinguishes a real key from a doc/comment naming the header."""
    for probe in lines[header_idx:header_idx + 4]:
        body = probe.replace("-----BEGIN", "").replace("PRIVATE KEY-----", "")
        if _KEY_MATERIAL.search(body):
            return True
    return False


def _f(sev: Severity, line: int, code: str, message: str) -> Finding:
    return Finding(tool=TOOL, severity=sev, line=line, code=code, message=message)


# --- repo scan ---------------------------------------------------------------
_SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".fettle", "venv", ".venv"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf", ".lock",
               ".woff", ".woff2", ".ttf", ".zip", ".gz"}


def _tracked_files(root: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        ).stdout
        return [ln for ln in out.splitlines() if ln]
    except (subprocess.CalledProcessError, FileNotFoundError):
        # not a git repo — walk the tree
        files = []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in _SKIP_DIRS and not d.startswith(".")]
            for fn in fns:
                files.append(os.path.relpath(os.path.join(dp, fn), root))
        return files


def _load_ignore(root: str) -> list[str]:
    path = os.path.join(root, ".fettle-ignore")
    if not os.path.isfile(path):
        return []
    with open(path) as fh:
        return [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]


def scan_repo(root: str, cfg: dict) -> list[Finding]:
    """Scan every tracked, non-binary, non-ignored file under root."""
    import fnmatch

    forbidden = (cfg.get("boundary") or {}).get("forbidden", [])
    ignore = _load_ignore(root)
    findings: list[Finding] = []
    self_name = os.path.basename(__file__)

    for rel in _tracked_files(root):
        if os.path.splitext(rel)[1].lower() in _BINARY_EXT:
            continue
        if os.path.basename(rel) == self_name:  # never scan the scanner's own patterns
            continue
        if any(fnmatch.fnmatch(rel, pat) for pat in ignore):
            continue
        abspath = os.path.join(root, rel)
        try:
            with open(abspath, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except (OSError, UnicodeError):
            continue
        for f in scan_text(text, forbidden):
            f.path = rel
            findings.append(f)
    return findings


def main() -> int:
    import argparse

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
    from fettle.config import load_config

    parser = argparse.ArgumentParser(description="Fettle boundary scanner")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    cfg = load_config(root)
    findings = scan_repo(root, cfg)

    if args.json:
        import json
        print(json.dumps([f.to_dict() for f in findings]))
    else:
        for f in findings:
            print(f"{f.path}:{f.line}: [{f.code}] {f.message}", file=sys.stderr)
        print(f"boundary scan: {len(findings)} finding(s)"
              + (" — clean" if not findings else ""))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
