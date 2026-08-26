"""P83 — Assurance Adversary suite.

Named attack scenarios that attempt to fool the assurance system. Each
adversary proves that Fettle detects the attack. These are the tests that
make the enforcement bar honest: if any adversary passes undetected, the
assurance system has a gap.

Scenarios are grouped by the defense they target:
  ledger    — hash-chain integrity, anchoring, rotation
  transcript— artifact-bound reconciliation, drift detection
  capsule   — policy monotonicity, tamper detection
  scope     — changed-file manipulation, boundary rules
  docs      — documentation claims matching code reality
"""

from __future__ import annotations

import json
import subprocess

from unittest.mock import patch

from fettle.evidence_ledger import verify_chain
from fettle.uat.reconcile import reconcile

# ── helpers ───────────────────────────────────────────────────────────────


def _init_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)])
    for flag in (("config", "user.email", "t@t"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(root), *flag], capture_output=True)
    (root / ".fettle").mkdir(exist_ok=True)
    return root


def _append(root, kind="gate_decision", **payload):
    from fettle.evidence_ledger import append_record

    return append_record(str(root), kind, **payload)


# ── ledger adversaries ────────────────────────────────────────────────────


class TestLedgerTamper:
    """Adversary: modify the governance ledger to hide a block or fake a pass."""

    def test_falsify_block_to_allow(self, tmp_path):
        """Attacker edits a blocked decision to read 'allow'."""
        root = _init_repo(tmp_path)
        _append(root, decision="block", gate="authorship")
        _append(root, decision="allow", gate="authorship")

        ledger = root / ".fettle" / "governance-ledger.jsonl"
        lines = ledger.read_text().splitlines()
        rec = json.loads(lines[0])
        rec["payload"]["decision"] = "allow"
        lines[0] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        ledger.write_text("\n".join(lines) + "\n")

        result = verify_chain(str(root))
        assert result["status"] == "tampered"
        assert result["at_seq"] == 1

    def test_delete_incriminating_record(self, tmp_path):
        """Attacker deletes the record that proves a violation."""
        root = _init_repo(tmp_path)
        _append(root, decision="allow")
        _append(root, decision="block", gate="destructive_guard")
        _append(root, decision="allow")

        ledger = root / ".fettle" / "governance-ledger.jsonl"
        lines = ledger.read_text().splitlines()
        del lines[1]  # delete the block
        ledger.write_text("\n".join(lines) + "\n")

        result = verify_chain(str(root))
        assert result["status"] == "tampered"

    def test_reorder_records(self, tmp_path):
        """Attacker swaps two records to change the narrative."""
        root = _init_repo(tmp_path)
        _append(root, decision="block")
        _append(root, decision="allow")

        ledger = root / ".fettle" / "governance-ledger.jsonl"
        lines = ledger.read_text().splitlines()
        lines[0], lines[1] = lines[1], lines[0]
        ledger.write_text("\n".join(lines) + "\n")

        result = verify_chain(str(root))
        assert result["status"] == "tampered"


# ── transcript adversaries ────────────────────────────────────────────────


class TestTranscriptDrift:
    """Adversary: modify the transcript after the artifact was captured."""

    SCENARIOS = [{"id": "demo/S1", "title": "Works", "steps": ["Given x"],
                  "requirements": []}]
    TRANSCRIPT = ("SCENARIO: demo/S1\nOBSERVED: exited 0\nOUTCOME: matches\n")
    TAMPERED = TRANSCRIPT.replace("exited 0", "everything worked")

    def test_drift_detected(self, tmp_path):
        from fettle.uat.artifacts import (
            load_scenario_artifacts,
            write_scenario_artifacts,
        )
        wt = tmp_path / "wt"
        wt.mkdir()
        write_scenario_artifacts(str(wt), self.TRANSCRIPT, self.SCENARIOS, "cli")

        verdicts = reconcile(
            self.SCENARIOS, self.TAMPERED,
            artifacts=load_scenario_artifacts(str(wt)),
            require_artifacts=True,
        )
        assert verdicts[0].verdict == "INDETERMINATE"
        assert "drifted" in verdicts[0].note


# ── capsule adversaries ──────────────────────────────────────────────────


class TestCapsuleTamper:
    """Adversary: child agent tries to widen its policy boundary."""

    def test_child_cannot_escalate_role(self, tmp_path):
        """A capsule with role=implementer cannot be widened to solo."""
        from fettle.policy_capsule import merge_for_child, write_capsule

        capsule_dir = tmp_path / "capsules"
        capsule_dir.mkdir(parents=True)
        with patch("fettle.policy_capsule._capsules_dir",
                   return_value=capsule_dir):
            path = write_capsule(
                {"role": "implementer"},
                origin={"session_id": "parent"},
            )

        child_local = {"role": "solo"}
        effective, _err = merge_for_child(
            json.loads(path.read_text())["policy"], child_local
        )
        assert effective["role"] == "implementer"  # cannot widen

