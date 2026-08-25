"""Survivor classification for the mutation ratchet (P48 follow-on).

Raw survivor count is not a valid enforcement bar: many mutants are
equivalent (semantically identical) or mutate implementation details that
no public contract observes. This module turns mutation-report survivors
into a triaged worklist:

- ``behavioral``      — no waiver on record; these block enforcement.
- ``equivalent`` /     — covered by a reviewed, versioned waiver entry;
  ``implementation_detail``         killing them adds brittleness, not quality.

Waivers live in a versioned YAML file (default ``survivor-waivers.yml``)
keyed by mutant fingerprint. Every waiver requires a classification and a
reason; unknown classifications or malformed fingerprints are findings,
never silently ignored.
"""

from __future__ import annotations

import re

WAIVER_SCHEMA = "fettle-survivor-waivers/v1"
DEFAULT_WAIVER_PATH = "survivor-waivers.yml"
VALID_CLASSIFICATIONS = frozenset({"equivalent", "implementation_detail"})
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


def _finding(message: str, fix: str) -> dict:
    return {"severity": "ERROR", "message": message, "fix": fix}


def load_waivers(text: str, source: str = "<waivers>") -> tuple[dict[str, dict], list[dict]]:
    """Parse + validate the waiver registry. Returns (waivers, findings)."""
    import yaml

    findings: list[dict] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return {}, [_finding(f"invalid YAML in {source}: {exc}",
                             "fix the YAML syntax")]
    if not isinstance(data, dict):
        return {}, [_finding("waiver file must be a mapping",
                             f"start with '{WAIVER_SCHEMA.split('/')[0]}: ...'")]
    if str(data.get("schema_version", "")) != WAIVER_SCHEMA.split("/")[1]:
        findings.append(_finding(
            f"unsupported schema version {data.get('schema_version')!r}",
            f"set 'schema_version: {WAIVER_SCHEMA.split('/')[1]}'"))
    waivers_raw = data.get("waivers") or {}
    if not isinstance(waivers_raw, dict):
        findings.append(_finding("'waivers' must be a mapping keyed by "
                                 "mutant fingerprint",
                                 "use the 64-hex fingerprint as the key"))
        waivers_raw = {}

    waivers: dict[str, dict] = {}
    for fingerprint, entry in sorted(waivers_raw.items()):
        fp = str(fingerprint)
        if not isinstance(entry, dict):
            findings.append(_finding(
                f"waiver {fp[:12]} must be a mapping",
                "add classification/reason/decided_by"))
            continue
        classification = str(entry.get("classification", ""))
        if classification not in VALID_CLASSIFICATIONS:
            findings.append(_finding(
                f"waiver {fp[:12]} has invalid classification "
                f"{classification!r}",
                f"use one of {sorted(VALID_CLASSIFICATIONS)}"))
            continue
        reason_raw = entry.get("reason")
        reason = "" if reason_raw is None else str(reason_raw).strip()
        if not reason:
            findings.append(_finding(
                f"waiver {fp[:12]} has no reason",
                "document why this survivor is acceptable"))
            continue
        waivers[fp] = {
            "classification": classification,
            "reason": reason,
            "decided_by": str(entry.get("decided_by", "operator")),
        }
    return waivers, findings


def classify_survivors(report: dict, waivers: dict[str, dict]) -> dict:
    """Split report survivors into behavioral vs waived worklists."""
    behavioral: list[dict] = []
    counts = {cls: 0 for cls in sorted(VALID_CLASSIFICATIONS)}
    unknown_waived: list[str] = []
    survivors = report.get("non_killed") or []
    for survivor in survivors:
        fingerprint = str(survivor.get("fingerprint", ""))
        waiver = waivers.get(fingerprint)
        if waiver is None:
            behavioral.append({
                "fingerprint": fingerprint,
                "source_context_digest":
                    survivor.get("source_context_digest", ""),
            })
            continue
        cls = waiver["classification"]
        counts[cls] += 1
        if fingerprint and not _FINGERPRINT_RE.match(fingerprint):
            unknown_waived.append(fingerprint)

    return {
        "status": "completed",
        "total_survivors": len(survivors),
        "behavioral": behavioral,
        "behavioral_count": len(behavioral),
        "waived_counts": counts,
        "enforce_ready": len(behavioral) == 0,
        "invalid_fingerprints": sorted(set(unknown_waived)),
    }


def summarize_classification(classification: dict) -> str:
    lines = [
        f"survivors: {classification['total_survivors']} total · "
        f"{classification['behavioral_count']} behavioral · "
        f"waived {sum(classification['waived_counts'].values())}",
    ]
    if classification["enforce_ready"]:
        lines.append("enforcement bar: MET (zero unexplained behavioral)")
    else:
        lines.append(f"enforcement bar: NOT met — "
                     f"{classification['behavioral_count']} behavioral "
                     f"survivors need killing or waivers")
        lines.extend(f"  - {s['fingerprint'][:16]}"
                     for s in classification["behavioral"][:10])
    return "\n".join(lines)
