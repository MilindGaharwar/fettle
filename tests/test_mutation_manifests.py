"""Partition manifest contracts owned by mutation evidence."""

import json
from unittest.mock import patch

from fettle.mutation_test import _canonical_digest, build_d4_corpus_identity


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


def test_d4_corpus_identity_seals_source_tests_runtime_policy_and_workflows(tmp_path):
    (tmp_path / "fettle").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / "fettle/a.py").write_text("VALUE = 1\n")
    (tmp_path / "tests/test_a.py").write_text("import fettle.a\n")
    (tmp_path / "requirements-mutation.txt").write_text("mutmut==2.5.1\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    (tmp_path / ".github/workflows/mutation-d4.yml").write_text("name: D4\n")
    (tmp_path / ".github/workflows/mutation-d4-shard.yml").write_text("name: D4 shard\n")
    manifests = []
    for index in range(256):
        manifest = {
            "schema_version": "1", "revision": "a" * 40,
            "shard_index": index, "shard_count": 256, "files": ["fettle/a.py"],
            "ranges": [{"file": "fettle/a.py", "start": 1, "end": 1}],
        }
        manifest["digest"] = _canonical_digest(manifest)
        manifests.append(manifest)
    corpus = [{"fingerprint": f"{index:064x}", "shard_index": index} for index in range(256)]
    preflight = {
        "status": "completed", "passed": True, "revision": "a" * 40,
        "shard_count": 256, "generated": 256, "canonicalized": 256, "collisions": 0,
        "fingerprints": [item["fingerprint"] for item in corpus], "corpus": corpus,
        "corpus_digest": _canonical_digest(corpus),
        "manifest_digests": [manifest["digest"] for manifest in manifests],
    }
    cfg = {
        "mode": "advisory", "paths": ["fettle/"], "exclude": [], "full_shards": 256,
        "test_mappings": {"fettle/a.py": ["tests/test_a.py"]}, "score_target": 70,
    }

    with (
        patch("fettle.mutation_test._revision", return_value="a" * 40),
        patch("fettle.mutation_test._run", return_value=type("Result", (), {
            "returncode": 0, "stdout": "b" * 40 + "\n",
        })()),
    ):
        identity = build_d4_corpus_identity(str(tmp_path), cfg, manifests, preflight)

    assert identity["manifest_count"] == 256
    assert identity["mutation_paths"] == ["fettle/a.py"]
    assert identity["mapped_test_paths"] == ["tests/test_a.py"]
    assert set(identity["workflow_digests"]) == {"mutation-d4.yml", "mutation-d4-shard.yml"}
    assert identity["engine_budget_seconds"] == 20_100
    assert identity["digest"] == _canonical_digest({key: value for key, value in identity.items() if key != "digest"})


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
