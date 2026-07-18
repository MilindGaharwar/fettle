"""Tests for WP-120 — Suppressions with expiry and owner."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from suppressions_v3 import (
    Suppression,
    load_suppressions,
    save_suppressions,
    add_suppression,
    remove_suppression,
    parse_inline_suppression,
    is_suppressed,
    get_expired,
    get_ownerless,
    get_expiring_soon,
    suppressions_report,
)


@pytest.fixture
def project(tmp_path):
    """Create a project directory with .fettle/."""
    (tmp_path / ".fettle").mkdir()
    return tmp_path


class TestLoadSave:
    def test_load_empty(self, project):
        result = load_suppressions(project)
        assert result == []

    def test_load_missing_file(self, tmp_path):
        result = load_suppressions(tmp_path)
        assert result == []

    def test_round_trip(self, project):
        entries = [
            Suppression(rule="BLE001", path="legacy/", reason="legacy code", owner="@alice", until="2026-12-01"),
            Suppression(rule="S608", reason="parameterized elsewhere", owner="@bob"),
        ]
        save_suppressions(project, entries)
        loaded = load_suppressions(project)
        assert len(loaded) == 2
        assert loaded[0].rule == "BLE001"
        assert loaded[0].owner == "@alice"
        assert loaded[0].until == "2026-12-01"
        assert loaded[1].rule == "S608"
        assert loaded[1].owner == "@bob"
        assert loaded[1].until == ""

    def test_corrupt_file(self, project):
        path = project / ".fettle" / "suppressions.json"
        path.write_text("not json at all")
        result = load_suppressions(project)
        assert result == []

    def test_invalid_schema(self, project):
        path = project / ".fettle" / "suppressions.json"
        path.write_text(json.dumps({"wrong": "structure"}))
        result = load_suppressions(project)
        assert result == []


class TestAddRemove:
    def test_add(self, project):
        entry = add_suppression(project, rule="S110", reason="intentional", owner="@me", until="2027-01-01")
        assert entry.rule == "S110"
        assert entry.created_at != ""
        loaded = load_suppressions(project)
        assert len(loaded) == 1

    def test_add_multiple(self, project):
        add_suppression(project, rule="A", reason="r1")
        add_suppression(project, rule="B", reason="r2")
        loaded = load_suppressions(project)
        assert len(loaded) == 2

    def test_remove_valid(self, project):
        add_suppression(project, rule="A", reason="r1")
        add_suppression(project, rule="B", reason="r2")
        removed = remove_suppression(project, 0)
        assert removed is not None
        assert removed.rule == "A"
        loaded = load_suppressions(project)
        assert len(loaded) == 1
        assert loaded[0].rule == "B"

    def test_remove_invalid_index(self, project):
        add_suppression(project, rule="A", reason="r1")
        removed = remove_suppression(project, 5)
        assert removed is None

    def test_remove_negative_index(self, project):
        add_suppression(project, rule="A", reason="r1")
        removed = remove_suppression(project, -1)
        assert removed is None


class TestInlineParsing:
    def test_full_format(self):
        line = "x = 1  # fettle:ignore[BLE001] reason=legacy owner=@alice until=2026-12-01"
        s = parse_inline_suppression(line)
        assert s is not None
        assert s.rule == "BLE001"
        assert s.reason == "legacy"
        assert s.owner == "@alice"
        assert s.until == "2026-12-01"

    def test_rule_only(self):
        line = "x = 1  # fettle:ignore[S608]"
        s = parse_inline_suppression(line)
        assert s is not None
        assert s.rule == "S608"
        assert s.reason == ""
        assert s.owner == ""
        assert s.until == ""

    def test_no_match(self):
        line = "x = 1  # normal comment"
        assert parse_inline_suppression(line) is None

    def test_reason_with_spaces(self):
        line = "x = 1  # fettle:ignore[BLE001] reason=legacy code here owner=@bob"
        s = parse_inline_suppression(line)
        assert s is not None
        assert s.rule == "BLE001"
        assert s.owner == "@bob"


class TestExpiry:
    def test_not_expired(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        s = Suppression(rule="X", until=future)
        assert not s.is_expired

    def test_expired(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        s = Suppression(rule="X", until=past)
        assert s.is_expired

    def test_no_expiry_never_expires(self):
        s = Suppression(rule="X", until="")
        assert not s.is_expired

    def test_days_until_expiry(self):
        future = (date.today() + timedelta(days=7)).isoformat()
        s = Suppression(rule="X", until=future)
        assert s.days_until_expiry == 7

    def test_days_until_expiry_none(self):
        s = Suppression(rule="X", until="")
        assert s.days_until_expiry is None


class TestIsSuppressed:
    def test_active_suppression_matches(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        supps = [Suppression(rule="BLE001", path="legacy/", until=future)]
        assert is_suppressed("BLE001", "legacy/old.py", supps)

    def test_expired_suppression_ignored(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        supps = [Suppression(rule="BLE001", path="legacy/", until=past)]
        assert not is_suppressed("BLE001", "legacy/old.py", supps)

    def test_wrong_rule(self):
        supps = [Suppression(rule="BLE001")]
        assert not is_suppressed("S608", "any.py", supps)

    def test_path_mismatch(self):
        supps = [Suppression(rule="BLE001", path="legacy/")]
        assert not is_suppressed("BLE001", "src/main.py", supps)

    def test_empty_path_matches_all(self):
        supps = [Suppression(rule="BLE001", path="")]
        assert is_suppressed("BLE001", "anything/here.py", supps)


class TestGetExpiredOwnerless:
    def test_get_expired(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        future = (date.today() + timedelta(days=30)).isoformat()
        supps = [
            Suppression(rule="A", until=past),
            Suppression(rule="B", until=future),
            Suppression(rule="C", until=""),
        ]
        expired = get_expired(supps)
        assert len(expired) == 1
        assert expired[0].rule == "A"

    def test_get_ownerless(self):
        supps = [
            Suppression(rule="A", owner="@alice"),
            Suppression(rule="B", owner=""),
            Suppression(rule="C", owner="  "),
        ]
        ownerless = get_ownerless(supps)
        assert len(ownerless) == 2

    def test_get_expiring_soon(self):
        soon = (date.today() + timedelta(days=5)).isoformat()
        far = (date.today() + timedelta(days=30)).isoformat()
        supps = [
            Suppression(rule="A", until=soon),
            Suppression(rule="B", until=far),
            Suppression(rule="C", until=""),
        ]
        expiring = get_expiring_soon(supps, days=14)
        assert len(expiring) == 1
        assert expiring[0].rule == "A"


class TestReport:
    def test_empty_report(self, project):
        report = suppressions_report(project)
        assert report["total"] == 0
        assert report["active"] == 0
        assert report["expired"] == 0

    def test_full_report(self, project):
        past = (date.today() - timedelta(days=1)).isoformat()
        future = (date.today() + timedelta(days=30)).isoformat()
        soon = (date.today() + timedelta(days=5)).isoformat()
        entries = [
            Suppression(rule="A", until=past, reason="old", owner="@alice"),
            Suppression(rule="B", until=future, reason="good", owner="@bob"),
            Suppression(rule="C", until=soon, reason="soon", owner=""),
        ]
        save_suppressions(project, entries)
        report = suppressions_report(project)
        assert report["total"] == 3
        assert report["active"] == 2
        assert report["expired"] == 1
        assert report["ownerless"] == 1
        assert report["expiring_soon"] == 1
