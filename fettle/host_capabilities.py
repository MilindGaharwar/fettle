"""Host event capability matrix — single source of truth (strict parity).

Declares, per supported agent host, the native hook events, their
translation into dispatcher events, and whether the host exposes a
subagent-start signal. The dispatcher itself is host-agnostic: it handles
any ``hook_event_name`` a translator forwards.

Parity contract (enforced by tests/test_host_event_parity.py):

1. Every host supports all CORE_EVENTS (natively or via translation).
2. Declared native events must match what the transport/init code actually
   wires — drift fails the suite.
3. SubagentStart is Claude-specific because only Claude Code emits it; the
   host-equal delegation mechanism is ``fettle spawn`` env lineage
   (FETTLE_POLICY_CAPSULE + FETTLE_PARENT_SESSION), which all hosts share.
"""

from __future__ import annotations

CORE_EVENTS = ("PreToolUse", "PostToolUse", "Stop")

CLAUDE_EVENTS = ("PreToolUse", "PostToolUse", "Stop", "SubagentStart")
CODEX_EVENTS = ("PreToolUse", "PostToolUse", "Stop")
GEMINI_NATIVE = ("BeforeTool", "AfterTool", "AfterAgent")
GEMINI_TRANSLATION = {"BeforeTool": "PreToolUse", "AfterTool": "PostToolUse",
                      "AfterAgent": "Stop"}
OPENCODE_NATIVE = ("tool.execute.before", "tool.execute.after", "session.idle")
OPENCODE_TRANSLATION = {"tool.execute.before": "PreToolUse",
                        "tool.execute.after": "PostToolUse",
                        "session.idle": "Stop"}

SUBAGENT_START_REASON = (
    "Only Claude Code emits a subagent-start hook event. Delegation on every "
    "host is equal through fettle spawn env lineage (FETTLE_POLICY_CAPSULE + "
    "FETTLE_PARENT_SESSION), which the dispatcher reads host-agnostically."
)


def _translated(native: tuple[str, ...], mapping: dict[str, str]) -> tuple[str, ...]:
    seen: list[str] = []
    for event in native:
        translated = mapping.get(event, event)
        if translated not in seen:
            seen.append(translated)
    return tuple(seen)


def host_capabilities() -> dict[str, dict]:
    """Capability matrix: host -> native events, dispatcher events, flags."""
    return {
        "claude_code": {
            "native": CLAUDE_EVENTS,
            "dispatcher_events": CLAUDE_EVENTS,
            "translation": {},
            "subagent_start": True,
        },
        "codex": {
            "native": CODEX_EVENTS,
            "dispatcher_events": CODEX_EVENTS,
            "translation": {},
            "subagent_start": False,
        },
        "gemini": {
            "native": GEMINI_NATIVE,
            "dispatcher_events": _translated(GEMINI_NATIVE, GEMINI_TRANSLATION),
            "translation": GEMINI_TRANSLATION,
            "subagent_start": False,
        },
        "opencode": {
            "native": OPENCODE_NATIVE,
            "dispatcher_events": _translated(OPENCODE_NATIVE,
                                             OPENCODE_TRANSLATION),
            "translation": OPENCODE_TRANSLATION,
            "subagent_start": False,
        },
    }


def core_event_gaps() -> dict[str, tuple[str, ...]]:
    """Hosts missing any CORE_EVENT after translation, with the gap."""
    gaps: dict[str, tuple[str, ...]] = {}
    for host, caps in host_capabilities().items():
        supported = set(caps["dispatcher_events"])
        missing = tuple(e for e in CORE_EVENTS if e not in supported)
        if missing:
            gaps[host] = missing
    return gaps


def hosts_supporting(event: str) -> tuple[str, ...]:
    return tuple(host for host, caps in host_capabilities().items()
                 if event in caps["dispatcher_events"])
