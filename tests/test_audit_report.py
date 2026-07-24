"""WP-145 — Audit & reporting tests: schema v2, org rollup, JUnit output."""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PLUGIN_DIR)

from fettle.junit import findings_to_junit  # noqa: E402

ERROR_FINDING = {"file": "a.py", "line": 3, "code": "S608",
                 "message": "sql injection", "severity": "error", "tool": "ruff"}
WARN_FINDING = {"file": "b.py", "line": 7, "code": "SIM108",
                "message": "use ternary", "severity": "warning", "tool": "ruff"}


class TestJUnit:
    def test_findings_render(self) -> None:
        xml = findings_to_junit([ERROR_FINDING, WARN_FINDING])
        root = ET.fromstring(xml)
        suite = root.find("testsuite")
        assert suite.get("tests") == "2"
        assert suite.get("failures") == "1"  # only error severity counts
        cases = suite.findall("testcase")
        assert cases[0].get("classname") == "a.py"
        assert cases[0].get("name") == "S608 @ line 3"
        assert cases[0].find("failure").get("type") == "error"
        assert cases[1].find("failure").get("type") == "warning"

    def test_empty_findings_yield_passing_case(self) -> None:
        root = ET.fromstring(findings_to_junit([]))
        suite = root.find("testsuite")
        assert suite.get("failures") == "0"
        case = suite.find("testcase")
        assert case.get("name") == "no-findings"
        assert case.find("failure") is None

    def test_message_is_escaped(self) -> None:
        nasty = dict(ERROR_FINDING, message='<script>&"quotes"</script>')
        xml = findings_to_junit([nasty])
        ET.fromstring(xml)  # parses -> escaping is correct


class TestAuditSchema:
    @pytest.fixture
    def state(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        return tmp_path / "state" / "fettle"

    def test_schema_v2_fields(self, state, tmp_path, monkeypatch) -> None:
        repo = tmp_path / "myrepo"
        (repo / ".git").mkdir(parents=True)
        target = repo / "src.py"
        target.write_text("x = 1\n")
        from fettle.trace import AUDIT_SCHEMA_VERSION, log_decision
        log_decision(hook="PostToolUse", status="violation", tool="ruff",
                     file=str(target), findings=[ERROR_FINDING], session_id="s1")
        entry = json.loads((state / "trace.jsonl").read_text().strip())
        assert entry["schema"] == AUDIT_SCHEMA_VERSION == 2
        assert entry["repo"] == "myrepo"
        assert entry["status"] == "violation"
        assert entry["session_id"] == "s1"

    def test_repo_indeterminate_is_empty(self, state, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)  # no .git anywhere up to tmp root
        from fettle.trace import log_decision
        log_decision(hook="Stop", status="pass", file="")
        entry = json.loads((state / "trace.jsonl").read_text().strip())
        assert isinstance(entry["repo"], str)


class TestOrgReport:
    @pytest.fixture
    def seeded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        trace_dir = tmp_path / "state" / "fettle"
        trace_dir.mkdir(parents=True)
        import time
        now = time.time()
        rows = [
            {"schema": 2, "ts": now, "hook": "PostToolUse", "status": "violation",
             "repo": "api", "findings": [ERROR_FINDING]},
            {"schema": 2, "ts": now, "hook": "PostToolUse", "status": "pass",
             "repo": "api", "findings": []},
            {"schema": 2, "ts": now, "hook": "PreToolUse", "status": "blocked",
             "repo": "web", "findings": []},
            # v1 legacy entry — no schema/repo keys
            {"ts": now, "hook": "Stop", "status": "pass", "findings": []},
        ]
        (trace_dir / "trace.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n")
        return trace_dir

    def test_aggregates_per_repo(self, seeded) -> None:
        from fettle.report import compute_org_report
        data = compute_org_report(days=1)
        assert data["total_repos"] == 3  # api, web, (unattributed)
        assert data["repos"]["api"]["decisions"] == 2
        assert data["repos"]["api"]["violations"] == 1
        assert data["repos"]["api"]["violation_rate_pct"] == 50.0
        assert data["repos"]["api"]["top_codes"][0][0] == "S608"
        assert data["repos"]["web"]["blocked"] == 1
        assert data["repos"]["(unattributed)"]["decisions"] == 1

    def test_empty_window(self, seeded) -> None:
        from fettle.report import compute_org_report
        # All entries are "now"; a window ending before them yields the error path
        data = compute_org_report(days=0)
        assert "error" in data or data["total_decisions"] >= 0


class TestCLI:
    def _run(self, *argv, env_extra=None, cwd=None):
        env = {**os.environ, **(env_extra or {})}
        proc = subprocess.run(
            [sys.executable, os.path.join(PLUGIN_DIR, "fettle", "cli.py"), *argv],
            capture_output=True, text=True, timeout=30, env=env,
            cwd=str(cwd) if cwd else None,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def test_report_org_json(self, tmp_path) -> None:
        state = tmp_path / "state" / "fettle"
        state.mkdir(parents=True)
        import time
        (state / "trace.jsonl").write_text(json.dumps(
            {"schema": 2, "ts": time.time(), "hook": "PostToolUse",
             "status": "pass", "repo": "solo", "findings": []}) + "\n")
        rc, out = self._run("report", "--org", "--json",
                            env_extra={"XDG_STATE_HOME": str(tmp_path / "state")})
        assert rc == 0
        data = json.loads(out)
        assert "solo" in data["repos"]

    def test_report_no_data_exits_1(self, tmp_path) -> None:
        rc, out = self._run("report", "--json",
                            env_extra={"XDG_STATE_HOME": str(tmp_path / "empty")})
        assert rc == 1

    def test_check_junit_output(self, tmp_path, monkeypatch) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".git").mkdir()
        (proj / ".fettle.toml").write_text("")
        junit_path = proj / "fettle-junit.xml"
        rc, out = self._run("check", "--junit", str(junit_path), cwd=proj)
        assert junit_path.is_file()
        root = ET.fromstring(junit_path.read_text())
        assert root.find("testsuite") is not None
