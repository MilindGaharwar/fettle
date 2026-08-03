"""Tests for fettle.fp_stamp — false-positive stamp management."""

from fettle.fp_stamp import fp_rate, is_fp_stamped, load_fp_stamps, stamp_fp


class TestFpStamp:
    def test_stamp_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        stamp_fp("BLE001", "app.py", 42, "intentional catch-all")
        stamps = load_fp_stamps()
        assert len(stamps) == 1
        assert stamps[0]["rule"] == "BLE001"
        assert stamps[0]["file"] == "app.py"
        assert stamps[0]["line"] == 42
        assert stamps[0]["reason"] == "intentional catch-all"
        assert stamps[0]["fp"] is True

    def test_is_fp_stamped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        stamp_fp("E001", "x.py", 10, "false alarm")
        assert is_fp_stamped("E001", "x.py", 10) is True
        assert is_fp_stamped("E001", "x.py", 11) is False
        assert is_fp_stamped("E002", "x.py", 10) is False

    def test_load_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        assert load_fp_stamps() == []

    def test_fp_rate_calculation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        stamp_fp("A", "f.py", 1, "r")
        stamp_fp("B", "f.py", 2, "r")
        assert fp_rate(10) == 0.2

    def test_fp_rate_zero_findings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        assert fp_rate(0) == 0.0

    def test_multiple_stamps(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        stamp_fp("A", "a.py", 1, "reason 1")
        stamp_fp("B", "b.py", 2, "reason 2")
        stamps = load_fp_stamps()
        assert len(stamps) == 2
