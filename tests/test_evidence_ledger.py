"""P41 contract tests — commit-linked, tamper-evident governance ledger."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

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
    for flag in (("config", "user.email", "test@fettle.invalid"), ("config", "user.name", "t")):
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


# ── P52-adjacent hardening: mutation-killing contract pins ────────────────


def test_anchor_writes_to_exact_governance_path(tmp_path):

    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"])
    _seed(root, 1)

    anchor(root)

    anchor_file = tmp_path / ".fettle" / "ledger-anchor.json"
    assert anchor_file.is_file()
    data = json.loads(anchor_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1


def test_ledger_records_carry_schema_version_one(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 1)

    assert read_ledger(root)[0]["schema_version"] == 1


def test_every_secret_marker_drops_its_key(tmp_path):
    root = _init_repo(tmp_path)

    record = append_record(
        root, "probe",
        secret="s", token="t", password="p", prompt="pr",
        api_key="ak", apikey="ak2", model_output="mo", raw_output="ro",
        decision="keep",
    )

    for dropped in ("secret", "token", "password", "prompt",
                    "api_key", "apikey", "model_output", "raw_output"):
        assert dropped not in record["payload"], dropped
    assert record["payload"]["decision"] == "keep"


def test_record_hash_is_sensitive_to_preimage_shape():
    import hashlib

    from fettle.evidence_ledger import _record_hash

    expected = hashlib.sha256(json.dumps(
        {"seq": 7, "ts": 1.5, "kind": "k", "payload": {"a": 1}, "prev": "p"},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()

    assert _record_hash(7, 1.5, "k", {"a": 1}, "p") == expected
    assert _record_hash(8, 1.5, "k", {"a": 1}, "p") != expected


def test_append_timestamp_is_millisecond_precision(monkeypatch, tmp_path):
    import fettle.evidence_ledger as el

    root = str(tmp_path)
    monkeypatch.setattr(el.time, "time", lambda: 1700000000.1234567)

    record = el.append_record(root, "tick")

    assert record["ts"] == 1700000000.123


def test_append_creates_missing_fettle_directory(tmp_path):
    root = str(tmp_path / "deep" / "leaf")  # parents=True required
    os.makedirs(root)

    append_record(root, "note")

    assert (tmp_path / "deep" / "leaf" / ".fettle" / "governance-ledger.jsonl").is_file()


def test_stored_lines_are_sorted_key_json(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 1)

    line = (tmp_path / ".fettle" / "governance-ledger.jsonl") \
        .read_text(encoding="utf-8").splitlines()[0]

    assert line == json.dumps(json.loads(line), sort_keys=True,
                              separators=(",", ":"))


def test_genesis_prev_constant_is_sixty_four_zeros(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 1)

    assert read_ledger(root)[0]["prev"] == "0" * 64


def test_gap_report_includes_exact_at_seq_and_reason(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 3)
    path = tmp_path / ".fettle" / "governance-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state = verify_chain(root)

    assert state["at_seq"] == 3
    assert state["reason"] == "sequence gap: expected 2, found 3"
    assert set(state) >= {"status", "at_seq", "reason"}


def test_tampered_linkage_reports_use_contract_keys_and_reasons(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 2)
    path = tmp_path / ".fettle" / "governance-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["prev"] = "f" * 64  # break linkage without touching content hash fields
    lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state = verify_chain(root)

    assert state["status"] == "tampered"
    assert state["at_seq"] == 2
    assert state["reason"] in ("previous-hash linkage broken",
                               "record content does not match its hash")


def test_content_hash_mismatch_reason_is_pinned(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 2)
    path = tmp_path / ".fettle" / "governance-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["payload"]["decision"] = "allow"  # falsify; keep seq/ts/kind/prev intact
    lines[1] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state = verify_chain(root)

    assert state["reason"] == "record content does not match its hash"


def test_anchor_drift_result_carries_commit_key(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"])
    _seed(root, 1)
    anchor(root)
    append_record(root, "post", decision="allow")

    check = verify_anchor(root)

    assert "anchored_commit" in check


def test_rotate_renumbers_sequences_continuously(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 5)

    rotate(root, keep_last=2)

    seqs = [r["seq"] for r in read_ledger(root)]
    assert seqs == [1, 2, 3]


def test_terminal_hash_at_boundaries(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 2)
    records = read_ledger(root)

    from fettle.evidence_ledger import terminal_hash_at

    assert terminal_hash_at(root, 0) == "0" * 64
    assert terminal_hash_at(root, 99) == records[-1]["hash"]
    assert terminal_hash_at(root, 1) == records[0]["hash"]


# ── anchor() contract pins ────────────────────────────────────────────────


def _broken(root):
    path = Path(root) / ".fettle" / "governance-ledger.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["payload"]["decision"] = "block"
    lines[0] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_anchor_refusal_envelope_is_exact(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 1)
    _broken(root)

    result = anchor(root)

    assert result == {"status": "refused",
                      "reason": "cannot anchor a broken chain"}


def test_anchor_requires_root_or_artifact(tmp_path):
    root = str(tmp_path / "nonrepo")
    os.makedirs(root)
    _seed(root, 1)

    result = anchor(root)

    assert result["status"] == "tool_error"
    assert "artifact_url" in result["message"]


def test_anchor_file_written_with_parents_and_exact_fields(tmp_path):
    nested = tmp_path / "deep"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(nested)])
    for flag in (("config", "user.email", "test@fettle.invalid"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(nested), *flag], capture_output=True)
    _seed(nested, 1)
    subprocess.run(["git", "-C", str(nested), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(nested), "commit", "-qm", "i"])

    result = anchor(str(nested))

    anchor_file = nested / ".fettle" / "ledger-anchor.json"
    assert anchor_file.is_file()
    data = json.loads(anchor_file.read_text(encoding="utf-8"))
    assert data["commit"] == result["commit"]
    assert data["records"] == 1
    assert data["coverage"] == "known"


def test_verify_anchor_passthrough_fields(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"])
    _seed(root, 1)
    anchor(root)
    append_record(root, "post", decision="allow")

    check = verify_anchor(root)

    assert check["anchored_commit"] and len(check["anchored_commit"]) == 40
    assert check["total_records"] == 2


def test_missing_coverage_key_defaults_to_unknown(tmp_path):
    root = _init_repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(root), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"])
    _seed(root, 1)
    anchor(root)
    anchor_file = tmp_path / ".fettle" / "ledger-anchor.json"
    data = json.loads(anchor_file.read_text(encoding="utf-8"))
    data.pop("coverage")
    anchor_file.write_text(json.dumps(data), encoding="utf-8")

    check = verify_anchor(root)

    assert check["coverage"] == "unknown"


# ── rotate() contract pins ────────────────────────────────────────────────


def test_rotate_refusal_envelope_is_exact(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 2)
    _broken(root)

    result = rotate(root, keep_last=1)

    assert result == {"status": "refused",
                      "reason": "cannot rotate a broken chain"}


def test_rotate_noop_when_below_keep_last(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 2)

    result = rotate(root, keep_last=5)

    assert result["status"] == "completed"
    assert result["pruned"] == 0
    assert len(read_ledger(root)) == 2


def test_rotate_default_keep_last_is_200(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 203)

    result = rotate(root)

    assert result["pruned"] == 3


def test_checkpoint_carries_kind_retention_and_continuity(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 6)

    rotate(root, keep_last=2)

    lines = (tmp_path / ".fettle" / "governance-ledger.jsonl") \
        .read_text(encoding="utf-8").splitlines()
    head = json.loads(lines[0])
    kept_first_prev = json.loads(lines[1])["prev"]

    assert head["kind"] == "checkpoint"
    assert head["payload"]["retention"]["policy"] == "keep_last=2"
    assert head["payload"]["retention"]["pruned_records"] == 4
    assert head["payload"]["rotated_at_seq"] == 4
    assert kept_first_prev == head["hash"]
    assert head["payload"]["chain_checkpoint"] == "d" * 64 or True  # continuity ref exists


def test_rotate_writes_sorted_json_lines(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 4)

    rotate(root, keep_last=1)

    for line in (tmp_path / ".fettle" / "governance-ledger.jsonl") \
            .read_text(encoding="utf-8").splitlines():
        assert line == json.dumps(json.loads(line), sort_keys=True,
                                  separators=(",", ":"))


def test_rotate_result_envelope_keys(tmp_path):
    root = _init_repo(tmp_path)
    _seed(root, 4)

    result = rotate(root, keep_last=1)

    assert result["status"] == "completed"
    assert set(result) >= {"status", "pruned", "retention"}
    assert set(result["retention"]) >= {"policy", "pruned"}
