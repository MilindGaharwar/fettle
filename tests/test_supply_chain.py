"""Tests for WP-147: pinned tools + installed-file hash verification."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata

from fettle.supply_chain import PINNED_TOOLS, verify_record, verify_tool_hashes


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _make_dist(tmp_path, name="fakepkg", version="1.0.0", files=None):
    """Build a real on-disk installed distribution and return Distribution.at()."""
    files = files if files is not None else {"fakepkg/__init__.py": b"x = 1\n"}
    site = tmp_path / "site"
    dist_info = site / f"{name}-{version}.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )
    record_lines = []
    for rel, data in files.items():
        target = site / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        record_lines.append(f"{rel},{_record_hash(data)},{len(data)}")
    record_lines.append(f"{name}-{version}.dist-info/RECORD,,")
    (dist_info / "RECORD").write_text("\n".join(record_lines) + "\n")
    return importlib.metadata.Distribution.at(dist_info), site


class TestPinnedTools:
    def test_canonical_home_reexported_by_init_cmd(self):
        from fettle import init_cmd

        assert init_cmd.PINNED_TOOLS is PINNED_TOOLS

    def test_pins_present(self):
        assert set(PINNED_TOOLS) == {"ruff", "semgrep", "pre-commit"}


class TestVerifyRecord:
    def test_clean_install_verifies(self, tmp_path):
        dist, _ = _make_dist(tmp_path)
        result = verify_record(dist)
        assert result == {"verified": 1, "tampered": [], "missing": []}

    def test_tampered_file_detected(self, tmp_path):
        dist, site = _make_dist(tmp_path)
        (site / "fakepkg/__init__.py").write_bytes(b"x = 666  # tampered\n")
        result = verify_record(dist)
        assert result["tampered"] == ["fakepkg/__init__.py"]
        assert result["verified"] == 0

    def test_missing_file_detected(self, tmp_path):
        dist, site = _make_dist(tmp_path)
        (site / "fakepkg/__init__.py").unlink()
        result = verify_record(dist)
        assert result["missing"] == ["fakepkg/__init__.py"]

    def test_no_record_returns_none(self, tmp_path):
        dist, site = _make_dist(tmp_path)
        (site / "fakepkg-1.0.0.dist-info/RECORD").unlink()
        assert verify_record(dist) is None


class TestVerifyToolHashes:
    def _patch_lookup(self, monkeypatch, dists: dict):
        def fake_distribution(name):
            if name in dists:
                return dists[name]
            raise importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(
            "fettle.supply_chain.importlib.metadata.distribution", fake_distribution
        )

    def test_clean_tool_passes(self, tmp_path, monkeypatch):
        dist, _ = _make_dist(tmp_path, name="ruff", version="0.15.20")
        self._patch_lookup(monkeypatch, {"ruff": dist})
        checks = verify_tool_hashes({"ruff": "0.15.20"})
        assert checks == [{
            "name": "supply:ruff", "required": False, "ok": True,
            "detail": "0.15.20 — 1 files verified against RECORD",
        }]

    def test_version_drift_warns(self, tmp_path, monkeypatch):
        dist, _ = _make_dist(tmp_path, name="ruff", version="0.15.19")
        self._patch_lookup(monkeypatch, {"ruff": dist})
        [check] = verify_tool_hashes({"ruff": "0.15.20"})
        assert check["ok"] is False
        assert check["required"] is False
        assert "drift" in check["detail"]

    def test_tampering_is_required_failure(self, tmp_path, monkeypatch):
        dist, site = _make_dist(tmp_path, name="ruff", version="0.15.20")
        (site / "fakepkg/__init__.py").write_bytes(b"evil\n")
        self._patch_lookup(monkeypatch, {"ruff": dist})
        [check] = verify_tool_hashes({"ruff": "0.15.20"})
        assert check["ok"] is False
        assert check["required"] is True
        assert "INTEGRITY FAILURE" in check["detail"]
        assert "1 tampered" in check["detail"]

    def test_not_installed_is_skipped_not_silent(self, monkeypatch):
        self._patch_lookup(monkeypatch, {})
        [check] = verify_tool_hashes({"ruff": "0.15.20"})
        assert check["ok"] is True
        assert "skipped" in check["detail"]

    def test_no_record_warns(self, tmp_path, monkeypatch):
        dist, site = _make_dist(tmp_path, name="ruff", version="0.15.20")
        (site / "ruff-0.15.20.dist-info/RECORD").unlink()
        self._patch_lookup(monkeypatch, {"ruff": dist})
        [check] = verify_tool_hashes({"ruff": "0.15.20"})
        assert check["ok"] is False
        assert check["required"] is False
        assert "no RECORD" in check["detail"]


class TestDoctorWiring:
    def test_cmd_doctor_forwards_flag(self, monkeypatch):
        from fettle import cli

        captured: dict = {}
        monkeypatch.setattr(
            "subprocess.run", lambda cmd, **kw: captured.update(cmd=cmd)
        )
        cli.cmd_doctor(argparse.Namespace(verify_hashes=True))
        assert captured["cmd"][-1] == "--verify-hashes"

    def test_cmd_doctor_default_no_flag(self, monkeypatch):
        from fettle import cli

        captured: dict = {}
        monkeypatch.setattr(
            "subprocess.run", lambda cmd, **kw: captured.update(cmd=cmd)
        )
        cli.cmd_doctor(argparse.Namespace())
        assert "--verify-hashes" not in captured["cmd"]

    def test_doctor_main_includes_supply_checks(self, monkeypatch, capsys):
        from fettle import doctor

        monkeypatch.setattr("sys.argv", ["doctor.py", "--verify-hashes", "--json"])
        monkeypatch.setattr(
            "fettle.supply_chain.verify_tool_hashes",
            lambda: [{"name": "supply:ruff", "required": False, "ok": True,
                      "detail": "0.15.20 — 42 files verified against RECORD"}],
        )
        doctor.main()
        import json

        out = json.loads(capsys.readouterr().out)
        names = [c["name"] for c in out["checks"]]
        assert "supply:ruff" in names
