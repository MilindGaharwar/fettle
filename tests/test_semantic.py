"""Tests for fettle.semantic — link fusion + query surface (Stage 6, S6.1)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fettle.semantic import (
    build_graph,
    closest_ids,
    find_orphans,
    format_links,
    format_orphans,
    links_for,
)

SPEC = """\
---
fettle-spec: v1
id: greeter
status: active
scope:
  - "src/**"
---

## Requirements

- R1. Greets the user by name.
- R2. Rejects empty names.

## Scenarios

### S1. Basic greeting (traces R1)

- Given the app is installed
- When the user runs `greet Ada`
- Then the output contains "Hello, Ada"
"""

WORK_ITEM = """\
---
fettle-work-item: v1
id: add-greeting
status: open
spec: greeter
---

Implement greeting.
"""

TEST_FILE = '''\
# traces: greeter/S1
def test_greeting():
    assert True
'''


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "greeter.md").write_text(SPEC)
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "add-greeting.md").write_text(WORK_ITEM)
    (tmp_path / "test_greeting.py").write_text(TEST_FILE)
    return tmp_path


def _cfg() -> dict:
    return {"worktrees": {"root": ".fettle/worktrees"}}


class TestBuildGraph:
    def test_nodes_and_edges_fused(self, tmp_path):
        g = build_graph(str(_repo(tmp_path)), _cfg())
        assert g.nodes["greeter"]["kind"] == "spec"
        assert g.nodes["greeter/R1"]["kind"] == "requirement"
        assert g.nodes["greeter/S1"]["kind"] == "scenario"
        assert g.nodes["test_greeting.py"]["kind"] == "test"
        assert g.nodes["add-greeting"]["kind"] == "work-item"
        labels = {(e["src"], e["label"], e["dst"]) for e in g.edges}
        assert ("greeter/S1", "traces", "greeter/R1") in labels
        assert ("test_greeting.py", "covers", "greeter/S1") in labels
        assert ("add-greeting", "implements", "greeter") in labels

    def test_uat_evidence_included(self, tmp_path):
        repo = _repo(tmp_path)
        wt = repo / ".fettle" / "worktrees" / "uat-x" / ".fettle"
        wt.mkdir(parents=True)
        (wt / "uat-report.json").write_text(json.dumps({
            "session_id": "uat-x",
            "verdicts": [{"scenario_id": "greeter/S1", "verdict": "CONFIRMED",
                          "observed": "", "note": ""}]}))
        (repo / ".fettle" / "uat-attestations.json").write_text(json.dumps([
            {"scenario_id": "greeter/S1", "outcome": "matches",
             "operator": "milind", "observed": "x", "source": "operator"}]))
        g = build_graph(str(repo), _cfg())
        kinds = [n["kind"] for n in g.nodes.values()]
        assert "verdict" in kinds and "attestation" in kinds
        observes = [e for e in g.edges if e["label"] == "observes"]
        assert all(e["dst"] == "greeter/S1" for e in observes)
        assert len(observes) == 2


class TestQueries:
    def test_links_for_scenario_shows_full_chain(self, tmp_path):
        g = build_graph(str(_repo(tmp_path)), _cfg())
        info = links_for(g, "greeter/S1")
        link_ids = {(l["label"], l["id"]) for l in info["links"]}
        assert ("traces", "greeter/R1") in link_ids
        assert ("covers", "test_greeting.py") in link_ids
        assert ("contains", "greeter") in link_ids

    def test_unknown_id_suggestions(self, tmp_path):
        g = build_graph(str(_repo(tmp_path)), _cfg())
        assert links_for(g, "greter/S1") is None
        assert "greeter/S1" in closest_ids(g, "S1")
        assert closest_ids(g, "greeter/S9")  # prefix fallback

    def test_format_links_readable(self, tmp_path):
        g = build_graph(str(_repo(tmp_path)), _cfg())
        out = format_links(links_for(g, "greeter/S1"))
        assert "greeter/S1" in out and "[scenario]" in out
        assert "covers" in out and "test_greeting.py" in out


class TestOrphans:
    def test_untraced_requirement_and_missing_spec(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "work" / "ghost.md").write_text(
            WORK_ITEM.replace("id: add-greeting", "id: ghost")
                     .replace("spec: greeter", "spec: nope"))
        orphans = find_orphans(build_graph(str(repo), _cfg()))
        by_id = {o["id"]: o for o in orphans}
        assert "greeter/R2" in by_id  # no scenario traces R2
        assert "unknown spec 'nope'" in by_id["ghost"]["problem"]
        assert "greeter/S1" not in by_id  # covered by test

    def test_scenario_saved_by_uat_evidence(self, tmp_path):
        repo = _repo(tmp_path)
        (repo / "test_greeting.py").unlink()  # no test coverage
        orphans = find_orphans(build_graph(str(repo), _cfg()))
        assert any(o["id"] == "greeter/S1" for o in orphans)
        (repo / ".fettle").mkdir()
        (repo / ".fettle" / "uat-attestations.json").write_text(json.dumps([
            {"scenario_id": "greeter/S1", "outcome": "matches",
             "operator": "m", "observed": "x", "source": "operator"}]))
        orphans = find_orphans(build_graph(str(repo), _cfg()))
        assert not any(o["id"] == "greeter/S1" for o in orphans)

    def test_format_orphans(self, tmp_path):
        orphans = find_orphans(build_graph(str(_repo(tmp_path)), _cfg()))
        out = format_orphans(orphans)
        assert "greeter/R2" in out and "fix:" in out
        assert format_orphans([]).startswith("\u2713")


class TestGraphifyEnrichment:
    def test_scopes_edges_when_graph_present(self, tmp_path):
        repo = _repo(tmp_path)
        out = repo / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text(json.dumps({"nodes": [
            {"id": "n1", "file": "src/greet.py"},
            {"id": "n2", "file": "lib/other.py"},
            {"id": "n3"}]}))
        g = build_graph(str(repo), _cfg())
        assert g.nodes["src/greet.py"] == {"kind": "code", "source": "graphify"}
        assert {"src": "greeter", "label": "scopes", "dst": "src/greet.py"} in g.edges
        assert "lib/other.py" not in g.nodes  # outside spec scope

    def test_absent_or_malformed_graph_degrades_silently(self, tmp_path):
        repo = _repo(tmp_path)
        g = build_graph(str(repo), _cfg())  # absent
        assert not any(n.get("kind") == "code" for n in g.nodes.values())
        out = repo / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{broken")
        g = build_graph(str(repo), _cfg())  # malformed
        assert not any(n.get("kind") == "code" for n in g.nodes.values())


class TestCLI:
    def test_links_id_json(self, tmp_path):
        repo = _repo(tmp_path)
        r = subprocess.run([sys.executable, "-m", "fettle.cli", "links",
                            "greeter/S1", "--json"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["kind"] == "scenario"
        assert any(l["id"] == "test_greeting.py" for l in data["links"])

    def test_links_unknown_id_exit_2_with_suggestion(self, tmp_path):
        repo = _repo(tmp_path)
        r = subprocess.run([sys.executable, "-m", "fettle.cli", "links", "greeterr"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 2
        assert "greeter" in r.stderr

    def test_links_orphans_exit_1(self, tmp_path):
        repo = _repo(tmp_path)
        r = subprocess.run([sys.executable, "-m", "fettle.cli", "links", "--orphans"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 1  # greeter/R2 untraced
        assert "greeter/R2" in r.stdout

    def test_links_no_args_exit_2(self, tmp_path):
        repo = _repo(tmp_path)
        r = subprocess.run([sys.executable, "-m", "fettle.cli", "links"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 2
        assert "--orphans" in r.stderr
