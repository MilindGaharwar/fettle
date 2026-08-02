"""Tests for topology footprint prediction + disjointness (WP-159, B1)."""

import pytest

from fettle.topology import Footprint, find_conflicts, predict_footprint


@pytest.fixture
def repo(tmp_path):
    """Small project: util.py imported by app.py; docs + isolated module."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "util.py").write_text("X = 1\n")
    (tmp_path / "pkg" / "app.py").write_text("from pkg.util import X\n")
    (tmp_path / "pkg" / "island.py").write_text("Y = 2\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# guide\n")
    return tmp_path


class TestFootprint:
    def test_scope_glob_expansion(self, repo):
        fp = predict_footprint(str(repo), "a", ["docs/**"])
        assert fp.seeds == {"docs/guide.md"}
        assert not fp.unknown

    def test_import_hop_widens_python_seeds(self, repo):
        fp = predict_footprint(str(repo), "a", ["pkg/util.py"])
        assert "pkg/util.py" in fp.seeds
        assert "pkg/app.py" in fp.expanded  # app imports util

    def test_island_stays_narrow(self, repo):
        fp = predict_footprint(str(repo), "a", ["pkg/island.py"])
        assert fp.expanded == {"pkg/island.py"}

    def test_no_scope_is_unknown(self, repo):
        assert predict_footprint(str(repo), "a", []).unknown


class TestConflicts:
    def test_disjoint_items_no_conflict(self, repo):
        fps = [predict_footprint(str(repo), "a", ["pkg/island.py"]),
               predict_footprint(str(repo), "b", ["docs/**"])]
        assert find_conflicts(fps) == []

    def test_import_coupling_conflicts(self, repo):
        # a touches util; b touches app — app is in a's 1-hop footprint.
        fps = [predict_footprint(str(repo), "a", ["pkg/util.py"]),
               predict_footprint(str(repo), "b", ["pkg/app.py"])]
        conflicts = find_conflicts(fps)
        assert len(conflicts) == 1
        assert "pkg/app.py" in conflicts[0].overlap
        assert "import dependents" in conflicts[0].reason

    def test_unknown_scope_conflicts_with_everything(self, repo):
        fps = [Footprint(item_id="mystery", unknown=True),
               predict_footprint(str(repo), "b", ["docs/**"])]
        conflicts = find_conflicts(fps)
        assert len(conflicts) == 1
        assert "declares no scope" in conflicts[0].reason


def _work_item(repo, item_id, scope=(), spec="", status="open"):
    items = repo / "docs" / "work" / "items"
    items.mkdir(parents=True, exist_ok=True)
    scope_lines = "".join(f"  - {s}\n" for s in scope)
    (items / f"{item_id}.md").write_text(
        f"---\nfettle-work-item: true\nid: {item_id}\nstatus: {status}\n"
        + (f"scope:\n{scope_lines}" if scope else "")
        + (f"spec: {spec}\n" if spec else "")
        + f"---\n\n# {item_id}\n"
    )


class TestAdvise:
    def _advise(self, repo, monkeypatch, risky=False, note="test risk"):
        from fettle import topology
        monkeypatch.setattr(topology, "_trace_risk", lambda days=30: (risky, note))
        return topology.advise(str(repo))

    def test_no_items_solo(self, repo, monkeypatch):
        data = self._advise(repo, monkeypatch)
        assert data["topology"] == "solo"
        assert "no open work items" in data["rationale"][0]

    def test_single_low_risk_item_solo(self, repo, monkeypatch):
        _work_item(repo, "one", scope=("pkg/island.py",))
        assert self._advise(repo, monkeypatch)["topology"] == "solo"

    def test_single_risky_item_writer_reviewer(self, repo, monkeypatch):
        _work_item(repo, "one", scope=("pkg/island.py",))
        data = self._advise(repo, monkeypatch, risky=True)
        assert data["topology"] == "writer-reviewer"
        assert any("review" in c for c in data["commands"])

    def test_spec_linked_item_pipeline(self, repo, monkeypatch):
        _work_item(repo, "one", scope=("pkg/island.py",), spec="my-spec")
        data = self._advise(repo, monkeypatch)
        assert data["topology"] == "pipeline"
        assert any("uat" in c for c in data["commands"])

    def test_disjoint_items_parallel_workers(self, repo, monkeypatch):
        _work_item(repo, "a", scope=("pkg/island.py",))
        _work_item(repo, "b", scope=("docs/**",))
        data = self._advise(repo, monkeypatch)
        assert data["topology"] == "parallel-workers"
        assert len([c for c in data["commands"] if "fettle spawn" in c]) == 2

    def test_overlapping_items_refused(self, repo, monkeypatch):
        _work_item(repo, "a", scope=("pkg/util.py",))
        _work_item(repo, "b", scope=("pkg/app.py",))
        data = self._advise(repo, monkeypatch)
        assert data["topology"] == "solo"
        assert data["conflicts"]
        assert any("REFUSING" in r for r in data["rationale"])

    def test_done_items_ignored(self, repo, monkeypatch):
        _work_item(repo, "a", scope=("pkg/island.py",), status="done")
        data = self._advise(repo, monkeypatch)
        assert data["items"] == []

    def test_render(self, repo, monkeypatch):
        _work_item(repo, "a", scope=("pkg/island.py",))
        _work_item(repo, "b", scope=("docs/**",))
        from fettle.topology import render_advice
        out = render_advice(self._advise(repo, monkeypatch))
        assert "parallel-workers" in out
        assert "fettle spawn" in out
