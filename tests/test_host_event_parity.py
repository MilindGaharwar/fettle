"""Strict host event parity — enforced equality of core capability, and
honest per-host deltas for everything else."""

from __future__ import annotations

from pathlib import Path

import pytest

from fettle.host_capabilities import (
    CORE_EVENTS,
    SUBAGENT_START_REASON,
    core_event_gaps,
    host_capabilities,
    hosts_supporting,
)

ROOT = Path(__file__).resolve().parent.parent


def test_every_host_supports_all_core_events():
    gaps = core_event_gaps()

    assert gaps == {}, f"hosts missing core events: {gaps}"


def test_matrix_covers_exactly_the_supported_hosts():
    hosts = set(host_capabilities())

    assert hosts == {"claude_code", "codex", "gemini", "opencode"}


def test_declared_native_events_match_transport_sources():
    """Declared native events must appear in the transport/init source that
    wires them — silent capability drift fails here."""
    sources = {
        "claude_code": [(ROOT / "fettle" / "bridge.py").read_text(encoding="utf-8"),
                        (ROOT / "fettle" / "agents" / "claude_code.py").read_text(encoding="utf-8")],
        "codex": [(ROOT / "fettle" / "init_cmd.py").read_text(encoding="utf-8")],
        "gemini": [(ROOT / "fettle" / "init_cmd.py").read_text(encoding="utf-8"),
                   (ROOT / "fettle" / "agents" / "gemini.py").read_text(encoding="utf-8")],
        "opencode": [(ROOT / "fettle" / "bridge.py").read_text(encoding="utf-8")],
    }

    for host, caps in host_capabilities().items():
        combined = "\n".join(sources[host])
        for event in caps["native"]:
            assert f'"{event}"' in combined or f"'{event}'" in combined, (
                f"{host} declares native event {event!r} but its transport "
                f"source never references it"
            )


def test_subagent_start_is_strictly_claude_with_documented_reason():
    caps = host_capabilities()

    assert caps["claude_code"]["subagent_start"] is True
    for host in ("codex", "gemini", "opencode"):
        assert caps[host]["subagent_start"] is False, (
            f"{host} now exposes a subagent-start signal — update the "
            f"matrix, translator, and docs/event-map.md, then relax this"
        )
    assert "fettle spawn" in SUBAGENT_START_REASON


def test_no_undeclared_subagent_start_wiring_in_other_hosts():
    """Future enforcement: if another host's transport starts wiring a
    subagent-start signal, this fails and forces a matrix update."""
    other_hosts = [
        ROOT / "fettle" / "agents" / "codex.py",
        ROOT / "fettle" / "agents" / "gemini.py",
        ROOT / "fettle" / "agents" / "opencode.py",
        ROOT / "fettle" / "init_cmd.py",
    ]
    offenders = []
    for path in other_hosts:
        text = path.read_text(encoding="utf-8")
        if "SubagentStart" in text or "subagent_start" in text \
                or "AfterAgentStart" in text:
            offenders.append(path.name)

    assert not offenders, (
        f"non-Claude transports reference subagent-start signals: {offenders} "
        f"— extend host_capabilities and docs/event-map.md first"
    )


def test_event_map_documents_the_parity_truth():
    event_map = (ROOT / "docs" / "event-map.md").read_text(encoding="utf-8")
    subagent_section = event_map.split("### SubagentStart", 1)[1]

    assert "Claude Code" in subagent_section
    for host in ("Codex CLI", "Gemini CLI", "OpenCode"):
        assert host not in subagent_section.split("| **Durability**")[0], (
            f"event map implies {host} supports SubagentStart"
        )


def test_hosts_supporting_helper():
    assert set(hosts_supporting("PreToolUse")) == set(host_capabilities())
    assert hosts_supporting("SubagentStart") == ("claude_code",)


def test_core_events_are_the_documented_three():
    assert tuple(CORE_EVENTS) == ("PreToolUse", "PostToolUse", "Stop")


@pytest.mark.parametrize("host", ["claude_code", "codex", "gemini", "opencode"])
def test_translation_output_is_within_dispatcher_vocabulary(host):
    from fettle.dispatcher_registry import CHECKS

    known = {e for c in CHECKS for e in c.events} | {"SubagentStart"}
    caps = host_capabilities()[host]

    for event in caps["dispatcher_events"]:
        assert event in known, (
            f"{host} translates to {event!r}, which no check consumes"
        )


# ─── Enforcement matrix (2026-08 audit: support ≠ enforcement) ────────────


@pytest.mark.parametrize("host", ["claude_code", "codex", "gemini", "opencode"])
def test_every_core_event_has_a_declared_enforcement_level(host):
    caps = host_capabilities()[host]
    for event in CORE_EVENTS:
        assert caps["enforcement"].get(event) in ("block", "notify"), (
            f"{host} declares no enforcement level for {event}"
        )


def test_opencode_post_and_stop_are_notify_only():
    from fettle.host_capabilities import enforcement_gaps

    assert enforcement_gaps() == {"opencode": ("PostToolUse", "Stop")}
