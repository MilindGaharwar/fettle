"""WP-144 — Central policy distribution tests.

Key invariants:
- The hook path NEVER touches the network (cache-only resolution).
- Digest pins are mandatory and verified on fetch AND on every cache read.
- Merge order: defaults -> org policy -> repo config (repo wins).
- Offline/unsynced policy degrades to local config, never crashes.
"""

import hashlib
import io
import os
import subprocess
import sys

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PLUGIN_DIR)

from fettle import policy_remote  # noqa: E402
from fettle.policy_remote import (  # noqa: E402
    PolicyError, fetch_and_cache, load_cached, parse_extends,
)

ORG_POLICY = b'[gates.lint]\nmode = "enforce"\n\n[gates.plan]\nenabled = true\nthreshold = 2\n'
ORG_SHA = hashlib.sha256(ORG_POLICY).hexdigest()


@pytest.fixture
def cache(tmp_path, monkeypatch):
    cache_dir = tmp_path / "policy-cache"
    monkeypatch.setenv("FETTLE_POLICY_CACHE_DIR", str(cache_dir))
    return cache_dir


def _seed_cache(cache_dir, blob=ORG_POLICY):
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{hashlib.sha256(blob).hexdigest()}.toml").write_bytes(blob)


def _extends(sha=ORG_SHA):
    return {"url": "https://example.com/org.toml", "sha256": sha}


class TestParseExtends:
    def test_absent_is_none(self) -> None:
        assert parse_extends({}) is None
        assert parse_extends({"gates": {}}) is None

    def test_valid(self) -> None:
        parsed = parse_extends({"extends": {"url": "https://x.example/p.toml", "sha256": ORG_SHA}})
        assert parsed == {"url": "https://x.example/p.toml", "sha256": ORG_SHA}

    @pytest.mark.parametrize("extends", [
        "https://x.example/p.toml",                                  # not a table
        {"sha256": ORG_SHA},                                          # missing url
        {"url": "http://x.example/p.toml", "sha256": ORG_SHA},        # not https
        {"url": "file:///etc/passwd", "sha256": ORG_SHA},             # not https
        {"url": "https://x.example/p.toml"},                          # missing pin
        {"url": "https://x.example/p.toml", "sha256": "deadbeef"},    # short pin
    ])
    def test_malformed_raises(self, extends) -> None:
        with pytest.raises(PolicyError):
            parse_extends({"extends": extends})


class TestCache:
    def test_miss_returns_none(self, cache) -> None:
        assert load_cached(_extends()) is None

    def test_hit_returns_policy(self, cache) -> None:
        _seed_cache(cache)
        policy = load_cached(_extends())
        assert policy["gates"]["lint"]["mode"] == "enforce"

    def test_tampered_cache_discarded(self, cache) -> None:
        cache.mkdir(parents=True)
        path = cache / f"{ORG_SHA}.toml"
        path.write_bytes(b'[gates.lint]\nmode = "off"  # tampered\n')
        assert load_cached(_extends()) is None
        assert not path.exists(), "tampered cache file must be deleted"


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestFetch:
    def test_fetch_verifies_and_caches(self, cache, monkeypatch) -> None:
        monkeypatch.setattr(policy_remote.urllib.request, "urlopen",
                            lambda req, timeout: _FakeResponse(ORG_POLICY))
        policy = fetch_and_cache(_extends())
        assert policy["gates"]["plan"]["threshold"] == 2
        assert (cache / f"{ORG_SHA}.toml").read_bytes() == ORG_POLICY

    def test_digest_mismatch_rejected_and_not_cached(self, cache, monkeypatch) -> None:
        monkeypatch.setattr(policy_remote.urllib.request, "urlopen",
                            lambda req, timeout: _FakeResponse(b"[gates]\n"))
        with pytest.raises(PolicyError, match="digest mismatch"):
            fetch_and_cache(_extends())
        assert not (cache / f"{ORG_SHA}.toml").exists()

    def test_oversize_rejected(self, cache, monkeypatch) -> None:
        big = b"#" + b"x" * policy_remote.MAX_POLICY_BYTES
        monkeypatch.setattr(policy_remote.urllib.request, "urlopen",
                            lambda req, timeout: _FakeResponse(big))
        with pytest.raises(PolicyError, match="exceeds"):
            fetch_and_cache({"url": "https://x.example/p.toml",
                             "sha256": hashlib.sha256(big).hexdigest()})

    def test_network_failure_is_policy_error(self, cache, monkeypatch) -> None:
        def _boom(req, timeout):
            raise OSError("connection refused")
        monkeypatch.setattr(policy_remote.urllib.request, "urlopen", _boom)
        with pytest.raises(PolicyError, match="could not fetch"):
            fetch_and_cache(_extends())


class TestLoadConfigIntegration:
    @pytest.fixture
    def repo(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".fettle.toml").write_text(
            f'[extends]\nurl = "https://example.com/org.toml"\nsha256 = "{ORG_SHA}"\n\n'
            '[gates.plan]\nthreshold = 9\n'
        )
        return proj

    def test_org_policy_applies_under_repo_config(self, repo, cache, monkeypatch) -> None:
        _seed_cache(cache)
        monkeypatch.setattr(policy_remote.urllib.request, "urlopen",
                            lambda *a, **k: pytest.fail("hook path must never touch the network"))
        from fettle.config import load_config
        cfg = load_config(str(repo))
        assert cfg["gates"]["lint"]["mode"] == "enforce"      # from org policy
        assert cfg["gates"]["plan"]["enabled"] is True        # from org policy
        assert cfg["gates"]["plan"]["threshold"] == 9         # repo wins over org (=2)

    def test_unsynced_policy_degrades_to_local(self, repo, cache, monkeypatch) -> None:
        monkeypatch.setattr(policy_remote.urllib.request, "urlopen",
                            lambda *a, **k: pytest.fail("hook path must never touch the network"))
        from fettle.config import load_config
        cfg = load_config(str(repo))
        assert cfg["gates"]["lint"]["mode"] == "advisory"     # default; org not applied
        assert cfg["gates"]["plan"]["threshold"] == 9         # repo config still applies


class TestCLI:
    def _run(self, cwd, *argv, env_extra=None):
        env = {**os.environ, **(env_extra or {})}
        proc = subprocess.run(
            [sys.executable, os.path.join(PLUGIN_DIR, "fettle", "cli.py"), "policy", *argv],
            capture_output=True, text=True, timeout=30, cwd=str(cwd), env=env,
        )
        return proc.returncode, proc.stdout + proc.stderr

    @pytest.fixture
    def repo(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".git").mkdir()
        (proj / ".fettle.toml").write_text(
            f'[extends]\nurl = "https://example.com/org.toml"\nsha256 = "{ORG_SHA}"\n'
        )
        return proj

    def test_status_uncached(self, repo, tmp_path) -> None:
        rc, out = self._run(repo, "status",
                            env_extra={"FETTLE_POLICY_CACHE_DIR": str(tmp_path / "pc")})
        assert rc == 1 and "not cached" in out

    def test_status_cached(self, repo, tmp_path) -> None:
        cache_dir = tmp_path / "pc"
        _seed_cache(cache_dir)
        rc, out = self._run(repo, "status",
                            env_extra={"FETTLE_POLICY_CACHE_DIR": str(cache_dir)})
        assert rc == 0 and "digest verified" in out

    def test_no_extends_is_clean_exit(self, tmp_path) -> None:
        proj = tmp_path / "plain"
        proj.mkdir()
        (proj / ".git").mkdir()
        rc, out = self._run(proj, "status")
        assert rc == 0 and "local policy only" in out


class TestSchemaKnowsExtends:
    def test_extends_validates(self) -> None:
        from fettle.config_schema import validate_config
        errors, warnings = validate_config(
            {"extends": {"url": "https://x.example/p.toml", "sha256": ORG_SHA}}
        )
        assert errors == [] and warnings == []
