"""P41 contract tests — commit-linked, tamper-evident governance ledger."""

from __future__ import annotations

import json
import subprocess

from fettle.evidence_ledger import (
    anchor,
    append_record,
    read_ledger,
    rotate,
    verify_anchor,
    verify_chain,
)


def _init_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)])
    for flag in (("config", "user.email", "t@t"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(tmp_path), *flag], capture_output=True)
    return str(tmp_path)


def _seed(root, count=3):
    for i in range(count):
        append_record(root, "gate_decision", gate="authorship",
                      decision="allow" if i % 2 == 0 else "block", index=i)


def test_chain_verifies_when_untouched(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root)

    state = verify_chain(root)

    assert state["status"] == "verified"
    assert state["records"] == 3


def test_editing_middle_record_breaks_verification_at_that_point(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root)
    path = tmp_path / ".fettle" / "governance-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["payload"]["decision"] = "allow"  # falsify a block
    lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state = verify_chain(root)

    assert state["status"] == "tampered"
    assert state["at_seq"] == 2


def test_deleting_middle_record_breaks_sequence(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root)
    path = tmp_path / ".fettle" / "governance-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state = verify_chain(root)

    assert state["status"] == "tampered"
    assert "gap" in state["reason"]


def test_anchor_binds_terminal_digest_to_commit(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"])
    _seed(root)

    result = anchor(root)

    assert result["status"] == "completed"
    check = verify_anchor(root)
    assert check["status"] == "anchored"
    assert check["records_since_anchor"] == 0


def test_growth_after_anchor_is_drift_not_tampering(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"])
    _seed(root, 1)
    anchor(root)

    append_record(root, "gate_decision", gate="verify", decision="allow")

    check = verify_anchor(root)
    assert check["status"] == "anchored"
    assert check["records_since_anchor"] == 1


def test_prefix_tampering_after_anchor_is_detected(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"])
    _seed(root, 2)
    anchor(root)
    path = tmp_path / ".fettle" / "governance-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["payload"]["decision"] = "block"
    lines[0] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    check = verify_anchor(root)

    assert check["status"] == "tampered"


def test_rotation_preserves_chain_and_records_retention(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 5)

    result = rotate(root, keep_last=2)

    assert result["pruned"] == 3
    state = verify_chain(root)
    assert state["status"] == "verified"
    retention = json.loads(
        (tmp_path / ".fettle" / "governance-ledger.jsonl")
        .read_text(encoding="utf-8").splitlines()[0]
    )["payload"]["retention"]
    assert retention["pruned_records"] == 3


def test_secret_like_payload_keys_are_dropped_by_default(tmp_path):
    root = _init_repo(tmp_path)

    record = append_record(
        root, "spawn",
        api_key="sk-live-danger", prompt="ignore previous instructions",
        model_output="raw text", gate="spawn", decision="allow",
    )

    assert "api_key" not in record["payload"]
    assert "prompt" not in record["payload"]
    assert "model_output" not in record["payload"]
    assert record["payload"]["decision"] == "allow"


def test_unanchored_ledger_reports_unanchored(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 1)

    assert verify_anchor(root)["status"] == "unanchored"


def test_read_ledger_round_trips_payloads(tmp_path):
    root = _init_repo(tmp_path)
    append_record(root, "note", gate="x", detail={"nested": True})

    records = read_ledger(root)

    assert records[0]["payload"]["detail"] == {"nested": True}


def test_artifact_url_anchor_reports_unknown_coverage(tmp_path):
    root = _init_repo(tmp_path)  # repo WITHOUT commits
    _seed(root, 2)

    result = anchor(root, artifact_url="https://ci/artifact/123")

    assert result["status"] == "completed"
    assert result["coverage"] == "unknown"
    check = verify_anchor(root)
    assert check["status"] == "anchored"
    assert check["coverage"] == "unknown"


def test_commit_anchor_reports_known_coverage(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"])
    _seed(root, 1)

    result = anchor(root)
    check = verify_anchor(root)

    assert result["coverage"] == "known"
    assert check["coverage"] == "known"
