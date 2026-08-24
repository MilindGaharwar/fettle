"""WP-146: compliance mapping — rules as evidence for CWE / OWASP ASVS / SOC 2.

The canonical rule→control mapping lives HERE (the runtime is stdlib-only, so
we don't parse rule YAML in production). Bundled rule packs mirror these tags
in ``metadata.compliance``; a test pins the two in sync so neither drifts.

``fettle report --compliance`` joins this mapping with the audit trail: for
each control it shows which rules enforce it and how often they fired/blocked
in the reporting window — an evidence table, not a compliance claim. Controls
with no findings are still listed as covered (the gate exists and is active);
rules that fired but map to nothing are surfaced as unmapped, never dropped.

Aligned with the v1.1 governance arc (WP-127..132): one mapping, one report.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ControlMapping:
    """Compliance tags for one rule. Empty string = honestly unmapped."""

    cwe: str = ""   # MITRE CWE id, e.g. "CWE-89"
    asvs: str = ""  # OWASP ASVS v4 control, e.g. "V5.3.4"
    soc2: str = ""  # SOC 2 common criteria, e.g. "CC7.1"


# ── Canonical mapping for bundled semgrep rule packs ─────────────────────────
# Mirrored in rules/*.yml metadata.compliance — pinned by test_compliance.py.
# Deliberately conservative: a tag is only present where the mapping is
# defensible. SOC 2: CC7.1 = vulnerability identification, CC7.2 = anomaly
# monitoring, CC8.1 = change management / quality gates.

RULE_COMPLIANCE: dict[str, ControlMapping] = {
    # SQL injection family
    "sql-fstring": ControlMapping(cwe="CWE-89", asvs="V5.3.4", soc2="CC7.1"),
    "sql-string-concat-go": ControlMapping(cwe="CWE-89", asvs="V5.3.4", soc2="CC7.1"),
    "string-built-sql-ts": ControlMapping(cwe="CWE-89", asvs="V5.3.4", soc2="CC7.1"),
    # Swallowed failures
    "bare-except-swallow": ControlMapping(cwe="CWE-390", asvs="V7.4.2", soc2="CC7.2"),
    "broad-except-no-reraise": ControlMapping(cwe="CWE-390", asvs="V7.4.2", soc2="CC7.2"),
    "empty-error-swallow-go": ControlMapping(cwe="CWE-390", asvs="V7.4.2", soc2="CC7.2"),
    "empty-catch-block": ControlMapping(cwe="CWE-390", asvs="V7.4.2", soc2="CC7.2"),
    # Test-isolation: cwd-relative mutation-flow roots in tests (shard-201)
    "test-flow-root-cwd": ControlMapping(cwe="CWE-362", asvs="V14.3.2", soc2="CC8.1"),
    # Active debug code
    "debug-breakpoint": ControlMapping(cwe="CWE-489", asvs="V14.3.2", soc2="CC8.1"),
    "debug-pdb": ControlMapping(cwe="CWE-489", asvs="V14.3.2", soc2="CC8.1"),
    "debug-print-statement": ControlMapping(cwe="CWE-489", asvs="V14.3.2", soc2="CC8.1"),
    "debug-print-go": ControlMapping(cwe="CWE-489", asvs="V14.3.2", soc2="CC8.1"),
    "debug-console-log": ControlMapping(cwe="CWE-489", asvs="V14.3.2", soc2="CC8.1"),
    "debug-debugger-statement": ControlMapping(cwe="CWE-489", asvs="V14.3.2", soc2="CC8.1"),
    # Missing timeouts → resource exhaustion
    "missing-httpx-timeout": ControlMapping(cwe="CWE-400", soc2="CC7.2"),
    "http-client-no-timeout-go": ControlMapping(cwe="CWE-400", soc2="CC7.2"),
    "fetch-without-timeout": ControlMapping(cwe="CWE-400", soc2="CC7.2"),
    # Reliability / change-management quality gates (no clean CWE — say so)
    "regex-llm-output": ControlMapping(soc2="CC8.1"),
    "regex-llm-output-ts": ControlMapping(soc2="CC8.1"),
    "unawaited-promise": ControlMapping(cwe="CWE-772", soc2="CC8.1"),
    "datetime-now-pipeline": ControlMapping(soc2="CC8.1"),
    "health-score-inversion": ControlMapping(soc2="CC8.1"),
    "orphaned-queue-flag": ControlMapping(soc2="CC8.1"),
    "non-atomic-write-output": ControlMapping(cwe="CWE-662", soc2="CC8.1"),
}

# OWASP ASVS + SOC 2 tags for the ruff S-codes fettle's security review runs.
# CWE for these codes comes from security_review._CWE_MAP (single source).
_RUFF_ASVS: dict[str, str] = {
    "S608": "V5.3.4", "S701": "V5.3.3",
    "S105": "V2.10.4", "S106": "V2.10.4", "S107": "V2.10.4",
    "S301": "V5.5.1", "S302": "V5.5.1",
    "S303": "V6.2.2", "S324": "V6.2.2",
    "S501": "V9.2.1",
    "S602": "V5.3.8", "S603": "V5.3.8", "S604": "V5.3.8",
    "S110": "V7.4.2",
}


def _ruff_compliance() -> dict[str, ControlMapping]:
    from fettle.security_review import _CWE_MAP

    out: dict[str, ControlMapping] = {}
    for code, cwe_label in _CWE_MAP.items():
        cwe = cwe_label.split(" ")[0]  # "CWE-89 (SQL Injection)" → "CWE-89"
        out[code] = ControlMapping(cwe=cwe, asvs=_RUFF_ASVS.get(code, ""), soc2="CC7.1")
    return out


def full_mapping() -> dict[str, ControlMapping]:
    """All known rule/check ids → compliance tags (bundled packs + ruff S)."""
    return {**RULE_COMPLIANCE, **_ruff_compliance()}


# ── Evidence report ──────────────────────────────────────────────────────────


@dataclass
class ControlCoverageSummary:
    control: str
    rules: list[str] = field(default_factory=list)
    findings: int = 0
    blocked: int = 0


def _source_digest(records: list[dict]) -> str:
    canonical_records = sorted(
        json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        for record in records
    )
    canonical = "[" + ",".join(canonical_records) + "]"
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_compliance_report(days: int = 30) -> dict:
    """Evidence table: control → enforcing rules → fire counts in the window.

    Never raises; with no trace data the static coverage is still reported.
    """
    from fettle.trace import get_recent_decisions

    mapping = full_mapping()
    cutoff = time.time() - days * 86400
    fired: Counter[str] = Counter()
    blocked: Counter[str] = Counter()
    source_records: list[dict] = []
    source_timestamps: list[float] = []
    malformed_source_records = 0
    for entry in get_recent_decisions(limit=10000):
        if not isinstance(entry, dict):
            malformed_source_records += 1
            continue
        timestamp = entry.get("ts")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            malformed_source_records += 1
            continue
        if timestamp <= cutoff:
            continue
        findings = entry.get("findings")
        if not isinstance(findings, list):
            malformed_source_records += 1
            continue
        # Status vocabulary matches report.py: dispatcher writes
        # "blocked"/"block" for enforced denials, "violation" for findings.
        is_block = entry.get("status") in ("blocked", "block")
        included = False
        for f in findings:
            if not isinstance(f, dict):
                malformed_source_records += 1
                continue
            code = f.get("code", "")
            if not isinstance(code, str) or not code:
                malformed_source_records += 1
                continue
            included = True
            fired[code] += 1
            if is_block:
                blocked[code] += 1
        if included:
            source_records.append(entry)
            source_timestamps.append(timestamp)

    frameworks: dict[str, dict[str, ControlCoverageSummary]] = {
        "cwe": {}, "asvs": {}, "soc2": {},
    }
    for rule_id, cm in sorted(mapping.items()):
        for framework, control in (("cwe", cm.cwe), ("asvs", cm.asvs), ("soc2", cm.soc2)):
            if not control:
                continue
            ev = frameworks[framework].setdefault(control, ControlCoverageSummary(control))
            ev.rules.append(rule_id)
            ev.findings += fired.get(rule_id, 0)
            ev.blocked += blocked.get(rule_id, 0)

    unmapped = sorted(code for code in fired if code not in mapping)
    return {
        "period_days": days,
        "source_window_start": min(source_timestamps) if source_timestamps else None,
        "source_window_end": max(source_timestamps) if source_timestamps else None,
        "source_digest": _source_digest(source_records),
        "source_complete": malformed_source_records == 0,
        "malformed_source_records": malformed_source_records,
        "frameworks": {
            fw: {
                control: {
                    "rules": ev.rules,
                    "findings": ev.findings,
                    "blocked": ev.blocked,
                }
                for control, ev in sorted(controls.items())
            }
            for fw, controls in frameworks.items()
        },
        "mapped_rules": len(mapping),
        "unmapped_fired_rules": unmapped,
    }


def render_compliance_table(data: dict) -> str:
    """Human-readable evidence table for `fettle report --compliance`."""
    lines = [f"── Fettle Compliance Evidence ({data['period_days']}d) ──", ""]
    titles = {"cwe": "CWE", "asvs": "OWASP ASVS v4", "soc2": "SOC 2 (CC series)"}
    for fw, controls in data["frameworks"].items():
        lines.append(f"  {titles[fw]}")
        for control, ev in controls.items():
            hits = f"findings: {ev['findings']}" + (
                f"  blocked: {ev['blocked']}" if ev["blocked"] else "")
            lines.append(f"    {control:<10} {hits}")
            for rule in ev["rules"]:
                lines.append(f"      · {rule}")
        lines.append("")
    if data["unmapped_fired_rules"]:
        lines.append("  Fired but unmapped (no compliance tags):")
        for code in data["unmapped_fired_rules"]:
            lines.append(f"    · {code}")
        lines.append("")
    lines.append(f"  {data['mapped_rules']} rules carry compliance tags. "
                 "This table is evidence of enforcement, not a certification.")
    return "\n".join(lines)
