"""Canonical mutation-corpus aggregation and inventory contracts."""

import json

import pytest

from fettle.mutation_test import (
    aggregate_preflight_shards,
    build_calibration_representation_inventory,
    load_mutation_report_candidates,
    read_calibration_representation_inventory,
)
from scripts.staged_preflight import FROZEN_CANDIDATE, WAVES

def test_all_fixed_waves_feed_authoritative_complete_corpus_aggregation(monkeypatch, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("\n".join(f"line_{index} = 1" for index in range(256)) + "\n")
    reports = []
    for shards in WAVES.values():
        for index in shards:
            fingerprint = f"{index + 1:064x}"
            reports.append({
                "status": "completed", "passed": True, "engine_version": "2.5.1",
                "shard_index": index, "shard_count": 256, "manifest_digest": f"{index:064x}",
                "line_ranges": [{"file": "src/app.py", "start": index + 1, "end": index + 1}],
                "files": ["src/app.py"], "generated": 1, "canonicalized": 1, "collisions": 0,
                "fingerprints": [fingerprint], "corpus": [{"fingerprint": fingerprint}],
            })

    monkeypatch.setattr("fettle.mutation_test._revision", lambda _root: FROZEN_CANDIDATE)

    result = aggregate_preflight_shards(str(tmp_path), reports, ["src/"], [], 256)

    assert result["status"] == "completed"
    assert result["generated"] == result["canonicalized"] == 256
    assert result["collisions"] == 0


def test_explicit_representation_inventory_excludes_quarantine_and_detects_tampering(tmp_path):
    reports = tmp_path / "reports"
    valid = reports / "valid" / "mutation-report.json"
    empty = reports / "historical" / "mutation-report.json"
    valid.parent.mkdir(parents=True)
    empty.parent.mkdir(parents=True)
    valid.write_text(json.dumps({"status": "completed", "shard_index": 0}) + "\n")
    empty.write_bytes(b"")
    candidates, quarantine = load_mutation_report_candidates(reports)
    inventory = build_calibration_representation_inventory(reports, candidates, [0], quarantine)
    inventory_path = reports / "inventory.json"
    inventory_path.write_text(json.dumps(inventory))

    selected = read_calibration_representation_inventory(inventory_path)

    assert selected == [{"status": "completed", "shard_index": 0}]
    assert inventory["representations"][0]["path"] == "valid/mutation-report.json"
    assert inventory["quarantined"][0]["path"] == empty.as_posix()
    valid.write_text(json.dumps({"status": "completed", "shard_index": 1}))
    with pytest.raises(ValueError, match="digest differs"):
        read_calibration_representation_inventory(inventory_path)
