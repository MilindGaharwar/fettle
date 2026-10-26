"""Partition manifest contracts owned by mutation evidence."""

import json


def test_partition_manifest_rejects_tampering(tmp_path, monkeypatch):
    from fettle.mutation_test import load_partition_manifest, write_partition_manifests

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/a.py").write_text("x = 1\n")
    (tmp_path / "tests/test_a.py").write_text("import src.a\n")
    monkeypatch.setattr("fettle.mutation_test._revision", lambda root: "a" * 40)
    paths = write_partition_manifests(
        str(tmp_path), {"paths": ["src/"], "full_shards": 1, "default_chunk_lines": 60},
        tmp_path / "manifests",
    )
    manifest = load_partition_manifest(paths[0])
    assert manifest["ranges"] == [{"file": "src/a.py", "start": 1, "end": 1}]

    value = json.loads(paths[0].read_text())
    value["ranges"][0]["end"] = 2
    paths[0].write_text(json.dumps(value))
    try:
        load_partition_manifest(paths[0])
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("tampered manifest was accepted")


def test_partition_manifest_must_match_configured_shard_count(tmp_path, monkeypatch):
    from fettle.mutation_test import run_mutation_test, write_partition_manifests

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/a.py").write_text("x = 1\n")
    (tmp_path / "tests/test_a.py").write_text("import src.a\n")
    monkeypatch.setattr("fettle.mutation_test._revision", lambda root: "a" * 40)
    manifest = write_partition_manifests(
        str(tmp_path), {"paths": ["src/"], "full_shards": 1}, tmp_path / "manifests",
    )[0]

    result = run_mutation_test(str(tmp_path), {
        "paths": ["src/"], "all": True, "full_shards": 2, "manifest": str(manifest),
    })

    assert result["status"] == "unknown"
    assert "shard count" in result["message"]


def test_partition_manifest_files_must_match_ranges(tmp_path):
    from fettle.mutation_test import load_partition_manifest

    payload = {
        "schema_version": "1", "revision": "a" * 40, "shard_index": 0,
        "shard_count": 1, "files": ["src/a.py"],
        "ranges": [{"file": "src/b.py", "start": 1, "end": 1}],
    }
    from fettle.mutation_test import _canonical_digest
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({**payload, "digest": _canonical_digest(payload)}))

    try:
        load_partition_manifest(path)
    except ValueError as exc:
        assert "files" in str(exc)
    else:
        raise AssertionError("inconsistent manifest was accepted")
