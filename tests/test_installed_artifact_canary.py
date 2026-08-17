import hashlib
import json
import sys
from pathlib import Path

import pytest

from fettle import installed_artifact_canary as canary


def _wheel(tmp_path: Path) -> Path:
    wheel = tmp_path / "finefettle-1.11.1-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    return wheel


def _init_result(work_root: Path) -> dict:
    return {
        "dry_run_bridge_written": False,
        "bridge_manifest": work_root / "manifest.json",
        "registrations": {host: "pass" for host in canary.HOSTS},
    }


def test_canary_emits_schema_valid_report(tmp_path, monkeypatch):
    wheel = _wheel(tmp_path)
    work_root = tmp_path / "outside" / "canary"
    output = tmp_path / "candidate.json"
    monkeypatch.setattr(canary, "_module_root", lambda: tmp_path / "installed" / "site-packages")
    manifest = work_root / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("manifest")
    monkeypatch.setattr(canary, "_run_init", lambda *_args, **_kwargs: _init_result(work_root))
    monkeypatch.setattr(canary, "_doctor_bridge_passes", lambda *_args: True)
    monkeypatch.setattr(canary, "_probe_transports", lambda *_args: {
        host: "pass" for host in canary.HOSTS
    })

    report = canary.run_canary(
        stage="candidate",
        wheel=wheel,
        output=output,
        work_root=work_root,
        checkout_root=tmp_path / "checkout",
        pipx_version="1.7.1",
    )

    assert not output.exists()
    assert report["package"]["wheel"]["sha256"] == hashlib.sha256(b"wheel bytes").hexdigest()
    assert report["environment"]["checkout_independent"] is True
    assert all(host["registration"] == "pass" for host in report["hosts"].values())
    assert report["hosts"]["claude-code"]["live_evidence"]["state"] == "pass"
    assert report["hosts"]["opencode"]["live_evidence"]["state"] == "pass"


def test_canary_rejects_work_root_or_module_inside_checkout(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    wheel = _wheel(tmp_path)
    monkeypatch.setattr(canary, "_module_root", lambda: checkout / "fettle")

    with pytest.raises(ValueError, match="source checkout"):
        canary.run_canary(
            stage="candidate", wheel=wheel, output=tmp_path / "out.json",
            work_root=tmp_path / "outside", checkout_root=checkout, pipx_version="1.7.1",
        )

    monkeypatch.setattr(canary, "_module_root", lambda: tmp_path / "installed")
    with pytest.raises(ValueError, match="work root"):
        canary.run_canary(
            stage="candidate", wheel=wheel, output=tmp_path / "out.json",
            work_root=checkout / "work", checkout_root=checkout, pipx_version="1.7.1",
        )


def test_canary_dry_run_must_not_write_bridge(tmp_path, monkeypatch):
    wheel = _wheel(tmp_path)
    work_root = tmp_path / "outside"
    monkeypatch.setattr(canary, "_module_root", lambda: tmp_path / "installed")

    def bad_init(*_args, **_kwargs):
        result = _init_result(work_root)
        result["dry_run_bridge_written"] = True
        return result

    monkeypatch.setattr(canary, "_run_init", bad_init)

    with pytest.raises(ValueError, match="dry-run wrote"):
        canary.run_canary(
            stage="candidate", wheel=wheel, output=tmp_path / "out.json",
            work_root=work_root, checkout_root=tmp_path / "checkout", pipx_version="1.7.1",
        )


def test_canary_fails_when_any_host_transport_does_not_pass(tmp_path, monkeypatch):
    wheel = _wheel(tmp_path)
    work_root = tmp_path / "outside"
    monkeypatch.setattr(canary, "_module_root", lambda: tmp_path / "installed")
    manifest = work_root / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("manifest")
    monkeypatch.setattr(canary, "_run_init", lambda *_args, **_kwargs: _init_result(work_root))
    monkeypatch.setattr(canary, "_doctor_bridge_passes", lambda *_args: True)
    monkeypatch.setattr(canary, "_probe_transports", lambda *_args: {
        **{host: "pass" for host in canary.HOSTS}, "gemini-cli": "blocked",
    })

    with pytest.raises(ValueError, match="gemini-cli transport did not pass"):
        canary.run_canary(
            stage="candidate", wheel=wheel, output=tmp_path / "out.json",
            work_root=work_root, checkout_root=tmp_path / "checkout", pipx_version="1.7.1",
        )


def test_cli_writes_report_atomically(tmp_path, monkeypatch):
    wheel = _wheel(tmp_path)
    output = tmp_path / "report.json"
    expected = {"schema_version": "1"}
    monkeypatch.setattr(canary, "run_canary", lambda **_kwargs: expected)

    code = canary.main([
        "--stage", "public", "--wheel", str(wheel), "--output", str(output),
        "--work-root", str(tmp_path / "work"), "--checkout-root", str(tmp_path / "checkout"),
        "--pipx-version", "1.7.1",
    ])

    assert code == 0
    assert json.loads(output.read_text()) == expected
    assert not output.with_suffix(".json.tmp").exists()


def test_live_evidence_authority_is_strict_and_complete():
    evidence = canary.load_live_evidence()

    assert set(evidence) == set(canary.HOSTS)
    assert evidence["codex-cli"]["state"] == "pass"
    assert evidence["gemini-cli"]["observed_at"] is None
    assert all("host_version" in item and "reference" in item for item in evidence.values())


def test_module_interpreter_is_current_python():
    assert canary._python() == Path(sys.executable).resolve()


def test_init_uses_platform_bridge_root(tmp_path, monkeypatch):
    home = tmp_path / "home"
    work_root = tmp_path / "work"
    bridge_root = tmp_path / "platform-data" / "fettle" / "bridge"
    manifest = bridge_root / "1.11.1" / "manifest.json"
    env = canary._environment(home)
    calls = 0

    def run_json(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            manifest.parent.mkdir(parents=True)
            manifest.write_text("manifest")
        return [
            {"name": name, "status": "created"}
            for name in canary._STEP_NAMES.values()
        ]

    monkeypatch.setattr(canary, "_bridge_root", lambda *_args: bridge_root)
    monkeypatch.setattr(canary, "_run_json", run_json)
    monkeypatch.setattr(canary.subprocess, "run", lambda *_args, **_kwargs: None)

    result = canary._run_init(work_root, env)

    assert result["dry_run_bridge_written"] is False
    assert result["bridge_manifest"] == manifest
