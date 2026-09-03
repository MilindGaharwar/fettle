"""P41 — Durable, commit-linked governance evidence ledger.

Evolves mutable local traces into a queryable, tamper-EVIDENT (not immutable)
hash-chained ledger:

- Every record hashes over its sequence number, timestamp, kind, redacted
  payload, and the previous record's hash — editing or deleting any middle
  record breaks verification at that exact point.
- ``anchor`` periodically binds the terminal digest to a repository commit;
  verification reports whether the ledger drifted *after* an anchor (normal)
  versus diverging from the anchored digest (tampering).
- Rotation prunes old records while preserving chain continuity via a
  checkpoint record plus retention metadata.
- Redaction drops secret-like payload keys by default (prompts, tokens,
  raw model output) before anything touches disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

LEDGER_REL = ".fettle/governance-ledger.jsonl"
ANCHOR_REL = ".fettle/ledger-anchor.json"
SCHEMA_VERSION = 1

_SECRET_KEY_MARKERS = ("secret", "token", "password", "prompt", "api_key", "apikey")
CHECKPOINT_KIND = "checkpoint"


def _paths(root: str) -> tuple[Path, Path]:
    base = Path(root)
    return base / LEDGER_REL, base / ANCHOR_REL


def _redact(payload: dict) -> dict:
    clean = {}
    for key, value in payload.items():
        lowered = key.lower()
        if isinstance(value, str) and any(m in lowered for m in _SECRET_KEY_MARKERS):
            continue
        if lowered in {"raw_output", "model_output"}:
            continue
        clean[key] = value
    return clean


def _record_hash(seq: int, ts: float, kind: str, payload: dict, prev: str) -> str:
    preimage = json.dumps(
        {"seq": seq, "ts": ts, "kind": kind, "payload": payload, "prev": prev},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(preimage.encode()).hexdigest()


def _read_records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def read_ledger(root: str) -> list[dict]:
    path, _anchor = _paths(root)
    return _read_records(path)


def append_record(root: str, kind: str, **payload) -> dict:
    path, _anchor = _paths(root)
    records = _read_records(path)
    prev = records[-1]["hash"] if records else "0" * 64
    seq = (records[-1]["seq"] + 1) if records else 1
    clean = _redact(payload)
    record = {
        "schema_version": SCHEMA_VERSION,
        "seq": seq,
        "ts": round(time.time(), 3),
        "kind": kind,
        "payload": clean,
        "prev": prev,
    }
    record["hash"] = _record_hash(record["seq"], record["ts"], kind, clean, prev)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    return record


def verify_chain(root: str) -> dict:
    """Full-chain verification. Reports the first break precisely."""
    try:
        records = read_ledger(root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "tampered", "at_seq": None,
                "reason": f"ledger is malformed: {exc}"}
    prev = "0" * 64
    expected_seq = 1
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            return {"status": "tampered", "at_seq": expected_seq,
                    "reason": "ledger record is malformed"}
        seq = record.get("seq")
        if seq != expected_seq:
            return {
                "status": "tampered", "at_seq": seq,
                "reason": f"sequence gap: expected {expected_seq}, found {seq}",
            }
        if (record.get("schema_version") != SCHEMA_VERSION
                or not isinstance(record.get("ts"), (int, float))
                or not isinstance(record.get("kind"), str)
                or not isinstance(record.get("payload"), dict)
                or not isinstance(record.get("prev"), str)
                or not isinstance(record.get("hash"), str)):
            return {"status": "tampered", "at_seq": seq,
                    "reason": "ledger record is malformed"}
        recomputed = _record_hash(
            record["seq"], record["ts"], record["kind"],
            record["payload"], record["prev"],
        )
        # First record: a plain genesis must start from the zero hash, while
        # a rotation checkpoint legitimately continues a pruned chain.
        if position == 0 and record.get("kind") != CHECKPOINT_KIND:
            if record.get("prev") != prev:
                return {
                    "status": "tampered", "at_seq": seq,
                    "reason": "genesis previous-hash linkage broken",
                }
        elif position > 0 and record.get("prev") != prev:
            return {
                "status": "tampered", "at_seq": seq,
                "reason": "previous-hash linkage broken",
            }
        if record.get("hash") != recomputed:
            return {
                "status": "tampered", "at_seq": seq,
                "reason": "record content does not match its hash",
            }
        prev = record["hash"]
        expected_seq += 1
    return {"status": "verified", "records": len(records), "terminal_hash": prev}


def anchor(root: str, commit: str | None = None,
           artifact_url: str | None = None) -> dict:
    """Bind the terminal digest to a repository commit or CI artifact URL."""
    state = verify_chain(root)
    if state["status"] != "verified":
        return {"status": "refused", "reason": "cannot anchor a broken chain"}
    if commit is None:
        commit = _rev_parse(root)
        if commit is None:
            if not artifact_url:
                return {"status": "tool_error",
                        "message": "not a git repository; pass artifact_url "
                                   "to anchor against a CI artifact"}
            # Externally owned commits: coverage is explicitly unknown.
            return _write_anchor(root, state, commit=None,
                                 artifact_url=artifact_url,
                                 coverage="unknown")
    return _write_anchor(root, state, commit=commit,
                         artifact_url=artifact_url, coverage="known")


def _write_anchor(root: str, state: dict, commit: str | None,
                  artifact_url: str | None, coverage: str) -> dict:
    path, anchor_path = _paths(root)
    terminal = state["terminal_hash"]
    anchor_path.parent.mkdir(parents=True, exist_ok=True)
    anchor_path.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "anchored_at": round(time.time(), 3),
        "commit": commit,
        "artifact_url": artifact_url,
        "coverage": coverage,
        "records": state["records"],
        "terminal_hash": terminal,
    }, indent=2) + "\n", encoding="utf-8")
    return {"status": "completed", "commit": commit,
            "artifact_url": artifact_url, "coverage": coverage,
            "records": state["records"], "terminal_hash": terminal}


def _rev_parse(root: str) -> str | None:
    done = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def verify_anchor(root: str) -> dict:
    """Check ledger against its last anchor: anchored | drifted | tampered."""
    _path, anchor_path = _paths(root)
    if not anchor_path.is_file():
        return {"status": "unanchored"}
    try:
        anchor_data = json.loads(anchor_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "tampered", "reason": f"anchor is malformed: {exc}"}
    if (not isinstance(anchor_data, dict)
            or anchor_data.get("schema_version") != SCHEMA_VERSION
            or not isinstance(anchor_data.get("records"), int)
            or anchor_data["records"] < 0
            or not isinstance(anchor_data.get("terminal_hash"), str)
            or len(anchor_data["terminal_hash"]) != 64):
        return {"status": "tampered", "reason": "anchor is malformed"}
    state = verify_chain(root)
    if state["status"] != "verified":
        return {**state, "anchored_commit": anchor_data.get("commit"),
                "coverage": anchor_data.get("coverage", "unknown")}
    records_now = state["records"]
    anchored_records = anchor_data.get("records", 0)
    if records_now < anchored_records:
        return {
            "status": "tampered", "reason": "ledger shorter than its anchor",
            "anchored_commit": anchor_data.get("commit"),
            "coverage": anchor_data.get("coverage", "unknown"),
        }
    terminal_now = terminal_hash_at(root, anchored_records)
    if terminal_now != anchor_data["terminal_hash"]:
        return {
            "status": "tampered",
            "reason": "prefix diverges from anchored terminal digest",
            "anchored_commit": anchor_data.get("commit"),
            "coverage": anchor_data.get("coverage", "unknown"),
        }
    return {
        "status": "anchored",
        "anchored_commit": anchor_data.get("commit"),
        "coverage": anchor_data.get("coverage", "unknown"),
        "records_since_anchor": records_now - anchored_records,
        "total_records": records_now,
    }


def terminal_hash_at(root: str, count: int) -> str:
    records = read_ledger(root)
    if not records or count <= 0:
        return "0" * 64
    return records[min(count, len(records)) - 1]["hash"]


def rotate(root: str, keep_last: int = 200) -> dict:
    """Prune history, preserving continuity through a checkpoint record."""
    path, _anchor = _paths(root)
    records = _read_records(path)
    state = verify_chain(root)
    if state["status"] != "verified":
        return {"status": "refused", "reason": "cannot rotate a broken chain"}
    total = len(records)
    if total <= keep_last:
        return {"status": "completed", "pruned": 0,
                "retention": {"policy": f"keep_last={keep_last}", "pruned": 0}}
    kept = records[-keep_last:]
    pruned = records[:-keep_last]
    checkpoint = {
        "schema_version": SCHEMA_VERSION,
        "seq": 1,
        "ts": round(time.time(), 3),
        "kind": CHECKPOINT_KIND,
        "payload": {
            "retention": {"policy": f"keep_last={keep_last}",
                          "pruned_records": len(pruned)},
            "chain_checkpoint": pruned[-1]["hash"],
            "rotated_at_seq": total - keep_last,
        },
        "prev": pruned[-1]["hash"],
    }
    checkpoint["hash"] = _record_hash(
        checkpoint["seq"], checkpoint["ts"], checkpoint["kind"],
        checkpoint["payload"], checkpoint["prev"],
    )
    new_records = [checkpoint]
    prev = checkpoint["hash"]
    for i, rec in enumerate(kept, start=2):
        payload = rec.get("payload", {})
        rec = {
            **rec, "seq": i, "prev": prev,
            "hash": _record_hash(i, rec["ts"], rec["kind"], payload, prev),
        }
        new_records.append(rec)
        prev = rec["hash"]
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for rec in new_records:
            handle.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    os.replace(tmp, path)
    return {"status": "completed", "pruned": len(pruned),
            "retention": {"policy": f"keep_last={keep_last}",
                          "pruned": len(pruned),
                          "checkpoint": checkpoint["hash"][:12]}}
