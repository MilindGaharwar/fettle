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
