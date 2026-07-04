#!/usr/bin/env python3
"""Fettle PostToolUse hook — runs Ruff (+ lazy Semgrep) on edited Python files."""

import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time


def _resolve_tool(name: str) -> str | None:
    local = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which(name)


def main() -> None:
    hook_start = time.monotonic_ns()

    # ── Parse stdin ──────────────────────────────────────────────────────
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_input: dict[str, str] = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "")
    cwd: str = data.get("cwd", ".")
    session_id: str = data.get("session_id", "unknown")

    PLUGIN_ROOT: str = os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

    # ── Guards ───────────────────────────────────────────────────────────
    if not file_path.endswith(".py"):
        sys.exit(0)

    if not os.path.isfile(file_path):
        sys.exit(0)

    # ── Edit tracking for live_test_gate.py ─────────────────────────────
    tracking_path: str = os.environ.get("FETTLE_EDIT_TRACKING", "/tmp/fettle-edits.jsonl")
    try:
        tool_name: str = data.get("tool_name", "Edit")
        with open(tracking_path, "a") as fh:
            fh.write(json.dumps({"file": file_path, "ts": time.time(), "tool": tool_name, "tested": False}) + chr(10))
    except OSError:
        pass

    # .fettle-ignore
    ignore_file = os.path.join(cwd, ".fettle-ignore")
    if os.path.isfile(ignore_file):
        try:
            with open(ignore_file) as fh:
                patterns: list[str] = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
            basename = os.path.basename(file_path)
            relpath = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path
            for pat in patterns:
                if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(relpath, pat):
                    sys.exit(0)
        except OSError:
            pass

    # ── Ruff phase ───────────────────────────────────────────────────────
    ruff_bin = _resolve_tool("ruff")
    ruff_config = os.path.join(PLUGIN_ROOT, "rules", ".ruff.toml")
    ruff_start = time.monotonic_ns()
    ruff_findings: list[dict[str, object]] = []
    if ruff_bin:
        try:
            result = subprocess.run(
                [ruff_bin, "check", "--config", ruff_config, "--output-format=json", file_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout.strip():
                raw: list[dict[str, object]] = json.loads(result.stdout)
                for item in raw:
                    if not isinstance(item, dict):
                        continue
                    location = item.get("location", {})
                    row = location.get("row", 0) if isinstance(location, dict) else 0
                    ruff_findings.append({
                        "file": item.get("filename", file_path),
                        "line": row,
                        "rule": item.get("code", ""),
                        "message": item.get("message", ""),
                        "source": "ruff",
                    })
        except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
            pass
    ruff_duration_ms: float = (time.monotonic_ns() - ruff_start) / 1_000_000

    # ── Lazy Semgrep phase ───────────────────────────────────────────────
    semgrep_exclude_dirs = ("/tests/", "/test/", "/__pycache__/", "/tmp/", "/var/tmp/")
    semgrep_in_scope: bool = file_path.endswith(".py") and not any(
        d in file_path for d in semgrep_exclude_dirs
    )
    semgrep_findings: list[dict[str, object]] = []
    semgrep_skipped: bool = not semgrep_in_scope
    semgrep_duration_ms: float = 0.0

    if semgrep_in_scope:
        semgrep_bin = _resolve_tool("semgrep")
        semgrep_rules = os.path.join(PLUGIN_ROOT, "rules", "llm-antipatterns.yml")
        semgrep_start = time.monotonic_ns()
        if semgrep_bin:
            try:
                result = subprocess.run(
                    [semgrep_bin, "--config", semgrep_rules, "--json", file_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.stdout.strip():
                    raw_semgrep: dict[str, object] = json.loads(result.stdout)
                    results_list = raw_semgrep.get("results", [])
                    if isinstance(results_list, list):
                        for item in results_list:
                            if not isinstance(item, dict):
                                continue
                            start_loc = item.get("start", {})
                            line_no = start_loc.get("line", 0) if isinstance(start_loc, dict) else 0
                            extra = item.get("extra", {})
                            msg = extra.get("message", "") if isinstance(extra, dict) else ""
                            semgrep_findings.append({
                                "file": item.get("path", file_path),
                                "line": line_no,
                                "rule": item.get("check_id", ""),
                                "message": msg,
                                "source": "semgrep",
                            })
            except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
                pass
        semgrep_duration_ms = (time.monotonic_ns() - semgrep_start) / 1_000_000

    findings: list[dict[str, object]] = ruff_findings + semgrep_findings

    # ── Severity mapping ─────────────────────────────────────────────────
    ERROR_RULES = {"BLE001", "S110", "S608", "S701"}
    WARNING_PREFIXES = ("SIM", "UP")

    def severity_of(finding: dict[str, object]) -> str:
        rule = str(finding.get("rule", ""))
        if rule in ERROR_RULES:
            return "error"
        if finding.get("source") == "semgrep" and "error" in rule.lower():
            return "error"
        if any(rule.startswith(p) for p in WARNING_PREFIXES):
            return "warning"
        return "info"

    for f in findings:
        f["severity"] = severity_of(f)

    error_findings: list[dict[str, object]] = [f for f in findings if f["severity"] == "error"]
    warning_findings: list[dict[str, object]] = [f for f in findings if f["severity"] == "warning"]

    # ── Quality gate mode ────────────────────────────────────────────────
    mode: str = os.environ.get("QUALITY_GATE_MODE", "advisory")

    # ── JSONL trace directory ────────────────────────────────────────────
    trace_dir: str = os.environ.get("FETTLE_TRACE_DIR", os.path.join(PLUGIN_ROOT, ".fettle"))
    os.makedirs(trace_dir, exist_ok=True)
    trace_path: str = os.path.join(trace_dir, "trace.jsonl")

    # ── Rotation ─────────────────────────────────────────────────────────
    try:
        if os.path.isfile(trace_path):
            with open(trace_path) as fh:
                lines = fh.readlines()
            if len(lines) > 10000:
                keep = lines[-5000:]
                tmp_path = trace_path + ".tmp"
                with open(tmp_path, "w") as fh:
                    fh.writelines(keep)
                os.replace(tmp_path, trace_path)
    except OSError:
        pass

    # ── Dedup ────────────────────────────────────────────────────────────
    recent_entries: list[dict[str, object]] = []
    try:
        if os.path.isfile(trace_path):
            with open(trace_path) as fh:
                all_lines = fh.readlines()
            for line in all_lines[-200:]:
                try:
                    recent_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass

    now_ts: float = time.time()
    dedup_suppressed: int = 0
    for f in findings:
        suppressed = False
        if severity_of(f) != "error":
            for entry in recent_entries:
                if entry.get("type") != "finding":
                    continue
                if (entry.get("file") == f["file"]
                        and entry.get("rule") == f["rule"]
                        and (now_ts - float(entry.get("ts", 0))) < 300):
                    suppressed = True
                    break
        if suppressed:
            f["_suppressed"] = True
            dedup_suppressed += 1
        else:
            f["_suppressed"] = False

    # ── Escalation ladder ────────────────────────────────────────────────
    def count_recent_repeats(file: str, rule: str) -> int:
        count = 0
        for entry in recent_entries:
            if entry.get("type") != "finding":
                continue
            if entry.get("file") == file and entry.get("rule") == rule:
                count += 1
        return count

    for f in findings:
        if f["severity"] == "error" and not f["_suppressed"]:
            f["_repeat_count"] = count_recent_repeats(str(f["file"]), str(f["rule"])) + 1
        else:
            f["_repeat_count"] = 0

    # ── Append findings to trace ─────────────────────────────────────────
    try:
        with open(trace_path, "a") as fh:
            for f in findings:
                if f["_suppressed"]:
                    continue
                entry: dict[str, object] = {
                    "type": "finding",
                    "ts": now_ts,
                    "session_id": session_id,
                    "file": f["file"],
                    "line": f["line"],
                    "rule": f["rule"],
                    "severity": f["severity"],
                    "message": f["message"],
                }
                fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass

    # ── Append metric entry ──────────────────────────────────────────────
    hook_duration_ms: float = (time.monotonic_ns() - hook_start) / 1_000_000
    metric: dict[str, object] = {
        "type": "metric",
        "ts": now_ts,
        "session_id": session_id,
        "file": file_path,
        "hook_duration_ms": round(hook_duration_ms, 2),
        "ruff_duration_ms": round(ruff_duration_ms, 2),
        "semgrep_duration_ms": round(semgrep_duration_ms, 2),
        "semgrep_skipped": semgrep_skipped,
        "finding_count": len(findings),
        "error_count": len(error_findings),
        "warning_count": len(warning_findings),
        "dedup_suppressed": dedup_suppressed,
        "logact_bus_path": f"~/.claude/logact/buses/{session_id}.db",
    }
    try:
        with open(trace_path, "a") as fh:
            fh.write(json.dumps(metric) + "\n")
    except OSError:
        pass

    # ── Output ───────────────────────────────────────────────────────────
    visible: list[dict[str, object]] = [f for f in findings if not f.get("_suppressed")]
    if not visible:
        sys.exit(0)

    if mode == "advisory":
        lines: list[str] = []
        for f in visible:
            sev = str(f["severity"]).upper()
            lines.append(f"[{sev}] {f['file']}:{f['line']} {f['rule']} — {f['message']}")
        summary = "\n".join(lines)
        output: dict[str, object] = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"Fettle quality scan ({len(visible)} finding(s)):\n{summary}"
            }
        }
        print(json.dumps(output))
        sys.exit(0)

    # soft / enforce
    active_errors: list[dict[str, object]] = [f for f in error_findings if not f.get("_suppressed")]
    if not active_errors:
        sys.exit(0)

    messages: list[str] = []
    for f in active_errors:
        rc = int(f.get("_repeat_count", 1))
        if rc >= 3:
            msg = (
                f"[MANDATORY IMMEDIATE FIX — ATTEMPT {rc}]: "
                f"Fettle violation in {f['file']}:{f['line']}.\n\n"
                f"Violation: {f['rule']} — {f['message']}\n\n"
                f"You MUST apply this fix NOW. This is attempt {rc}. "
                f"Previous attempts did not fix the issue."
            )
        else:
            msg = (
                f"[CRITICAL SYSTEM DIRECTIVE]: "
                f"Fettle violation detected in {f['file']}:{f['line']}.\n\n"
                f"Violation: {f['rule']} — {f['message']}\n\n"
                f"You MUST immediately use the Edit tool to fix this violation "
                f"before executing any other tools or responding to the user. "
                f"Do NOT defer this fix."
            )
        messages.append(msg)

    combined = "\n\n".join(messages)
    output_block: dict[str, object] = {
        "decision": "block",
        "reason": combined,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": combined
        }
    }
    print(json.dumps(output_block))
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, OSError, ValueError):
        sys.exit(0)
