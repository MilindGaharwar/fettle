"""Tests for fettle.cache — result caching for unchanged files."""

from fettle.cache import (
    _config_hash,
    _file_hash,
    cache_key,
    cache_stats,
    get_cached,
    invalidate_all,
    set_cached,
)


class TestFileHash:
    def test_hashes_content(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("hello")
        h = _file_hash(str(f))
        assert len(h) == 16
        assert h == _file_hash(str(f))  # deterministic

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("hello")
        b.write_text("world")
        assert _file_hash(str(a)) != _file_hash(str(b))

    def test_missing_file_returns_empty(self):
        assert _file_hash("/nonexistent/x.py") == ""


class TestConfigHash:
    def test_same_config_same_hash(self):
        cfg = {"severity": {"error_rules": ["A"]}, "gates": {"lint": {"enabled": True}}}
        assert _config_hash(cfg) == _config_hash(cfg)

    def test_different_config_different_hash(self):
        c1 = {"severity": {"error_rules": ["A"]}, "gates": {"lint": {"enabled": True}}}
        c2 = {"severity": {"error_rules": ["B"]}, "gates": {"lint": {"enabled": True}}}
        assert _config_hash(c1) != _config_hash(c2)


class TestCacheOperations:
    def test_get_miss_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        assert get_cached("nonexistent_key") is None

    def test_set_then_get(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        data = {"findings": [{"code": "E001"}]}
        set_cached("mykey", data)
        result = get_cached("mykey")
        assert result == data

    def test_invalidate_all_clears(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        set_cached("k1", {"x": 1})
        set_cached("k2", {"x": 2})
        invalidate_all()
        assert get_cached("k1") is None
        assert get_cached("k2") is None

    def test_cache_stats(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        set_cached("s1", {"data": "x" * 100})
        stats = cache_stats()
        assert stats["entries"] == 1
        assert stats["size_kb"] >= 0


class TestCacheKey:
    def test_combines_file_and_config(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1")
        cfg = {"severity": {}, "gates": {"lint": {}}}
        key = cache_key(str(f), cfg)
        assert "_" in key
        assert len(key) > 10
