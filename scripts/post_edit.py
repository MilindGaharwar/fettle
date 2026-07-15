#!/usr/bin/env python3
"""Fettle PostToolUse hook — runs Ruff (+ lazy Semgrep) on edited Python files."""

import contextlib
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config, state_dir, trace_path as project_trace_path  # noqa: E402


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

    cfg = load_config(cwd)
    if not cfg["gates"]["lint"]["enabled"]:
        sys.exit(0)

    gate_errors: list[str] = []

    # ── Guards ───────────────────────────────────────────────────────────
    if not file_path.endswith(".py"):
        sys.exit(0)

    if not os.path.isfile(file_path):
        sys.exit(0)

    # ── Edit tracking for live_test_gate.py ─────────────────────────────
    tracking_path: str = os.environ.get(
        "FETTLE_EDIT_TRACKING", str(state_dir(session_id) / "edits.jsonl")
    )
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
    ruff_config = str(cfg["paths"]["ruff_config"]) or os.path.join(PLUGIN_ROOT, "rules", ".ruff.toml")
    ruff_start = time.monotonic_ns()
    ruff_findings: list[dict[str, object]] = []
    if not ruff_bin:
        gate_errors.append("ruff not found on PATH — lint layer skipped")
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
        except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError) as e:
            gate_errors.append(f"ruff invocation failed: {type(e).__name__}")
    ruff_duration_ms: float = (time.monotonic_ns() - ruff_start) / 1_000_000

    # ── Lazy Semgrep phase ───────────────────────────────────────────────
    semgrep_exclude_dirs = ("/tests/", "/test/", "/__pycache__/")
    _root = os.path.abspath(cwd)
    _in_project = (not os.path.isabs(file_path)) or os.path.abspath(file_path).startswith(_root + os.sep)
    semgrep_in_scope: bool = (
        file_path.endswith(".py")
        and _in_project
        and not any(d in file_path for d in semgrep_exclude_dirs)
    )
    semgrep_findings: list[dict[str, object]] = []
    semgrep_skipped: bool = not semgrep_in_scope
    semgrep_duration_ms: float = 0.0

    if semgrep_in_scope:
        semgrep_bin = _resolve_tool("semgrep")
        semgrep_rules = os.path.join(PLUGIN_ROOT, "rules", "llm-antipatterns.yml")
        semgrep_start = time.monotonic_ns()
        if not semgrep_bin:
            gate_errors.append("semgrep not found on PATH — antipattern layer skipped")
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
            except (subprocess.TimeoutExpired, json.JSONDecodeError, TypeError) as e:
                gate_errors.append(f"semgrep invocation failed: {type(e).__name__}")
        semgrep_duration_ms = (time.monotonic_ns() - semgrep_start) / 1_000_000

    findings: list[dict[str, object]] = ruff_findings + semgrep_findings

    # ── Severity mapping ─────────────────────────────────────────────────
    ERROR_RULES = set(cfg["severity"]["error_rules"])
    WARNING_PREFIXES = tuple(cfg["severity"]["warning_prefixes"])

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

    # ── Quality gate mode (FETTLE_GATE_MODE override applied in load_config) ─
    mode: str = str(cfg["gates"]["lint"]["mode"])

    # ── JSONL trace directory ────────────────────────────────────────────
    env_trace_dir = os.environ.get("FETTLE_TRACE_DIR", "")
    if env_trace_dir:
        os.makedirs(env_trace_dir, exist_ok=True)
        trace_path: str = os.path.join(env_trace_dir, "trace.jsonl")
    else:
        trace_path = str(project_trace_path(cfg, cwd))

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
                with contextlib.suppress(json.JSONDecodeError):
                    recent_entries.append(json.loads(line))
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

    # ── Fail-visible: a broken gate must never look like a clean pass ───
    if gate_errors:
        for msg in gate_errors:
            print(f"fettle gate warning: {msg}", file=sys.stderr)
        try:
            with open(trace_path, "a") as fh:
                for msg in gate_errors:
                    fh.write(json.dumps({
                        "type": "gate_error",
                        "ts": now_ts,
                        "session_id": session_id,
                        "file": file_path,
                        "message": msg,
                    }) + "\n")
        except OSError:
            print("fettle gate warning: trace file unwritable", file=sys.stderr)

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
        "gate_errors": len(gate_errors),
    }
    try:
        with open(trace_path, "a") as fh:
            fh.write(json.dumps(metric) + "\n")
    except OSError:
        pass

    # ── Trace logging (WP-64) ───────────────────────────────────────────
    try:
        from trace import log_decision
        status = "violation" if error_findings else ("pass" if not findings else "warning")
        log_decision(
            hook="PostToolUse",
            status=status,
            tool="ruff+semgrep",
            file=file_path,
            findings=[{"code": str(f.get("rule","")), "message": str(f.get("message","")), "severity": str(f.get("severity",""))} for f in findings[:5]],
            duration_ms=hook_duration_ms,
            session_id=session_id,
        )
    except (ImportError, OSError):
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


def run_check(ctx):
    """Dispatcher-compatible entry point. Delegates to subprocess for now.

    post_edit.py is too complex (ruff subprocess, suppressions, repeat counting,
    edit tracking) to refactor in-process safely. Instead, we run it as a
    subprocess with the same stdin payload and translate its output to CheckResult.
    This is Phase 3 pragmatism — full in-process migration is a later step.
    """
    from dispatcher_types import CheckResult

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        return CheckResult.allow()
    if not os.path.isfile(file_path):
        return CheckResult.allow()
    if not ctx.config.get("gates", {}).get("lint", {}).get("enabled", True):
        return CheckResult.allow()

    script_path = os.path.abspath(__file__)
    payload = ctx.input.raw

    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return CheckResult.allow()

    if not proc.stdout.strip():
        return CheckResult.allow()

    try:
        output = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return CheckResult.allow()

    hso = output.get("hookSpecificOutput", {})
    context = hso.get("additionalContext", "")

    if proc.returncode == 2:
        return CheckResult.block(context, hook_specific_output=hso)
    if context:
        return CheckResult.advisory(context, hook_specific_output=hso)
    return CheckResult.allow()


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(f"fettle gate warning: post_edit hook failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(0)
