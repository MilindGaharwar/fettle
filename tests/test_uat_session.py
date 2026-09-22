"""Tests for fettle.uat.session (Stage 5, S5.2)."""

from __future__ import annotations

import subprocess
import sys
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.runners import RunnerResult
from fettle.evidence import parse_artifact
from fettle.uat.session import (
    build_prompt,
    collect_scenarios,
    generate_profile,
    load_checkpoint,
    run_session,
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

## Scenarios

### S1. Basic greeting (traces R1)

- Given the app is installed
- When the user runs `greet Ada`
- Then the output contains "Hello, Ada"
"""


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path,
                   capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@fettle.invalid"], cwd=tmp_path,
                   capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path,
                   capture_output=True, check=True)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = \"x\"\n\n[project.scripts]\ngreet = \"x:main\"\n")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "greeter.md").write_text(SPEC)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path,
                   capture_output=True, check=True)
    return tmp_path


def _cfg() -> dict:
    return {
        "uat": {"surfaces": ["auto"], "app_url": "", "start_command": "",
                "runner": "claude", "timeout_s": 1800, "mode": "report"},
        "worktrees": {"root": ".fettle/worktrees"},
    }


class TestNetworkController:
    def test_corrupt_resource_journal_blocks_execution(self, tmp_path, monkeypatch):
        from fettle.uat import controller
        from fettle.uat.recovery import lease

        monkeypatch.setattr(controller, "_store_root", lambda: tmp_path / "receipts")
        root = tmp_path / "product"
        root.mkdir()
        with lease(str(root), "colima-fettle-uat"):
            journal = next((tmp_path / "receipts/resources").glob("*.json"))
            journal_name = journal.name
        journal = tmp_path / "receipts/resources" / journal_name
        journal.write_text('{"schema_version":1}')
        invalidated = []
        with patch("fettle.uat.network_controller._docker") as docker:
            with pytest.raises(ValueError, match="ownership journal"):
                with lease(str(root), "colima-fettle-uat", on_acquired=lambda: invalidated.append(True)):
                    pytest.fail("corrupt journal acquired")
        docker.assert_not_called()
        assert invalidated == [True]

    def test_sigkill_and_vm_restart_recover_only_owned_resources(self, api_fixture):
        import json
        import os
        import signal
        import time
        from fettle.uat import controller, network_controller
        from fettle.uat.reconcile import reconcile_session
        from fettle.uat.session import _file_digest

        if os.environ.get("FETTLE_UAT_VM_RESTART") != "1":
            pytest.skip("explicit dedicated VM restart qualification opt-in required")
        root, path, contract, config = api_fixture
        app = root / "app.py"
        original = app.read_text()
        app.write_text(original.replace("self.send_response(200)",
                                        "__import__('time').sleep(5); self.send_response(200)"))
        contract["actions"][0]["timeout_s"] = 15
        path.write_text(json.dumps(contract))
        approval = _file_digest(path)
        code = ("import sys; from pathlib import Path; from fettle.config import load_config; "
                "from fettle.uat import controller; controller._store_root=lambda:Path(sys.argv[4]); "
                "controller.run_contract_session(sys.argv[1],load_config(sys.argv[1],strict=True),"
                "sys.argv[2],sys.argv[3],True,'api')")
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        process = subprocess.Popen([sys.executable, "-c", code, str(root), str(path), approval,
                                    str(root.parent / "receipts")], env=environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        journal = None
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                journals = list((root.parent / "receipts/resources").glob("*.json"))
                if journals:
                    journal = json.loads(journals[0].read_text())
                    names = network_controller._docker(contract["context"], ["ps", "--filter",
                        "label=fettle.uat.owner=" + journal["owner"], "--format", "{{.Names}}"])
                    if "-observer" in names:
                        break
                assert process.poll() is None, "capture exited before SIGKILL"
            else:
                pytest.fail("observer never started")
            process.kill()
            process.wait(timeout=5)
            assert process.returncode == -signal.SIGKILL
            verdicts, checkpoint, error = reconcile_session(str(root), str(root))
            assert not checkpoint.get("acceptance_complete", False)
            with pytest.raises(ValueError, match="active"):
                from fettle.uat.recovery import lease
                with lease(str(root), contract["context"]):
                    pytest.fail("surviving Docker client lost its lease")
            subprocess.run(["/opt/homebrew/bin/colima", "stop", "--profile", "fettle-uat"],
                           check=True, capture_output=True, timeout=90)
            subprocess.run(["/opt/homebrew/bin/colima", "start", "fettle-uat"],
                           check=True, capture_output=True, timeout=120)
            app.write_text(original)
            foreign = "fettle-foreign-recovery-canary"
            network_controller._docker(contract["context"], ["volume", "create", foreign])
            try:
                result = controller.run_contract_session(str(root), config, str(path), approval, True, "api")
                assert result.status == "completed", result.error
                verdicts, checkpoint, error = reconcile_session(str(root), str(root))
                assert checkpoint["acceptance_complete"], error
                assert not list((root.parent / "receipts/resources").glob("*.json"))
                for kind in ("container", "volume", "network"):
                    listing = ["ps", "-a"] if kind == "container" else [kind, "ls"]
                    assert not network_controller._docker(contract["context"], [*listing, "--filter",
                        "label=fettle.uat.owner=" + journal["owner"], "--format", "{{.ID}}"] ).strip()
                network_controller._docker(contract["context"], ["volume", "inspect", foreign])
            finally:
                network_controller._docker(contract["context"], ["volume", "rm", foreign])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    @pytest.fixture
    def api_fixture(self, tmp_path, monkeypatch):
        import json
        from fettle.config import load_config
        from fettle.uat import controller
        from fettle.uat.network_controller import IMAGE
        from fettle.uat.session import _digest

        product = tmp_path / "product"
        product.mkdir()
        root = _git_repo(product)
        monkeypatch.setattr(controller, "_store_root", lambda: tmp_path / "receipts")
        app = root / "app.py"
        app.write_text(
            "from http.server import BaseHTTPRequestHandler,HTTPServer\n"
            "class Handler(BaseHTTPRequestHandler):\n"
            "    def do_GET(self):\n"
            "        self.send_response(200)\n"
            "        self.end_headers()\n"
            "        self.wfile.write(b'Hello, Ada')\n"
            "HTTPServer(('0.0.0.0',8080),Handler).serve_forever()\n")
        contract = {
            "schema_version": 2, "surface": "api", "runtime_image": IMAGE,
            "context": "colima-fettle-uat", "product": {"argv": ["/product/app.py"], "port": 8080},
            "scenario_digest": _digest(collect_scenarios(str(root))),
            "actions": [{"scenario_id": "greeter/S1", "timeout_s": 3,
                         "steps": [{"method": "GET", "path": "/", "body": "",
                                    "expect": {"status_code": 200, "body": "Hello, Ada"}}]}],
        }
        path = root / "contract.json"
        path.write_text(json.dumps(contract))
        return root, path, contract, load_config(str(root), strict=True)

    @pytest.mark.parametrize("field,value", [
        ("runtime_image", "python:latest"), ("context", "--host=evil"),
        ("surface", "web"), ("schema_version", True), ("actions", []),
    ])
    def test_rejects_unqualified_contract(self, api_fixture, field, value):
        from fettle.uat.network_controller import validate_contract

        root, path, contract, config = api_fixture
        contract[field] = value
        with pytest.raises(ValueError):
            validate_contract(contract, collect_scenarios(str(root)))

    @pytest.mark.parametrize("path", ["//evil.invalid/", "http://evil.invalid", "/bad\r\nHost:evil", "/bad path"])
    def test_rejects_nonlocal_request(self, api_fixture, path):
        from fettle.uat.network_controller import validate_contract

        root, contract_path, contract, config = api_fixture
        contract["actions"][0]["steps"][0]["path"] = path
        with pytest.raises(ValueError):
            validate_contract(contract, collect_scenarios(str(root)))

    def test_changed_source_never_reaches_container(self, api_fixture):
        from fettle.uat.controller import _source
        from fettle.uat.network_controller import execute

        root, path, contract, config = api_fixture
        entries = _source(str(root))
        (root / "app.py").write_text("print('changed after snapshot')\n")
        with patch("fettle.uat.network_controller._docker") as docker:
            with pytest.raises(ValueError, match="frozen source inventory"):
                execute(str(root), contract, entries)
        docker.assert_not_called()

    @pytest.mark.parametrize("case,expected", [
        ("success", "CONFIRMED"), ("wrong-output", "CONTRADICTED"),
        ("redirect", "CONTRADICTED"), ("server-error", "CONTRADICTED"),
        ("overflow", "BLOCKED"), ("startup-failure", "BLOCKED"),
    ])
    def test_real_api_capture_and_replay(self, api_fixture, case, expected):
        import json
        import os
        from fettle.uat import controller
        from fettle.uat.reconcile import reconcile_session, validate_canonical_evidence
        from fettle.uat.session import _file_digest

        if os.environ.get("FETTLE_UAT_DOCKER") != "1":
            pytest.skip("explicit opt-in required for prepared local Docker qualification")
        root, path, contract, config = api_fixture
        app = root / "app.py"
        code = app.read_text()
        if case == "wrong-output":
            code = code.replace("Hello, Ada", "wrong output")
        if case == "redirect":
            code = code.replace("send_response(200)", "send_response(302)")
        if case == "server-error":
            code = code.replace("send_response(200)", "send_response(500)")
        if case == "overflow":
            code = code.replace("b'Hello, Ada'", "b'x' * 65537")
        if case == "startup-failure":
            code = "raise RuntimeError('seeded startup failure')\n"
        app.write_text(code)
        result = controller.run_contract_session(str(root), config, str(path), _file_digest(path), True, "api")
        if case == "startup-failure":
            assert result.status == "error"
            assert "product exited" in result.error
            return
        verdicts, checkpoint, error = reconcile_session(str(root), str(root))
        assert not error, error + result.error
        assert verdicts[0].verdict == expected
        assert checkpoint["acceptance_complete"] == (expected == "CONFIRMED")
        report = json.loads((root / ".fettle/uat-report.json").read_text())
        canonical = validate_canonical_evidence(str(root), report)
        assert (canonical.result_state.value == "pass") == (expected == "CONFIRMED")
        report["verdicts"][0]["observed"] = "forged"
        assert validate_canonical_evidence(str(root), report).result_state.value != "pass"
        app.write_text(code + "\nchanged = True\n")
        assert validate_canonical_evidence(str(root), report).result_state.value != "pass"


    def test_restart_retains_observed_state(self, api_fixture):
        import json
        import os
        from fettle.uat import controller
        from fettle.uat.reconcile import reconcile_session
        from fettle.uat.session import _file_digest

        if os.environ.get("FETTLE_UAT_DOCKER") != "1":
            pytest.skip("explicit Docker qualification opt-in required")
        root, path, contract, config = api_fixture
        (root / "app.py").write_text(
            "from http.server import BaseHTTPRequestHandler,HTTPServer\n"
            "from pathlib import Path\n"
            "state=Path('/state/value')\n"
            "class Handler(BaseHTTPRequestHandler):\n"
            "    def do_POST(self):\n"
            "        state.write_text('Ada')\n"
            "        self.send_response(201)\n"
            "        self.end_headers()\n"
            "    def do_GET(self):\n"
            "        self.send_response(200)\n"
            "        self.end_headers()\n"
            "        self.wfile.write((state.read_text() if state.exists() else 'missing').encode())\n"
            "HTTPServer(('0.0.0.0',8080),Handler).serve_forever()\n")
        contract["actions"][0]["steps"] = [
            {"method": "POST", "path": "/", "body": "", "expect": {"status_code": 201, "body": ""}},
            {"restart": True},
            {"method": "GET", "path": "/", "body": "", "expect": {"status_code": 200, "body": "Ada"}},
        ]
        path.write_text(json.dumps(contract))
        result = controller.run_contract_session(str(root), config, str(path), _file_digest(path), True, "api")
        verdicts, checkpoint, error = reconcile_session(str(root), str(root))
        assert not error, error + result.error
        assert checkpoint["acceptance_complete"], verdicts

    @pytest.mark.parametrize("width,expected_text,audit", [
        (1280, "Hello, Ada", ""), (375, "Hello, Ada", ""), (1280, "wrong", ""),
        (1280, "Hello, Ada", "clean"), (375, "Hello, Ada", "clean"),
        (1280, "Hello, Ada", "label"), (1280, "Hello, Ada", "page"),
        (1280, "Hello, Ada", "console"), (1280, "Hello, Ada", "http"),
        (375, "Hello, Ada", "external"),
    ])
    def test_browser_form_submission(self, api_fixture, width, expected_text, audit):
        import json
        import os
        from fettle.uat import controller
        from fettle.uat.network_controller import AUDIT_EXPECTATION, BROWSER_IMAGE, validate_artifacts
        from fettle.uat.reconcile import reconcile_session
        from fettle.uat.session import _file_digest

        if os.environ.get("FETTLE_UAT_DOCKER") != "1":
            pytest.skip("explicit Docker qualification opt-in required")
        root, path, contract, config = api_fixture
        source = Path(os.environ["TMPDIR"]) / "fettle-playwright-seccomp.json"
        profile = json.loads(source.read_text())
        profile["syscalls"].append({"names": ["chroot"], "action": "SCMP_ACT_ALLOW"})
        profile_path = root.parent / "browser-seccomp.json"
        profile_path.write_text(json.dumps(profile, sort_keys=True))
        contract["surface"] = "web"
        contract["browser"] = {"image": BROWSER_IMAGE, "seccomp_path": str(profile_path),
                               "viewport": {"width": width, "height": 720}}
        contract["actions"][0]["timeout_s"] = 10
        contract["actions"][0]["steps"] = [
            {"op": "goto", "path": "/"},
            {"op": "fill", "label": "Name", "value": "Ada"},
            {"op": "click", "role": "button", "name": "Greet"},
            {"op": "text", "role": "status", "name": "", "expect": expected_text},
        ]
        if audit:
            contract["actions"][0]["timeout_s"] = 20
            contract["actions"][0]["steps"].append({"op": "audit", "expect": AUDIT_EXPECTATION})
        defect = {"label": '<input id="unlabeled">',
                  "page": '<script>throw new Error("seeded page failure")</script>',
                  "console": '<script>console.error("seeded console failure")</script>',
                  "http": '<script>fetch("/broken")</script>',
                  "external": '<script>fetch("https://example.invalid/blocked").catch(()=>{})</script>'}.get(audit, "")
        result_html = ('<!doctype html><html lang="en"><head><title>Result</title>'
                       '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
                       '<body><main><h1>Greeting</h1><p role="status">Hello, Ada</p>'
                       + defect + '</main></body></html>')
        html = ('<!doctype html><html lang="en"><title>Greeting</title><main>'
                '<form method="post"><label>Name<input name="name"></label>'
                '<button>Greet</button></form></main></html>')
        (root / "app.py").write_text(
            "from http.server import BaseHTTPRequestHandler,HTTPServer\n"
            "class Handler(BaseHTTPRequestHandler):\n"
            "    def do_GET(self):\n"
            "        self.send_response(503 if self.path == '/broken' else 200)\n"
            "        self.end_headers()\n"
            f"        self.wfile.write({html.encode()!r})\n"
            "    def do_POST(self):\n"
            "        self.rfile.read(int(self.headers['Content-Length']))\n"
            "        self.send_response(200)\n"
            "        self.end_headers()\n"
            f"        self.wfile.write({result_html.encode()!r})\n"
            "HTTPServer(('0.0.0.0',8080),Handler).serve_forever()\n")
        path.write_text(json.dumps(contract))
        result = controller.run_contract_session(str(root), config, str(path), _file_digest(path), True, "web")
        verdicts, checkpoint, error = reconcile_session(str(root), str(root))
        assert not error, error + result.error
        passed = expected_text == "Hello, Ada" and audit in ("", "clean")
        assert verdicts[0].verdict == ("CONFIRMED" if passed else "CONTRADICTED"), result.error
        assert checkpoint["acceptance_complete"] == passed
        if audit:
            import base64

            receipt = json.loads((root.parent / "receipts" / (result.session_id + ".json")).read_text())
            observed = receipt["observations"][0]
            assert len(observed["artifacts"]) == 1
            artifact = observed["artifacts"][0]
            (root.parent / f"audit-{width}-{audit}.png").write_bytes(base64.b64decode(artifact["data"]))
            diagnostics = json.loads(observed["stdout"])[1]["audit"]
            diagnostic = {"label": "accessibility_violations", "page": "page_errors",
                          "console": "console_errors", "http": "http_errors",
                          "external": "failed_requests"}.get(audit)
            if diagnostic:
                assert diagnostics[diagnostic], diagnostics
            artifact["sha256"] = "0" * 64
            with pytest.raises(ValueError, match="screenshot identity"):
                validate_artifacts(contract, contract["actions"][0], observed)

    def test_collector_scripts_compile(self):
        from fettle.uat.network_controller import BROWSE, COLLECT, SEED

        for name, source in (("browser", BROWSE), ("api", COLLECT), ("seed", SEED)):
            compile(source, name, "exec")

    def test_api_runtime_binds_controller_and_daemon(self, api_fixture):
        import json
        from fettle.uat.network_controller import runtime

        root, path, contract, config = api_fixture
        with patch("fettle.uat.network_controller._docker", side_effect=[
            json.dumps([{"Endpoints": {"docker": {"Host": "unix:///trusted/docker.sock"}}}]),
            json.dumps([{"Id": "immutable", "Config": {}}]),
            json.dumps({"ID": "daemon", "ServerVersion": "1", "KernelVersion": "1", "OSType": "linux"}),
        ]):
            captured = runtime(contract)
        assert captured["server"]["ID"] == "daemon"
        assert captured["capture"].startswith("sha256:")
        assert captured["recovery"].startswith("sha256:")

    def test_restart_only_contract_is_not_behavioral_coverage(self, api_fixture):
        from fettle.uat.network_controller import validate_contract

        root, path, contract, config = api_fixture
        contract["actions"][0]["steps"] = [{"restart": True}]
        with pytest.raises(ValueError, match="response assertion"):
            validate_contract(contract, collect_scenarios(str(root)))


    @pytest.mark.parametrize("failure", ["interruption", "cleanup"])
    def test_failed_capture_cannot_reuse_success(self, api_fixture, monkeypatch, failure):
        import os
        from fettle.uat import controller, network_controller
        from fettle.uat.reconcile import reconcile_session
        from fettle.uat.session import _file_digest

        if os.environ.get("FETTLE_UAT_DOCKER") != "1":
            pytest.skip("explicit Docker qualification opt-in required")
        root, path, contract, config = api_fixture
        approval = _file_digest(path)
        initial = controller.run_contract_session(str(root), config, str(path), approval, True, "api")
        assert initial.status == "completed", initial.error
        original = network_controller._docker

        def fail_once(context, arguments, **kwargs):
            if failure == "interruption" and arguments[0] == "run" and any(
                    isinstance(value, str) and value.endswith("-observer") for value in arguments):
                raise subprocess.TimeoutExpired("injected collector interruption", 1)
            result = original(context, arguments, **kwargs)
            if failure == "cleanup" and arguments[:2] == ["network", "rm"]:
                raise ValueError("injected cleanup acknowledgement failure")
            return result

        with monkeypatch.context() as scoped:
            scoped.setattr(network_controller, "_docker", fail_once)
            failed = controller.run_contract_session(str(root), config, str(path), approval, True, "api")
            assert failed.status == "error"
            verdicts, checkpoint, error = reconcile_session(str(root), str(root))
            assert not checkpoint.get("acceptance_complete", False)
        recovered = controller.run_contract_session(str(root), config, str(path), approval, True, "api")
        assert recovered.status == "completed", recovered.error
        verdicts, checkpoint, error = reconcile_session(str(root), str(root))
        assert checkpoint["acceptance_complete"], error
        assert recovered.session_id != initial.session_id


class TestReadOnlyController:
    def test_network_proposal_keeps_oracles_controller_side(self, tmp_path):
        import json
        from fettle.uat.controller import validate_proposal

        contract = {"scenario_digest": "frozen", "actions": [{"scenario_id": "api/S1", "timeout_s": 5,
            "steps": [{"method": "GET", "path": "/", "body": "", "expect": {"status_code": 200, "body": "ok"}}]}]}
        proposal = {"schema_version": 1, "scenario_digest": "frozen", "actions": [{
            "scenario_id": "api/S1", "timeout_s": 5, "steps": [{"method": "GET", "path": "/", "body": ""}]}]}
        path = tmp_path / "proposal.json"
        path.write_text(json.dumps(proposal))
        validate_proposal(str(path), contract)
        proposal["actions"][0]["steps"][0]["expect"] = {"status_code": 200, "body": "ok"}
        path.write_text(json.dumps(proposal))
        with pytest.raises(ValueError, match="proposal differs"):
            validate_proposal(str(path), contract)

    @pytest.mark.parametrize("change", ["valid", "oracle", "command", "missing", "boolean", "duplicate", "symlink"])
    def test_proposal_never_changes_authority(self, tmp_path, change):
        import json
        from fettle.uat.controller import validate_proposal

        contract = {"scenario_digest": "frozen", "actions": [
            {"scenario_id": "example/S1", "argv": ["/bin/echo", "hello"], "timeout_s": 1,
             "expect": {"exit_code": 0, "stdout": "hello\n", "stderr": ""}}]}
        action = {key: value for key, value in contract["actions"][0].items() if key != "expect"}
        proposal = {"schema_version": 1, "scenario_digest": "frozen", "actions": [action]}
        if change == "oracle":
            action["expect"] = contract["actions"][0]["expect"]
        elif change == "command":
            action["argv"] = ["/bin/sh", "-c", "true"]
        elif change == "missing":
            proposal["actions"] = []
        elif change == "boolean":
            action["timeout_s"] = True
        path = tmp_path / "proposal.json"
        content = json.dumps(proposal)
        if change == "duplicate":
            content = content.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
        path.write_text(content)
        if change == "symlink":
            link = tmp_path / "link.json"
            link.symlink_to(path)
            path = link
        if change == "valid":
            validate_proposal(str(path), contract)
        else:
            with pytest.raises(ValueError):
                validate_proposal(str(path), contract)

    def test_rejected_proposal_never_captures(self, capture_fixture):
        from fettle.uat import controller

        root, path, approval, config = capture_fixture
        proposal = root / "proposal.json"
        proposal.write_text('{}')
        with patch("fettle.uat.controller.capture") as capture:
            result = controller.run_contract_session(str(root), config, str(path), approval, True,
                                                     proposal_path=str(proposal))
        capture.assert_not_called()
        assert result.status == "error"
        assert "proposal" in result.error

    @pytest.fixture
    def capture_fixture(self, tmp_path, monkeypatch):
        import json
        from fettle.config import load_config
        from fettle.uat import controller
        from fettle.uat.session import _digest, _file_digest

        if sys.platform != "darwin":
            pytest.skip("native macOS capture qualification")
        product = tmp_path / "product"
        product.mkdir()
        root = _git_repo(product)
        monkeypatch.setattr(controller, "_store_root", lambda: tmp_path / "receipts")
        contract = {
            "schema_version": 1, "scenario_digest": _digest(collect_scenarios(str(root))),
            "actions": [{"scenario_id": "greeter/S1", "argv": ["/bin/echo", "Hello, Ada"],
                         "timeout_s": 2,
                         "expect": {"exit_code": 0, "stdout": "Hello, Ada\n", "stderr": ""}}],
        }
        path = root / "contract.json"
        path.write_text(json.dumps(contract))
        return root, path, _file_digest(path), load_config(str(root), strict=True)

    def test_real_observation_and_wrong_output(self, capture_fixture):
        import json
        from fettle.uat import controller
        from fettle.uat.session import _digest, _file_digest

        root, path, approval, config = capture_fixture
        for expected, verdict in (("Hello, Ada\n", "CONFIRMED"), ("wrong\n", "CONTRADICTED")):
            contract = json.loads(path.read_text())
            contract["actions"][0]["expect"]["stdout"] = expected
            path.write_text(json.dumps(contract))
            captured = controller.capture(str(root), config, str(path), _file_digest(path))
            session = {"session_id": captured["session_id"], "capture_digest": _digest(captured),
                       "capture_mode": controller.MODE, "surface": "cli",
                       "canonical_evidence_reference": {"kind": "fettle.uat.cli-observation",
                                                        "artifact_digest": _digest(captured)},
                       "scenario_ids": ["greeter/S1"]}
            verdicts, error = controller.validate_capture(str(root), session)
            assert not error
            assert verdicts[0]["verdict"] == verdict
            assert captured["observations"][0]["stdout"] == "Hello, Ada\n"

    def test_unapproved_contract_does_not_execute(self, capture_fixture):
        from fettle.uat import controller

        root, path, approval, config = capture_fixture
        with pytest.raises(ValueError, match="approved"):
            controller.capture(str(root), config, str(path), "sha256:" + "0" * 64)

    @pytest.mark.parametrize("invalid", [[], None, {"observations": []}])
    def test_malformed_receipt_is_nonpass(self, capture_fixture, invalid):
        import json
        from fettle.uat import controller
        from fettle.uat.session import _digest

        root, path, approval, config = capture_fixture
        captured = controller.capture(str(root), config, str(path), approval)
        receipt = controller._store_root() / (captured["session_id"] + ".json")
        receipt.write_text(json.dumps(invalid))
        verdicts, error = controller.validate_capture(str(root), {
            "session_id": captured["session_id"], "capture_digest": _digest(captured),
        })
        assert error
        assert not verdicts

    def test_report_and_canonical_accept_observation_not_caller_claim(self, capture_fixture):
        import json
        from fettle.evidence import ResultState, Validity
        from fettle.uat.controller import run_contract_session
        from fettle.uat.reconcile import reconcile_session, validate_canonical_evidence

        root, path, approval, config = capture_fixture
        result = run_contract_session(str(root), config, str(path), approval, True)
        assert result.status == "completed", result.error
        verdicts, checkpoint, error = reconcile_session(str(root), str(root))
        assert not error
        assert checkpoint["acceptance_complete"]
        assert verdicts[0].verdict == "CONFIRMED"
        report = json.loads((root / ".fettle" / "uat-report.json").read_text())
        validation = validate_canonical_evidence(str(root), report)
        assert validation.validity == Validity.VALID
        assert validation.result_state == ResultState.PASS
        report["verdicts"][0]["observed"] = "forged"
        assert validate_canonical_evidence(str(root), report).result_state != ResultState.PASS

    def test_sidecar_failure_downgrades_saved_completion(self, capture_fixture):
        import json
        from fettle.uat.controller import run_contract_session
        from fettle.uat.reconcile import reconcile_session

        root, path, approval, config = capture_fixture
        result = run_contract_session(str(root), config, str(path), approval, True)
        assert result.status == "completed", result.error
        with patch("fettle.uat.reconcile._write_report_evidence", side_effect=OSError("full")):
            _, checkpoint, error = reconcile_session(str(root), str(root))
        assert error
        assert not checkpoint["acceptance_complete"]
        report = json.loads((root / ".fettle" / "uat-report.json").read_text())
        assert not report["completion"]["complete"]
        assert "full" in report["session_error"]

    @pytest.mark.parametrize("case,exit_code", [
        ("success", 0), ("defect", 1), ("timeout", 1), ("no-consent", 1), ("unapproved", 1),
    ])
    def test_public_cli_run_report_and_canonical(self, capture_fixture, case, exit_code):
        import json
        import os
        from fettle.uat.session import _file_digest

        root, path, approval, config = capture_fixture
        contract = json.loads(path.read_text())
        if case == "defect":
            contract["actions"][0]["expect"]["stdout"] = "different\n"
        if case == "timeout":
            contract["actions"][0]["argv"] = [str(Path(sys.executable).resolve()), "-I", "-c",
                                              "import time; time.sleep(5)"]
            contract["actions"][0]["timeout_s"] = 1
        path.write_text(json.dumps(contract))
        approval = "sha256:" + "0" * 64 if case == "unapproved" else _file_digest(path)
        environment = {"HOME": str(root.parent / "controller-home"), "PATH": os.environ["PATH"],
                       "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                       "TMPDIR": str(root.parent)}
        arguments = [sys.executable, "-m", "fettle", "uat", "run", "--contract", str(path),
                     "--approve-contract", approval, "--json"]
        if case != "no-consent":
            arguments.append("--yes")
        doctor = subprocess.run(
            [sys.executable, "-m", "fettle", "uat", "doctor", "--contract", str(path),
             "--approve-contract", approval, "--json"],
            cwd=root, env=environment, capture_output=True, text=True, timeout=30,
        )
        assert doctor.returncode == (1 if case == "unapproved" else 0), doctor.stderr + doctor.stdout
        assert not (root / ".fettle" / "uat-session.json").exists()
        text_doctor = subprocess.run(
            [sys.executable, "-m", "fettle", "uat", "doctor", "--contract", str(path),
             "--approve-contract", approval],
            cwd=root, env=environment, capture_output=True, text=True, timeout=30,
        )
        assert text_doctor.returncode == doctor.returncode, text_doctor.stderr
        assert "read-only contract" in text_doctor.stdout
        run = subprocess.run(arguments, cwd=root, env=environment, capture_output=True,
                             text=True, timeout=30)
        assert run.returncode == exit_code, run.stderr + run.stdout
        response = json.loads(run.stdout)
        assert response["acceptance_complete"] == (case == "success")
        if case in {"unapproved", "no-consent"}:
            assert response["error"]
            assert not (root / ".fettle" / "uat-report.evidence.json").exists()
            return
        replay = subprocess.run(
            [sys.executable, "-m", "fettle", "uat", "report", "--worktree", str(root), "--json"],
            cwd=root, env=environment, capture_output=True, text=True, timeout=30,
        )
        assert replay.returncode == exit_code, replay.stderr + replay.stdout
        assert json.loads(replay.stdout)["acceptance_complete"] == (case == "success")
        validation = subprocess.run(
            [sys.executable, "-c", "import json; from pathlib import Path; "
             "from fettle.uat.reconcile import validate_canonical_evidence; "
             "report=json.loads(Path('.fettle/uat-report.json').read_text()); "
             "print(validate_canonical_evidence('.', report).result_state.value)"],
            cwd=root, env=environment, capture_output=True, text=True, timeout=30,
        )
        assert validation.returncode == 0, validation.stderr
        assert (validation.stdout.strip() == "pass") == (case == "success")

    @pytest.mark.parametrize("code,reason", [
        ("open('forbidden', 'w').write('bad')", "signal"),
        ("import os; os.fork()", "signal"),
        ("import socket; socket.socket().connect(('127.0.0.1', 9))", "signal"),
        ("import time; time.sleep(5)", "timed out"),
        ("print('x' * 100000)", "limit"),
    ])
    def test_native_denial_and_bounds(self, capture_fixture, code, reason):
        import json
        from fettle.uat import controller
        from fettle.uat.session import _file_digest

        root, path, approval, config = capture_fixture
        contract = json.loads(path.read_text())
        contract["actions"][0]["argv"] = [str(Path(sys.executable).resolve()), "-I", "-c", code]
        contract["actions"][0]["timeout_s"] = 1
        path.write_text(json.dumps(contract))
        captured = controller.capture(str(root), config, str(path), _file_digest(path))
        assert reason in captured["observations"][0]["error"]
        assert not (root / "forbidden").exists()

    def test_child_cannot_read_receipts(self, capture_fixture):
        import json
        from fettle.uat import controller
        from fettle.uat.session import _file_digest

        root, path, approval, config = capture_fixture
        store = controller._store_root()
        store.mkdir()
        secret = store / "canary"
        secret.write_text("controller-private-canary")
        contract = json.loads(path.read_text())
        contract["actions"][0]["argv"] = ["/bin/cat", str(secret)]
        path.write_text(json.dumps(contract))
        captured = controller.capture(str(root), config, str(path), _file_digest(path))
        observed = captured["observations"][0]
        assert observed["error"]
        assert "controller-private-canary" not in observed["stdout"]

    @pytest.mark.parametrize("change", ["source", "receipt", "context", "policy", "reference"])
    def test_stale_missing_and_replayed_evidence(self, capture_fixture, change):
        from fettle.uat import controller
        from fettle.uat.session import _digest

        root, path, approval, config = capture_fixture
        captured = controller.capture(str(root), config, str(path), approval)
        session = {"session_id": captured["session_id"], "capture_digest": _digest(captured),
                   "capture_mode": controller.MODE, "surface": "cli",
                   "canonical_evidence_reference": {"kind": "fettle.uat.cli-observation",
                                                    "artifact_digest": _digest(captured)},
                   "scenario_ids": ["greeter/S1"]}
        if change == "source":
            (root / "new-input.txt").write_text("changed")
        elif change == "receipt":
            (controller._store_root() / (captured["session_id"] + ".json")).unlink()
        elif change == "policy":
            (root / ".fettle.toml").write_text('[uat]\ntimeout_s = 12\n')
        elif change == "reference":
            del session["canonical_evidence_reference"]
        else:
            session["capture_digest"] = "sha256:" + "0" * 64
        verdicts, error = controller.validate_capture(str(root), session)
        assert error
        assert verdicts == []


class FakeRunner:
    name = "fake"

    def __init__(self, transcript="SCENARIO: greeter/S1\nOUTCOME: matches", error=""):
        self.transcript, self.error = transcript, error
        self.calls: list[dict] = []

    def run(self, prompt, cwd, timeout_s=600):
        self.calls.append({"prompt": prompt, "cwd": cwd, "timeout_s": timeout_s})
        return RunnerResult(transcript=self.transcript, exit_code=0,
                            duration_s=0.1, error=self.error)


class TestScenariosAndPrompt:
    def test_nested_worktree_does_not_duplicate_scenarios(self, tmp_path):
        repo = _git_repo(tmp_path)
        nested = repo / ".fettle" / "worktrees" / "uat-test" / "specs"
        nested.mkdir(parents=True)
        (nested / "greeter.md").write_text(SPEC)
        assert len(collect_scenarios(str(repo))) == 1

    def test_duplicate_active_ids_rejected(self, tmp_path):
        repo = _git_repo(tmp_path)
        (repo / "specs" / "duplicate.md").write_text(SPEC)
        with pytest.raises(ValueError, match="duplicate scenario"):
            collect_scenarios(str(repo))

    def test_profile_values_preserve_declared_classes(self):
        profile = generate_profile("audit")
        values = {item["equivalence_class"]: item["value"] for item in profile["inputs"]}
        assert values["boundary_zero"] == "0"
        assert values["boundary_large"].isdecimal()
        assert int(values["boundary_large"]) == 999999999
        assert re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"])
        assert re.fullmatch(r"\+1-202-555-\d{4}", values["phone"])
        assert values["whitespace"].startswith("  ") and values["whitespace"].endswith("  ")
        assert values["ascii_name"].isascii()
        assert not values["unicode_name"].isascii()
        assert profile["equivalence_class_count"] == len(values)
        assert generate_profile("another-seed")["seed_sha256"] != profile["seed_sha256"]

    def test_collect_scenarios_active_only(self, tmp_path):
        repo = _git_repo(tmp_path)
        (repo / "specs" / "draft.md").write_text(
            SPEC.replace("id: greeter", "id: draft-one")
                .replace("status: active", "status: draft"))
        scenarios = collect_scenarios(str(repo))
        assert [s["id"] for s in scenarios] == ["greeter/S1"]
        assert "When the user runs `greet Ada`" in scenarios[0]["steps"]
        assert scenarios[0]["requirements"] == ["Greets the user by name."]

    def test_prompt_contains_persona_and_steps(self, tmp_path):
        repo = _git_repo(tmp_path)
        prompt = build_prompt("cli", collect_scenarios(str(repo)), _cfg()["uat"])
        assert "first-time user" in prompt
        assert "do not read source code" in prompt
        assert "greeter/S1" in prompt
        assert 'Then the output contains "Hello, Ada"' in prompt
        assert "could-not-attempt" in prompt  # honest-failure channel

    def test_prompt_access_from_app_url(self):
        cfg = {"app_url": "http://localhost:8000"}
        assert "http://localhost:8000" in build_prompt("api", [], cfg)

    def test_prompt_access_from_start_command(self):
        cfg = {"start_command": "npm run dev"}
        prompt = build_prompt("api", [], cfg)
        assert "npm run dev" in prompt
        assert "RESTART_PROBE:" in prompt
        assert "stop the configured application" in prompt

    def test_seeded_profile_has_eight_distinct_equivalence_classes(self):
        first = generate_profile("uat-fixed-seed")
        second = generate_profile("uat-fixed-seed")
        assert first == second
        assert len(first["inputs"]) >= 8
        assert len({item["sha256"] for item in first["inputs"]}) >= 8


class TestRunSession:
    def test_real_process_failure_stays_nonpass_through_report(self, tmp_path):
        import json
        from fettle.uat.reconcile import reconcile_session, validate_canonical_evidence

        class ProcessRunner:
            name = "controlled-process"

            def run(self, prompt, cwd, timeout_s=600):
                process = subprocess.run(
                    [sys.executable, "-c", "print('Hello, Ada!'); raise SystemExit(2)"],
                    cwd=cwd, capture_output=True, text=True, timeout=10,
                )
                transcript = ("SCENARIO: greeter/S1\nOBSERVED: " + process.stdout
                              + "OUTCOME: matches\n")
                return RunnerResult(transcript, process.returncode, 0.1)

        repo = _git_repo(tmp_path)
        result = self._run(repo, runner=ProcessRunner())
        assert result.status == "error"
        assert "exited 2" in result.error
        verdicts, checkpoint, error = reconcile_session(str(repo), result.worktree)
        assert not error
        assert verdicts[0].verdict == "INDETERMINATE"
        assert not checkpoint["acceptance_complete"]
        report = json.loads((Path(result.worktree) / ".fettle" / "uat-report.json").read_text())
        assert not report["completion"]["complete"]
        validation = validate_canonical_evidence(result.worktree, report)
        assert validation.result_state.value != "pass"

    def test_canonical_session_validation_requires_current_dependencies(self, tmp_path):
        from fettle.uat.reconcile import _session_error

        repo = _git_repo(tmp_path)
        result = self._run(repo)
        checkpoint = load_checkpoint(result.worktree)
        assert _session_error(result.worktree, checkpoint) == ""
        sidecar = Path(result.worktree) / ".fettle" / "uat-session.evidence.json"
        retained = sidecar.read_bytes()
        sidecar.unlink()
        assert _session_error(result.worktree, checkpoint)
        sidecar.write_bytes(retained)
        Path(result.transcript_path).write_text("changed transcript")
        assert _session_error(result.worktree, checkpoint)

    def test_changed_requirement_invalidates_session(self, tmp_path):
        from fettle.uat.reconcile import _session_error

        repo = _git_repo(tmp_path)
        result = self._run(repo)
        checkpoint = load_checkpoint(result.worktree)
        spec = Path(result.worktree) / "specs" / "greeter.md"
        spec.write_text(SPEC.replace("Hello, Ada", "Goodbye, Ada"))
        assert "stale" in _session_error(result.worktree, checkpoint)

    def _run(self, repo, runner=None, surface="cli", consent=True):
        with patch("fettle.runners.claude.shutil.which",
                   return_value="/usr/bin/claude"):
            return run_session(str(repo), _cfg(), surface,
                               runner=runner or FakeRunner(), consent=consent)

    def test_happy_path(self, tmp_path):
        repo = _git_repo(tmp_path)
        runner = FakeRunner()
        result = self._run(repo, runner)
        assert result.status == "completed", result.error
        assert result.scenario_ids == ["greeter/S1"]
        assert Path(result.worktree).is_dir()
        assert "greeter/S1" in runner.calls[0]["prompt"]
        assert runner.calls[0]["cwd"] == result.worktree
        transcript = Path(result.transcript_path).read_text()
        assert "OUTCOME: matches" in transcript

    def test_configured_restart_probe_is_retained(self, tmp_path):
        repo = _git_repo(tmp_path)
        config = _cfg()
        config["uat"]["start_command"] = "python -m x"
        runner = FakeRunner(transcript=(
            "SCENARIO: greeter/S1\n"
            "OBSERVED: $ greet Ada -> Hello, Ada!\n"
            "OUTCOME: matches\n"
            "RESTART_PROBE:\n"
            "BEFORE: profile Ada exists\n"
            "AFTER: profile Ada exists after restart\n"
            "OUTCOME: persisted\n"
            "NOTES: stopped and relaunched python -m x\n"
        ))
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"):
            result = run_session(str(repo), config, "cli", runner=runner, consent=True)

        cp = load_checkpoint(result.worktree)
        artifact = Path(cp["restart_probe"]["artifact"])
        assert cp["profile"]["equivalence_class_count"] >= 8
        assert cp["restart_probe"]["status"] == "captured"
        assert artifact.is_file()
        assert "profile Ada exists after restart" in artifact.read_text()

    def test_stateless_session_marks_restart_not_applicable(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo)
        assert load_checkpoint(result.worktree)["restart_probe"] == {
            "status": "NOT_APPLICABLE",
            "reason": "uat.start_command is not configured",
        }

    def test_checkpoint_written_and_resumable(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo)
        cp = load_checkpoint(result.worktree)
        assert cp["status"] == "completed"
        assert cp["session_id"] == result.session_id
        assert cp["transcript"] == result.transcript_path
        assert cp["evidence_id"].startswith("ev-")
        assert result.evidence_id == cp["evidence_id"]

    def test_canonical_session_sidecar_is_additive_and_portable(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo)
        cp = load_checkpoint(result.worktree)
        artifact = parse_artifact(
            (Path(result.worktree) / ".fettle" / "uat-session.evidence.json").read_bytes()
        )
        assert cp["canonical_evidence_reference"]["artifact_digest"] == artifact.artifact_digest
        assert artifact.kind == "fettle.uat.session"
        assert artifact.payload["scenario_ids"] == ("greeter/S1",)
        assert artifact.payload["transcript"]["path"].endswith("-transcript.txt")
        assert result.worktree not in str(artifact.to_dict())

    def test_canonical_session_sidecar_can_be_rolled_back(self, tmp_path):
        repo = _git_repo(tmp_path)
        config = _cfg()
        config["uat"]["canonical_evidence"] = False
        with patch("fettle.runners.claude.shutil.which", return_value="/usr/bin/claude"):
            result = run_session(str(repo), config, "cli", runner=FakeRunner(), consent=True)
        cp = load_checkpoint(result.worktree)
        assert cp["canonical_evidence"] is False
        assert "canonical_evidence_reference" not in cp
        assert not (Path(result.worktree) / ".fettle" / "uat-session.evidence.json").exists()

    def test_canonical_session_write_failure_is_recorded(self, tmp_path):
        repo = _git_repo(tmp_path)
        with patch("fettle.uat.session._write_session_evidence", side_effect=OSError("full")):
            result = self._run(repo)

        cp = load_checkpoint(result.worktree)
        assert result.status == "completed"
        assert cp["canonical_evidence_error"] == "full"
        assert "canonical_evidence_reference" not in cp

    def test_atomic_checkpoint_failure_prevents_execution(self, tmp_path):
        repo = _git_repo(tmp_path)
        runner = FakeRunner()
        with patch("fettle.uat.session._write_bytes_atomic", side_effect=OSError("full")):
            result = self._run(repo, runner)
        assert result.status == "error"
        assert "checkpoint" in result.error
        assert not runner.calls

    def test_worktree_is_claimed(self, tmp_path):
        from fettle.work_items import claim_for_worktree
        repo = _git_repo(tmp_path)
        result = self._run(repo)
        assert claim_for_worktree(str(repo), result.worktree) == result.session_id

    def test_runner_error_surfaces(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo, FakeRunner(transcript="partial",
                                            error="runner timed out after 1800s"))
        assert result.status == "timeout"
        assert "timed out" in result.error
        assert load_checkpoint(result.worktree)["status"] == "timeout"

    def test_undrivable_surface_names_doctor(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo, surface="kiosk")
        assert result.status == "error"
        assert "not drivable" in result.error and "uat doctor" in result.error

    def test_no_consent_blocks_with_explanation(self, tmp_path):
        repo = _git_repo(tmp_path)
        result = self._run(repo, consent=False)
        assert result.status == "error"
        assert "--yes" in result.error and "normal host permission checks" in result.error

    def test_web_without_playwright_points_to_reinstall_and_manual(self, tmp_path):
        repo = _git_repo(tmp_path)
        with patch("fettle.uat.doctor._playwright_available", return_value=False):
            result = self._run(repo, surface="web")
        assert result.status == "error"
        assert "reinstall finefettle" in result.error and "playwright install" in result.error
        assert "uat manual" in result.error

    def test_secret_redacted_from_transcript(self, tmp_path):
        repo = _git_repo(tmp_path)
        leaky = ("SCENARIO: greeter/S1\n"
                 "OBSERVED: config shows AWS_SECRET_ACCESS_KEY "
                 "AKIAIOSFODNN7REALKEY\n"
                 "OUTCOME: matches\n")
        result = self._run(repo, FakeRunner(transcript=leaky))
        stored = Path(result.transcript_path).read_text()
        assert "AKIAIOSFODNN7REALKEY" not in stored
        assert "REDACTED" in stored

    def test_capability_gap_blocks(self, tmp_path):
        repo = _git_repo(tmp_path)
        with patch("fettle.runners.claude.shutil.which", return_value=None):
            result = run_session(str(repo), _cfg(), "cli",
                                 runner=FakeRunner(), consent=True)
        assert result.status == "error"
        assert "capability gap" in result.error

    def test_no_scenarios_blocks(self, tmp_path):
        repo = _git_repo(tmp_path)
        (repo / "specs" / "greeter.md").unlink()
        result = self._run(repo)
        assert result.status == "error"
        assert "no active spec scenarios" in result.error


class TestCLI:
    def test_uat_run_requires_consent(self, tmp_path):
        import json as _json
        repo = _git_repo(tmp_path)
        r = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "uat", "run", "--json"],
            cwd=repo, capture_output=True, text=True)
        assert r.returncode == 1
        data = _json.loads(r.stdout)
        assert "--yes" in data["error"]

    def test_uat_run_json_with_gap(self, tmp_path):
        import json as _json
        repo = _git_repo(tmp_path)
        r = subprocess.run(
            [sys.executable, "-m", "fettle.cli", "uat", "run",
             "--surface", "kiosk", "--yes", "--json"],
            cwd=repo, capture_output=True, text=True)
        assert r.returncode == 1
        data = _json.loads(r.stdout)
        assert data["status"] == "error"
        assert "not drivable" in data["error"]
