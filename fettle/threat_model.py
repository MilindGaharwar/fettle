"""WP-Q — Threat Model Command.

LLM-assisted STRIDE analysis. Auto-populates entry points and data
stores from code, then produces a structured threat model template.
NOT deterministic auto-detection — this is a guided template.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _grep_probe(patterns: list[str], grep_args: list[str], root: str,
                per_pattern_limit: int, total_limit: int) -> tuple[list[str], list[str]]:
    """Run grep probes. Returns (matches, probe_errors).

    Probe failures are returned, not swallowed — an empty section caused by a
    dead grep must not read as "nothing to threat-model here".
    """
    matches: list[str] = []
    errors: list[str] = []
    for pat in patterns:
        try:
            result = subprocess.run(
                ["grep", *grep_args, pat, root],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines()[:per_pattern_limit]:
                matches.append(line.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            errors.append(f"probe '{pat}' failed: {type(exc).__name__}")
            continue
    return matches[:total_limit], errors


def _find_entry_points(root: str) -> tuple[list[str], list[str]]:
    """Grep for HTTP route decorators and API endpoint definitions."""
    patterns = [
        r"@app\.(get|post|put|delete|patch)\(",
        r"@router\.(get|post|put|delete|patch)\(",
        r"app\.add_url_rule\(",
        r"@api_view\(",
        r"path\(['\"]",
        r"router\.(get|post|put|delete)\(",
    ]
    return _grep_probe(
        patterns,
        ["-rEn", "--include=*.py", "--include=*.ts", "--include=*.js"],
        root, per_pattern_limit=20, total_limit=30,
    )


def _find_data_stores(root: str) -> tuple[list[str], list[str]]:
    """Grep for database connections, file writes, cache usage."""
    patterns = [
        r"create_engine\(",
        r"sqlite3\.connect\(",
        r"MongoClient\(",
        r"Redis\(",
        r"psycopg2\.connect\(",
        r"pymysql\.connect\(",
        r"open\(.+['\"]w",
        r"S3Client\(",
    ]
    return _grep_probe(
        patterns,
        ["-rEn", "--include=*.py", "--include=*.ts"],
        root, per_pattern_limit=10, total_limit=20,
    )


def _find_auth_mechanisms(root: str) -> tuple[list[str], list[str]]:
    """Grep for authentication patterns."""
    patterns = [
        r"jwt\.",
        r"oauth",
        r"authenticate\(",
        r"login\(",
        r"session\[",
        r"Bearer",
        r"api_key",
        r"token.*verify",
    ]
    return _grep_probe(
        patterns,
        ["-rEni", "--include=*.py", "--include=*.ts"],
        root, per_pattern_limit=10, total_limit=15,
    )


def generate_threat_model(root: str, service_name: str) -> str:
    """Generate a STRIDE-based threat model template with auto-populated data."""
    entry_points, ep_errors = _find_entry_points(root)
    data_stores, ds_errors = _find_data_stores(root)
    auth_mechanisms, auth_errors = _find_auth_mechanisms(root)
    probe_errors = ep_errors + ds_errors + auth_errors

    ep_section = "\n".join("- " + ep for ep in entry_points) if entry_points else "- None detected (add manually)"
    ds_section = "\n".join("- " + ds for ds in data_stores) if data_stores else "- None detected (add manually)"
    auth_section = "\n".join("- " + a for a in auth_mechanisms) if auth_mechanisms else "- None detected (add manually)"
    probe_note = ""
    if probe_errors:
        probe_note = (
            "\n> ⚠ **Auto-detection incomplete** — "
            + str(len(probe_errors))
            + " probe(s) failed; sections below may be missing real entries. "
            + "Verify manually. (" + "; ".join(probe_errors[:3]) + ")\n"
        )

    template = (
        "# Threat Model: " + service_name + "\n"
        + probe_note + "\n"
        "## 1. System Overview\n\n"
        "**Service:** " + service_name + "\n"
        "**Scope:** [Define what is in/out of scope]\n"
        "**Data sensitivity:** [Public / Internal / Confidential / Restricted]\n\n"
        "## 2. Entry Points (auto-detected)\n\n" + ep_section + "\n\n"
        "## 3. Data Stores (auto-detected)\n\n" + ds_section + "\n\n"
        "## 4. Authentication Mechanisms (auto-detected)\n\n" + auth_section + "\n\n"
        "## 5. STRIDE Analysis\n\n"
        "### Spoofing\n"
        "| Threat | Impact | Likelihood | Mitigation |\n"
        "|--------|--------|------------|------------|\n"
        "| [Identity spoofing via...] | [H/M/L] | [H/M/L] | [Control] |\n\n"
        "### Tampering\n"
        "| Threat | Impact | Likelihood | Mitigation |\n"
        "|--------|--------|------------|------------|\n"
        "| [Data modification via...] | [H/M/L] | [H/M/L] | [Control] |\n\n"
        "### Repudiation\n"
        "| Threat | Impact | Likelihood | Mitigation |\n"
        "|--------|--------|------------|------------|\n"
        "| [Action denial via...] | [H/M/L] | [H/M/L] | [Control] |\n\n"
        "### Information Disclosure\n"
        "| Threat | Impact | Likelihood | Mitigation |\n"
        "|--------|--------|------------|------------|\n"
        "| [Data leak via...] | [H/M/L] | [H/M/L] | [Control] |\n\n"
        "### Denial of Service\n"
        "| Threat | Impact | Likelihood | Mitigation |\n"
        "|--------|--------|------------|------------|\n"
        "| [Resource exhaustion via...] | [H/M/L] | [H/M/L] | [Control] |\n\n"
        "### Elevation of Privilege\n"
        "| Threat | Impact | Likelihood | Mitigation |\n"
        "|--------|--------|------------|------------|\n"
        "| [Privilege escalation via...] | [H/M/L] | [H/M/L] | [Control] |\n\n"
        "## 6. Recommendations\n\n"
        "- [ ] [Priority 1 action]\n"
        "- [ ] [Priority 2 action]\n"
        "- [ ] [Priority 3 action]\n"
    )
    return template


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Fettle threat model generator")
    parser.add_argument("--name", default="", help="Service name")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--output", default="", help="Output file path")
    args = parser.parse_args()

    name = args.name or os.path.basename(os.path.abspath(args.root))
    model = generate_threat_model(args.root, name)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(model)
        print("Threat model written to: " + args.output, file=sys.stderr)
    else:
        print(model)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
