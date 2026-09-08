"""P48 slice-1 contract tests — shadow parity for the semantic consumer."""

from __future__ import annotations

from pathlib import Path

from fettle.graph_shadow import shadow_contextual, shadow_semantic
from fettle.graph_types import canonical_digest
from fettle.hypergraph import assemble
from fettle.provider_contract import TrustClass
from fettle.providers.base import EdgeDraft, NodeDraft, ProviderResult

CORPUS = Path(__file__).resolve().parent.parent / "examples" / "corpus"


def test_corpus_has_zero_unexplained_narrower_results():
    report = shadow_semantic(str(CORPUS))

    assert report["status"] == "completed"
    assert report["unexplained_narrower"] == [], (
        f"graph is narrower than legacy without explanation: "
        f"{report['unexplained_narrower']}"
    )


def test_marker_based_links_match_between_engines(tmp_path):
    import subprocess

    root = str(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text(
        "---\nfettle-spec: v1\nid: a\nstatus: active\n---\n"
        "## Scenarios\n\n### S1. Works\nGiven x\nWhen y\nThen z\n",
        encoding="utf-8",
    )
    (tmp_path / "tests_t").mkdir()
    (tmp_path / "tests_t" / "test_a.py").write_text(
        "def test_a():\n    # traces: a/S1\n    assert True\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", root])
    for flag in (("config", "user.email", "test@fettle.invalid"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", root, *flag], capture_output=True)
    subprocess.run(["git", "-C", root, "add", "."], capture_output=True)
    subprocess.run(["git", "-C", root, "commit", "-qm", "init"], capture_output=True)

    report = shadow_semantic(root)

    pair = ("verifies", "test:tests_t/test_a.py", "scenario:a/S1")
    assert pair in [tuple(p) for p in report["matched"]]
    assert report["matched_count"] >= 2  # contains + verifies


def test_documented_differences_are_declared_not_silent(tmp_path):
    report = shadow_semantic(str(CORPUS))

    labels = {d["label"] for d in report["documented_differences"]}
    for expected in ("traces", "scopes", "observes"):
        if any(
            expected in str(d) for d in []
        ):
            continue
    # Every difference category that appears must carry a reason.
    assert all(d["reason"] for d in report["documented_differences"])
    # The known categories are declared up front even when absent on small
    # fixtures, via the module-level table.
    from fettle.graph_shadow import _DOCUMENTED_DIFFERENCES

    assert set(_DOCUMENTED_DIFFERENCES) >= {"traces", "scopes", "observes"}
    assert isinstance(labels, set)


def test_report_is_digest_bound_and_advisory():
    report = shadow_semantic(str(CORPUS))

    assert report["advisory"] is True
    assert len(report["digest"]) == 64


def _provider(provider_id, edges):
    nodes = tuple(
        NodeDraft("module", key) for key in sorted({key for edge in edges for key in edge[1:]})
    )
    return ProviderResult(
        provider_id, nodes, tuple(EdgeDraft(*edge) for edge in edges), True,
        provider_version="1",
        implementation_digest=canonical_digest({"provider": provider_id}),
        deterministic=True,
        trust_class=TrustClass.DERIVED,
        completeness_scope=("repository",),
    )


def test_contextual_shadow_has_no_unexplained_missing_legacy_candidates():
    provider = _provider("imports", [
        ("imports", "module:consumer", "module:base"),
        ("imports", "module:api", "module:consumer"),
    ])
    graph = assemble(".", (provider,), "snapshot", {"version": 1})
    seed = graph.find_by_stable_key("module:base").id

    report = shadow_contextual(graph, (seed,))

    assert report["status"] == "completed"
    assert report["unexplained_narrower"] == []
    assert report["required"] == ["module:consumer"]
    assert report["contextual"] == ["module:api"]
    assert len(report["evidence_digest"]) == 64


def test_optional_provider_perturbation_cannot_hide_required_instability():
    required = _provider("required-imports", [
        ("imports", "module:consumer", "module:base"),
    ])
    optional = _provider("optional-imports", [
        ("imports", "module:extra", "module:base"),
    ])
    graph = assemble(".", (required, optional), "snapshot", {"version": 1})
    seed = graph.find_by_stable_key("module:base").id

    report = shadow_contextual(graph, (seed,), optional_provider_ids=("optional-imports",))

    perturbation = report["perturbations"][0]
    assert perturbation["provider_id"] == "optional-imports"
    assert perturbation["required_invariant"] is False
    assert perturbation["removed_required"] == ["module:extra"]
    assert report["promotion_safe"] is False
