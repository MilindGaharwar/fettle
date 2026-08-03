"""WP-148: opt-in, privacy-first telemetry — anonymous counters only.

Three hard rules, in order of importance:

1. **Default off.** No config = no telemetry, ever.
2. **Only the org can opt in.** ``[telemetry] enabled = true`` is honored
   only when it arrives via the digest-pinned central policy (WP-144
   ``[extends]``) — the one channel an individual developer can't quietly
   edit. The same table in a repo's own .fettle.toml is ignored and the
   attempt is surfaced, not swallowed.
3. **Counters only.** The payload is fully enumerated below: aggregate
   integers plus the fettle version. No code, no paths, no repo names, no
   rule ids, no session ids — nothing that identifies a machine, person, or
   project. ``fettle telemetry show`` prints the exact payload; the schema
   test pins the key set so it can't grow silently.

Payload (schema ``fettle-telemetry/1``)::

    {
      "schema": "fettle-telemetry/1",
      "period_days": 30,
      "counters": {
        "decisions": 0,     # hook decisions in the window
        "fired": 0,         # decisions that produced findings
        "blocked": 0,       # decisions enforced as blocks
        "overridden": 0,    # decisions recorded as overridden (reserved;
                            # populated only when gates log that status)
        "tool_errors": 0    # scanner failures (fail-open events)
      },
      "fettle_version": "1.3.0"
    }

Sending is fire-and-forget with a strict timeout and never raises — a
telemetry endpoint being down must never affect any gate.
"""

from __future__ import annotations

import json
import os
import time
import tomllib
import urllib.request
from collections import Counter
from pathlib import Path

from fettle import __version__

PAYLOAD_SCHEMA = "fettle-telemetry/1"
SEND_TIMEOUT_S = 5.0

# Trace statuses → counter buckets (vocabulary from trace.py / report.py).
_BLOCK_STATUSES = ("blocked", "block")
_OVERRIDE_STATUSES = ("overridden", "override")
_ERROR_STATUSES = ("tool_error", "check_error")


def _endpoint_allowed(endpoint: str) -> bool:
    """https anywhere, or plain http only to loopback (WP-12, audit M-05).

    startswith() checks pass hosts like http://127.0.0.1.evil.example —
    the hostname must be parsed, not prefix-matched.
    """
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(endpoint)
    except ValueError:
        return False
    if parts.scheme == "https":
        return True
    return parts.scheme == "http" and parts.hostname in ("127.0.0.1", "::1", "localhost")


def telemetry_settings(cwd: str | None = None) -> dict:
    """Resolve telemetry state with provenance.

    Returns {"enabled": bool, "endpoint": str, "source": str, "note": str}.
    source is "org-policy" when enabled; "default" otherwise. A repo-level
    enable attempt is reported in note — ignored loudly, not silently.
    """
    root = Path(cwd or os.getcwd())
    result = {"enabled": False, "endpoint": "", "source": "default", "note": ""}

    config_path = root / ".fettle.toml"
    if not config_path.is_file():
        return result
    try:
        raw_cfg = tomllib.loads(config_path.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return result

    repo_tel = raw_cfg.get("telemetry", {})
    if isinstance(repo_tel, dict) and repo_tel.get("enabled"):
        result["note"] = (
            "[telemetry] enabled in .fettle.toml is ignored — telemetry can "
            "only be enabled by the org's digest-pinned central policy ([extends])"
        )

    from fettle.policy_remote import resolve_cached_policy

    org_cfg = resolve_cached_policy(raw_cfg)
    if not org_cfg:
        return result
    org_tel = org_cfg.get("telemetry", {})
    if not (isinstance(org_tel, dict) and org_tel.get("enabled")):
        return result
    endpoint = str(org_tel.get("endpoint", ""))
    if not _endpoint_allowed(endpoint):
        result["note"] = (
            f"org policy enables telemetry but endpoint {endpoint[:48]!r} is "
            "not https:// — telemetry stays off"
        )
        return result
    result.update(enabled=True, endpoint=endpoint, source="org-policy")
    return result


def compute_payload(days: int = 30) -> dict:
    """The exact payload that would be sent — aggregate counters only."""
    from fettle.trace import get_recent_decisions

    cutoff = time.time() - days * 86400
    counters: Counter[str] = Counter()
    for entry in get_recent_decisions(limit=10000):
        if entry.get("ts", 0) <= cutoff:
            continue
        counters["decisions"] += 1
        status = entry.get("status", "")
        if entry.get("findings"):
            counters["fired"] += 1
        if status in _BLOCK_STATUSES:
            counters["blocked"] += 1
        elif status in _OVERRIDE_STATUSES:
            counters["overridden"] += 1
        elif status in _ERROR_STATUSES:
            counters["tool_errors"] += 1
    return {
        "schema": PAYLOAD_SCHEMA,
        "period_days": days,
        "counters": {
            "decisions": counters["decisions"],
            "fired": counters["fired"],
            "blocked": counters["blocked"],
            "overridden": counters["overridden"],
            "tool_errors": counters["tool_errors"],
        },
        "fettle_version": __version__,
    }


def send_payload(payload: dict, endpoint: str, timeout: float = SEND_TIMEOUT_S) -> bool:
    """POST the payload as JSON. Fire-and-forget: returns False on any failure,
    never raises — telemetry must never break anything."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "fettle-telemetry"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — endpoint validated in telemetry_settings
            return 200 <= resp.status < 300
    except OSError:
        return False
