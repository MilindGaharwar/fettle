"""WP-120 — Suppressions with expiry and owner.

Extended suppression model:
  # fettle:ignore[rule-id] reason=... owner=@handle until=YYYY-MM-DD

Features:
- Inline comment suppressions with structured metadata
- File-level suppressions in .fettle/suppressions.json
- Expired suppressions become findings themselves
- Ownerless suppressions flagged in reports
- `fettle suppressions report` for review meetings
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


SCHEMA_VERSION = "1"

_INLINE_RE = re.compile(
    r"#\s*fettle:ignore\[([^\]]+)\]"
    r"(?:\s+reason=(.*?))??"
    r"(?:\s+owner=(@\S+))?"
    r"(?:\s+until=(\d{4}-\d{2}-\d{2}))?"
    r"\s*$"
)


@dataclass
class Suppression:
    """A single suppression entry with full metadata."""

    rule: str
    path: str = ""
    reason: str = ""
    owner: str = ""
    until: str = ""
    created_at: str = ""
    source: str = "file"

    @property
    def is_expired(self) -> bool:
        if not self.until:
            return False
        return self.until < date.today().isoformat()

    @property
    def is_ownerless(self) -> bool:
        return not self.owner.strip()

    @property
    def days_until_expiry(self) -> int | None:
        if not self.until:
            return None
        try:
            expiry = date.fromisoformat(self.until)
            return (expiry - date.today()).days
        except ValueError:
            return None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_expired"] = self.is_expired
        d["is_ownerless"] = self.is_ownerless
        d["days_until_expiry"] = self.days_until_expiry
        return d


def _suppressions_path(project_root: Path) -> Path:
    return project_root / ".fettle" / "suppressions.json"


def _empty_data() -> dict:
    return {"schema_version": SCHEMA_VERSION, "suppressions": []}


def load_suppressions(project_root: Path) -> list[Suppression]:
    """Load suppressions from .fettle/suppressions.json."""
    path = _suppressions_path(project_root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or "suppressions" not in data:
            return []
        return [
            Suppression(
                rule=s.get("rule", ""),
                path=s.get("path", ""),
                reason=s.get("reason", ""),
                owner=s.get("owner", ""),
                until=s.get("until", ""),
                created_at=s.get("created_at", ""),
                source="file",
            )
            for s in data["suppressions"]
            if isinstance(s, dict) and s.get("rule")
        ]
    except (json.JSONDecodeError, OSError):
        return []


def save_suppressions(project_root: Path, suppressions: list[Suppression]) -> None:
    """Atomic write of suppressions to .fettle/suppressions.json."""
    supp_dir = project_root / ".fettle"
    supp_dir.mkdir(parents=True, exist_ok=True)
    path = _suppressions_path(project_root)

    data = {
        "schema_version": SCHEMA_VERSION,
        "suppressions": [
            {
                "rule": s.rule,
                "path": s.path,
                "reason": s.reason,
                "owner": s.owner,
                "until": s.until,
                "created_at": s.created_at,
            }
            for s in suppressions
        ],
    }
    content = json.dumps(data, indent=2) + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=str(supp_dir), suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp_path, str(path))
    except Exception:
        import contextlib
        with contextlib.suppress(OSError):
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def add_suppression(
    project_root: Path,
    rule: str,
    reason: str,
    path: str = "",
    owner: str = "",
    until: str = "",
) -> Suppression:
    """Add a new suppression entry."""
    suppressions = load_suppressions(project_root)
    entry = Suppression(
        rule=rule,
        path=path,
        reason=reason,
        owner=owner,
        until=until,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        source="file",
    )
    suppressions.append(entry)
    save_suppressions(project_root, suppressions)
    return entry


def remove_suppression(project_root: Path, index: int) -> Suppression | None:
    """Remove a suppression by index. Returns removed entry or None."""
    suppressions = load_suppressions(project_root)
    if index < 0 or index >= len(suppressions):
        return None
    removed = suppressions.pop(index)
    save_suppressions(project_root, suppressions)
    return removed


def parse_inline_suppression(line_content: str) -> Suppression | None:
    """Parse an inline fettle:ignore comment with structured metadata.

    Format: # fettle:ignore[rule-id] reason=... owner=@handle until=YYYY-MM-DD
    """
    match = _INLINE_RE.search(line_content)
    if not match:
        return None
    rule = match.group(1).strip()
    reason = (match.group(2) or "").strip()
    owner = (match.group(3) or "").strip()
    until = (match.group(4) or "").strip()
    return Suppression(
        rule=rule,
        reason=reason,
        owner=owner,
        until=until,
        source="inline",
    )


def is_suppressed(
    finding_rule: str,
    finding_path: str,
    suppressions: list[Suppression],
) -> bool:
    """Check if a finding is suppressed by an active (non-expired) suppression."""
    for s in suppressions:
        if s.is_expired:
            continue
        if s.rule != finding_rule:
            continue
        if s.path and finding_path and not finding_path.startswith(s.path):
            continue
        return True
    return False


def get_expired(suppressions: list[Suppression]) -> list[Suppression]:
    """Return all expired suppressions (these become findings themselves)."""
    return [s for s in suppressions if s.is_expired]


def get_ownerless(suppressions: list[Suppression]) -> list[Suppression]:
    """Return all suppressions without an owner."""
    return [s for s in suppressions if s.is_ownerless]


def get_expiring_soon(suppressions: list[Suppression], days: int = 14) -> list[Suppression]:
    """Return suppressions expiring within N days."""
    results = []
    for s in suppressions:
        remaining = s.days_until_expiry
        if remaining is not None and 0 <= remaining <= days:
            results.append(s)
    return results


def suppressions_report(project_root: Path) -> dict[str, Any]:
    """Generate a full suppressions report for review meetings."""
    suppressions = load_suppressions(project_root)
    expired = get_expired(suppressions)
    ownerless = get_ownerless(suppressions)
    expiring_soon = get_expiring_soon(suppressions)
    active = [s for s in suppressions if not s.is_expired]

    return {
        "total": len(suppressions),
        "active": len(active),
        "expired": len(expired),
        "ownerless": len(ownerless),
        "expiring_soon": len(expiring_soon),
        "expired_items": [s.to_dict() for s in expired],
        "ownerless_items": [s.to_dict() for s in ownerless],
        "expiring_soon_items": [s.to_dict() for s in expiring_soon],
    }


def cmd_suppressions(args: argparse.Namespace) -> None:
    """CLI handler for `fettle suppressions` subcommand."""
    from paths import find_repo_root

    project_root = find_repo_root()
    if not project_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(1)

    action = getattr(args, "supp_action", None)

    if action == "list":
        suppressions = load_suppressions(project_root)
        if not suppressions:
            print("No suppressions configured.")
            return
        print(f"{'#':<4} {'Rule':<25} {'Path':<20} {'Owner':<12} {'Until':<12} {'Status':<10}")
        print("-" * 85)
        for i, s in enumerate(suppressions):
            status = "EXPIRED" if s.is_expired else "active"
            remaining = s.days_until_expiry
            if remaining is not None and 0 <= remaining <= 14:
                status = f"{remaining}d left"
            print(
                f"{i:<4} {s.rule:<25} {s.path or '*':<20} "
                f"{s.owner or '(none)':<12} {s.until or '(never)':<12} {status:<10}"
            )

    elif action == "add":
        entry = add_suppression(
            project_root,
            rule=args.rule,
            reason=args.reason,
            path=args.path,
            owner=args.owner,
            until=args.until,
        )
        print(f"Added suppression: {entry.rule} (path={entry.path or '*'}, until={entry.until or 'never'})")

    elif action == "remove":
        removed = remove_suppression(project_root, args.index)
        if removed:
            print(f"Removed suppression #{args.index}: {removed.rule} ({removed.reason})")
        else:
            print(f"Error: index {args.index} out of range.", file=sys.stderr)
            sys.exit(1)

    elif action == "report":
        report = suppressions_report(project_root)
        print(f"── Suppressions Report ──\n")
        print(f"  Total: {report['total']}")
        print(f"  Active: {report['active']}")
        print(f"  Expired: {report['expired']}")
        print(f"  Ownerless: {report['ownerless']}")
        print(f"  Expiring soon (14d): {report['expiring_soon']}")
        if report["expired_items"]:
            print("\n── Expired (now findings!) ──")
            for item in report["expired_items"]:
                print(f"  {item['rule']} in {item['path'] or '*'} (expired {item['until']})")
        if report["ownerless_items"]:
            print("\n── Ownerless (assign an owner) ──")
            for item in report["ownerless_items"]:
                print(f"  {item['rule']} in {item['path'] or '*'}: {item['reason']}")
        if report["expiring_soon_items"]:
            print("\n── Expiring Soon ──")
            for item in report["expiring_soon_items"]:
                print(f"  {item['rule']} in {item['path'] or '*'} (expires {item['until']}, {item['days_until_expiry']}d)")

    elif action == "expired":
        suppressions = load_suppressions(project_root)
        expired = get_expired(suppressions)
        if not expired:
            print("No expired suppressions.")
            return
        print(f"── {len(expired)} Expired Suppression(s) — these are now active findings ──\n")
        for s in expired:
            print(f"  {s.rule} in {s.path or '*'} (expired {s.until}, reason: {s.reason})")

    else:
        print("Usage: fettle suppressions {list|add|remove|report|expired}")
        sys.exit(1)
