"""House invariant: every surfaced verdict is recoverable from retained evidence."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from fettle.evidence_ledger import read_ledger, verify_chain
from fettle.uat.reconcile import Verdict, write_report
from fettle.verify_gate import _write_stamp


def _trace_path(state: Path) -> Path:
    return state / "fettle" / "trace.jsonl"


def _assert_verdicts_evidenced(root: Path, state: Path) -> None:
    traces = [
        json.loads(line)
        for line in _trace_path(state).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    verdicts = [row for row in traces if row.get("hook") in {
        "authorship_gate", "verify", "uat_report",
    }]
    assert {row["hook"] for row in verdicts} == {
        "authorship_gate", "verify", "uat_report",
    }
    assert verify_chain(str(root))["status"] == "verified"
    ledger = read_ledger(str(root))

    for verdict in verdicts:
        references = verdict.get("evidence") or []
        assert references, f"{verdict['hook']} verdict has no evidence reference"
        matching = [
            row for row in ledger
            if row["kind"] == "verdict"
            and row["payload"].get("hook") == verdict["hook"]
            and row["payload"].get("evidence") == references
        ]
        assert matching, f"{verdict['hook']} verdict is absent from evidence ledger"
        for reference in references:
            digest = reference.get("artifact_digest")
            if not digest:
                continue
            candidates = list((root / ".fettle").glob("*evidence.json"))
            assert any(
                json.loads(path.read_text(encoding="utf-8")).get("artifact_digest") == digest
                for path in candidates
            ), f"backing artifact {digest} is missing"


def _record_standard_flows(root: Path, state: Path) -> None:
    (root / ".fettle.toml").write_text(
        'role = "implementer"\n[gates.authorship]\nenabled = true\nmode = "enforce"\n',
        encoding="utf-8",
    )
    env = {**os.environ, "XDG_STATE_HOME": str(state)}
    dispatched = subprocess.run(
        [sys.executable, str(Path(__file__).parents[1] / "scripts" / "dispatcher.py")],
        input=json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "tests/test_x.py"},
            "cwd": str(root),
            "session_id": "session-1",
        }),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert dispatched.returncode == 2, dispatched.stderr
    _write_stamp(str(root), {
        "ok": True, "session_id": "session-1", "head_sha": "",
        "dirty_digest": "", "exit_code": 0, "command": "pytest -q",
        "duration_s": 0.1, "scope": "full", "impacted": [], "error": "",
    }, {})
    path, error = write_report(
        str(root), {"session_id": "uat-1", "surface": "cli"},
        [Verdict("scenario-1", "CONFIRMED", "command succeeded", "")],
    )
    assert path and not error


def test_standard_verdict_flows_are_evidenced(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    fixture = Path(__file__).parents[1] / "examples" / "assurance-loop"
    shutil.copytree(fixture, root)
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))

    _record_standard_flows(root, state)

    _assert_verdicts_evidenced(root, state)


def test_deleting_backing_artifact_breaks_invariant_loudly(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    state = tmp_path / "state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    _record_standard_flows(root, state)
    (root / ".fettle" / "verify-evidence.json").unlink()

    try:
        _assert_verdicts_evidenced(root, state)
    except AssertionError as exc:
        assert "backing artifact" in str(exc)
    else:
        raise AssertionError("missing canonical artifact did not break the invariant")
