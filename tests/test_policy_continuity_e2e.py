"""Stage A (A0) — policy-continuity red test: delegation must not weaken policy.

Design doc: docs/engagement/12-stage-a-policy-continuity.md §6.

A simulated child agent runs the dispatcher in a bare temp directory (no
.fettle.toml — escape route E1) with a FETTLE_POLICY_CAPSULE handed down by
its parent. The capsule's policy must govern the child:

1. capsule enforce-mode destructive gate blocks in a repo-less cwd,
2. a tampered capsule fails closed,
3. FETTLE_GATE_MODE=off cannot override a verified capsule (E3).

These tests are the evidence the Stage A slices exist to turn green. They
carry xfail(strict=False) until slice A3 lands; the A3 commit removes the
markers. The capsule documents are built BY HAND here (canonical JSON +
sha256) so the wire format is pinned independently of policy_capsule.py.
"""

import contextlib
import hashlib
import json
import os
import subprocess
import sys

import pytest

DISPATCHER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "dispatcher.py",
)

XFAIL_A3 = pytest.mark.xfail(
    reason="red until Stage A slice A3 (capsule resolution in load_config)",
    strict=False,
)


def _make_capsule(tmp_path, policy: dict, tamper: bool = False) -> str:
    """Write a capsule document per design §2.1; returns its path."""
    body = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(body.encode()).hexdigest()
    doc = {
        "fettle_capsule": 1,
        "digest": digest,
        "policy": policy,
        "origin": {
            "repo_root": str(tmp_path), "repo": "capsule-test",
            "session_id": "parent-session", "created_at": "2026-08-02T00:00:00",
            "fettle_version": "1.4.0",
        },
        "lineage": [],
    }
    if tamper:
        # Policy weakened after signing — digest no longer matches.
        doc["policy"]["gates"]["destructive"]["mode"] = "advisory"
    path = tmp_path / "capsules" / f"{digest[:16]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


def _enforcing_policy() -> dict:
    return {"gates": {"destructive": {"enabled": True, "mode": "enforce"}}}


def _run_child_dispatcher(cwd, env_extra: dict) -> tuple[int, dict | None]:
    """Simulated child: a destructive Bash Pre event in a repo-less cwd."""
    env = os.environ.copy()
    env.pop("FETTLE_GATE_MODE", None)
    env.pop("FETTLE_CONFIG", None)
    env.update(env_extra)
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push --force origin main"},
        "cwd": str(cwd),
        "session_id": "child-session",
    }
    proc = subprocess.run(
        [sys.executable, DISPATCHER],
        input=json.dumps(payload),
        capture_output=True, text=True, timeout=15, env=env,
    )
    out = None
    if proc.stdout.strip():
        with contextlib.suppress(json.JSONDecodeError):
            out = json.loads(proc.stdout.strip())
    return proc.returncode, out


def _is_block(out: dict | None) -> bool:
    if not isinstance(out, dict):
        return False
    if out.get("decision") == "block":
        return True
    hso = out.get("hookSpecificOutput", {})
    return isinstance(hso, dict) and hso.get("permissionDecision") == "deny"


class TestDelegatedPolicyGoverns:
    """E1: child in a bare cwd must still run under the parent's policy."""

    @XFAIL_A3
    def test_capsule_enforce_blocks_in_repoless_cwd(self, tmp_path) -> None:
        child_cwd = tmp_path / "child"
        child_cwd.mkdir()
        capsule = _make_capsule(tmp_path, _enforcing_policy())
        rc, out = _run_child_dispatcher(
            child_cwd, {"FETTLE_POLICY_CAPSULE": capsule})
        assert rc == 0  # hooks always exit 0; the block is in the output
        assert _is_block(out), f"capsule enforce mode not honored: {out}"

    def test_without_capsule_child_is_ungoverned_baseline(self, tmp_path) -> None:
        """Documents the pre-Stage-A world: defaults are advisory → no block.

        NOT xfailed — when this ever changes, the threat model doc must too.
        """
        child_cwd = tmp_path / "child"
        child_cwd.mkdir()
        rc, out = _run_child_dispatcher(child_cwd, {})
        assert rc == 0
        assert not _is_block(out)


class TestCapsuleTamperFailsClosed:
    """§2.4 D-A4: digest mismatch → block, independent of repo config."""

    @XFAIL_A3
    def test_tampered_capsule_blocks(self, tmp_path) -> None:
        child_cwd = tmp_path / "child"
        child_cwd.mkdir()
        capsule = _make_capsule(tmp_path, _enforcing_policy(), tamper=True)
        rc, out = _run_child_dispatcher(
            child_cwd, {"FETTLE_POLICY_CAPSULE": capsule})
        assert rc == 0
        assert _is_block(out), f"tampered capsule must fail closed: {out}"


class TestKillSwitchNeutered:
    """E3 / D-A3: env kill switches cannot weaken a verified capsule."""

    @XFAIL_A3
    def test_gate_mode_off_cannot_override_capsule(self, tmp_path) -> None:
        child_cwd = tmp_path / "child"
        child_cwd.mkdir()
        capsule = _make_capsule(tmp_path, _enforcing_policy())
        rc, out = _run_child_dispatcher(
            child_cwd,
            {"FETTLE_POLICY_CAPSULE": capsule, "FETTLE_GATE_MODE": "off"},
        )
        assert rc == 0
        assert _is_block(out), f"FETTLE_GATE_MODE=off must not defeat capsule: {out}"
