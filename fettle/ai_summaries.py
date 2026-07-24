"""Fettle v0.5.0 — WP-100: AI-agent optimized summaries."""

from __future__ import annotations

from fettle.finding import CheckFinding, FindingSeverity


def format_ai_summary(findings: list[CheckFinding], duration_ms: float = 0) -> str:
    """Format findings as a concise AI-agent-optimized summary."""
    if not findings:
        return "No findings."

    blocking = [f for f in findings if f.blocking]
    warnings = [f for f in findings if f.severity == FindingSeverity.WARNING and not f.blocking]
    info = [f for f in findings if f.severity == FindingSeverity.INFO]

    header = f"{len(blocking)} blocking, {len(warnings)} warning, {len(info)} info"
    if duration_ms:
        header += f" ({duration_ms:.0f}ms)"

    lines = [header, ""]
    for f in findings[:10]:
        loc = f"{f.file}:{f.line}" if f.file and f.line else f.file or ""
        msg = f.message[:200]
        line = f"[{f.severity.value.upper()}] {loc} — {msg}"
        if f.suggested_fix:
            fix = f.suggested_fix[:150]
            line += f"\n  fix: {fix}"
        lines.append(line[:500])

    if len(findings) > 10:
        lines.append(f"... and {len(findings) - 10} more.")

    if blocking:
        lines.append("")
        lines.append("Run `fettle check --changed` to clear.")

    return "\n".join(lines)
