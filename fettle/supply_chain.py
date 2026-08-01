"""WP-147: supply-chain posture — pinned tools + installed-file verification.

``PINNED_TOOLS`` is the canonical tool pin list (init_cmd re-exports it; the
CI workflows and templates mirror the same versions). ``fettle doctor
--verify-hashes`` checks two things for each pinned tool that is installed as
a Python distribution in this environment:

1. the installed version matches the pin (drift = warn), and
2. every installed file still matches the sha256 recorded in the wheel's
   RECORD at install time (mismatch = tampering = required failure).

This is offline and stdlib-only: the trust anchor is the RECORD file pip
wrote from the wheel, which itself was hash-verified against PyPI at install
time. Release-side signing (Sigstore), SBOM (CycloneDX) and SLSA provenance
live in .github/workflows/release.yml — this module is the consumer-side half.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import io
from pathlib import Path

# Pinned tool versions — kept in lockstep with ci.yml / release.yml /
# templates/gitlab-ci.yml. Canonical home; init_cmd re-exports for --install-tools.
PINNED_TOOLS = {
    "ruff": "0.15.20",
    "semgrep": "1.168.0",
    "pre-commit": "4.4.0",
}


def verify_record(dist: importlib.metadata.Distribution) -> dict | None:
    """Verify installed files against the distribution's RECORD hashes.

    Returns {"verified": int, "tampered": [paths], "missing": [paths]},
    or None when the distribution has no RECORD (can't verify).
    """
    text = dist.read_text("RECORD")
    if text is None:
        return None
    verified = 0
    tampered: list[str] = []
    missing: list[str] = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or not row[1]:
            continue  # RECORD itself and .pyc entries carry no hash
        rel_path, hash_spec = row[0], row[1]
        algo, _, expected = hash_spec.partition("=")
        target = Path(str(dist.locate_file(rel_path)))
        if not target.is_file():
            missing.append(rel_path)
            continue
        with open(target, "rb") as f:
            digest = hashlib.file_digest(f, algo).digest()
        actual = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        if actual == expected:
            verified += 1
        else:
            tampered.append(rel_path)
    return {"verified": verified, "tampered": tampered, "missing": missing}


def verify_tool_hashes(pinned: dict[str, str] | None = None) -> list[dict]:
    """Doctor-style checks for each pinned tool installed in this environment.

    Tampering (RECORD hash mismatch) is a required failure; version drift is
    a warning; tools not installed as Python distributions here (e.g. a
    standalone binary) are reported as skipped, never silently omitted.
    """
    checks: list[dict] = []
    for tool, pin in (pinned or PINNED_TOOLS).items():
        name = f"supply:{tool}"
        try:
            dist = importlib.metadata.distribution(tool)
        except importlib.metadata.PackageNotFoundError:
            checks.append({
                "name": name, "required": False, "ok": True,
                "detail": "not installed as a Python distribution here — skipped",
            })
            continue
        installed = dist.version
        if installed != pin:
            checks.append({
                "name": name, "required": False, "ok": False,
                "detail": f"version drift: installed {installed}, pinned {pin}",
            })
            continue
        result = verify_record(dist)
        if result is None:
            checks.append({
                "name": name, "required": False, "ok": False,
                "detail": f"{installed} — no RECORD; cannot verify file hashes",
            })
        elif result["tampered"] or result["missing"]:
            bad = result["tampered"] + result["missing"]
            checks.append({
                "name": name, "required": True, "ok": False,
                "detail": (f"{installed} — INTEGRITY FAILURE: "
                           f"{len(result['tampered'])} tampered, "
                           f"{len(result['missing'])} missing "
                           f"(first: {bad[0]}) — reinstall the tool"),
            })
        else:
            checks.append({
                "name": name, "required": False, "ok": True,
                "detail": f"{installed} — {result['verified']} files verified against RECORD",
            })
    return checks
