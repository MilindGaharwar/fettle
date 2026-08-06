import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fettle.graph_types import (
    FreshnessAssessment,
    FreshnessState,
    GraphGeneration,
    Hyperedge,
    Incidence,
    Node,
    SourceEntry,
    SourceIdentity,
    SourceObjectType,
    SourcePathClass,
    SourceRepositoryState,
    SourceSnapshotClass,
    SubmoduleHandling,
    canonical_json,
    normalize_path,
)


def test_canonical_json_is_order_independent_and_normalizes_unicode():
    first = {"z": 1, "name": "Cafe\u0301"}
    second = {"name": "Caf\u00e9", "z": 1}
    assert canonical_json(first) == canonical_json(second)


def test_canonical_json_rejects_keys_that_collide_after_unicode_normalization():
    with pytest.raises(ValueError, match="normalize to the same value"):
        canonical_json({"Caf\u00e9": 1, "Cafe\u0301": 2})


def test_node_identity_ignores_checkout_path_and_insertion_order():
    first = Node.create("file", "src/App.py", {"language": "python", "size": 10})
    second = Node.create("file", "src/App.py", {"size": 10, "language": "python"})
    assert first.id == second.id
    assert len(first.id) == 64


def test_paths_preserve_case_and_reject_absolute_or_escaping_paths():
    assert normalize_path(r"Src\App.py") == "Src/App.py"
    with pytest.raises(ValueError):
        normalize_path("../secret")
    with pytest.raises(ValueError):
        normalize_path("/tmp/file")


def test_unknown_or_noncanonical_attribute_values_are_rejected():
    with pytest.raises(TypeError):
        Node.create("file", "a.py", {"ratio": 0.5})
    with pytest.raises(TypeError):
        Node(**json.loads('{"id":"x","kind":"file","stable_key":"a","attributes_json":"{}","provenance":[],"extra":1}'))

    with pytest.raises(ValueError, match="canonical JSON object"):
        Node("x", "file", "a", '{"z":1, "a":2}', ())


def test_edge_and_generation_deduplicate_and_sort_inputs():
    edge = Hyperedge.create(
        "imports", (("b", "consumer", "out", 1), ("a", "source", "in", 0)), "provider",
    )
    generation = GraphGeneration.create(
        "source", "rules", ("b", "a", "a"), (edge.id,), ("i2", "i1", "i1"), ("p", "p"),
    )
    assert generation.node_ids == ("a", "b")
    assert generation.incidence_ids == ("i1", "i2")
    assert generation.provider_fact_set_ids == ("p",)
    assert len(generation.digest) == 64

    reordered = Hyperedge.create(
        "imports", (("a", "source", "in", 0), ("b", "consumer", "out", 1)), "provider",
    )
    assert edge.id == reordered.id
    assert edge.incidence_signature == reordered.incidence_signature


def test_source_identity_canonicalizes_entries_and_checkout_root():
    symlink = SourceEntry.create(
        "links/current", SourceObjectType.SYMLINK, content_digest="link-hash", size=10,
        symlink_text="../src/current",
    )
    gitlink = SourceEntry.create(
        "vendor/lib", SourceObjectType.GITLINK, content_digest="commit", size=0,
        gitlink_commit="abc123", submodule_handling=SubmoduleHandling.DECLARED_INCOMPLETE,
    )
    first = SourceIdentity.create(
        SourceSnapshotClass.WORKING, "repo-id", "/tmp/checkout-a", (gitlink, symlink),
        repository_state=SourceRepositoryState("head", "tree", "index", (), False, "disabled", "materialized"),
        policy_digest="policy", policy_provenance_digest="policy-layers",
        provider_manifest_digest="providers",
    )
    second = SourceIdentity.create(
        SourceSnapshotClass.WORKING, "repo-id", "/different/checkout", (symlink, gitlink),
        repository_state=SourceRepositoryState("head", "tree", "index", (), False, "disabled", "materialized"),
        policy_digest="policy", policy_provenance_digest="policy-layers",
        provider_manifest_digest="providers",
    )
    assert first.id == second.id
    assert first.entries == (symlink, gitlink)


def test_source_entry_variants_fail_closed():
    with pytest.raises(ValueError, match="symlink text"):
        SourceEntry.create("link", SourceObjectType.SYMLINK, "hash", 1)
    with pytest.raises(ValueError, match="gitlink commit and handling"):
        SourceEntry.create("module", SourceObjectType.GITLINK, "hash", 0)
    with pytest.raises(ValueError, match="tombstone"):
        SourceEntry.create("deleted.py", SourceObjectType.TOMBSTONE, "hash", 0)

    tombstone = SourceEntry.create("deleted.py", SourceObjectType.TOMBSTONE, "", 0, deleted=True)
    assert tombstone.deleted


def test_source_manifest_contract_records_git_policy_and_path_visibility():
    entry = SourceEntry.create(
        "generated/schema.json", SourceObjectType.FILE, "content", 42,
        path_class=SourcePathClass.IGNORED_SEMANTIC,
    )
    state = SourceRepositoryState(
        head_commit="", head_tree="", index_tree="index", index_conflict_stages=(("conflict.py", 2, "blob"),),
        detached=False, sparse_checkout_state="cone:src", lfs_state="pointers", unborn=True,
    )
    source = SourceIdentity.create(
        SourceSnapshotClass.WORKING, "repo", "/checkout", (entry,), repository_state=state,
        policy_digest="policy", policy_provenance_digest="layers", provider_manifest_digest="providers",
    )
    assert source.repository_state.index_conflict_stages == (("conflict.py", 2, "blob"),)
    assert source.entries[0].path_class == SourcePathClass.IGNORED_SEMANTIC
    assert len(source.id) == 64


def test_source_manifest_rejects_duplicate_paths_and_invalid_conflict_stages():
    first = SourceEntry.create("a.py", SourceObjectType.FILE, "one", 1)
    second = SourceEntry.create("a.py", SourceObjectType.FILE, "two", 2)
    state = SourceRepositoryState("head", "tree", "index", (), False, "disabled", "materialized")
    with pytest.raises(ValueError, match="paths must be unique"):
        SourceIdentity.create(
            SourceSnapshotClass.COMMITTED, "repo", "/checkout", (first, second), repository_state=state,
            policy_digest="policy", policy_provenance_digest="layers", provider_manifest_digest="providers",
        )
    with pytest.raises(ValueError, match="conflict stage"):
        SourceRepositoryState("head", "tree", "index", (("a.py", 4, "blob"),), False, "off", "clean")


def test_incidence_rejects_unknown_direction():
    with pytest.raises(ValueError, match="direction"):
        Incidence("edge", "node", "consumer", "sideways")


def test_freshness_never_represents_mismatched_or_unexplained_current_generation():
    current = FreshnessAssessment.create("source-a", "source-a", FreshnessState.CURRENT)
    assert current.authorizes_current_action

    with pytest.raises(ValueError, match="matching source"):
        FreshnessAssessment.create("source-a", "source-b", FreshnessState.CURRENT)
    with pytest.raises(ValueError, match="requires a reason"):
        FreshnessAssessment.create("source-a", "source-b", FreshnessState.SUPERSEDED)

    stale = FreshnessAssessment.create(
        "source-a", "source-b", FreshnessState.SUPERSEDED, "new snapshot requested",
    )
    assert not stale.authorizes_current_action


def test_canonical_digest_is_stable_across_processes_and_checkout_paths(tmp_path):
    script = (
        "from fettle.graph_types import canonical_digest; "
        "print(canonical_digest({'name':'Cafe\\u0301','items':['b','a']}))"
    )
    env = os.environ | {"PYTHONPATH": str(Path(__file__).parents[1])}
    first = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env, check=True, capture_output=True, text=True,
    ).stdout.strip()
    second_dir = tmp_path / "other"
    second_dir.mkdir()
    second = subprocess.run(
        [sys.executable, "-c", script], cwd=second_dir, env=env, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert first == second
    assert len(first) == 64
