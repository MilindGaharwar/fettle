"""P64 consolidated methodology guarantees (workflow-level, items 21/22/26).

These pin the mutation workflow's staged-readiness properties so a future
edit cannot silently drop preflight gating, tool pinning, or identity
binding.
"""

from __future__ import annotations

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "mutation.yml"
)
MUTATION_REQUIREMENTS = (
    Path(__file__).resolve().parent.parent / "requirements-mutation.txt"
)


def test_item21_full_fanout_requires_retained_preflight():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "retained-preflight/mutation-preflight.json" in text
    assert text.index("preflight-aggregate") < text.index("full-shard:")


def test_item22_mutation_tools_are_hash_pinned():
    text = MUTATION_REQUIREMENTS.read_text(encoding="utf-8")

    assert "--hash=sha256:" in text
    assert "mutmut==2.5.1" in text


def test_item26_workers_bind_manifest_and_preflight_identity():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "--resume-manifest mutation-manifests/partition-" in text
    assert "--retained-preflight retained-preflight/mutation-preflight.json" in text
    # Identity chain: manifest revision/digests are validated by the worker
    # (load_partition_manifest + retained preflight assertions in prepare).
    assert 'aggregate["revision"]==os.environ["GITHUB_SHA"]' in text


def test_replay_preparation_is_wired_before_aggregate():
    text = WORKFLOW.read_text(encoding="utf-8")

    prepare = text.index("--prepare-replay-matrix")
    aggregate = text.index("--aggregate mutation-changed-shards")
    assert prepare < aggregate
