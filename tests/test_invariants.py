"""Item 11 — house invariant: verdict-visible means evidenced.

For every blocked/violation decision recorded in the audit trace, a
corresponding bounded evidence record must exist on disk (same file target,
consistent exit semantics). Deleting the evidence side must make the
invariant fail loudly — proving it is not vacuous.

MVP scope per work item: authorship-gate decisions paired with
`build_evidence("authorship_verdict", ...)` records, mirroring the P52
two-role session flow. Graduates to verify stamps and UAT reports next.
"""

from __future__ import annotations

import json
from pathlib import Path


from fettle.trace import build_evidence, log_decision


def _trace_env(tmp_path: Path) -> dict[str, str]:
    # trace.py resolves via XDG_STATE_HOME/fettle/trace.jsonl
    return {"XDG_STATE_HOME": str(tmp_path / "xdg-state")}


def _trace_path(tmp_path: Path) -> Path:
    return tmp_path / "xdg-state" / "fettle" / "trace.jsonl"


def _record_pair(tmp_path: Path, hook: str, status: str, tool: str,
                 target: str) -> dict:
    """One real decision + its paired evidence artifact, as sessions do."""
    log_decision(hook=hook, status=status, tool=tool, file=target)
    allow = status in ("allow", "pass")
    evidence = build_evidence(
        kind="authorship_verdict",
        scope=tool,
        command=f"{hook} {tool} edits {target}",
        exit_code=0 if allow else 1,
    )
    evidence_dir = tmp_path / ".fettle" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    out = evidence_dir / f"{evidence['evidence_id']}.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return {"decision": {"status": status, "file": target},
            "artifact": str(out), "evidence_id": evidence["evidence_id"]}


def _invariant_holds(root: Path) -> tuple[bool, str]:
    """Every blocked/violation trace decision has a matching artifact."""
    trace_path = root / "xdg-state" / "fettle" / "trace.jsonl"
    if not trace_path.is_file():
        return True, ""
    decisions = [json.loads(line) for line in
                 trace_path.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    blocking = [d for d in decisions
                if d.get("status") in ("blocked", "block", "violation")]
    artifacts: list[dict] = []
    ev_dir = root / ".fettle" / "evidence"
    if ev_dir.is_dir():
        for art_path in sorted(ev_dir.glob("*.json")):
            try:
                artifacts.append(json.loads(art_path.read_text(encoding="utf-8")))
            except ValueError:
                return False, f"unreadable evidence artifact: {art_path.name}"
    for d in blocking:
        target = d.get("file", "")
        if not any(target in (a.get("command") or "") for a in artifacts):
            return False, (f"blocked decision for {target!r} has no "
                           f"matching evidence artifact")
    return True, ""


def test_blocked_decisions_are_evidenced(tmp_path):
    monkeypatch_env = _trace_env(tmp_path)
    import os

    old = os.environ.get("FETTLE_TRACE_PATH")
    os.environ.update(monkeypatch_env)
    try:
        [
            _record_pair(tmp_path, "PreToolUse", "blocked", "Write",
                         "tests/test_x.py"),
            _record_pair(tmp_path, "PreToolUse", "allow", "Write",
                         "src/impl.py"),
            _record_pair(tmp_path, "Stop", "violation", "verify",
                         "repo"),
        ]
    finally:
        if old is None:
            os.environ.pop("FETTLE_TRACE_PATH", None)
        else:
            os.environ["FETTLE_TRACE_PATH"] = old

    holds, why = _invariant_holds(tmp_path)

    assert holds, why
    # 3 decisions logged; 2 of them blocking with artifacts.
    trace_lines = _trace_path(tmp_path) \
        .read_text(encoding="utf-8").splitlines()
    assert len(trace_lines) == 3


def test_deleting_artifacts_breaks_the_invariant_loudly(tmp_path):
    monkeypatch_env = _trace_env(tmp_path)
    import os

    old = os.environ.get("FETTLE_TRACE_PATH")
    os.environ.update(monkeypatch_env)
    try:
        _record_pair(tmp_path, "PreToolUse", "blocked", "Write",
                     "tests/test_x.py")
        ev_dir = tmp_path / ".fettle" / "evidence"
        for stale in ev_dir.glob("*.json"):
            stale.unlink()
    finally:
        if old is None:
            os.environ.pop("FETTLE_TRACE_PATH", None)
        else:
            os.environ["FETTLE_TRACE_PATH"] = old

    holds, why = _invariant_holds(tmp_path)

    assert holds is False
    assert "no matching evidence artifact" in why
